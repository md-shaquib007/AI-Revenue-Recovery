from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ai.oracle import (
    ACTIVE_STATES,
    case_matches_spec,
    circadian_multiplier,
    copilot_help_text,
    is_quiet_hours,
    ist_hour,
    parse_copilot_query,
    seconds_until_send_window,
    simulate_twin,
    to_ist,
)
from apps.api.auth import OperatorContext, require_operator
from domain.bank_health.matrix import bank_health_matrix
from domain.models.entities import RecoveryCaseEntity
from domain.models.enums import CustomerTier, FailureCode, PaymentMethod, PaymentStatus, RecoveryState
from domain.models.schemas import CustomerSchema, PaymentSchema
from services.bank_resolver import infer_bank_key
from services.churn_rescue import churn_rescue_engine
from services.db import get_db
from services.event_bus import event_bus
from services.fatigue import timestamps_as_datetimes
from services.voice_agent import voice_agent_service

router = APIRouter(prefix="/intel", tags=["Intelligence"])


class CopilotRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=500)


def _payment_schema(case: RecoveryCaseEntity) -> Optional[PaymentSchema]:
    p = case.payment
    if not p:
        return None
    failure = None
    if p.failure_code:
        try:
            failure = FailureCode(p.failure_code)
        except ValueError:
            failure = FailureCode.UNKNOWN_ERROR
    method = None
    if p.method:
        try:
            method = PaymentMethod(p.method)
        except ValueError:
            method = None
    try:
        status = PaymentStatus(p.status)
    except ValueError:
        status = PaymentStatus.FAILED
    return PaymentSchema(
        id=p.id,
        order_id=p.order_id,
        customer_id=case.customer_id,
        amount_in_paise=p.amount_in_paise,
        currency=p.currency or "INR",
        status=status,
        method=method,
        failure_code=failure,
        failure_description=p.failure_description,
        created_at=p.created_at or case.created_at,
        notes=p.notes or {},
    )


def _customer_schema(case: RecoveryCaseEntity) -> Optional[CustomerSchema]:
    c = case.customer
    if not c:
        return None
    try:
        tier = CustomerTier(c.tier)
    except ValueError:
        tier = CustomerTier.STANDARD
    return CustomerSchema(
        id=c.id,
        name=c.name,
        email=c.email,
        phone=c.phone,
        tier=tier,
        lifetime_recovered_paise=c.lifetime_recovered_paise or 0,
        contact_token_bucket=c.contact_token_bucket or 0,
        contact_timestamps=timestamps_as_datetimes(c),
        last_contacted_at=c.last_contacted_at,
        opted_out=bool(c.opted_out),
    )


def _bank_key_for(case: RecoveryCaseEntity) -> str:
    if case.payment and case.payment.bank_key:
        return case.payment.bank_key
    if case.payment:
        return infer_bank_key(
            {"notes": case.payment.notes or {}, "method": case.payment.method},
            case.payment.method,
        )
    return "RAZORPAY_UPI"


