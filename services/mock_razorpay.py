import hashlib
import hmac
import time
import uuid
from typing import Any, Dict, Optional


class MockRazorpayClient:
    """
    In-memory Mock Razorpay API Client & Webhook Generator.
    Supports HMAC-SHA256 signature generation and bounded API test simulation.
    """

    WEBHOOK_SECRET = "test_webhook_secret_revive_2026"
    KEY_ID = "rzp_test_revive_key"
    KEY_SECRET = "rzp_test_revive_secret"

    def __init__(self):
        self._payment_links_created: Dict[str, Dict[str, Any]] = {}
        self._retries_attempted: Dict[str, Dict[str, Any]] = {}
        self._idempotent: Dict[str, Dict[str, Any]] = {}

    @classmethod
    def generate_webhook_signature(cls, payload_body: str, secret: Optional[str] = None) -> str:
        """Generates HMAC-SHA256 signature matching Razorpay webhook specification."""
        secret_to_use = (secret or cls.WEBHOOK_SECRET).encode("utf-8")
        return hmac.new(secret_to_use, payload_body.encode("utf-8"), hashlib.sha256).hexdigest()

    @classmethod
    def verify_webhook_signature(cls, payload_body: str, signature: str, secret: Optional[str] = None) -> bool:
        """Validates incoming Razorpay x-razorpay-signature header."""
        expected_sig = cls.generate_webhook_signature(payload_body, secret)
        return hmac.compare_digest(expected_sig, signature)

    def create_payment_link(
        self,
        amount_in_paise: int,
        customer_name: str,
        customer_email: str,
        customer_phone: Optional[str] = None,
        description: str = "Subscription Recovery Payment",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simulates Razorpay Payment Link API (POST /v1/payment_links)."""
        if idempotency_key and idempotency_key in self._idempotent:
            return self._idempotent[idempotency_key]
        link_id = f"plink_{uuid.uuid4().hex[:12]}"
        short_url = f"https://rzp.io/i/{uuid.uuid4().hex[:8]}"
        link_data = {
            "id": link_id,
            "amount": amount_in_paise,
            "currency": "INR",
            "status": "created",
            "short_url": short_url,
            "description": description,
            "customer": {
                "name": customer_name,
                "email": customer_email,
                "contact": customer_phone,
            },
            "created_at": int(time.time()),
        }
        self._payment_links_created[link_id] = link_data
        if idempotency_key:
            self._idempotent[idempotency_key] = link_data
        return link_data

    def retry_subscription_charge(self, subscription_id: str, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        """Simulates Razorpay Subscription Charge/Resume API."""
        if idempotency_key and idempotency_key in self._idempotent:
            return self._idempotent[idempotency_key]
        retry_id = f"retry_{uuid.uuid4().hex[:10]}"
        record = {
            "retry_id": retry_id,
            "subscription_id": subscription_id,
            "status": "scheduled",
            "timestamp": int(time.time()),
        }
        self._retries_attempted[retry_id] = record
        if idempotency_key:
            self._idempotent[idempotency_key] = record
        return record

    def charge_subscription(
        self,
        subscription_id: str,
        amount_in_paise: int,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Simulates Razorpay Subscription Direct Charge API (POST /v1/subscriptions/{id}/charge)."""
        if idempotency_key and idempotency_key in self._idempotent:
            return self._idempotent[idempotency_key]
        charge_id = f"sub_charge_{uuid.uuid4().hex[:10]}"
        record = {
            "id": charge_id,
            "entity": "subscription_charge",
            "subscription_id": subscription_id,
            "amount": amount_in_paise,
            "status": "charged",
            "created_at": int(time.time()),
        }
        self._retries_attempted[charge_id] = record
        if idempotency_key:
            self._idempotent[idempotency_key] = record
        return record


# Global singleton instance
mock_razorpay = MockRazorpayClient()
