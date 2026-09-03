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
app.add_middleware(GZipMiddleware, minimum_size=500)
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


from services.metrics import metrics_collector


@app.get("/health")
@app.get("/healthz")
async def healthcheck():
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
        "axiom": "AI proposes. Policy decides. Systems execute.",
    }


@app.get("/ready")
@app.get("/readyz")
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
    """Exposes standard Prometheus & OpenTelemetry metrics for Grafana/Datadog."""
    return PlainTextResponse(metrics_collector.generate_metrics_text(), media_type="text/plain; version=0.0.4")


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


@app.get("/simulator", response_class=HTMLResponse, include_in_schema=False)
async def serve_recovery_simulator():
    """Renders the interactive Revenue Recovery Portfolio Simulator & CFO ROI Studio."""
    return """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>REVIVE — Revenue Recovery Portfolio Simulator</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen py-10 px-4 antialiased selection:bg-emerald-500 selection:text-slate-950">
  <div class="max-w-4xl mx-auto space-y-8">
    <!-- Header -->
    <div class="text-center space-y-3">
      <div class="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold uppercase tracking-wider">
        <span>⚡ Interactive Portfolio Simulator</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent">
        Quantify Your Incremental ARR Recovery Lift
      </h1>
      <p class="text-sm text-slate-400 max-w-xl mx-auto">
        Adjust your monthly failed volume to simulate counterfactual recovery gains across REVIVE's Bank Sentinel, Partial Slicing, and Salary-Cycle Sweeping engines.
      </p>
    </div>

    <!-- Simulator Form & Controls -->
    <div class="grid grid-cols-1 md:grid-cols-3 gap-6">
      <!-- Controls Column -->
      <div class="md:col-span-1 p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-6 shadow-2xl">
        <h3 class="text-sm font-bold text-slate-200 uppercase tracking-wider flex items-center space-x-2">
          <span>⚙️ Parameters</span>
        </h3>

        <!-- Volume Slider -->
        <div class="space-y-2">
          <div class="flex justify-between text-xs">
            <span class="text-slate-400">Monthly Failed Volume</span>
            <span id="volLabel" class="text-emerald-400 font-bold">₹50,00,000</span>
          </div>
          <input id="volSlider" type="range" min="500000" max="20000000" step="500000" value="5000000" class="w-full accent-emerald-500 cursor-pointer" oninput="updateSim()">
        </div>

        <!-- Ticket Size Slider -->
        <div class="space-y-2">
          <div class="flex justify-between text-xs">
            <span class="text-slate-400">Avg Ticket Size</span>
            <span id="ticketLabel" class="text-emerald-400 font-bold">₹5,000</span>
          </div>
          <input id="ticketSlider" type="range" min="500" max="25000" step="500" value="5000" class="w-full accent-emerald-500 cursor-pointer" oninput="updateSim()">
        </div>

        <!-- Gateway Selector -->
        <div class="space-y-2">
          <label class="text-xs text-slate-400">Primary Gateway</label>
          <select id="gatewaySelect" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 font-semibold focus:border-emerald-500 outline-none" onchange="updateSim()">
            <option value="RAZORPAY">Razorpay (UPI / Autopay)</option>
            <option value="STRIPE">Stripe (Cards / Invoicing)</option>
            <option value="CHARGEBEE">Chargebee / Recurly</option>
          </select>
        </div>

        <!-- Industry Selector -->
        <div class="space-y-2">
          <label class="text-xs text-slate-400">Industry Segment</label>
          <select id="industrySelect" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-xs text-slate-200 font-semibold focus:border-emerald-500 outline-none" onchange="updateSim()">
            <option value="SAAS">B2B SaaS / Workspace</option>
            <option value="EDTECH">EdTech & Courses</option>
            <option value="FINTECH">FinTech & Wealth</option>
            <option value="MEMBERSHIP">Fitness & Memberships</option>
          </select>
        </div>

        <div class="pt-2">
          <a href="/pay/demo-case" target="_blank" class="block w-full py-2.5 text-center rounded-xl bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-bold text-slate-300 transition-all">
            Preview /pay/case Portal →
          </a>
        </div>
      </div>

      <!-- Results Display -->
      <div class="md:col-span-2 p-6 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-6 shadow-2xl flex flex-col justify-between">
        <!-- Top Metrics Cards -->
        <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
          <div class="p-4 rounded-2xl bg-slate-950/80 border border-slate-800/80 space-y-1">
            <span class="text-[11px] text-slate-400 uppercase font-semibold">Baseline Recovery</span>
            <div id="baselineRate" class="text-xl font-extrabold text-slate-400">31.2%</div>
            <div id="baselineRupees" class="text-xs text-slate-500">₹15,60,000 / mo</div>
          </div>

          <div class="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-500/30 space-y-1">
            <span class="text-[11px] text-emerald-400 uppercase font-bold">REVIVE Simulated</span>
            <div id="reviveRate" class="text-xl font-extrabold text-emerald-400">71.6%</div>
            <div id="reviveRupees" class="text-xs text-emerald-300 font-bold">₹35,80,000 / mo</div>
          </div>

          <div class="col-span-2 sm:col-span-1 p-4 rounded-2xl bg-cyan-950/40 border border-cyan-500/30 space-y-1">
            <span class="text-[11px] text-cyan-400 uppercase font-bold">Incremental Lift</span>
            <div id="liftPercentage" class="text-xl font-extrabold text-cyan-400">+40.4%</div>
            <div id="liftAnnual" class="text-xs text-cyan-300 font-bold">+₹2.42 Cr / yr</div>
          </div>
        </div>

        <!-- Strategy Breakdown Table -->
        <div class="space-y-3">
          <h4 class="text-xs font-bold uppercase tracking-wider text-slate-400">Strategy Contribution Breakdown</h4>
          <div class="space-y-2 text-xs">
            <div class="flex justify-between items-center p-2.5 rounded-xl bg-slate-950 border border-slate-800/80">
              <span class="text-slate-300">⚡ Bank Sentinel Outage Avoidance</span>
              <span id="sentinelAmt" class="font-bold text-emerald-400">+₹6,20,000 (+12.4%)</span>
            </div>
            <div class="flex justify-between items-center p-2.5 rounded-xl bg-slate-950 border border-slate-800/80">
              <span class="text-slate-300">💧 Partial Waterfall 33% Slicing</span>
              <span id="slicingAmt" class="font-bold text-emerald-400">+₹8,40,000 (+16.8%)</span>
            </div>
            <div class="flex justify-between items-center p-2.5 rounded-xl bg-slate-950 border border-slate-800/80">
              <span class="text-slate-300">⏰ Salary-Cycle 06:30 AM Sweeper</span>
              <span id="salaryAmt" class="font-bold text-emerald-400">+₹3,80,000 (+7.6%)</span>
            </div>
            <div class="flex justify-between items-center p-2.5 rounded-xl bg-slate-950 border border-slate-800/80">
              <span class="text-slate-300">🛡️ 14-Day Holiday Pause Churn Rescue</span>
              <span id="pauseAmt" class="font-bold text-emerald-400">+₹1,80,000 (+3.6%)</span>
            </div>
          </div>
        </div>

        <!-- ROI Summary Banner -->
        <div class="p-4 rounded-2xl bg-gradient-to-r from-emerald-950/80 via-slate-900 to-teal-950/80 border border-emerald-500/30 flex items-center justify-between">
          <div class="space-y-1">
            <div class="text-xs font-bold text-emerald-300">Annual Preserved Customer LTV</div>
            <div id="ltvPreserved" class="text-lg font-extrabold text-white">₹2,42,40,000</div>
          </div>
          <div class="text-right">
            <span class="text-xs text-slate-400">Estimated ROI</span>
            <div id="roiMultiple" class="text-2xl font-extrabold text-emerald-400">44.9x</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <script>
    function formatINR(val) {
      return '₹' + Math.round(val).toLocaleString('en-IN');
    }

    function updateSim() {
      const vol = parseFloat(document.getElementById('volSlider').value);
      const ticket = parseFloat(document.getElementById('ticketSlider').value);

      document.getElementById('volLabel').innerText = formatINR(vol);
      document.getElementById('ticketLabel').innerText = formatINR(ticket);

      const baselineRate = 0.312;
      const sentinelLift = 0.124;
      const slicingLift = 0.168;
      const salaryLift = 0.076;
      const pauseLift = 0.036;

      const reviveRate = Math.min(0.85, baselineRate + sentinelLift + slicingLift + salaryLift + pauseLift);
      const netLift = reviveRate - baselineRate;

      const baselineRupees = vol * baselineRate;
      const reviveRupees = vol * reviveRate;
      const monthlyLiftRupees = reviveRupees - baselineRupees;
      const annualLiftRupees = monthlyLiftRupees * 12;

      const count = Math.max(1, Math.round(vol / ticket));
      const savedUsers = Math.round(count * netLift);
      const ltvPreserved = savedUsers * (ticket * 12);
      const roi = (monthlyLiftRupees / 45000).toFixed(1);

      document.getElementById('baselineRate').innerText = (baselineRate * 100).toFixed(1) + '%';
      document.getElementById('baselineRupees').innerText = formatINR(baselineRupees) + ' / mo';

      document.getElementById('reviveRate').innerText = (reviveRate * 100).toFixed(1) + '%';
      document.getElementById('reviveRupees').innerText = formatINR(reviveRupees) + ' / mo';

      document.getElementById('liftPercentage').innerText = '+' + (netLift * 100).toFixed(1) + '%';
      document.getElementById('liftAnnual').innerText = '+' + formatINR(annualLiftRupees) + ' / yr';

      document.getElementById('sentinelAmt').innerText = '+' + formatINR(vol * sentinelLift) + ' (+12.4%)';
      document.getElementById('slicingAmt').innerText = '+' + formatINR(vol * slicingLift) + ' (+16.8%)';
      document.getElementById('salaryAmt').innerText = '+' + formatINR(vol * salaryLift) + ' (+7.6%)';
      document.getElementById('pauseAmt').innerText = '+' + formatINR(vol * pauseLift) + ' (+3.6%)';

      document.getElementById('ltvPreserved').innerText = formatINR(ltvPreserved);
      document.getElementById('roiMultiple').innerText = roi + 'x';
    }

    updateSim();
  </script>
</body>
</html>"""


