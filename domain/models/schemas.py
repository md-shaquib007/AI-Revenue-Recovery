from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
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


class WebhookPayload(BaseModel):
    event: Union[EventType, str]
    account_id: Optional[str] = None
    event_id: Optional[str] = None
    contains: List[str] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[int] = None


class PaymentSchema(BaseModel):
    id: str
    order_id: Optional[str] = None
    customer_id: str
    amount_in_paise: int
    currency: str = "INR"
    status: PaymentStatus
    method: Optional[PaymentMethod] = None
    failure_code: Optional[FailureCode] = None
    failure_description: Optional[str] = None
    created_at: datetime
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Dict[str, Any] = Field(default_factory=dict)


class CustomerSchema(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    tier: CustomerTier = CustomerTier.STANDARD
    lifetime_recovered_paise: int = 0
    contact_token_bucket: int = 2
    contact_timestamps: List[datetime] = Field(default_factory=list)
    last_contacted_at: Optional[datetime] = None
    opted_out: bool = False


class SubscriptionSchema(BaseModel):
    id: str
    customer_id: str
    plan_id: str
    status: str
    current_cycle_start: Optional[datetime] = None
    current_cycle_end: Optional[datetime] = None
    total_cycles: int = 12
    completed_cycles: int = 0
    retry_count: int = 0


class CandidateAction(BaseModel):
    action: ActionType
    confidence_score: float = Field(ge=0.0, le=1.0)
    expected_value_in_paise: int
    delay_seconds: int = 0
    channel: Optional[str] = None  # "whatsapp", "sms", "email", "silent_api"
    communication_copy: Optional[str] = None
    rationale: str


class AIDecisionProposal(BaseModel):
    failure_category: str
    is_transient: bool
    customer_churn_risk: float = Field(ge=0.0, le=1.0)
    recommended_actions: List[CandidateAction]
    primary_action: CandidateAction
    operator_explanation: str
    agent_mode: AgentMode = AgentMode.AI_REASONER
    latency_ms: int = 0
    tokens_used: int = 0


class PolicyCheckItem(BaseModel):
    rule_name: str
    passed: bool
    detail: str
    evaluated_at: datetime = Field(default_factory=datetime.utcnow)


class PolicyEvaluationResult(BaseModel):
    is_allowed: bool
    policy_checks: List[PolicyCheckItem]
    approved_action: ActionType
    override_reason: Optional[str] = None
    requires_human_approval: bool = False
    sanitized_copy: Optional[str] = None


class DecisionTraceSchema(BaseModel):
    id: str
    case_id: str
    step_number: int
    agent_mode: AgentMode
    raw_event_type: EventType
    diagnosis: Dict[str, Any]
    proposed_actions: List[Dict[str, Any]]
    proposed_action: Optional[str] = None
    approved_action: Optional[str] = None
    policy_checks: List[PolicyCheckItem]
    final_action: ActionType
    execution_result: Optional[Dict[str, Any]] = None
    operator_id: Optional[str] = None
    prev_hash: Optional[str] = None
    record_hash: Optional[str] = None
    latency_ms: int
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OperatorLoginRequest(BaseModel):
    username: str
    password: str


class OperatorTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    username: str
    role: str


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class RecoveryCaseSchema(BaseModel):
    id: str
    payment_id: str
    customer_id: str
    state: RecoveryState
    risk_tier: RiskTier
    amount_in_paise: int
    version: int = 1
    grace_expires_at: Optional[datetime] = None
    next_action_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_type: Optional[ResolutionType] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    traces: List[DecisionTraceSchema] = Field(default_factory=list)


class ChaosSimulationRequest(BaseModel):
    scenario: str  # "llm_outage", "out_of_order", "duplicate_storm", "prompt_injection", "bank_downtime"
    target_payment_id: Optional[str] = None
    payload: Optional[Dict[str, Any]] = None


class BenchmarkResultSchema(BaseModel):
    total_failed_amount_paise: int
    total_recovered_amount_paise: int
    recovery_rate_pct: float
    mean_time_to_recovery_seconds: float
    unnecessary_nudges_count: int
    duplicate_actions_count: int
    policy_violations_count: int
    human_escalations_count: int
    net_roi_multiple: float
