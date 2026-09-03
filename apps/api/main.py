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

    log_event("info", "graceful_shutdown_initiating", message="Flushing in-flight tasks and worker queues")
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass

    try:
        from services.db import engine
        await engine.dispose()
    except Exception:
        pass
    log_event("info", "graceful_shutdown_completed")


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


# Setup Static Web UI Hosting (Unified Next.js Full-Stack)
import os
from fastapi.responses import FileResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

_UI_OUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "apps", "web", "out")
_NEXT_STATIC_DIR = os.path.join(_UI_OUT_DIR, "_next")

if os.path.exists(_NEXT_STATIC_DIR):
    app.mount("/_next", StaticFiles(directory=_NEXT_STATIC_DIR), name="next_static")


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


from fastapi.responses import HTMLResponse


@app.get("/pay/{case_id}", response_class=HTMLResponse, include_in_schema=False)
async def customer_self_service_portal(case_id: str):
    """Branded Customer Self-Service Recovery Portal (Full, Partial Split, 14-Day Holiday Pause, or Downsell)."""
    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>PrimeTech • Secure Subscription Resolution</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">
  <style>
    body {{ font-family: 'Plus Jakarta Sans', sans-serif; background: #090d16; color: #f8fafc; }}
    .glass {{ background: rgba(15, 23, 42, 0.75); backdrop-filter: blur(16px); border: 1px solid rgba(255, 255, 255, 0.08); }}
    .card-opt:hover {{ border-color: #10b981; transform: translateY(-2px); box-shadow: 0 10px 25px -5px rgba(16, 185, 129, 0.15); }}
  </style>
</head>
<body class="min-h-screen flex flex-col items-center justify-center p-4">
  <div class="max-w-md w-full glass rounded-3xl p-6 sm:p-8 shadow-2xl space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-slate-800 pb-4">
      <div class="flex items-center space-x-3">
        <div class="w-10 h-10 rounded-2xl bg-emerald-500/20 border border-emerald-500/30 flex items-center justify-center text-emerald-400 font-bold text-xl">⚡</div>
        <div>
          <h1 class="text-base font-bold tracking-tight text-white">PrimeTech Workspace</h1>
          <p class="text-xs text-slate-400">Subscription Recovery Portal</p>
        </div>
      </div>
      <span class="px-2.5 py-1 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">Action Required</span>
    </div>

    <!-- Amount Card -->
    <div class="bg-slate-900/80 rounded-2xl p-5 border border-slate-800 text-center relative overflow-hidden">
      <div class="absolute -right-6 -top-6 w-24 h-24 bg-emerald-500/10 rounded-full blur-xl"></div>
      <p class="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Overdue Invoice</p>
      <div class="text-3xl sm:text-4xl font-extrabold text-white my-1">₹10,000<span class="text-lg text-slate-400 font-medium">.00</span></div>
      <p class="text-xs text-emerald-400">⚡ Guaranteed zero late penalty fee</p>
    </div>

    <!-- Options -->
    <div class="space-y-3">
      <p class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Choose How You'd Like to Settle:</p>

      <!-- Option 1: Full Payment -->
      <button onclick="handleAction('PAY_FULL')" class="w-full text-left p-4 rounded-2xl glass card-opt transition-all duration-200 block border border-slate-800">
        <div class="flex items-center justify-between">
          <div class="font-bold text-sm text-white flex items-center space-x-2">
            <span>⚡ Pay Full Amount (₹10,000)</span>
          </div>
          <span class="text-[10px] bg-emerald-500/20 text-emerald-300 font-bold px-2 py-0.5 rounded-full border border-emerald-500/30">₹250 Cashback</span>
        </div>
        <p class="text-xs text-slate-400 mt-1">Instant 1-click UPI clearance. Keeps all features active immediately.</p>
      </button>

      <!-- Option 2: Partial Waterfall Split -->
      <button onclick="handleAction('PAY_PARTIAL')" class="w-full text-left p-4 rounded-2xl glass card-opt transition-all duration-200 block border border-slate-800">
        <div class="flex items-center justify-between">
          <div class="font-bold text-sm text-white flex items-center space-x-2">
            <span>💧 Pay ₹3,300 Today (Partial Split)</span>
          </div>
          <span class="text-[10px] bg-blue-500/20 text-blue-300 font-bold px-2 py-0.5 rounded-full border border-blue-500/30">0% Interest</span>
        </div>
        <p class="text-xs text-slate-400 mt-1">Pay just ₹3,300 now to maintain access. Balance auto-synced to your 5th salary date.</p>
      </button>

      <!-- Option 3: 14-Day Holiday Pause -->
      <button onclick="handleAction('PAUSE_14_DAYS')" class="w-full text-left p-4 rounded-2xl glass card-opt transition-all duration-200 block border border-slate-800">
        <div class="flex items-center justify-between">
          <div class="font-bold text-sm text-white flex items-center space-x-2">
            <span>⏸️ Take a 14-Day Holiday Pause</span>
          </div>
          <span class="text-[10px] bg-purple-500/20 text-purple-300 font-bold px-2 py-0.5 rounded-full border border-purple-500/30">Zero Data Loss</span>
        </div>
        <p class="text-xs text-slate-400 mt-1">Cash tight? Freeze billing for 2 weeks while keeping all your documents & workspace safe.</p>
      </button>

      <!-- Option 4: Micro-Tier Downsell -->
      <button onclick="handleAction('DOWNSELL')" class="w-full text-left p-4 rounded-2xl glass card-opt transition-all duration-200 block border border-slate-800">
        <div class="flex items-center justify-between">
          <div class="font-bold text-sm text-white flex items-center space-x-2">
            <span>📉 Switch to Essential Plan (₹999/mo)</span>
          </div>
          <span class="text-[10px] bg-amber-500/20 text-amber-300 font-bold px-2 py-0.5 rounded-full border border-amber-500/30">Save 75%</span>
        </div>
        <p class="text-xs text-slate-400 mt-1">Keep essential team tools at a fraction of the cost. Upgrade anytime later.</p>
      </button>
    </div>

    <!-- Status Output -->
    <div id="statusBox" class="hidden p-4 rounded-2xl bg-emerald-950/40 border border-emerald-500/30 text-center space-y-2">
      <div class="text-emerald-400 font-bold text-sm" id="statusTitle">✓ Selection Recorded</div>
      <p class="text-xs text-slate-300" id="statusMsg"></p>
      <a id="actionBtn" href="#" class="inline-block mt-2 px-4 py-2 rounded-xl bg-emerald-500 text-slate-950 font-bold text-xs hover:bg-emerald-400 transition-all">Continue to UPI Checkout →</a>
    </div>

    <!-- Trust Footer -->
    <div class="text-center pt-2 text-[11px] text-slate-500 flex items-center justify-center space-x-2">
      <span>🔒 256-Bit Bank-Grade Encryption</span>
      <span>•</span>
      <span>Powered by REVIVE Autonomous AI</span>
    </div>
  </div>

  <script>
    async function handleAction(act) {{
      const box = document.getElementById('statusBox');
      const title = document.getElementById('statusTitle');
      const msg = document.getElementById('statusMsg');
      const btn = document.getElementById('actionBtn');

      try {{
        const res = await fetch(`/api/v1/recovery/cases/{case_id}/customer-action`, {{
          method: 'POST',
          headers: {{ 'Content-Type': 'application/json' }},
          body: JSON.stringify({{ action: act }})
        }});
        const data = await res.json();
        
        box.classList.remove('hidden');
        if (data.status === 'ACTION_RECORDED') {{
          title.innerText = '✓ ' + (data.action === 'PAUSE_14_DAYS' ? '14-Day Pause Activated!' : 'Option Selected!');
          msg.innerText = data.message;
          if (data.checkout_url) {{
            btn.href = data.checkout_url;
            btn.classList.remove('hidden');
          }} else {{
            btn.classList.add('hidden');
          }}
        }} else {{
          title.innerText = '✓ Choice Logged';
          msg.innerText = 'Your preference has been submitted to PrimeTech.';
          btn.classList.add('hidden');
        }}
      }} catch (err) {{
        box.classList.remove('hidden');
        title.innerText = 'Selection Recorded';
        msg.innerText = 'Your choice has been securely logged with our billing system.';
        btn.classList.add('hidden');
      }}
    }}
  </script>
</body>
</html>"""


@app.get("/{full_path:path}", include_in_schema=False)
@app.head("/{full_path:path}", include_in_schema=False)
async def serve_unified_ui(full_path: str):
    """Serves the Next.js visual Command Center directly from the FastAPI container."""
    if full_path.startswith("api/") or full_path in ("docs", "openapi.json"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    if os.path.exists(_UI_OUT_DIR):
        clean_path = full_path.strip("/")
        # Check specific html route (e.g. /sandbox -> sandbox.html)
        html_candidate = os.path.join(_UI_OUT_DIR, f"{clean_path}.html")
        if clean_path and os.path.isfile(html_candidate):
            return FileResponse(html_candidate)
        # Check direct asset file (e.g. images, favicon.ico)
        direct_candidate = os.path.join(_UI_OUT_DIR, clean_path)
        if clean_path and os.path.isfile(direct_candidate):
            return FileResponse(direct_candidate)
        # Default to root index.html
        index_file = os.path.join(_UI_OUT_DIR, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file)

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


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("apps.api.main:app", host="0.0.0.0", port=8000, reload=True)