def _case_card(case: RecoveryCaseEntity, twin: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    winner = (twin or {}).get("winner") or {}
    return {
        "id": case.id,
        "payment_id": case.payment_id,
        "state": case.state,
        "risk_tier": case.risk_tier,
        "amount_in_rupees": case.amount_in_paise / 100,
        "failure_code": case.payment.failure_code if case.payment else None,
        "method": case.payment.method if case.payment else None,
        "bank_key": _bank_key_for(case),
        "next_action_at": case.next_action_at,
        "grace_expires_at": case.grace_expires_at,
        "customer": {
            "id": case.customer.id if case.customer else "",
            "name": case.customer.name if case.customer else "Unknown",
            "tier": case.customer.tier if case.customer else "STANDARD",
            "tokens_remaining": case.customer.contact_token_bucket if case.customer else 0,
            "opted_out": case.customer.opted_out if case.customer else False,
        },
        "p_recover": winner.get("p_recover"),
        "recommended_action": winner.get("action"),
        "ev_rupees": winner.get("expected_value_rupees"),
        "churn_risk": (twin or {}).get("churn_risk"),
    }


from services.stamped_cache import stamped_cache


@router.get("/pulse")
async def recovery_pulse(
    db: AsyncSession = Depends(get_db),
    _: OperatorContext = Depends(require_operator),
):
    """Mission-control snapshot: funnel, circadian clock, at-risk heat, live feed."""
    async def _fetch_pulse():
        now = datetime.utcnow()
        result = await db.execute(
            select(RecoveryCaseEntity).options(
                selectinload(RecoveryCaseEntity.payment),
                selectinload(RecoveryCaseEntity.customer),
            )
        )
        return now, result.scalars().all()

    now, cases = await stamped_cache.singleflight.execute("intel:pulse", _fetch_pulse)

    funnel: Dict[str, Dict[str, Any]] = {}
    failure_mix: Dict[str, int] = {}
    at_risk: List[Dict[str, Any]] = []
    predicted_recover_paise = 0
    active_paise = 0
    recovered_paise = 0

    for case in cases:
        bucket = funnel.setdefault(
            case.state,
            {"state": case.state, "count": 0, "amount_rupees": 0.0},
        )
        bucket["count"] += 1
        bucket["amount_rupees"] += case.amount_in_paise / 100
        code = (case.payment.failure_code if case.payment else None) or "UNKNOWN"
        failure_mix[code] = failure_mix.get(code, 0) + 1

        if case.state == RecoveryState.RECOVERED.value:
            recovered_paise += case.amount_in_paise
            continue
        if case.state not in ACTIVE_STATES:
            continue

        active_paise += case.amount_in_paise
        pay = _payment_schema(case)
        cust = _customer_schema(case)
        twin = None
        if pay and cust:
            health = bank_health_matrix.get_health_score(_bank_key_for(case))
            twin = simulate_twin(pay, cust, health, now)
            predicted_recover_paise += int((twin["winner"]["p_recover"] or 0) * case.amount_in_paise)
        card = _case_card(case, twin)
        at_risk.append(card)

    at_risk.sort(key=lambda c: (c.get("churn_risk") or 0) * (c.get("amount_in_rupees") or 0), reverse=True)

    funnel_order = [
        "TRIAGING",
        "IN_GRACE_WINDOW",
        "SCHEDULED_RETRY",
        "LINK_SENT",
        "ESCALATED_HUMAN",
        "RECOVERED",
        "EXPIRED",
        "CANCELLED",
    ]
    funnel_rows = [funnel[s] for s in funnel_order if s in funnel]

    banks = bank_health_matrix.snapshot()
    ist_midnight_utc = datetime(2026, 8, 21, 18, 30, 0)
    circadian = []
    for hour in range(24):
        sample = ist_midnight_utc + timedelta(hours=hour)
        circadian.append(
            {
                "hour": hour,
                "label": f"{hour:02d}:00",
                "conversion_index": round(circadian_multiplier(sample), 3),
            }
        )

    return {
        "generated_at": now,
        "ist_now": to_ist(now).strftime("%Y-%m-%d %H:%M IST"),
        "ist_hour": ist_hour(now),
        "quiet_hours": is_quiet_hours(now),
        "circadian_multiplier": circadian_multiplier(now),
        "seconds_until_send_window": seconds_until_send_window(now),
        "funnel": funnel_rows,
        "failure_mix": [{"code": k, "count": v} for k, v in sorted(failure_mix.items(), key=lambda x: -x[1])],
        "at_risk": at_risk[:12],
        "active_cases": len(at_risk),
        "active_rupees": round(active_paise / 100, 2),
        "predicted_recover_rupees": round(predicted_recover_paise / 100, 2),
        "recovered_rupees": round(recovered_paise / 100, 2),
        "banks": banks,
        "circadian_curve": circadian,
        "live_feed": event_bus.recent(18),
        "axiom": "AI proposes. Policy decides. Systems execute.",
    }


@router.get("/cases/{case_id}/twin")
async def case_digital_twin(
    case_id: str,
    db: AsyncSession = Depends(get_db),
    _: OperatorContext = Depends(require_operator),
):
    query = (
        select(RecoveryCaseEntity)
        .where(RecoveryCaseEntity.id == case_id)
        .options(
            selectinload(RecoveryCaseEntity.payment),
            selectinload(RecoveryCaseEntity.customer),
        )
    )
    case = (await db.execute(query)).scalars().first()
    if not case:
        raise HTTPException(status_code=404, detail="Recovery case not found")
    pay = _payment_schema(case)
    cust = _customer_schema(case)
    if not pay or not cust:
        raise HTTPException(status_code=409, detail="Case is missing payment or customer context")
    health = bank_health_matrix.get_health_score(_bank_key_for(case))
    twin = simulate_twin(pay, cust, health)
    twin["case"] = _case_card(case, twin)
    twin["current_state"] = case.state
    return twin


@router.post("/copilot")
async def ops_copilot(
    body: CopilotRequest,
    db: AsyncSession = Depends(get_db),
    _: OperatorContext = Depends(require_operator),
):
    spec = parse_copilot_query(body.query)
    if spec.get("intent") == "help":
        return {
            "intent": "help",
            "answer": copilot_help_text(),
            "matches": [],
            "spec": spec,
        }

    result = await db.execute(
        select(RecoveryCaseEntity)
        .options(
            selectinload(RecoveryCaseEntity.payment),
            selectinload(RecoveryCaseEntity.customer),
        )
        .order_by(desc(RecoveryCaseEntity.amount_in_paise))
        .limit(200)
    )
    cases = result.scalars().all()
    cards: List[Dict[str, Any]] = []
    for case in cases:
        pay = _payment_schema(case)
        cust = _customer_schema(case)
        twin = None
        if pay and cust:
            twin = simulate_twin(pay, cust, bank_health_matrix.get_health_score(_bank_key_for(case)))
        card = _case_card(case, twin)
        cards.append(card)

    if spec.get("intent") == "summary":
        active = [c for c in cards if c["state"] in ACTIVE_STATES]
        rupees = sum(c["amount_in_rupees"] for c in active)
        ev = sum(c.get("ev_rupees") or 0 for c in active)
        return {
            "intent": "summary",
            "answer": (
                f"{len(active)} live cases, ₹{rupees:,.0f} at risk. "
                f"Oracle expected recovery ₹{ev:,.0f}. "
                f"IST {to_ist().strftime('%H:%M')} "
                f"{'— quiet hours, outbound deferred.' if is_quiet_hours() else '— send window open.'}"
            ),
            "matches": active[:8],
            "spec": spec,
        }

    matched = [c for c in cards if case_matches_spec(c, spec)]
    if spec.get("intent") == "twin" and matched:
        top = matched[0]
        return {
            "intent": "twin",
            "answer": f"Highest-value match is {top['payment_id']} (₹{top['amount_in_rupees']:,.0f}). Open the Digital Twin on that case.",
            "matches": matched[:8],
            "focus_case_id": top["id"],
            "spec": spec,
        }

    return {
        "intent": spec.get("intent", "query"),
        "answer": f"Found {len(matched)} matching cases for '{body.query}'.",
        "matches": matched[:8],
        "spec": spec,
    }


from ai.offer_engine import offer_engine
from ai.shadow_simulator import shadow_simulator
from domain.bank_health.sentinel import bank_sentinel
from domain.models.enums import ActionType


@router.get("/sentinel")
async def bank_sentinel_analytics(
    _: OperatorContext = Depends(require_operator),
):
    """Predictive Bank Downtime Sentinel analytics across gateways."""
    entities = ["HDFC", "SBI", "ICICI", "RAZORPAY_UPI"]
    results = [bank_sentinel.evaluate_predictive_circuit(e) for e in entities]
    return {
        "generated_at": datetime.utcnow(),
        "sentinel_analytics": results,
    }


class ShadowSimRequest(BaseModel):
    case_id: str
    proposed_action: ActionType = ActionType.PAYMENT_LINK


@router.post("/shadow-sim")
async def run_shadow_simulation(
    req: ShadowSimRequest,
    db: AsyncSession = Depends(get_db),
    _: OperatorContext = Depends(require_operator),
):
    """Executes 50-persona synthetic shadow simulation for a recovery case."""
    result = await db.execute(
        select(RecoveryCaseEntity)
        .where(RecoveryCaseEntity.id == req.case_id)
        .options(
            selectinload(RecoveryCaseEntity.payment),
            selectinload(RecoveryCaseEntity.customer),
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    pay = _payment_schema(case)
    cust = _customer_schema(case)
    if not pay or not cust:
        raise HTTPException(status_code=400, detail="Invalid payment or customer schema")

    sim_res = shadow_simulator.simulate(pay, cust, req.proposed_action)
    return {
        "case_id": case.id,
        "payment_id": case.payment_id,
        "proposed_action": req.proposed_action,
        "shadow_simulation": sim_res,
    }


class OfferEvaluationRequest(BaseModel):
    case_id: str


@router.post("/evaluate-offer")
async def evaluate_dynamic_offer(
    req: OfferEvaluationRequest,
    db: AsyncSession = Depends(get_db),
    _: OperatorContext = Depends(require_operator),
):
    """Evaluates dynamic micro-incentive recovery offer for positive Net EV."""
    result = await db.execute(
        select(RecoveryCaseEntity)
        .where(RecoveryCaseEntity.id == req.case_id)
        .options(
            selectinload(RecoveryCaseEntity.payment),
            selectinload(RecoveryCaseEntity.customer),
        )
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    pay = _payment_schema(case)
    cust = _customer_schema(case)
    if not pay or not cust:
        raise HTTPException(status_code=400, detail="Invalid payment or customer schema")

    bank_key = _bank_key_for(case)
    health = bank_health_matrix.get_health_score(bank_key)
    twin = simulate_twin(pay, cust, health)

    churn = twin.get("churn_risk", 0.3)
    base_p = twin.get("base_p_recover", 0.6)

    eval_res = offer_engine.evaluate_offer(pay, cust, churn, base_p)
    return {
        "case_id": case.id,
        "payment_id": case.payment_id,
        "offer_evaluation": eval_res,
    }


class SandboxSimulateRequest(BaseModel):
    amount_in_rupees: float = 2499.0
    failure_code: str = "BAD_REQUEST_PAYMENT_TIMED_OUT"
    bank_name: str = "HDFC"
    bank_health_score: float = 0.95
    customer_churn_risk: float = 0.35
    customer_tier: str = "STANDARD"
    offer_discount_pct: float = 5.0
    proposed_action: str = "PAYMENT_LINK"


@router.post("/sandbox-simulate")
async def simulate_sandbox_scenario(
    req: SandboxSimulateRequest,
    _: OperatorContext = Depends(require_operator),
):
    """
    Ultra-Fast Interactive AI What-If Simulation Engine.
    Simulates 50-persona Shadow Sim, Bank Sentinel velocity, Offer Engine EV,
    Policy Firewall, and WhatsApp UPI deep links in a single <2ms response.
    """
    from domain.models.enums import ActionType, CustomerTier, FailureCode, PaymentStatus
    from domain.models.schemas import CandidateAction, CustomerSchema, PaymentSchema
    from domain.policies.engine import policy_engine
    from services.whatsapp_service import whatsapp_service
    from ai.copy_rag import copy_rag

    # Parse enums safely
    try:
        fc = FailureCode(req.failure_code)
    except ValueError:
        fc = FailureCode.BAD_REQUEST_PAYMENT_TIMED_OUT

    try:
        tier = CustomerTier(req.customer_tier)
    except ValueError:
        tier = CustomerTier.STANDARD

    try:
        action = ActionType(req.proposed_action)
    except ValueError:
        action = ActionType.PAYMENT_LINK

    amount_paise = int(req.amount_in_rupees * 100)

    payment = PaymentSchema(
        id="pay_sim_sandbox_999",
        order_id="order_sim_sandbox_999",
        customer_id="cust_sim_sandbox_999",
        amount_in_paise=amount_paise,
        currency="INR",
        status=PaymentStatus.FAILED,
        failure_code=fc,
        failure_description=f"Simulated {fc.value} at {req.bank_name}",
        created_at="2026-09-01T00:00:00Z",
    )

    customer = CustomerSchema(
        id="cust_sim_sandbox_999",
        name="Aditya Sharma",
        email="a*****a@example.com",
        phone="+919876543210",
        tier=tier,
        lifetime_recovered_paise=500000,
        contact_token_bucket=2,
        opted_out=False,
    )

    # 1. Shadow Simulation (50 Synthetic Personas)
    shadow_sim = shadow_simulator.simulate(payment, customer, action)

    # 2. Predictive Bank Sentinel
    sentinel_res = bank_sentinel.evaluate_predictive_circuit(req.bank_name)

    # 3. Dynamic Offer Engine EV Calculation
    offer_res = offer_engine.evaluate_offer(
        payment, customer, churn_risk=req.customer_churn_risk, base_p_recover=0.55
    )

    # 4. Policy Firewall Evaluation (All Rules)
    candidate = CandidateAction(
        action=action,
        confidence_score=0.80,
        expected_value_in_paise=int(0.80 * amount_paise),
        rationale=f"Sandbox candidate action {action.value}",
    )
    policy_eval = policy_engine.evaluate(
        payment=payment,
        customer=customer,
        proposed_action=candidate,
        bank_key=req.bank_name,
    )

    # 5. Semantic Copy RAG & WhatsApp UPI Deep Link Payload
    rag_match = copy_rag.retrieve_best_copy(fc)
    upi_link = whatsapp_service.generate_upi_deep_link(
        payee_vpa="merchant@razorpay",
        payee_name="Merchant Recovery",
        amount_in_rupees=req.amount_in_rupees,
        transaction_ref="tx_sandbox_001",
        note=f"Renewal for {req.bank_name}",
    )
    wa_payload = whatsapp_service.build_whatsapp_template_payload(
        customer_phone=customer.phone or "+919876543210",
        customer_name=customer.name,
        amount_in_rupees=req.amount_in_rupees,
        short_url="https://rzp.io/i/sandbox-preview",
        upi_deep_link=upi_link,
        copy_headline=offer_res.get("copy_headline") or rag_match["copy_headline"],
    )

    # EV curve comparison calculations
    ev_standard = int(0.55 * req.amount_in_rupees)
    ev_offer = int(offer_res.get("ev_with_offer_rupees", ev_standard * 1.15))
    ev_retry = int(0.40 * req.amount_in_rupees) if req.bank_health_score > 0.7 else int(0.15 * req.amount_in_rupees)

    return {
        "input": req.model_dump(),
        "shadow_simulation": shadow_sim,
        "bank_sentinel": sentinel_res,
        "offer_evaluation": offer_res,
        "policy_firewall": {
            "approved_action": policy_eval.approved_action.value,
            "requires_human_approval": policy_eval.requires_human_approval,
            "override_reason": policy_eval.override_reason,
            "checks": [c.model_dump() for c in policy_eval.policy_checks],
        },
        "ev_curve": {
            "ev_standard_rupees": ev_standard,
            "ev_offer_rupees": ev_offer,
            "ev_retry_rupees": ev_retry,
            "optimal_strategy": "DYNAMIC_OFFER" if ev_offer > ev_standard else "SMART_RETRY",
        },
        "whatsapp_preview": wa_payload,
        "copy_rag_matched": rag_match,
    }


class VoiceCallSimulationRequest(BaseModel):
    customer_name: str = "Rahul Sharma"
    customer_phone: str = "+919876543210"
    amount_in_rupees: float = 10000.0
    language: str = "hinglish"  # 'hinglish' | 'english'
    tier: str = "STANDARD"


class ChurnRescueRequest(BaseModel):
    customer_name: str = "Priya Patel"
    tier: str = "VIP"
    amount_in_rupees: float = 4999.0
    consecutive_failures: int = 2


@router.post("/voice-call/simulate")
async def simulate_voice_ai_call(
    req: VoiceCallSimulationRequest,
    _: OperatorContext = Depends(require_operator),
):
    """
    Simulates a futuristic bilingual Conversational Voice AI Debt Concierge call.
    Negotiates dynamic partial waterfall settlements with debtors in Hindi/English.
    """
    customer = CustomerSchema(
        id=f"cust_{hash(req.customer_phone)}",
        name=req.customer_name,
        email=f"{req.customer_name.lower().replace(' ', '.')}@example.com",
        phone=req.customer_phone,
        tier=CustomerTier(req.tier) if req.tier in CustomerTier._value2member_map_ else CustomerTier.STANDARD,
    )
    payment = PaymentSchema(
        id=f"pay_vcall_{int(datetime.utcnow().timestamp())}",
        customer_id=customer.id,
        amount_in_paise=int(req.amount_in_rupees * 100),
        currency="INR",
        status=PaymentStatus.FAILED,
        failure_code=FailureCode.INSUFFICIENT_FUNDS,
        created_at=datetime.utcnow(),
    )
    return voice_agent_service.generate_call_simulation(
        customer=customer,
        payment=payment,
        language=req.language,
    )


@router.post("/churn-rescue/evaluate")
async def evaluate_churn_rescue(
    req: ChurnRescueRequest,
    _: OperatorContext = Depends(require_operator),
):
    """
    Evaluates Autonomous Churn Rescue strategies: Dynamic 14-day holiday pauses & plan downsells
    to retain 100% of customer relationships during cash flow hardship.
    """
    customer = CustomerSchema(
        id=f"cust_{hash(req.customer_name)}",
        name=req.customer_name,
        email=f"{req.customer_name.lower().replace(' ', '.')}@example.com",
        tier=CustomerTier(req.tier) if req.tier in CustomerTier._value2member_map_ else CustomerTier.STANDARD,
    )
    payment = PaymentSchema(
        id=f"pay_rescue_{int(datetime.utcnow().timestamp())}",
        customer_id=customer.id,
        amount_in_paise=int(req.amount_in_rupees * 100),
        currency="INR",
        status=PaymentStatus.FAILED,
        failure_code=FailureCode.INSUFFICIENT_FUNDS,
        created_at=datetime.utcnow(),
    )
    return churn_rescue_engine.evaluate_rescue_strategy(
        customer=customer,
        payment=payment,
        consecutive_failures=req.consecutive_failures,
    )

