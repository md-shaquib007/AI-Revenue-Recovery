from enum import Enum


class EventType(str, Enum):
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_CAPTURED = "payment.captured"
    PAYMENT_AUTHORIZED = "payment.authorized"
    SUBSCRIPTION_PENDING = "subscription.pending"
    SUBSCRIPTION_HALTED = "subscription.halted"
    SUBSCRIPTION_CHARGED = "subscription.charged"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    REFUND_PROCESSED = "refund.processed"


class PaymentStatus(str, Enum):
    CREATED = "created"
    AUTHORIZED = "authorized"
    CAPTURED = "captured"
    FAILED = "failed"
    REFUNDED = "refunded"


class PaymentMethod(str, Enum):
    UPI = "upi"
    CARD = "card"
    NETBANKING = "netbanking"
    WALLET = "wallet"
    EMI = "emi"


class FailureCode(str, Enum):
    # Transient / Retriable
    GATEWAY_ERROR = "GATEWAY_ERROR"
    BANK_DOWNTIME = "BANK_DOWNTIME"
    BAD_REQUEST_PAYMENT_TIMED_OUT = "BAD_REQUEST_PAYMENT_TIMED_OUT"
    NETWORK_ERROR = "NETWORK_ERROR"
    
    # Customer-Actionable (Needs Payment Link / Method Switch)
    INSUFFICIENT_FUNDS = "INSUFFICIENT_FUNDS"
    CARD_EXPIRED = "CARD_EXPIRED"
    BAD_REQUEST_AUTHENTICATION_FAILED = "BAD_REQUEST_AUTHENTICATION_FAILED"  # 3DS OTP dropped
    TRANSACTION_LIMIT_EXCEEDED = "TRANSACTION_LIMIT_EXCEEDED"
    
    # Terminal / Non-recoverable
    CARD_BLOCKED = "CARD_BLOCKED"
    ACCOUNT_FROZEN = "ACCOUNT_FROZEN"
    FRAUD_SUSPECTED = "FRAUD_SUSPECTED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class RecoveryState(str, Enum):
    TRIAGING = "TRIAGING"
    IN_GRACE_WINDOW = "IN_GRACE_WINDOW"
    SCHEDULED_RETRY = "SCHEDULED_RETRY"
    LINK_SENT = "LINK_SENT"
    ESCALATED_HUMAN = "ESCALATED_HUMAN"
    PARTIALLY_RECOVERED = "PARTIALLY_RECOVERED"
    RECOVERED = "RECOVERED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"  # Late capture resolved before action


class ActionType(str, Enum):
    WAIT = "WAIT"                          # Grace window / bank health cooloff
    SMART_RETRY = "SMART_RETRY"            # Background auto-charge when bank recovers
    PAYMENT_LINK = "PAYMENT_LINK"          # Send 1-click Razorpay payment link (WhatsApp/SMS)
    PARTIAL_WATERFALL = "PARTIAL_WATERFALL"# Dynamic partial payment slice (e.g. ₹3K of ₹10K)
    METHOD_SWITCH = "METHOD_SWITCH"        # Suggest UPI Intent if Card failed
    HUMAN_ESCALATION = "HUMAN_ESCALATION"  # High-value or anomalous case for Ops
    CANCEL_RECOVERY = "CANCEL_RECOVERY"    # Already captured or user paid
    DO_NOT_CONTACT = "DO_NOT_CONTACT"      # Opted-out / Fatigued / Terminal


class RiskTier(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CustomerTier(str, Enum):
    STANDARD = "STANDARD"
    VIP = "VIP"
    ENTERPRISE = "ENTERPRISE"
    HIGH_CHURN_RISK = "HIGH_CHURN_RISK"


class AgentMode(str, Enum):
    AI_REASONER = "AI_REASONER"
    DETERMINISTIC_FALLBACK = "DETERMINISTIC_FALLBACK"
    BASELINE_SYSTEM = "BASELINE_SYSTEM"


class ResolutionType(str, Enum):
    AUTO_CAPTURED = "AUTO_CAPTURED"
    LINK_PAID = "LINK_PAID"
    MANUAL_OPS_RECOVERED = "MANUAL_OPS_RECOVERED"
    UNRECOVERABLE_EXPIRED = "UNRECOVERABLE_EXPIRED"
    CANCELLED_BY_LATE_CAPTURE = "CANCELLED_BY_LATE_CAPTURE"
