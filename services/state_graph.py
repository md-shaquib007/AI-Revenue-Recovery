from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from domain.models.enums import ActionType


class CustomerRecoveryState:
    INITIAL_FAILURE = "INITIAL_FAILURE"
    NUDGE_DELIVERED = "NUDGE_DELIVERED"
    ENGAGED_VIEWED_PORTAL = "ENGAGED_VIEWED_PORTAL"
    LIQUIDITY_DISCLOSED = "LIQUIDITY_DISCLOSED"
    PARTIAL_SETTLEMENT_ACTIVE = "PARTIAL_SETTLEMENT_ACTIVE"
    HOLIDAY_PAUSED = "HOLIDAY_PAUSED"
    DOWNSELL_COMPLETED = "DOWNSELL_COMPLETED"
    FULLY_RECOVERED = "FULLY_RECOVERED"
    ABANDONED_CHURNED = "ABANDONED_CHURNED"


class CustomerStateGraphEngine:
    """
    Customer Recovery State Graph Engine.
    Models multi-step customer behavioral transitions and predicts
    the mathematically optimal Next-Best-Action based on live state history.
    """

    VALID_TRANSITIONS = {
        CustomerRecoveryState.INITIAL_FAILURE: [
            CustomerRecoveryState.NUDGE_DELIVERED,
            CustomerRecoveryState.ENGAGED_VIEWED_PORTAL,
            CustomerRecoveryState.FULLY_RECOVERED,
            CustomerRecoveryState.ABANDONED_CHURNED,
        ],
        CustomerRecoveryState.NUDGE_DELIVERED: [
            CustomerRecoveryState.ENGAGED_VIEWED_PORTAL,
            CustomerRecoveryState.LIQUIDITY_DISCLOSED,
            CustomerRecoveryState.PARTIAL_SETTLEMENT_ACTIVE,
            CustomerRecoveryState.HOLIDAY_PAUSED,
            CustomerRecoveryState.DOWNSELL_COMPLETED,
            CustomerRecoveryState.FULLY_RECOVERED,
            CustomerRecoveryState.ABANDONED_CHURNED,
        ],
        CustomerRecoveryState.ENGAGED_VIEWED_PORTAL: [
            CustomerRecoveryState.LIQUIDITY_DISCLOSED,
            CustomerRecoveryState.PARTIAL_SETTLEMENT_ACTIVE,
            CustomerRecoveryState.HOLIDAY_PAUSED,
            CustomerRecoveryState.DOWNSELL_COMPLETED,
            CustomerRecoveryState.FULLY_RECOVERED,
        ],
        CustomerRecoveryState.LIQUIDITY_DISCLOSED: [
            CustomerRecoveryState.PARTIAL_SETTLEMENT_ACTIVE,
            CustomerRecoveryState.FULLY_RECOVERED,
        ],
        CustomerRecoveryState.PARTIAL_SETTLEMENT_ACTIVE: [
            CustomerRecoveryState.FULLY_RECOVERED,
            CustomerRecoveryState.ABANDONED_CHURNED,
        ],
        CustomerRecoveryState.HOLIDAY_PAUSED: [
            CustomerRecoveryState.FULLY_RECOVERED,
            CustomerRecoveryState.DOWNSELL_COMPLETED,
        ],
        CustomerRecoveryState.DOWNSELL_COMPLETED: [
            CustomerRecoveryState.FULLY_RECOVERED,
        ],
        CustomerRecoveryState.FULLY_RECOVERED: [],
        CustomerRecoveryState.ABANDONED_CHURNED: [],
    }

    @classmethod
    def evaluate_transition(
        cls,
        current_state: str,
        event_trigger: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        metadata = metadata or {}
        next_state = current_state

        if event_trigger == "WEBHOOK_FAILED":
            next_state = CustomerRecoveryState.INITIAL_FAILURE
        elif event_trigger == "WHATSAPP_NUDGE_SENT":
            next_state = CustomerRecoveryState.NUDGE_DELIVERED
        elif event_trigger == "PORTAL_OPENED":
            next_state = CustomerRecoveryState.ENGAGED_VIEWED_PORTAL
        elif event_trigger == "SALARY_DATE_DISCLOSED":
            next_state = CustomerRecoveryState.LIQUIDITY_DISCLOSED
        elif event_trigger == "PARTIAL_PAYMENT_MADE":
            next_state = CustomerRecoveryState.PARTIAL_SETTLEMENT_ACTIVE
        elif event_trigger == "PAUSE_14_DAYS_SELECTED":
            next_state = CustomerRecoveryState.HOLIDAY_PAUSED
        elif event_trigger == "DOWNSELL_SELECTED":
            next_state = CustomerRecoveryState.DOWNSELL_COMPLETED
        elif event_trigger in ["FULL_PAYMENT_CAPTURED", "BALANCE_CLEARED"]:
            next_state = CustomerRecoveryState.FULLY_RECOVERED
        elif event_trigger == "EXHAUSTED_MAX_RETRIES":
            next_state = CustomerRecoveryState.ABANDONED_CHURNED

        # Determine Next-Best-Action
        next_best_action = cls._compute_next_best_action(next_state, metadata)

        return {
            "previous_state": current_state,
            "current_state": next_state,
            "event_trigger": event_trigger,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "next_best_action": next_best_action,
            "metadata": metadata,
        }

    @classmethod
    def _compute_next_best_action(cls, state: str, metadata: Dict[str, Any]) -> Dict[str, Any]:
        if state == CustomerRecoveryState.INITIAL_FAILURE:
            return {
                "action": "EVALUATE_BANK_SENTINEL_AND_OFFER",
                "recommended_channel": "WHATSAPP_BIOMETRIC_LINK",
                "urgency": "MEDIUM",
                "quiet_hours_compliant": True,
            }
        elif state == CustomerRecoveryState.LIQUIDITY_DISCLOSED:
            salary_day = metadata.get("salary_day", 5)
            return {
                "action": "SCHEDULE_SALARY_CYCLE_SWEEP",
                "scheduled_date": f"Day {salary_day} at 06:30 AM IST",
                "suppress_interim_nudges": True,
                "urgency": "LOW",
            }
        elif state == CustomerRecoveryState.PARTIAL_SETTLEMENT_ACTIVE:
            return {
                "action": "SCHEDULE_REMAINDER_SWEEP",
                "remaining_balance_rupees": metadata.get("balance_due_rupees", 6700.0),
                "suppress_interim_nudges": True,
                "urgency": "LOW",
            }
        elif state == CustomerRecoveryState.HOLIDAY_PAUSED:
            return {
                "action": "FREEZE_BILLING_PRESERVE_ACCESS",
                "resume_in_days": 14,
                "urgency": "LOW",
            }
        elif state == CustomerRecoveryState.FULLY_RECOVERED:
            return {
                "action": "EMIT_SOC2_CERTIFICATE_AND_CLOSE",
                "urgency": "NONE",
            }
        return {
            "action": "DISPATCH_PORTAL_INTERVENTION",
            "recommended_channel": "CUSTOMER_SELF_SERVICE_PORTAL",
            "urgency": "MEDIUM",
        }


customer_state_graph = CustomerStateGraphEngine()
