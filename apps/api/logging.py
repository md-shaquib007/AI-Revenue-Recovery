import json
import logging
import sys
import time
import uuid
from typing import Any, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.metrics import metrics
from apps.api.settings import get_settings


import re


# Real-Time Zero-Leak PII Redaction Regex Patterns
CC_REGEX = re.compile(r"\b(?:\d{4}[ -]?){3}(\d{4})\b")
EMAIL_REGEX = re.compile(r"\b([a-zA-Z0-9_.+-]{1,2})[a-zA-Z0-9_.+-]*(@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)\b")
PHONE_REGEX = re.compile(r"(\+?91[\-\s]?)?([6-9]\d{1})\d{6}(\d{2})")
PAN_REGEX = re.compile(r"\b([A-Z]{2})[A-Z]{3}\d{4}([A-Z]{1})\b")
AADHAAR_REGEX = re.compile(r"\b\d{4}[ -]?\d{4}[ -]?(\d{4})\b")


def sanitize_pii_value(val: Any) -> Any:
    """Recursively scrub PII (cards, phones, emails, PAN, Aadhaar) from log streams."""
    if isinstance(val, str):
        s = CC_REGEX.sub(r"****-****-****-\1", val)
        s = EMAIL_REGEX.sub(r"\1***\2", s)
        s = PHONE_REGEX.sub(r"+91-\2******\3", s)
        s = PAN_REGEX.sub(r"\1*****\2", s)
        s = AADHAAR_REGEX.sub(r"****-****-\1", s)
        return s
    elif isinstance(val, dict):
        return {k: sanitize_pii_value(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_pii_value(item) for item in val]
    return val


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("revive")
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    logger.propagate = False
    return logger


logger = configure_logging()


def log_event(level: str, event_name: str, **fields) -> None:
    sanitized_fields = {k: sanitize_pii_value(v) for k, v in fields.items()}
    payload = {"level": level, "message": event_name, **sanitized_fields}
    getattr(logger, level if level in ("info", "warning", "error", "debug") else "info")(
        json.dumps(payload, default=str)
    )


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        start = time.perf_counter()
        request.state.request_id = request_id
        try:
            response = await call_next(request)
        except Exception:
            log_event(
                "error",
                "unhandled_exception",
                request_id=request_id,
                path=request.url.path,
                method=request.method,
            )
            raise
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        response.headers["X-Request-ID"] = request_id
        log_event(
            "info",
            "http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            status=response.status_code,
            latency_ms=elapsed_ms,
        )
        return response


class EnterpriseSecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds enterprise security hardening HTTP headers (OWASP/SOC2)."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Permitted-Cross-Domain-Policies"] = "none"
        response.headers["Content-Security-Policy"] = "default-src 'self' https: data: 'unsafe-inline' 'unsafe-eval'; connect-src 'self' https: wss:;"
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app) -> None:
        super().__init__(app)
        self._hits: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        settings = get_settings()
        if not settings.enable_rate_limit:
            return await call_next(request)

        path = request.url.path
        if path in ("/health", "/ready", "/metrics"):
            return await call_next(request)

        client = request.client.host if request.client else "unknown"
        now = time.time()
        window = 60.0
        if path.startswith("/api/v1/webhooks"):
            limit = settings.webhook_rate_limit_per_minute
            key = f"wh:{client}"
        else:
            limit = settings.api_rate_limit_per_minute
            key = f"api:{client}"

        bucket = [t for t in self._hits.get(key, []) if now - t < window]
        if len(bucket) >= limit:
            metrics.inc("rate_limited")
            return Response(
                content='{"detail":"Rate limit exceeded"}',
                status_code=429,
                media_type="application/json",
                headers={"Retry-After": "60", "X-Request-ID": getattr(request.state, "request_id", "")},
            )
        bucket.append(now)
        self._hits[key] = bucket
        return await call_next(request)
