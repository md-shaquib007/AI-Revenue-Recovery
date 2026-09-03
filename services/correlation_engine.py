import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai.agent import ai_recovery_agent
from ai.bandit import contextual_bandit
from ai.copy_rag import copy_rag
from ai.offer_engine import offer_engine
from ai.oracle import churn_risk as oracle_churn
from ai.shadow_simulator import shadow_simulator
from apps.api.logging import log_event
from apps.api.metrics import metrics
from apps.api.settings import get_settings
from domain.bank_health.sentinel import bank_sentinel
from services.gateway_adapter import gateway_router
from services.whatsapp_service import whatsapp_service
from domain.models.entities import (
    CustomerEntity,
    DecisionTraceEntity,
    PaymentEntity,
    RecoveryCaseEntity,
    WebhookEventEntity,
)
from domain.models.enums import (
    ActionType,
    AgentMode,
    CustomerTier,
    EventType,
    FailureCode,
    PaymentMethod,
    PaymentStatus,
    RecoveryState,
    ResolutionType,
    RiskTier,
)
from domain.models.schemas import (
    CandidateAction,
    CustomerSchema,
    PaymentSchema,
    PolicyEvaluationResult,
)
from domain.policies.engine import policy_engine
from domain.state_machine.recovery_fsm import InvalidStateTransitionError, RecoveryStateMachine
from services.audit_ledger import audit_ledger
from services.bank_resolver import infer_bank_key
from services.event_bus import event_bus
from services.fatigue import record_contact, refresh_contact_window, timestamps_as_datetimes
from services.lock_manager import lock_manager
from services.razorpay_client import razorpay_service



