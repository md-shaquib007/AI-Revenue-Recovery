import json
import logging
import sys
import time
import uuid
from typing import Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from apps.api.metrics import metrics
from apps.api.settings import get_settings


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


def log_event(level: str, message: str, **fields) -> None:
    payload = {"level": level, "message": message, **fields}
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
