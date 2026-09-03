import asyncio
import os
from typing import Any, Dict, Optional

import httpx

from apps.api.settings import get_settings
from services.mock_razorpay import mock_razorpay


class RazorpayClientService:
    """Unified Razorpay client with mock fallback and idempotent outbound calls."""

    def __init__(self) -> None:
        settings = get_settings()
        self.key_id = settings.razorpay_key_id
        self.key_secret = settings.razorpay_key_secret
        self.webhook_secret = settings.razorpay_webhook_secret
        self.is_live_test_mode = settings.razorpay_enable_live_api

    def verify_signature(self, payload_str: str, signature: str) -> bool:
        return mock_razorpay.verify_webhook_signature(payload_str, signature, self.webhook_secret)

    async def create_payment_link(
        self,
        amount_in_paise: int,
        customer_name: str,
        customer_email: str,
        customer_phone: Optional[str] = None,
        description: str = "Subscription Payment Recovery",
        idempotency_key: Optional[str] = None,
        accept_partial: bool = False,
        first_min_partial_amount: Optional[int] = None,
    ) -> Dict[str, Any]:
        if not self.is_live_test_mode:
            return mock_razorpay.create_payment_link(
                amount_in_paise,
                customer_name,
                customer_email,
                customer_phone,
                description,
                idempotency_key=idempotency_key,
                accept_partial=accept_partial,
                first_min_partial_amount=first_min_partial_amount,
            )

        payload = {
            "amount": amount_in_paise,
            "currency": "INR",
            "accept_partial": accept_partial,
            "first_min_partial_amount": first_min_partial_amount or (int(amount_in_paise * 0.33) if accept_partial else None),
            "description": description,
            "customer": {
                "name": customer_name,
                "email": customer_email,
                "contact": customer_phone,
            },
            "notify": {"sms": bool(customer_phone), "email": True},
            "reminder_enable": True,
        }
        headers = {}
        if idempotency_key:
            headers["X-Razorpay-Idempotency-Key"] = idempotency_key

        return await self._request_with_retry(
            "POST",
            "https://api.razorpay.com/v1/payment_links",
            json_payload=payload,
            headers=headers,
        )

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        json_payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """
        Executes HTTP requests with exponential backoff retry on HTTP 429 / 5xx errors.
        Prevents outbound call failures during Razorpay API rate-limit spikes.
        """
        headers = headers or {}
        async with httpx.AsyncClient() as client:
            for attempt in range(1, max_retries + 1):
                try:
                    resp = await client.request(
                        method=method,
                        url=url,
                        json=json_payload,
                        auth=(self.key_id, self.key_secret),
                        headers=headers,
                        timeout=10.0,
                    )
                    if resp.status_code == 429 or resp.status_code >= 500:
                        if attempt < max_retries:
                            await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                            continue
                    resp.raise_for_status()
                    return resp.json()
                except (httpx.HTTPStatusError, httpx.RequestError) as exc:
                    if attempt >= max_retries:
                        raise exc
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))

    async def trigger_subscription_retry(
        self,
        subscription_id: str,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not self.is_live_test_mode:
            return mock_razorpay.retry_subscription_charge(subscription_id, idempotency_key=idempotency_key)

        url = f"https://api.razorpay.com/v1/subscriptions/{subscription_id}/resume"
        headers = {}
        if idempotency_key:
            headers["X-Razorpay-Idempotency"] = idempotency_key
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                auth=(self.key_id, self.key_secret),
                headers=headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def charge_subscription(
        self,
        subscription_id: str,
        amount_in_paise: int,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Direct Razorpay Subscription Charge API (POST /v1/subscriptions/{id}/charge)."""
        if not self.is_live_test_mode:
            return mock_razorpay.charge_subscription(subscription_id, amount_in_paise, idempotency_key=idempotency_key)

        url = f"https://api.razorpay.com/v1/subscriptions/{subscription_id}/charge"
        payload = {"amount": amount_in_paise}
        headers = {}
        if idempotency_key:
            headers["X-Razorpay-Idempotency"] = idempotency_key
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                url,
                json=payload,
                auth=(self.key_id, self.key_secret),
                headers=headers,
                timeout=10.0,
            )
            resp.raise_for_status()
            return resp.json()


razorpay_service = RazorpayClientService()
