import uuid
from datetime import datetime
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class WebhookEventEntity(Base):
    __tablename__ = "webhook_events"
    __table_args__ = (UniqueConstraint("event_id", name="uq_webhook_events_event_id"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(128), unique=True, nullable=False, index=True)
    event_type = Column(String(64), nullable=False, index=True)
    payload = Column(JSON, nullable=False)
    signature = Column(String(256), nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="PENDING", nullable=False)
    retry_count = Column(Integer, default=0, nullable=False)
    last_error = Column(Text, nullable=True)


class PaymentEntity(Base):
    __tablename__ = "payments"

    id = Column(String(64), primary_key=True)
    order_id = Column(String(64), nullable=True, index=True)
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    amount_in_paise = Column(BigInteger, nullable=False)
    currency = Column(String(8), default="INR", nullable=False)
    status = Column(String(32), nullable=False, index=True)
    method = Column(String(32), nullable=True)
    failure_code = Column(String(64), nullable=True, index=True)
    failure_description = Column(Text, nullable=True)
    bank_key = Column(String(64), nullable=True, index=True)
    created_at = Column(DateTime, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    notes = Column(JSON, default=dict)

    customer = relationship("CustomerEntity", back_populates="payments", lazy="noload")
    recovery_case = relationship("RecoveryCaseEntity", back_populates="payment", uselist=False, lazy="noload")


class CustomerEntity(Base):
    __tablename__ = "customers"

    id = Column(String(64), primary_key=True)
    name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False, index=True)
    phone = Column(String(32), nullable=True)
    tier = Column(String(32), default="STANDARD", nullable=False)
    lifetime_recovered_paise = Column(BigInteger, default=0, nullable=False)
    contact_token_bucket = Column(Integer, default=2, nullable=False)
    contact_timestamps = Column(JSON, default=list)
    last_contacted_at = Column(DateTime, nullable=True)
    opted_out = Column(Boolean, default=False, nullable=False)

    payments = relationship("PaymentEntity", back_populates="customer", lazy="noload")
    subscriptions = relationship("SubscriptionEntity", back_populates="customer", lazy="noload")
    recovery_cases = relationship("RecoveryCaseEntity", back_populates="customer", lazy="noload")


class SubscriptionEntity(Base):
    __tablename__ = "subscriptions"

    id = Column(String(64), primary_key=True)
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    plan_id = Column(String(64), nullable=False)
    status = Column(String(32), nullable=False, index=True)
    current_cycle_start = Column(DateTime, nullable=True)
    current_cycle_end = Column(DateTime, nullable=True)
    total_cycles = Column(Integer, default=12)
    completed_cycles = Column(Integer, default=0)
    retry_count = Column(Integer, default=0)

    customer = relationship("CustomerEntity", back_populates="subscriptions", lazy="noload")


class RecoveryCaseEntity(Base):
    __tablename__ = "recovery_cases"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    payment_id = Column(String(64), ForeignKey("payments.id"), nullable=False, unique=True, index=True)
    customer_id = Column(String(64), ForeignKey("customers.id"), nullable=False, index=True)
    state = Column(String(32), nullable=False, index=True)
    risk_tier = Column(String(16), nullable=False)
    amount_in_paise = Column(BigInteger, nullable=False)
    grace_expires_at = Column(DateTime, nullable=True)
    next_action_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    resolution_type = Column(String(32), nullable=True)
    last_idempotency_key = Column(String(128), nullable=True, index=True)
    predicted_ev_paise = Column(BigInteger, default=0, nullable=False)
    version = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    payment = relationship("PaymentEntity", back_populates="recovery_case", lazy="noload")
    customer = relationship("CustomerEntity", back_populates="recovery_cases", lazy="noload")
    decision_traces = relationship(
        "DecisionTraceEntity",
        back_populates="recovery_case",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class DecisionTraceEntity(Base):
    __tablename__ = "decision_traces"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    case_id = Column(String(36), ForeignKey("recovery_cases.id"), nullable=False, index=True)
    step_number = Column(Integer, nullable=False)
    agent_mode = Column(String(32), nullable=False)
    raw_event_type = Column(String(64), nullable=False)
    diagnosis = Column(JSON, nullable=False)
    proposed_actions = Column(JSON, nullable=False)
    proposed_action = Column(String(64), nullable=True)
    approved_action = Column(String(64), nullable=True)
    policy_checks = Column(JSON, nullable=False)
    final_action = Column(String(64), nullable=False)
    execution_result = Column(JSON, nullable=True)
    operator_id = Column(String(64), nullable=True)
    prev_hash = Column(String(64), nullable=True)
    record_hash = Column(String(64), nullable=True)
    latency_ms = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    recovery_case = relationship("RecoveryCaseEntity", back_populates="decision_traces", lazy="noload")


class BankHealthEntity(Base):
    __tablename__ = "bank_health"

    entity_key = Column(String(64), primary_key=True)
    health_score = Column(Float, nullable=False, default=0.95)
    downtime_until = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OperatorEntity(Base):
    __tablename__ = "operators"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username = Column(String(64), unique=True, nullable=False, index=True)
    password_hash = Column(String(256), nullable=False)
    role = Column(String(32), default="operator", nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