class EventCorrelationEngine:
    """
    Event Correlation Engine & State Machine Orchestrator.
    Handles event races, late captures, duplicate webhooks,
    AI reasoning pipelines, and strict policy gating.
    """

    async def process_webhook(
        self,
        db: AsyncSession,
        event_id: str,
        event_type: str,
        payload_data: Dict[str, Any],
        signature: str,
    ) -> Tuple[str, Dict[str, Any]]:
        start_time = time.perf_counter()
        metrics.inc("webhook_received")

        stmt = select(WebhookEventEntity).where(WebhookEventEntity.event_id == event_id)
        res = await db.execute(stmt)
        existing_event = res.scalars().first()
        if existing_event:
            metrics.inc("webhook_duplicate")
            return "DUPLICATE_IGNORED", {
                "status": "DUPLICATE_IGNORED",
                "message": f"Webhook event {event_id} already processed at {existing_event.processed_at}",
            }

        webhook_entity = WebhookEventEntity(
            event_id=event_id,
            event_type=event_type,
            payload=payload_data,
            signature=signature,
            status="PROCESSING",
        )
        db.add(webhook_entity)
        try:
            await db.flush()
        except IntegrityError:
            await db.rollback()
            metrics.inc("webhook_duplicate")
            return "DUPLICATE_IGNORED", {
                "status": "DUPLICATE_IGNORED",
                "message": f"Webhook event {event_id} already processed (unique constraint).",
            }

        try:
            payment_dict = payload_data.get("payload", {}).get("payment", {}).get("entity", {})
            if not payment_dict and "payment" in payload_data:
                payment_dict = payload_data.get("payment", {})

            payment_id = payment_dict.get("id")
            if not payment_id:
                webhook_entity.status = "SKIPPED_NO_PAYMENT_ENTITY"
                webhook_entity.processed_at = datetime.utcnow()
                return "SKIPPED", {"message": "Payload does not contain payment entity"}

            customer_id = payment_dict.get("customer_id") or f"cust_{payment_id[-8:]}"
            async with lock_manager.acquire(f"payment:{payment_id}"):
                cust_stmt = select(CustomerEntity).where(CustomerEntity.id == customer_id)
                cust_res = await db.execute(cust_stmt)
                customer_entity = cust_res.scalars().first()
                if not customer_entity:
                    customer_entity = CustomerEntity(
                        id=customer_id,
                        name=payment_dict.get("notes", {}).get("customer_name") or "Merchant Customer",
                        email=payment_dict.get("email") or f"{customer_id}@example.com",
                        phone=payment_dict.get("contact") or "+919876543210",
                        tier=CustomerTier.STANDARD.value,
                        lifetime_recovered_paise=0,
                        contact_token_bucket=policy_engine.MAX_CONTACTS_PER_WINDOW,
                        contact_timestamps=[],
                    )
                    db.add(customer_entity)
                    await db.flush()

                if event_type == EventType.PAYMENT_CAPTURED.value:
                    outcome = await self._handle_payment_captured(
                        db, payment_dict, customer_entity, event_id, start_time
                    )
                elif event_type == EventType.PAYMENT_FAILED.value:
                    outcome = await self._handle_payment_failed(
                        db, payment_dict, customer_entity, event_id, start_time
                    )
                elif event_type == EventType.REFUND_PROCESSED.value:
                    outcome = await self._handle_refund(db, payment_dict, start_time)
                elif event_type in (
                    EventType.SUBSCRIPTION_HALTED.value,
                    EventType.SUBSCRIPTION_CANCELLED.value,
                ):
                    outcome = await self._handle_subscription_stop(db, payment_dict, event_type, start_time)
                else:
                    outcome = {"status": "ACKNOWLEDGED", "event_type": event_type}

            webhook_entity.status = "PROCESSED"
            webhook_entity.processed_at = datetime.utcnow()
            webhook_entity.last_error = None
            await db.commit()
            event_bus.publish(
                {
                    "type": "webhook.processed",
                    "event_type": event_type,
                    "status": outcome.get("status"),
                    "case_id": outcome.get("case_id"),
                    "payment_id": payment_id,
                }
            )
            return outcome.get("status", "SUCCESS"), outcome
        except Exception as exc:
            metrics.inc("webhook_failed")
            log_event("error", "webhook_dead_letter", event_id=event_id, error=str(exc))
            try:
                webhook_entity.status = "FAILED"
                webhook_entity.last_error = str(exc)[:2000]
                webhook_entity.retry_count = (webhook_entity.retry_count or 0) + 1
                webhook_entity.processed_at = datetime.utcnow()
                await db.commit()
            except Exception:
                await db.rollback()
            raise

    def _next_step(self, case_entity: RecoveryCaseEntity) -> int:
        traces = case_entity.__dict__.get("decision_traces")
        if not traces:
            return 1
        return len(traces) + 1

    def _record_decision_trace(
        self,
        db: AsyncSession,
        case_entity: RecoveryCaseEntity,
        agent_mode: str,
        raw_event_type: str,
        diagnosis: Dict[str, Any],
        proposed_actions: list,
        proposed_action: Optional[str],
        approved_action: Optional[str],
        policy_checks: Any,
        final_action: str,
        execution_result: Optional[Dict[str, Any]],
        latency_ms: int,
        operator_id: Optional[str] = None,
    ) -> DecisionTraceEntity:
        step_number = self._next_step(case_entity)
        prev_hash = audit_ledger.GENESIS_HASH
        traces = case_entity.__dict__.get("decision_traces") or []
        if traces:
            sorted_traces = sorted(traces, key=lambda t: getattr(t, "step_number", 0))
            if sorted_traces and getattr(sorted_traces[-1], "record_hash", None):
                prev_hash = sorted_traces[-1].record_hash

        created_at = datetime.utcnow()
        record_hash = audit_ledger.calculate_record_hash(
            prev_hash=prev_hash,
            case_id=str(case_entity.id),
            step_number=step_number,
            agent_mode=agent_mode,
            final_action=final_action,
            diagnosis=diagnosis,
            policy_checks=policy_checks,
            execution_result=execution_result,
            created_at_str=str(created_at),
        )

        trace = DecisionTraceEntity(
            case_id=case_entity.id,
            step_number=step_number,
            agent_mode=agent_mode,
            raw_event_type=raw_event_type,
            diagnosis=diagnosis,
            proposed_actions=proposed_actions,
            proposed_action=proposed_action,
            approved_action=approved_action,
            policy_checks=policy_checks,
            final_action=final_action,
            execution_result=execution_result,
            operator_id=operator_id,
            prev_hash=prev_hash,
            record_hash=record_hash,
            latency_ms=latency_ms,
            created_at=created_at,
        )
        db.add(trace)
        case_entity.version = (case_entity.version or 1) + 1
        return trace

    def _apply_state(self, case_entity: RecoveryCaseEntity, target: RecoveryState) -> None:
        current = RecoveryState(case_entity.state)
        RecoveryStateMachine.validate_transition(current, target)
        case_entity.state = target.value

    def _customer_schema(self, customer_entity: CustomerEntity) -> CustomerSchema:
        refresh_contact_window(customer_entity)
        return CustomerSchema(
            id=customer_entity.id,
            name=customer_entity.name,
            email=customer_entity.email,
            phone=customer_entity.phone,
            tier=CustomerTier(customer_entity.tier),
            lifetime_recovered_paise=customer_entity.lifetime_recovered_paise,
            contact_token_bucket=customer_entity.contact_token_bucket,
            contact_timestamps=timestamps_as_datetimes(customer_entity),
            last_contacted_at=customer_entity.last_contacted_at,
            opted_out=customer_entity.opted_out,
        )

    async def _handle_payment_captured(
        self,
        db: AsyncSession,
        payment_dict: Dict[str, Any],
        customer_entity: CustomerEntity,
        event_id: str,
        start_time: float,
    ) -> Dict[str, Any]:
        payment_id = payment_dict.get("id")
        amount = int(payment_dict.get("amount", 0))

        stmt = select(PaymentEntity).where(PaymentEntity.id == payment_id)
        res = await db.execute(stmt)
        payment_entity = res.scalars().first()

        if not payment_entity:
            payment_entity = PaymentEntity(
                id=payment_id,
                order_id=payment_dict.get("order_id"),
                customer_id=customer_entity.id,
                amount_in_paise=amount,
                currency=payment_dict.get("currency", "INR"),
                status=PaymentStatus.CAPTURED.value,
                method=payment_dict.get("method"),
                bank_key=infer_bank_key(payment_dict),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(payment_entity)
            await db.flush()
        else:
            payment_entity.status = PaymentStatus.CAPTURED.value
            payment_entity.updated_at = datetime.utcnow()

        # Notify the Sentinel that this bank produced a successful capture.
        # This self-heals the failure velocity window and may auto-recover the circuit.
        captured_bank_key = infer_bank_key(payment_dict)
        bank_sentinel.record_success(captured_bank_key)

        # Record positive outcome in Contextual Bandit to update recovery probability distributions
        fc = None
        if payment_entity and payment_entity.failure_code:
            try:
                fc = FailureCode(payment_entity.failure_code)
            except ValueError:
                pass
        ct = CustomerTier(customer_entity.tier) if customer_entity.tier else CustomerTier.STANDARD
        contextual_bandit.record_outcome(fc, captured_bank_key, ct, recovered=True)

        case_stmt = (
            select(RecoveryCaseEntity)
            .where(RecoveryCaseEntity.payment_id == payment_id)
            .options(selectinload(RecoveryCaseEntity.decision_traces))
        )
        case_res = await db.execute(case_stmt)
        case_entity = case_res.scalars().first()

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)

        if case_entity and not RecoveryStateMachine.is_terminal(RecoveryState(case_entity.state)):
            old_state = RecoveryState(case_entity.state)
            self._apply_state(case_entity, RecoveryState.RECOVERED)
            case_entity.resolved_at = datetime.utcnow()
            case_entity.resolution_type = ResolutionType.AUTO_CAPTURED.value
            case_entity.next_action_at = None
            customer_entity.lifetime_recovered_paise += amount

            self._record_decision_trace(
                db=db,
                case_entity=case_entity,
                agent_mode=AgentMode.AI_REASONER.value,
                raw_event_type=EventType.PAYMENT_CAPTURED.value,
                diagnosis={
                    "event": "payment.captured",
                    "previous_state": old_state.value,
                    "reason": "Payment captured organically within grace window or after retry.",
                    "proposed_action": ActionType.CANCEL_RECOVERY.value,
                    "approved_action": ActionType.CANCEL_RECOVERY.value,
                },
                proposed_actions=[{"action": ActionType.CANCEL_RECOVERY.value, "confidence": 1.0}],
                proposed_action=ActionType.CANCEL_RECOVERY.value,
                approved_action=ActionType.CANCEL_RECOVERY.value,
                policy_checks=[
                    {"rule_name": "NO_OP_ON_CAPTURED", "passed": True, "detail": "Active recovery cancelled immediately."}
                ],
                final_action=ActionType.CANCEL_RECOVERY.value,
                execution_result={"message": "All scheduled communications & retries cancelled successfully."},
                latency_ms=elapsed_ms,
            )
            event_bus.publish({"type": "case.recovered", "case_id": case_entity.id, "payment_id": payment_id})
            return {
                "status": "RECOVERED",
                "case_id": case_entity.id,
                "amount_recovered": amount,
                "note": "Payment captured organically. Intelligent Non-Action saved customer fatigue.",
            }

        return {"status": "CAPTURED", "payment_id": payment_id}

    async def _handle_payment_failed(
        self,
        db: AsyncSession,
        payment_dict: Dict[str, Any],
        customer_entity: CustomerEntity,
        event_id: str,
        start_time: float,
    ) -> Dict[str, Any]:
        payment_id = payment_dict.get("id")
        amount = int(payment_dict.get("amount", 0))
        error_code_raw = (
            payment_dict.get("error_code")
            or payment_dict.get("error_reason")
            or payment_dict.get("failure_code")
            or "BAD_REQUEST_PAYMENT_TIMED_OUT"
        )
        error_desc = payment_dict.get("error_description") or "Payment failed at acquiring bank."
        notes = payment_dict.get("notes") or {}
        bank_key = infer_bank_key(payment_dict)

        failure_code = FailureCode.BAD_REQUEST_PAYMENT_TIMED_OUT
        for code in FailureCode:
            if code.value.lower() in str(error_code_raw).lower():
                failure_code = code
                break

        stmt = select(PaymentEntity).where(PaymentEntity.id == payment_id)
        res = await db.execute(stmt)
        payment_entity = res.scalars().first()

        if not payment_entity:
            payment_entity = PaymentEntity(
                id=payment_id,
                order_id=payment_dict.get("order_id"),
                customer_id=customer_entity.id,
                amount_in_paise=amount,
                currency=payment_dict.get("currency", "INR"),
                status=PaymentStatus.FAILED.value,
                method=payment_dict.get("method") or PaymentMethod.UPI.value,
                failure_code=failure_code.value,
                failure_description=error_desc,
                bank_key=bank_key,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                notes=notes,
            )
            db.add(payment_entity)
            await db.flush()
        else:
            payment_entity.status = PaymentStatus.FAILED.value
            payment_entity.failure_code = failure_code.value
            payment_entity.failure_description = error_desc
            payment_entity.bank_key = bank_key
            payment_entity.updated_at = datetime.utcnow()

        payment_schema = PaymentSchema(
            id=payment_entity.id,
            order_id=payment_entity.order_id,
            customer_id=customer_entity.id,
            amount_in_paise=payment_entity.amount_in_paise,
            currency=payment_entity.currency,
            status=PaymentStatus(payment_entity.status),
            method=PaymentMethod(payment_entity.method) if payment_entity.method else None,
            failure_code=failure_code,
            failure_description=payment_entity.failure_description,
            created_at=payment_entity.created_at,
            notes=notes if isinstance(notes, dict) else {},
        )
        customer_schema = self._customer_schema(customer_entity)

        # ── FUTURISTIC AI LAYER 1: Bank Sentinel ─────────────────────────────────
        # Record this failure in the Sentinel's sliding velocity window.
        # Then evaluate the predictive circuit to see if the bank is deteriorating.
        bank_sentinel.record_event(bank_key, is_failure=True)
        sentinel_analytics = bank_sentinel.evaluate_predictive_circuit(bank_key)
        # ─────────────────────────────────────────────────────────────────────────

        ai_proposal = await ai_recovery_agent.reason(payment_schema, customer_schema)

        # ── FUTURISTIC AI LAYER 2: Shadow Simulator ───────────────────────────────
        # Run 50-persona friction simulation on the AI's proposed action.
        # If friction is too high (>45%), auto-pivot to the lowest-friction alternative.
        proposed_action_for_sim = ai_proposal.primary_action.action
        shadow_result = shadow_simulator.simulate(payment_schema, customer_schema, proposed_action_for_sim)
        shadow_pivot_applied = False

        if shadow_result["friction_score_pct"] > 45.0 and shadow_result.get("recommended_pivot"):
            try:
                pivot_action = ActionType(shadow_result["recommended_pivot"])
                log_event(
                    "info",
                    "shadow_sim_pivot",
                    payment_id=payment_id,
                    from_action=proposed_action_for_sim.value,
                    to_action=pivot_action.value,
                    friction_pct=shadow_result["friction_score_pct"],
                )
                # Mutate the primary action on the proposal to the lower-friction alternative
                ai_proposal.primary_action.action = pivot_action
                metrics.inc("shadow_sim_pivot")
                shadow_pivot_applied = True
            except ValueError:
                pass  # Unrecognised pivot value — continue with original proposal
        # ─────────────────────────────────────────────────────────────────────────

        # Pass bank_key into policy engine so Rule 7 (Sentinel Circuit Override) fires
        policy_result: PolicyEvaluationResult = policy_engine.evaluate(
            payment=payment_schema,
            customer=customer_schema,
            proposed_action=ai_proposal.primary_action,
            bank_key=bank_key,
        )
        if policy_result.approved_action != ai_proposal.primary_action.action:
            metrics.inc("policy_veto")

        final_action = policy_result.approved_action
        risk_tier = RiskTier.CRITICAL if amount >= 5_000_000 else RiskTier.MEDIUM

        case_stmt = (
            select(RecoveryCaseEntity)
            .where(RecoveryCaseEntity.payment_id == payment_id)
            .options(selectinload(RecoveryCaseEntity.decision_traces))
        )
        case_res = await db.execute(case_stmt)
        case_entity = case_res.scalars().first()
        if not case_entity:
            case_entity = RecoveryCaseEntity(
                payment_id=payment_id,
                customer_id=customer_entity.id,
                state=RecoveryState.TRIAGING.value,
                risk_tier=risk_tier.value,
                amount_in_paise=amount,
                predicted_ev_paise=ai_proposal.primary_action.expected_value_in_paise,
            )
            db.add(case_entity)
            await db.flush()
        elif RecoveryStateMachine.is_terminal(RecoveryState(case_entity.state)):
            return {
                "status": "IGNORED_TERMINAL",
                "case_id": case_entity.id,
                "state": case_entity.state,
            }

        target_state, grace_expiry, next_action_time = self._plan_state(final_action, ai_proposal.primary_action)
        try:
            self._apply_state(case_entity, target_state)
        except InvalidStateTransitionError:
            log_event(
                "error",
                "invalid_fsm_transition",
                case_id=case_entity.id,
                from_state=case_entity.state,
                to_state=target_state.value,
            )
            target_state = RecoveryState(case_entity.state)
            grace_expiry = case_entity.grace_expires_at
            next_action_time = case_entity.next_action_at

        case_entity.grace_expires_at = grace_expiry
        case_entity.next_action_at = next_action_time
        case_entity.predicted_ev_paise = ai_proposal.primary_action.expected_value_in_paise

        exec_result: Dict[str, Any] = {}
        if final_action in [ActionType.PAYMENT_LINK, ActionType.METHOD_SWITCH]:
            record_contact(customer_entity)
            idem_key = f"plink:{payment_id}:{int(datetime.utcnow().timestamp())}"

            # ── FUTURISTIC AI LAYER 3: Dynamic Micro-Incentive Offer Engine ──────
            # For NSF/high churn-risk cases where a payment link is being sent,
            # evaluate whether attaching a micro-discount copy improves Net EV.
            offer_copy: Optional[str] = None
            offer_eval: Optional[Dict[str, Any]] = None
            try:
                churn_risk = oracle_churn(customer_schema)
                base_p = ai_proposal.primary_action.confidence_score
                offer_eval = offer_engine.evaluate_offer(
                    payment_schema, customer_schema,
                    churn_risk=churn_risk, base_p_recover=base_p
                )
                if offer_eval.get("offer_recommended"):
                    discount = offer_eval["discount_amount_rupees"]
                    # Validate against policy MaxOfferCapRule before using
                    if policy_engine.validate_offer_budget(amount, discount, customer_schema.tier):
                        offer_copy = offer_eval.get("copy_headline")
                        metrics.inc("offer_engine_applied")
            except Exception:
                pass  # Offer engine is additive — never block recovery on failure
            # ── FUTURISTIC AI LAYER 4: Semantic Copy RAG Matching ────────────────
            rag_match = copy_rag.retrieve_best_copy(failure_code)
            copy_headline = offer_copy or rag_match["copy_headline"]
            # ────────────────────────────────────────────────────────────────────

            description_base = f"Payment for {payment_entity.order_id or payment_id}"
            description = f"{copy_headline} | {description_base}"

            link_resp = await gateway_router.create_payment_link(
                amount_in_paise=amount,
                customer_name=customer_entity.name,
                customer_email=customer_entity.email,
                customer_phone=customer_entity.phone,
                description=description,
                bank_key=bank_key,
                idempotency_key=idem_key,
            )

            # Generate 1-click WhatsApp UPI Deep-Link Payload
            short_url = link_resp.get("short_url", "https://rzp.io/i/revive")
            upi_deep_link = whatsapp_service.generate_upi_deep_link(
                payee_vpa="merchant@razorpay",
                payee_name="Merchant Recovery",
                amount_in_rupees=amount / 100.0,
                transaction_ref=payment_id,
                note=f"Payment for {payment_entity.order_id or payment_id}",
            )
            wa_payload = whatsapp_service.build_whatsapp_template_payload(
                customer_phone=customer_entity.phone or "+919876543210",
                customer_name=customer_entity.name,
                amount_in_rupees=amount / 100.0,
                short_url=short_url,
                upi_deep_link=upi_deep_link,
                copy_headline=copy_headline,
            )

            case_entity.last_idempotency_key = idem_key
            exec_result = {
                "payment_link_id": link_resp.get("id"),
                "short_url": short_url,
                "gateway_used": link_resp.get("gateway_used", "RAZORPAY"),
                "channel": ai_proposal.primary_action.channel,
                "sanitized_copy": policy_result.sanitized_copy,
                "idempotency_key": idem_key,
                "offer_applied": offer_eval if offer_eval and offer_eval.get("offer_recommended") else None,
                "copy_rag_matched": rag_match,
                "upi_deep_link": upi_deep_link,
                "whatsapp_payload": wa_payload,
            }
        elif final_action == ActionType.SMART_RETRY:
            exec_result = {
                "scheduled_retry_delay": ai_proposal.primary_action.delay_seconds,
                "target_time": str(next_action_time),
            }
        elif final_action == ActionType.WAIT:
            exec_result = {
                "grace_window_seconds": ai_proposal.primary_action.delay_seconds,
                "grace_expires_at": str(grace_expiry),
                "sentinel_reason": policy_result.override_reason if sentinel_analytics["circuit_triggered"] else None,
            }
        elif final_action == ActionType.HUMAN_ESCALATION:
            exec_result = {
                "escalated_reason": policy_result.override_reason or "High value safety gate triggered",
                "requires_ops_action": True,
            }

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        self._record_decision_trace(
            db=db,
            case_entity=case_entity,
            agent_mode=ai_proposal.agent_mode.value,
            raw_event_type=EventType.PAYMENT_FAILED.value,
            diagnosis={
                "category": ai_proposal.failure_category,
                "is_transient": ai_proposal.is_transient,
                "explanation": ai_proposal.operator_explanation,
                "proposed_action": ai_proposal.primary_action.action.value,
                "approved_action": final_action.value,
                "tokens_used": ai_proposal.tokens_used,
                # AI Intel embedded in every trace for full auditability
                "sentinel_analytics": sentinel_analytics,
                "shadow_simulation": shadow_result,
                "shadow_pivot_applied": shadow_pivot_applied,
            },
            proposed_actions=[act.model_dump(mode="json") for act in ai_proposal.recommended_actions],
            proposed_action=ai_proposal.primary_action.action.value,
            approved_action=final_action.value,
            policy_checks=[c.model_dump(mode="json") for c in policy_result.policy_checks],
            final_action=final_action.value,
            execution_result=exec_result,
            latency_ms=elapsed_ms,
        )
        event_bus.publish(
            {
                "type": "case.updated",
                "case_id": case_entity.id,
                "state": target_state.value,
                "action": final_action.value,
            }
        )
        return {
            "status": "PROCESSED",
            "case_id": case_entity.id,
            "state": target_state.value,
            "action": final_action.value,
            "latency_ms": elapsed_ms,
            "decision": exec_result,
            "ai_intel": {
                "sentinel_status": sentinel_analytics["status"],
                "shadow_friction_pct": shadow_result["friction_score_pct"],
                "shadow_pivot": shadow_pivot_applied,
            },
        }

    def _plan_state(
        self, final_action: ActionType, primary: CandidateAction
    ) -> Tuple[RecoveryState, Optional[datetime], Optional[datetime]]:
        now = datetime.utcnow()
        followup = now + timedelta(seconds=get_settings().followup_seconds)
        if final_action == ActionType.WAIT:
            grace_expiry = now + timedelta(seconds=primary.delay_seconds)
            return RecoveryState.IN_GRACE_WINDOW, grace_expiry, grace_expiry
        if final_action == ActionType.SMART_RETRY:
            next_action_time = now + timedelta(seconds=primary.delay_seconds)
            return RecoveryState.SCHEDULED_RETRY, None, next_action_time
        if final_action in [ActionType.PAYMENT_LINK, ActionType.METHOD_SWITCH]:
            if primary.delay_seconds and primary.delay_seconds > 0:
                return RecoveryState.SCHEDULED_RETRY, None, now + timedelta(seconds=primary.delay_seconds)
            return RecoveryState.LINK_SENT, None, followup
        if final_action == ActionType.HUMAN_ESCALATION:
            return RecoveryState.ESCALATED_HUMAN, None, None
        if final_action == ActionType.CANCEL_RECOVERY:
            return RecoveryState.CANCELLED, None, None
        if final_action == ActionType.DO_NOT_CONTACT:
            return RecoveryState.EXPIRED, None, None
        return RecoveryState.TRIAGING, None, None

    async def _handle_refund(
        self,
        db: AsyncSession,
        payment_dict: Dict[str, Any],
        start_time: float,
    ) -> Dict[str, Any]:
        payment_id = payment_dict.get("id")
        case_stmt = (
            select(RecoveryCaseEntity)
            .where(RecoveryCaseEntity.payment_id == payment_id)
            .options(selectinload(RecoveryCaseEntity.decision_traces))
        )
        case_entity = (await db.execute(case_stmt)).scalars().first()
        if not case_entity or RecoveryStateMachine.is_terminal(RecoveryState(case_entity.state)):
            return {"status": "ACKNOWLEDGED", "note": "Refund observed; no active recovery."}

        old_state = case_entity.state
        self._apply_state(case_entity, RecoveryState.CANCELLED)
        case_entity.resolved_at = datetime.utcnow()
        case_entity.resolution_type = ResolutionType.CANCELLED_BY_LATE_CAPTURE.value
        case_entity.next_action_at = None
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        self._record_decision_trace(
            db=db,
            case_entity=case_entity,
            agent_mode=AgentMode.DETERMINISTIC_FALLBACK.value,
            raw_event_type=EventType.REFUND_PROCESSED.value,
            diagnosis={
                "event": "refund.processed",
                "previous_state": old_state,
                "reason": "Refund issued. Recovery cancelled to avoid double-collection.",
                "proposed_action": ActionType.CANCEL_RECOVERY.value,
                "approved_action": ActionType.CANCEL_RECOVERY.value,
            },
            proposed_actions=[{"action": ActionType.CANCEL_RECOVERY.value}],
            proposed_action=ActionType.CANCEL_RECOVERY.value,
            approved_action=ActionType.CANCEL_RECOVERY.value,
            policy_checks=[
                {"rule_name": "NO_COLLECT_AFTER_REFUND", "passed": True, "detail": "Refund kills recovery."}
            ],
            final_action=ActionType.CANCEL_RECOVERY.value,
            execution_result={"message": "Recovery cancelled after refund."},
            latency_ms=elapsed_ms,
        )
        event_bus.publish({"type": "case.cancelled", "case_id": case_entity.id, "reason": "refund"})
        return {"status": "CANCELLED", "case_id": case_entity.id, "reason": "refund.processed"}

    async def _handle_subscription_stop(
        self,
        db: AsyncSession,
        payment_dict: Dict[str, Any],
        event_type: str,
        start_time: float,
    ) -> Dict[str, Any]:
        payment_id = payment_dict.get("id")
        if not payment_id:
            return {"status": "ACKNOWLEDGED", "event_type": event_type}
        case_stmt = (
            select(RecoveryCaseEntity)
            .where(RecoveryCaseEntity.payment_id == payment_id)
            .options(selectinload(RecoveryCaseEntity.decision_traces))
        )
        case_entity = (await db.execute(case_stmt)).scalars().first()
        if not case_entity or RecoveryStateMachine.is_terminal(RecoveryState(case_entity.state)):
            return {"status": "ACKNOWLEDGED", "event_type": event_type}
        self._apply_state(case_entity, RecoveryState.EXPIRED)
        case_entity.resolved_at = datetime.utcnow()
        case_entity.resolution_type = ResolutionType.UNRECOVERABLE_EXPIRED.value
        case_entity.next_action_at = None
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        self._record_decision_trace(
            db=db,
            case_entity=case_entity,
            agent_mode=AgentMode.DETERMINISTIC_FALLBACK.value,
            raw_event_type=event_type,
            diagnosis={
                "event": event_type,
                "reason": "Subscription halted/cancelled. Recovery expired.",
                "proposed_action": ActionType.DO_NOT_CONTACT.value,
                "approved_action": ActionType.DO_NOT_CONTACT.value,
            },
            proposed_actions=[{"action": ActionType.DO_NOT_CONTACT.value}],
            proposed_action=ActionType.DO_NOT_CONTACT.value,
            approved_action=ActionType.DO_NOT_CONTACT.value,
            policy_checks=[
                {"rule_name": "SUBSCRIPTION_TERMINAL", "passed": True, "detail": "No further dunning."}
            ],
            final_action=ActionType.DO_NOT_CONTACT.value,
            execution_result={"message": "Dunning stopped; subscription is terminal."},
            latency_ms=elapsed_ms,
        )
        event_bus.publish({"type": "case.expired", "case_id": case_entity.id, "reason": event_type})
        return {"status": "EXPIRED", "case_id": case_entity.id, "event_type": event_type}


correlation_engine = EventCorrelationEngine()
