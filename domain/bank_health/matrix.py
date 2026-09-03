from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from domain.models.enums import FailureCode, PaymentMethod
from domain.models.entities import BankHealthEntity


class BankHealthMatrix:
    """
    Live Bank & Gateway Telemetry Matrix with Circuit Breakers.
    Correlates payment failures with bank/gateway stability.
    """

    def __init__(self):
        # Default baseline health: 1.0 is 100% healthy
        self._health_scores: Dict[str, float] = {
            "HDFC": 0.98,
            "SBI": 0.95,
            "ICICI": 0.99,
            "AXIS": 0.97,
            "KOTAK": 0.99,
            "RAZORPAY_UPI": 0.98,
            "RAZORPAY_CARDS": 0.99,
        }
        self._downtime_windows: Dict[str, datetime] = {}

    def get_health_score(self, entity_key: str) -> float:
        """Returns health score between 0.0 (total down) and 1.0 (perfect)."""
        entity_key = entity_key.upper()
        # If in downtime window, return degraded health
        if entity_key in self._downtime_windows:
            if datetime.utcnow() < self._downtime_windows[entity_key]:
                return self._health_scores.get(entity_key, 0.3)
            else:
                # Downtime expired, restore baseline
                del self._downtime_windows[entity_key]
                self._health_scores[entity_key] = 0.98

        return self._health_scores.get(entity_key, 0.95)

    def inject_downtime(self, entity_key: str, duration_minutes: int = 15, degraded_score: float = 0.25):
        """Simulates a sudden gateway or bank outage for chaos testing."""
        entity_key = entity_key.upper()
        self._health_scores[entity_key] = degraded_score
        self._downtime_windows[entity_key] = datetime.utcnow() + timedelta(minutes=duration_minutes)

    def recover_entity(self, entity_key: str):
        """Restores bank/gateway to 100% health."""
        entity_key = entity_key.upper()
        self._health_scores[entity_key] = 1.0
        self._downtime_windows.pop(entity_key, None)

    def calculate_smart_delay(
        self,
        failure_code: Optional[FailureCode],
        method: Optional[PaymentMethod],
        bank_name: Optional[str] = "HDFC",
    ) -> int:
        """
        Calculates the safest recovery delay (in seconds) before attempting
        a retry or sending communications.
        """
        entity_key = bank_name.upper() if bank_name else "RAZORPAY_UPI"
        health = self.get_health_score(entity_key)

        # Base delays by failure code
        if failure_code in [FailureCode.GATEWAY_ERROR, FailureCode.BANK_DOWNTIME, FailureCode.NETWORK_ERROR]:
            if health < 0.7:
                # Severe downtime: cooloff 30 minutes
                return 1800
            # Moderate jitter: cooloff 5 minutes
            return 300

        elif failure_code == FailureCode.BAD_REQUEST_AUTHENTICATION_FAILED:
            # 3DS OTP dropped: give customer 8 minutes grace window to complete in app
            return 480

        elif failure_code == FailureCode.INSUFFICIENT_FUNDS:
            # Salary / fund topup delay: wait 4 hours for silent retry, or generate link
            return 14400

        elif failure_code == FailureCode.CARD_EXPIRED:
            # Terminal for card auto-charge, immediate payment link required
            return 0

        # Default grace window for unclassified transient errors
        return 300

    def snapshot(self) -> List[Dict[str, Any]]:
        now = datetime.utcnow()
        rows = []
        for key, score in sorted(self._health_scores.items()):
            until = self._downtime_windows.get(key)
            live_score = self.get_health_score(key)
            degraded = bool(until and now < until) or live_score < 0.7
            rows.append(
                {
                    "entity_key": key,
                    "health_score": round(live_score, 4),
                    "health_pct": round(live_score * 100, 1),
                    "status": "Degraded" if degraded else "Healthy",
                    "downtime_until": until.isoformat() if until and now < until else None,
                }
            )
        return rows

    async def persist(self, db) -> None:
        from sqlalchemy import select

        now = datetime.utcnow()
        for key, score in self._health_scores.items():
            result = await db.execute(select(BankHealthEntity).where(BankHealthEntity.entity_key == key))
            row = result.scalars().first()
            until = self._downtime_windows.get(key)
            if row:
                row.health_score = score
                row.downtime_until = until
                row.updated_at = now
            else:
                db.add(
                    BankHealthEntity(
                        entity_key=key,
                        health_score=score,
                        downtime_until=until,
                        updated_at=now,
                    )
                )

    async def load_from_db(self, db) -> None:
        from sqlalchemy import select

        result = await db.execute(select(BankHealthEntity))
        for row in result.scalars().all():
            self._health_scores[row.entity_key] = row.health_score
            if row.downtime_until:
                self._downtime_windows[row.entity_key] = row.downtime_until


# Global singleton instance
bank_health_matrix = BankHealthMatrix()
