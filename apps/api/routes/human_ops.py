from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from apps.api.auth import OperatorContext, require_operator
from apps.api.settings import get_settings
from domain.models.entities import DecisionTraceEntity, RecoveryCaseEntity
from domain.models.enums import AgentMode, RecoveryState, ResolutionType
from domain.state_machine.recovery_fsm import RecoveryStateMachine
from services.db import get_db
from services.razorpay_client import razorpay_service

router = APIRouter(prefix="/ops", tags=["Human Ops Review"])


class HumanDecisionRequest(BaseModel):
    action: str
    operator_notes: str = ""


@router.get("/queue")
async def get_human_escalation_queue(
    db: AsyncSession = Depends(get_db),
    _: OperatorContext = Depends(require_operator),
):
    query = (
        select(RecoveryCaseEntity)
        .where(RecoveryCaseEntity.state == RecoveryState.ESCALATED_HUMAN.value)
        .options(
            selectinload(RecoveryCaseEntity.payment),
            selectinload(RecoveryCaseEntity.customer),
            selectinload(RecoveryCaseEntity.decision_traces),
        )
        .order_by(desc(RecoveryCaseEntity.amount_in_paise))
    )
    result = await db.execute(query)
    cases = result.scalars().all()

    output = []
    for c in cases:
        latest_trace = c.decision_traces[-1] if c.decision_traces else None
        reason = "High value transaction threshold"
        if latest_trace and latest_trace.policy_checks:
            first = latest_trace.policy_checks[0]
            if isinstance(first, dict):
                reason = first.get("detail") or reason
        output.append({
            "case_id": c.id,
            "payment_id": c.payment_id,
            "customer_name": c.customer.name if c.customer else "Unknown",
            "customer_email": c.customer.email if c.customer else "",
            "customer_phone": c.customer.phone if c.customer else "",
            "amount_in_rupees": c.amount_in_paise / 100,
            "failure_code": c.payment.failure_code if c.payment else "UNKNOWN",
            "risk_tier": c.risk_tier,
            "escalated_reason": reason,
            "created_at": c.created_at,
        })

    return {"pending_count": len(output), "queue": output}


@router.post("/cases/{case_id}/decision")
async def submit_human_decision(
    case_id: str,
    decision: HumanDecisionRequest,
    db: AsyncSession = Depends(get_db),
    operator: OperatorContext = Depends(require_operator),
):
    query = (
        select(RecoveryCaseEntity)
        .where(RecoveryCaseEntity.id == case_id)
        .options(
            selectinload(RecoveryCaseEntity.payment),
            selectinload(RecoveryCaseEntity.customer),
            selectinload(RecoveryCaseEntity.decision_traces),
        )
    )
    result = await db.execute(query)
    c = result.scalars().first()
    if not c:
        raise HTTPException(status_code=404, detail="Recovery case not found")

    if c.state != RecoveryState.ESCALATED_HUMAN.value:
        raise HTTPException(status_code=400, detail=f"Case is in state {c.state}, not ESCALATED_HUMAN")

    exec_result: Dict[str, Any] = {
        "operator_action": decision.action,
        "notes": decision.operator_notes,
        "operator_id": operator.id,
        "operator_username": operator.username,
    }

    if decision.action not in ("APPROVE_LINK", "RETRY_CHARGE", "DISMISS"):
        raise HTTPException(status_code=400, detail="Unknown action")

    if decision.action == "APPROVE_LINK":
        RecoveryStateMachine.validate_transition(RecoveryState(c.state), RecoveryState.LINK_SENT)
        c.state = RecoveryState.LINK_SENT.value
        idem_key = f"plink:{c.payment_id}:ops"
        link = await razorpay_service.create_payment_link(
            amount_in_paise=c.amount_in_paise,
            customer_name=c.customer.name if c.customer else "Customer",
            customer_email=c.customer.email if c.customer else "customer@example.com",
            customer_phone=c.customer.phone if c.customer else None,
            description="Human Approved High-Value Recovery",
            idempotency_key=idem_key,
        )
        c.last_idempotency_key = idem_key
        exec_result["payment_link"] = link
        c.next_action_at = datetime.utcnow() + timedelta(seconds=get_settings().followup_seconds)
    elif decision.action == "RETRY_CHARGE":
        RecoveryStateMachine.validate_transition(RecoveryState(c.state), RecoveryState.SCHEDULED_RETRY)
        c.state = RecoveryState.SCHEDULED_RETRY.value
        c.next_action_at = datetime.utcnow()
        exec_result["retry_status"] = "scheduled_immediate"
    elif decision.action == "DISMISS":
        RecoveryStateMachine.validate_transition(RecoveryState(c.state), RecoveryState.EXPIRED)
        c.state = RecoveryState.EXPIRED.value
        c.resolved_at = datetime.utcnow()
        c.resolution_type = ResolutionType.UNRECOVERABLE_EXPIRED.value
        c.next_action_at = None
    from services.audit_ledger import audit_ledger

    step_number = len(c.decision_traces) + 1 if c.decision_traces else 1
    prev_hash = audit_ledger.GENESIS_HASH
    if c.decision_traces:
        sorted_t = sorted(c.decision_traces, key=lambda t: t.step_number)
        if sorted_t and sorted_t[-1].record_hash:
            prev_hash = sorted_t[-1].record_hash

    diagnosis_data = {
        "action_taken": decision.action,
        "operator_notes": decision.operator_notes,
        "proposed_action": decision.action,
        "approved_action": decision.action,
    }
    policy_checks_data = [{"rule_name": "HUMAN_OPERATOR_SIGN_OFF", "passed": True, "detail": f"Approved by {operator.username}."}]
    created_at = datetime.utcnow()
    record_hash = audit_ledger.calculate_record_hash(
        prev_hash=prev_hash,
        case_id=str(c.id),
        step_number=step_number,
        agent_mode=AgentMode.AI_REASONER.value,
        final_action=decision.action,
        diagnosis=diagnosis_data,
        policy_checks=policy_checks_data,
        execution_result=exec_result,
        created_at_str=str(created_at),
    )

    trace = DecisionTraceEntity(
        case_id=c.id,
        step_number=step_number,
        agent_mode=AgentMode.AI_REASONER.value,
        raw_event_type="human.operator.decision",
        diagnosis=diagnosis_data,
        proposed_actions=[{"action": decision.action}],
        proposed_action=decision.action,
        approved_action=decision.action,
        policy_checks=policy_checks_data,
        final_action=decision.action,
        execution_result=exec_result,
        operator_id=operator.id,
        prev_hash=prev_hash,
        record_hash=record_hash,
        latency_ms=10,
        created_at=created_at,
    )
    db.add(trace)
    c.version = (c.version or 1) + 1
    await db.commit()

    return {
        "status": "DECISION_RECORDED",
        "case_id": case_id,
        "new_state": c.state,
        "execution": exec_result,
    }