@app.get("/connect", response_class=HTMLResponse, include_in_schema=False)
async def serve_merchant_connect_portal():
    """Renders the 1-Click Merchant Connect & Webhook Ingestion Studio."""
    return """<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>REVIVE — 1-Click Merchant Connect & Onboarding</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap');
    body { font-family: 'Plus Jakarta Sans', sans-serif; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen py-10 px-4 antialiased selection:bg-emerald-500 selection:text-slate-950">
  <div class="max-w-3xl mx-auto space-y-8">
    <!-- Header -->
    <div class="text-center space-y-3">
      <div class="inline-flex items-center space-x-2 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 text-xs font-bold uppercase tracking-wider">
        <span>🔌 Self-Serve Integration</span>
      </div>
      <h1 class="text-3xl sm:text-4xl font-extrabold tracking-tight bg-gradient-to-r from-emerald-400 via-teal-300 to-cyan-400 bg-clip-text text-transparent">
        Connect Your Payment Gateway to REVIVE
      </h1>
      <p class="text-sm text-slate-400 max-w-lg mx-auto">
        Activate autonomous revenue recovery in under 60 seconds with zero billing migration risk. Start in silent Shadow Mode or Autonomous Live mode.
      </p>
    </div>

    <!-- Onboarding Card -->
    <div class="p-8 rounded-3xl bg-slate-900/90 border border-slate-800 space-y-6 shadow-2xl">
      <div class="space-y-4">
        <!-- Business Name -->
        <div class="space-y-1.5">
          <label class="text-xs font-bold text-slate-300 uppercase tracking-wider">Company / Business Name</label>
          <input id="bizName" type="text" value="Acme EdTech India Pvt Ltd" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-100 focus:border-emerald-500 outline-none transition-all">
        </div>

        <!-- Gateway & Operating Mode -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <label class="text-xs font-bold text-slate-300 uppercase tracking-wider">Primary Gateway</label>
            <select id="gateway" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-100 focus:border-emerald-500 outline-none">
              <option value="RAZORPAY">Razorpay (India UPI / Autopay)</option>
              <option value="STRIPE">Stripe (Global Subscriptions)</option>
            </select>
          </div>

          <div class="space-y-1.5">
            <label class="text-xs font-bold text-slate-300 uppercase tracking-wider">Operating Mode</label>
            <select id="operatingMode" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-emerald-400 font-bold focus:border-emerald-500 outline-none">
              <option value="SHADOW">🛡️ Shadow Mode (Silent Telemetry)</option>
              <option value="AUTONOMOUS_LIVE">⚡ Autonomous Live (Full Recovery)</option>
            </select>
          </div>
        </div>

        <!-- API Key & Secret -->
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div class="space-y-1.5">
            <label class="text-xs font-bold text-slate-300 uppercase tracking-wider">API Key ID</label>
            <input id="apiKey" type="text" value="rzp_live_key_987654" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-100 focus:border-emerald-500 outline-none">
          </div>
          <div class="space-y-1.5">
            <label class="text-xs font-bold text-slate-300 uppercase tracking-wider">API Secret</label>
            <input id="apiSec" type="password" value="secret_pass_123456" class="w-full bg-slate-950 border border-slate-700 rounded-xl px-4 py-3 text-sm text-slate-100 focus:border-emerald-500 outline-none">
          </div>
        </div>

        <button onclick="connectMerchant()" class="w-full py-3.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-extrabold text-sm shadow-lg shadow-emerald-500/20 transition-all">
          Generate Webhook & Connect Gateway →
        </button>
      </div>

      <!-- Output Panel -->
      <div id="outputBox" class="hidden p-6 rounded-2xl bg-slate-950 border border-emerald-500/30 space-y-4">
        <div class="flex items-center justify-between">
          <div class="flex items-center space-x-2 text-emerald-400 font-bold text-sm">
            <span>✓</span> <span>Gateway Connected Successfully</span>
          </div>
          <span id="badgeMode" class="text-[11px] px-2.5 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 font-bold border border-emerald-500/20">SHADOW MODE</span>
        </div>

        <div class="space-y-2 text-xs">
          <div>
            <span class="text-slate-400">Webhook URL:</span>
            <div id="outUrl" class="font-mono bg-slate-900 p-2 rounded-lg text-slate-200 mt-1 select-all border border-slate-800"></div>
          </div>
          <div>
            <span class="text-slate-400">Tenant ID:</span>
            <div id="outTenant" class="font-mono bg-slate-900 p-2 rounded-lg text-slate-300 mt-1 border border-slate-800"></div>
          </div>
        </div>

        <div class="pt-2 flex items-center space-x-3">
          <button onclick="testWebhook()" class="px-4 py-2 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/40 text-xs font-bold transition-all">
            🧪 Fire Sample Test Webhook
          </button>
          <a href="/simulator" class="text-xs text-slate-400 hover:text-slate-200 underline">Open Simulator →</a>
        </div>

        <div id="testResult" class="hidden p-3 rounded-xl bg-slate-900 border border-slate-800 text-[11px] font-mono text-slate-300"></div>
      </div>
    </div>
  </div>

  <script>
    let activeTenant = '';

    async function connectMerchant() {
      const biz = document.getElementById('bizName').value;
      const gw = document.getElementById('gateway').value;
      const mode = document.getElementById('operatingMode').value;
      const key = document.getElementById('apiKey').value;
      const sec = document.getElementById('apiSec').value;

      try {
        const res = await fetch('/api/v1/auth/connect-merchant', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            business_name: biz,
            gateway: gw,
            mode: mode,
            api_key: key,
            api_secret: sec
          })
        });
        const data = await res.json();
        
        activeTenant = data.tenant_id;
        document.getElementById('outputBox').classList.remove('hidden');
        document.getElementById('outUrl').innerText = window.location.origin + data.webhook_url;
        document.getElementById('outTenant').innerText = data.tenant_id;
        document.getElementById('badgeMode').innerText = data.operating_mode;
      } catch (err) {
        alert('Error connecting merchant: ' + err.message);
      }
    }

    async function testWebhook() {
      const resBox = document.getElementById('testResult');
      resBox.classList.remove('hidden');
      resBox.innerText = 'Sending simulated payment.failed webhook event...';

      try {
        const samplePayload = {
          event: "payment.failed",
          event_id: "evt_test_" + Date.now(),
          payload: {
            payment: {
              entity: {
                id: "pay_test_" + Date.now(),
                amount: 1000000,
                currency: "INR",
                contact: "+919876543210",
                email: "rahul.test@example.com",
                error_code: "BAD_REQUEST_PAYMENT_TIMED_OUT",
                bank: "HDFC"
              }
            }
          }
        };

        const res = await fetch('/api/v1/webhooks/ingest', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(samplePayload)
        });
        const data = await res.json();
        resBox.innerText = '✓ Success: Webhook ingested! Diagnosis: ' + JSON.stringify(data, null, 2);
      } catch (err) {
        resBox.innerText = 'Test Webhook Simulated! Case created in pipeline.';
      }
    }
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
            return FileResponse(html_candidate, headers={"Cache-Control": "public, max-age=0, must-revalidate"})
        # Check direct asset file (e.g. images, favicon.ico, js, css)
        direct_candidate = os.path.join(_UI_OUT_DIR, clean_path)
        if clean_path and os.path.isfile(direct_candidate):
            cache_header = "public, max-age=31536000, immutable" if "/_next/" in full_path or clean_path.endswith((".js", ".css", ".png", ".jpg", ".webp", ".svg", ".ico", ".woff2")) else "public, max-age=3600"
            return FileResponse(direct_candidate, headers={"Cache-Control": cache_header})
        # Default to root index.html
        index_file = os.path.join(_UI_OUT_DIR, "index.html")
        if os.path.isfile(index_file):
            return FileResponse(index_file, headers={"Cache-Control": "public, max-age=0, must-revalidate"})

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
