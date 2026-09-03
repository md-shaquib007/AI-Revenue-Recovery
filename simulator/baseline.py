from typing import Any, Dict, List
from domain.models.enums import FailureCode


class BaselineFixedRetryEngine:
    """
    Legacy / Naive Fixed Retry Engine.
    Represents standard fintech behavior before Revive:
    - Fixed 10-minute retry regardless of error type.
    - Blindly sends generic notifications on every failure.
    - Zero grace-period awareness.
    - Zero bank health telemetry.
    - Zero customer fatigue protection.
    """

    def process_event_stream(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_failed_paise = 0
        total_recovered_paise = 0
        unnecessary_nudges = 0
        duplicate_actions = 0
        policy_violations = 0
        total_failures = 0
        recovered_failures = 0

        # Track active payments in baseline
        payment_tracker: Dict[str, Dict[str, Any]] = {}

        for evt in events:
            p_id = evt["payment_id"]
            e_type = evt["event_type"]

            if e_type == "payment.failed":
                total_failures += 1
                total_failed_paise += evt["amount_in_paise"]

                # Naive: immediately schedule SMS and fixed retry
                unnecessary_nudges += 1

                # If customer is fatigued or opted out, baseline still contacts (policy violation)
                if evt.get("opted_out"):
                    policy_violations += 1

                # High value with no human check (policy violation)
                if evt["amount_in_paise"] >= 5_000_000:
                    policy_violations += 1

                # Duplicate actions if already failed before
                if p_id in payment_tracker:
                    duplicate_actions += 1

                payment_tracker[p_id] = {
                    "amount_in_paise": evt["amount_in_paise"],
                    "failure_code": evt["failure_code"],
                    "will_capture_late": evt.get("will_capture_late", False),
                    "status": "FAILED",
                }

                # Baseline fixed recovery probability (naively lower due to spam & blind retries during outages)
                if evt["failure_code"] in [FailureCode.CARD_BLOCKED.value, FailureCode.CARD_EXPIRED.value]:
                    # Fixed retry on expired/blocked card ALWAYS fails (0% recovery without smart link)
                    pass
                elif evt["failure_code"] == FailureCode.GATEWAY_ERROR.value:
                    # 15% chance by luck
                    if evt.get("will_capture_late"):
                        total_recovered_paise += evt["amount_in_paise"]
                        recovered_failures += 1
                elif evt.get("will_capture_late"):
                    total_recovered_paise += evt["amount_in_paise"]
                    recovered_failures += 1
                elif evt["failure_code"] == FailureCode.INSUFFICIENT_FUNDS.value:
                    # Naive retry captures ~18%
                    total_recovered_paise += int(evt["amount_in_paise"] * 0.18)

            elif e_type == "payment.captured":
                if p_id in payment_tracker and payment_tracker[p_id]["status"] == "FAILED":
                    payment_tracker[p_id]["status"] = "CAPTURED"
                    # Baseline still sent the nudge before this captured!
                    # So unnecessary nudge was already counted.

        recovery_rate_pct = (
            (total_recovered_paise / total_failed_paise * 100) if total_failed_paise > 0 else 0.0
        )

        return {
            "name": "Baseline (Fixed 10m Retry + Generic SMS)",
            "total_failed_amount_paise": total_failed_paise,
            "total_recovered_amount_paise": total_recovered_paise,
            "recovery_rate_pct": round(recovery_rate_pct, 2),
            "unnecessary_nudges_count": unnecessary_nudges,
            "duplicate_actions_count": duplicate_actions,
            "policy_violations_count": policy_violations,
            "human_escalations_count": 0,
        }
