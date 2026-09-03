import time
from datetime import datetime, timedelta
from typing import Any, Dict, List

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai.agent import ai_recovery_agent
from apps.api.logging import log_event
from apps.api.metrics import metrics
from apps.api.settings import get_settings
from domain.models.entities import DecisionTraceEntity, RecoveryCaseEntity
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
)
from domain.models.schemas import CustomerSchema, PaymentSchema
from domain.policies.engine import policy_engine
from domain.state_machine.recovery_fsm import InvalidStateTransitionError, RecoveryStateMachine
from services.event_bus import event_bus
from services.fatigue import record_contact, refresh_contact_window, timestamps_as_datetimes
from services.razorpay_client import razorpay_service

ACTIVE_WORKER_STATES = (
    RecoveryState.IN_GRACE_WINDOW.value,
    RecoveryState.SCHEDULED_RETRY.value,
    RecoveryState.LINK_SENT.value,
)


class RecoveryWorker:
    """Executes due SMART_RETRY / grace-expiry actions. Systems execute."""

    async def tick(self, db: AsyncSession, limit: int = 25) -> Dict[str, Any]:
        metrics.inc("worker_ticks")
        now = datetime.utcnow()
        query = (
            select(RecoveryCaseEntity)
            .where(RecoveryCaseEntity.state.in_(ACTIVE_WORKER_STATES))
            .where(RecoveryCaseEntity.next_action_at.is_not(None))
            .where(RecoveryCaseEntity.next_action_at <= now)
            .options(
                selectinload(RecoveryCaseEntity.payment),
                selectinload(RecoveryCaseEntity.customer),
                selectinload(RecoveryCaseEntity.decision_traces),
            )
            .limit(limit)
        )
        result = await db.execute(query)
        cases = result.scalars().all()
        processed: List[str] = []
        errors: List[str] = []
        for case in cases:
            try:
                await self._process_case(db, case, now)
                processed.append(case.id)
                metrics.inc("worker_actions")
            except Exception as exc:
                log_event("error", "worker_case_failed", case_id=case.id, error=str(exc))
                errors.append(f"{case.id}:{exc}")
        if processed:
            event_bus.publish({"type": "worker.tick", "processed": processed, "count": len(processed)})
        return {"processed": processed, "errors": errors, "scanned_at": now.isoformat()}

    async def _process_case(self, db: AsyncSession, case: RecoveryCaseEntity, now: datetime) -> None:
        if RecoveryStateMachine.is_terminal(RecoveryState(case.state)):
            case.next_action_at = None
            return
        if not case.payment or not case.customer:
            return
        if case.payment.status == PaymentStatus.CAPTURED.value:
            current = RecoveryState(case.state)
            RecoveryStateMachine.validate_transition(current, RecoveryState.RECOVERED)
            case.state = RecoveryState.RECOVERED.value
            case.resolved_at = now
            case.resolution_type = ResolutionType.AUTO_CAPTURED.value
            case.next_action_at = None
            return

        refresh_contact_window(case.customer)
        failure_code = None
        if case.payment.failure_code:
            try:
                failure_code = FailureCode(case.payment.failure_code)
            except ValueError:
                failure_code = FailureCode.UNKNOWN_ERROR
        payment_schema = PaymentSchema(
            id=case.payment.id,
            order_id=case.payment.order_id,
            customer_id=case.customer.id,
            amount_in_paise=case.payment.amount_in_paise,
            currency=case.payment.currency,
            status=PaymentStatus(case.payment.status),
            method=PaymentMethod(case.payment.method) if case.payment.method else None,
            failure_code=failure_code,
            failure_description=case.payment.failure_description,
            created_at=case.payment.created_at,
            notes=case.payment.notes or {},
        )
        customer_schema = CustomerSchema(
            id=case.customer.id,
            name=case.customer.name,
            email=case.customer.email,
            phone=case.customer.phone,
            tier=CustomerTier(case.customer.tier),
            lifetime_recovered_paise=case.customer.lifetime_recovered_paise,
            contact_token_bucket=case.customer.contact_token_bucket,
            contact_timestamps=timestamps_as_datetimes(case.customer),
            last_contacted_at=case.customer.last_contacted_at,
            opted_out=case.customer.opted_out,
        )

        start = time.perf_counter()
        proposal = await ai_recovery_agent.reason(payment_schema, customer_schema)
        # After grace, do not wait again — prefer retry or link
        if case.state == RecoveryState.IN_GRACE_WINDOW.value and proposal.primary_action.action == ActionType.WAIT:
            proposal.primary_action.action = ActionType.SMART_RETRY
            proposal.primary_action.delay_seconds = 0
            proposal.primary_action.rationale = "Grace window expired without capture. Escalating to smart retry."
        if case.state == RecoveryState.LINK_SENT.value and proposal.primary_action.action in (
            ActionType.WAIT,
            ActionType.SMART_RETRY,
        ):
            proposal.primary_action.action = ActionType.PAYMENT_LINK
            proposal.primary_action.delay_seconds = 0
            proposal.primary_action.rationale = "Unpaid payment link follow-up. Second-touch before expiry."

        policy = policy_engine.evaluate(payment_schema, customer_schema, proposal.primary_action)
        approved = policy.approved_action
        if approved == ActionType.WAIT and case.state == RecoveryState.IN_GRACE_WINDOW.value:
            approved = ActionType.SMART_RETRY
        if case.state == RecoveryState.LINK_SENT.value and approved in (ActionType.WAIT, ActionType.SMART_RETRY):
            approved = ActionType.DO_NOT_CONTACT

        exec_result: Dict[str, Any] = {"source": "recovery_worker"}
        target = RecoveryState(case.state)
        followup_at = datetime.utcnow() + timedelta(seconds=get_settings().followup_seconds)

        if approved == ActionType.SMART_RETRY and case.state != RecoveryState.LINK_SENT.value:
            idem_key = f"retry:{case.id}:{now.strftime('%Y%m%d%H%M')}"
            sub_id = case.payment.order_id or case.payment_id
            if sub_id and str(sub_id).startswith("sub_"):
                retry = await razorpay_service.charge_subscription(
                    subscription_id=sub_id,
                    amount_in_paise=case.amount_in_paise,
                    idempotency_key=idem_key,
                )
            else:
                retry = await razorpay_service.trigger_subscription_retry(
                    subscription_id=sub_id,
                    idempotency_key=idem_key,
                )
            case.last_idempotency_key = idem_key
            exec_result["retry"] = retry
            exec_result["idempotency_key"] = idem_key
            # Mock retry does not capture; follow up with a payment link if policy allows
            link_action = proposal.primary_action.model_copy(update={"action": ActionType.PAYMENT_LINK})
            follow = policy_engine.evaluate(payment_schema, customer_schema, link_action)
            if follow.approved_action in (ActionType.PAYMENT_LINK, ActionType.METHOD_SWITCH):
                approved = follow.approved_action
                policy = follow
            else:
                target = RecoveryState.SCHEDULED_RETRY
                case.next_action_at = None

        if approved in (ActionType.PAYMENT_LINK, ActionType.METHOD_SWITCH):
            record_contact(case.customer)
            idem_key = f"plink:{case.payment_id}:worker:{now.strftime('%Y%m%d%H%M%S')}"
            link = await razorpay_service.create_payment_link(
                amount_in_paise=case.amount_in_paise,
                customer_name=case.customer.name,
                customer_email=case.customer.email,
                customer_phone=case.customer.phone,
                description=f"Recovery follow-up for {case.payment_id}",
                idempotency_key=idem_key,
            )
            case.last_idempotency_key = idem_key
            exec_result["payment_link_id"] = link.get("id")
            exec_result["short_url"] = link.get("short_url")
            exec_result["sanitized_copy"] = policy.sanitized_copy
            target = RecoveryState.LINK_SENT
            case.next_action_at = followup_at
            case.grace_expires_at = None
        elif approved == ActionType.HUMAN_ESCALATION:
            target = RecoveryState.ESCALATED_HUMAN
            case.next_action_at = None
        elif approved == ActionType.DO_NOT_CONTACT:
            target = RecoveryState.EXPIRED
            case.resolved_at = now
            case.resolution_type = ResolutionType.UNRECOVERABLE_EXPIRED.value
            case.next_action_at = None
        elif approved == ActionType.CANCEL_RECOVERY:
            target = RecoveryState.CANCELLED
            case.resolved_at = now
            case.next_action_at = None

        try:
            RecoveryStateMachine.validate_transition(RecoveryState(case.state), target)
            case.state = target.value
        except InvalidStateTransitionError:
            exec_result["fsm_blocked"] = f"{case.state} -> {target.value}"
            case.next_action_at = None

        elapsed_ms = int((time.perf_counter() - start) * 1000)
        from services.audit_ledger import audit_ledger

        step = len(case.decision_traces) + 1 if case.decision_traces else 1
        prev_hash = audit_ledger.GENESIS_HASH
        if case.decision_traces:
            sorted_t = sorted(case.decision_traces, key=lambda t: t.step_number)
            if sorted_t and sorted_t[-1].record_hash:
                prev_hash = sorted_t[-1].record_hash

        diagnosis_data = {
            "explanation": proposal.operator_explanation,
            "proposed_action": proposal.primary_action.action.value,
            "approved_action": approved.value,
            "source": "recovery_worker",
        }
        policy_checks_data = [c.model_dump(mode="json") for c in policy.policy_checks]
        created_at = datetime.utcnow()
        record_hash = audit_ledger.calculate_record_hash(
            prev_hash=prev_hash,
            case_id=str(case.id),
            step_number=step,
            agent_mode=proposal.agent_mode.value,
            final_action=approved.value,
            diagnosis=diagnosis_data,
            policy_checks=policy_checks_data,
            execution_result=exec_result,
            created_at_str=str(created_at),
        )

        db.add(
            DecisionTraceEntity(
                case_id=case.id,
                step_number=step,
                agent_mode=proposal.agent_mode.value,
                raw_event_type="worker.due_action",
                diagnosis=diagnosis_data,
                proposed_actions=[proposal.primary_action.model_dump(mode="json")],
                proposed_action=proposal.primary_action.action.value,
                approved_action=approved.value,
                policy_checks=policy_checks_data,
                final_action=approved.value,
                execution_result=exec_result,
                prev_hash=prev_hash,
                record_hash=record_hash,
                latency_ms=elapsed_ms,
                created_at=created_at,
            )
        )
        case.version = (case.version or 1) + 1


recovery_worker = RecoveryWorker()
