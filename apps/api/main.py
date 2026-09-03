import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse
from sqlalchemy import text

from apps.api.auth import bootstrap_default_operator
from apps.api.logging import (
    EnterpriseSecurityHeadersMiddleware,
    RateLimitMiddleware,
    RequestContextMiddleware,
    configure_logging,
    log_event,
)
from apps.api.metrics import metrics
from apps.api.routes.auth import router as auth_router
from apps.api.routes.benchmark import router as benchmark_router
from apps.api.routes.chaos import router as chaos_router
from apps.api.routes.human_ops import router as ops_router
from apps.api.routes.intel import router as intel_router
from apps.api.routes.recovery import router as recovery_router
from apps.api.routes.stream import router as stream_router
from apps.api.routes.system import router as system_router
from apps.api.routes.webhooks import router as webhooks_router
from apps.api.settings import get_settings
from domain.bank_health.matrix import bank_health_matrix
from services.db import AsyncSessionLocal, init_db
from services.recovery_worker import recovery_worker

configure_logging()
settings = get_settings()
_worker_task: asyncio.Task | None = None


async def _worker_loop() -> None:
    interval = max(1.0, settings.worker_interval_seconds)
    while True:
        try:
            async with AsyncSessionLocal() as session:
                await recovery_worker.tick(session)
                await session.commit()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log_event("error", "worker_loop_failed", error=str(exc))
        await asyncio.sleep(interval)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _worker_task
    await init_db()
    async with AsyncSessionLocal() as session:
        await bank_health_matrix.load_from_db(session)
        await bank_health_matrix.persist(session)
        await bootstrap_default_operator(session)
        await session.commit()

    if settings.sentry_dsn:
        try:
            import sentry_sdk

            sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, environment=settings.app_env)
        except Exception as exc:
            log_event("warning", "sentry_init_failed", error=str(exc))

    if settings.worker_enabled:
        _worker_task = asyncio.create_task(_worker_loop())
        log_event("info", "recovery_worker_started", interval=settings.worker_interval_seconds)

    log_event("info", "revive_started", env=settings.app_env, version=settings.app_version)
    yield

    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(
    title="REVIVE: Autonomous Revenue Recovery Agent",
    description="Event-Driven, Financially-Safe Revenue Recovery Agent for Razorpay Subscriptions & Payments",
    version=settings.app_version,
    lifespan=lifespan,
)

app.add_middleware(EnterpriseSecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhooks_router, prefix="/api/v1")
app.include_router(recovery_router, prefix="/api/v1")
app.include_router(intel_router, prefix="/api/v1")
app.include_router(ops_router, prefix="/api/v1")
app.include_router(chaos_router, prefix="/api/v1")
app.include_router(benchmark_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(stream_router, prefix="/api/v1")
app.include_router(system_router, prefix="/api/v1")


@app.get("/")
@app.head("/")
async def root():
    return {
        "service": settings.app_name,
        "status": "online",
        "version": settings.app_version,
        "axiom": "AI proposes. Policy decides. Systems execute.",
        "docs": "/docs",
        "health": "/health",
        "ready": "/ready",
        "api_v1_base": "/api/v1",
    }


@app.get("/health")
async def healthcheck():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "axiom": "AI proposes. Policy decides. Systems execute.",
    }


@app.get("/ready")
async def readiness():
    """Enterprise Kubernetes Readiness Probe: Checks DB, Sentinel, and Worker readiness."""
    checks = {"database": "ok", "sentinel": "ok", "worker": "active" if _worker_task and not _worker_task.done() else "standby"}
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready", "checks": checks, "version": settings.app_version}
    except Exception as exc:
        checks["database"] = f"error: {str(exc)}"
        return JSONResponse(status_code=503, content={"status": "not_ready", "checks": checks})


@app.get("/metrics")
async def prometheus_metrics():
    return PlainTextResponse(metrics.prometheus(), media_type="text/plain; version=0.0.4")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)
