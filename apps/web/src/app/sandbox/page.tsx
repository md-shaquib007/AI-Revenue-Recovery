"use client";

import { useState, useEffect } from "react";
import { 
  Sliders, 
  Sparkles, 
  Zap, 
  ShieldCheck, 
  ShieldAlert, 
  CheckCircle2, 
  Smartphone, 
  TrendingUp, 
  RefreshCw, 
  ArrowRight,
  Send,
  QrCode
} from "lucide-react";
import { DashboardShell } from "@/components/DashboardShell";
import { apiFetch } from "@/lib/api";

type SimulationResult = {
  input: {
    amount_in_rupees: number;
    failure_code: string;
    bank_name: string;
    bank_health_score: number;
    customer_churn_risk: number;
    customer_tier: string;
    offer_discount_pct: number;
    proposed_action: string;
  };
  shadow_simulation: {
    total_simulated_personas: number;
    consensus_index_pct: number;
    friction_score_pct: number;
    personas_sample: Array<{ persona_id: string; trait: string; preferred_action: string; friction_pct: number }>;
  };
  bank_sentinel: {
    entity_key: string;
    status: string;
    circuit_triggered: boolean;
    predictive_outage_risk_pct: number;
    failure_velocity_per_min: number;
  };
  offer_evaluation: {
    offer_recommended: boolean;
    discount_amount_rupees: number;
    net_ev_lift_rupees: number;
    copy_headline?: string;
  };
  policy_firewall: {
    approved_action: string;
    requires_human_approval: boolean;
    override_reason?: string;
    checks: Array<{ rule_name: string; passed: boolean; reason: string }>;
  };
  ev_curve: {
    ev_standard_rupees: number;
    ev_offer_rupees: number;
    ev_retry_rupees: number;
    optimal_strategy: string;
  };
  whatsapp_preview: {
    interactive: {
      body: { text: string };
      action: { buttons: Array<{ reply: { title: string } }> };
    };
    metadata: { upi_deep_link: string; short_url: string };
  };
  copy_rag_matched: {
    copy_headline: string;
    similarity_score: number;
  };
};

function UpiQrPattern({ amount }: { amount: number }) {
  return (
    <div className="flex items-center gap-3 bg-white p-2.5 rounded-xl text-slate-950 shadow-md">
      <div className="w-12 h-12 bg-slate-950 rounded-lg flex items-center justify-center p-1 flex-shrink-0">
        <svg viewBox="0 0 24 24" className="w-full h-full text-white fill-current">
          <path d="M2 2h7v7H2V2zm2 2v3h3V4H4zm11-2h7v7h-7V2zm2 2v3h3V4h-3zM2 15h7v7H2v-7zm2 2v3h3v-3H4zm7-13h2v2h-2V4zm2 2h2v2h-2V6zm-2 4h2v2h-2v-2zm4-4h2v2h-2V6zm2 2h2v2h-2V8zm-2 4h2v2h-2v-2zm-6 3h2v2h-2v-2zm2 2h2v2h-2v-2zm2-2h2v2h-2v-2zm2 2h2v4h-2v-4zm2-2h2v2h-2v-2zm-2 4h2v2h-2v-2zm4-4h2v2h-2v-2zm0 4h2v2h-2v-2z" />
        </svg>
      </div>
      <div className="text-left leading-tight">
        <div className="text-[10px] font-bold tracking-tight text-slate-800 uppercase font-mono">Scan with Any UPI App</div>
        <div className="text-xs font-extrabold text-emerald-700">₹{amount.toLocaleString()}</div>
        <div className="text-[9px] text-slate-500 font-sans">GPay · PhonePe · Paytm · BHIM</div>
      </div>
    </div>
  );
}

export default function SandboxPage() {
  const [amount, setAmount] = useState(2499);
  const [failureCode, setFailureCode] = useState("BAD_REQUEST_PAYMENT_TIMED_OUT");
  const [bank, setBank] = useState("HDFC");
  const [healthScore, setHealthScore] = useState(0.95);
  const [churnRisk, setChurnRisk] = useState(0.35);
  const [tier, setTier] = useState("STANDARD");
  const [discountPct, setDiscountPct] = useState(5.0);
  const [proposedAction, setProposedAction] = useState("PAYMENT_LINK");

  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<SimulationResult | null>(null);

  const runSimulation = async () => {
    setLoading(true);
    try {
      const res = await apiFetch<SimulationResult>("/intel/sandbox-simulate", {
        method: "POST",
        body: JSON.stringify({
          amount_in_rupees: amount,
          failure_code: failureCode,
          bank_name: bank,
          bank_health_score: healthScore,
          customer_churn_risk: churnRisk,
          customer_tier: tier,
          offer_discount_pct: discountPct,
          proposed_action: proposedAction,
        }),
      });
      setResult(res);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    runSimulation();
  }, [amount, failureCode, bank, healthScore, churnRisk, tier, discountPct, proposedAction]);

  return (
    <DashboardShell>
      <div className="space-y-6">
        {/* Page Title Banner */}
        <div className="glass-panel rounded-2xl p-6 sm:p-8 bg-gradient-to-r from-blue-950/40 via-slate-900/80 to-purple-950/40 border border-blue-500/30 shadow-xl">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div>
              <div className="flex items-center gap-2 text-xs font-mono text-cyan-400 font-bold uppercase tracking-wider">
                <Sparkles className="h-4 w-4" /> AI What-If Simulation Studio
              </div>
              <h1 className="text-2xl sm:text-3xl font-extrabold text-slate-100 mt-1.5 font-sans tracking-tight">
                Interactive Revenue Recovery Sandbox
              </h1>
              <p className="text-xs sm:text-sm text-slate-300 mt-1 max-w-2xl leading-relaxed">
                Tweak live customer, banking, and payment variables to preview 50-persona Shadow Simulation friction, dynamic EV curves, and Policy Firewall decisions in real time.
              </p>
            </div>

            <button
              onClick={runSimulation}
              disabled={loading}
              className="bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium px-4 py-2 rounded-xl text-xs flex items-center justify-center gap-2 shadow-lg transition-all active:scale-95 flex-shrink-0"
            >
              <RefreshCw className={`h-3.5 w-3.5 ${loading ? "animate-spin" : ""}`} />
              {loading ? "Recomputing..." : "Recalculate AI Engine"}
            </button>
          </div>
        </div>

        {/* Main Grid: Left Controls, Right Output */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
          {/* Controls Column (5 cols) */}
          <div className="lg:col-span-5 space-y-5">
            <div className="glass-panel rounded-2xl p-5 sm:p-6 space-y-5 border-slate-800">
              <div className="flex items-center gap-2 text-xs font-bold text-slate-200 uppercase font-mono border-b border-slate-800 pb-3">
                <Sliders className="h-4 w-4 text-blue-400" /> Simulation Parameters
              </div>

              {/* Amount Slider */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-400">Invoice Amount</span>
                  <span className="font-bold text-slate-100 text-sm">₹{amount.toLocaleString()}</span>
                </div>
                <input
                  type="range"
                  min={500}
                  max={100000}
                  step={500}
                  value={amount}
                  onChange={(e) => setAmount(Number(e.target.value))}
                  className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-blue-500"
                />
                <div className="flex justify-between text-[10px] text-slate-500 font-mono">
                  <span>₹500 (Standard)</span>
                  <span>₹50k (High-Value Gate)</span>
                  <span>₹100k (Max)</span>
                </div>
              </div>

              {/* Bank Health Slider */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-400">Bank Gateway Telemetry</span>
                  <span className={`font-bold text-sm ${healthScore >= 0.7 ? "text-emerald-400" : "text-amber-400"}`}>
                    {Math.round(healthScore * 100)}% ({healthScore >= 0.7 ? "Healthy" : "Degraded"})
                  </span>
                </div>
                <input
                  type="range"
                  min={0.1}
                  max={1.0}
                  step={0.05}
                  value={healthScore}
                  onChange={(e) => setHealthScore(Number(e.target.value))}
                  className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-emerald-500"
                />
              </div>

              {/* Customer Churn Risk Slider */}
              <div className="space-y-2">
                <div className="flex justify-between text-xs font-mono">
                  <span className="text-slate-400">Customer Churn Risk</span>
                  <span className={`font-bold text-sm ${churnRisk >= 0.5 ? "text-rose-400" : "text-cyan-400"}`}>
                    {Math.round(churnRisk * 100)}% ({churnRisk >= 0.5 ? "High Risk" : "Stable"})
                  </span>
                </div>
                <input
                  type="range"
                  min={0.05}
                  max={0.95}
                  step={0.05}
                  value={churnRisk}
                  onChange={(e) => setChurnRisk(Number(e.target.value))}
                  className="w-full h-2 bg-slate-800 rounded-lg appearance-none cursor-pointer accent-cyan-500"
                />
              </div>

              {/* Selectors Grid */}
              <div className="grid grid-cols-2 gap-3 pt-2">
                <div className="space-y-1">
                  <label className="text-[10px] font-mono uppercase text-slate-400">Target Bank</label>
                  <select
                    value={bank}
                    onChange={(e) => setBank(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                  >
                    <option value="HDFC">HDFC Bank</option>
                    <option value="SBI">State Bank of India</option>
                    <option value="ICICI">ICICI Bank</option>
                    <option value="AXIS">Axis Bank</option>
                    <option value="RAZORPAY_UPI">Razorpay UPI</option>
                  </select>
                </div>

                <div className="space-y-1">
                  <label className="text-[10px] font-mono uppercase text-slate-400">Customer Tier</label>
                  <select
                    value={tier}
                    onChange={(e) => setTier(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500"
                  >
                    <option value="STANDARD">Standard</option>
                    <option value="VIP">VIP Customer</option>
                    <option value="ENTERPRISE">Enterprise</option>
                  </select>
                </div>

                <div className="col-span-2 space-y-1">
                  <label className="text-[10px] font-mono uppercase text-slate-400">Failure Reason</label>
                  <select
                    value={failureCode}
                    onChange={(e) => setFailureCode(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500 font-mono"
                  >
                    <option value="BAD_REQUEST_PAYMENT_TIMED_OUT">BAD_REQUEST_PAYMENT_TIMED_OUT (3DS Timeout)</option>
                    <option value="INSUFFICIENT_FUNDS">INSUFFICIENT_FUNDS (NSF Low Balance)</option>
                    <option value="CARD_EXPIRED">CARD_EXPIRED (Card Validity Expired)</option>
                    <option value="GATEWAY_ERROR">GATEWAY_ERROR (Infrastructure Down)</option>
                    <option value="BAD_REQUEST_AUTHENTICATION_FAILED">BAD_REQUEST_AUTHENTICATION_FAILED (Auth Failed)</option>
                  </select>
                </div>

                <div className="col-span-2 space-y-1">
                  <label className="text-[10px] font-mono uppercase text-slate-400">Candidate Action Route</label>
                  <select
                    value={proposedAction}
                    onChange={(e) => setProposedAction(e.target.value)}
                    className="w-full bg-slate-900 border border-slate-800 rounded-xl px-3 py-2 text-xs text-slate-200 focus:outline-none focus:border-blue-500 font-mono font-bold text-blue-400"
                  >
                    <option value="PAYMENT_LINK">PAYMENT_LINK (1-Click Recovery Link)</option>
                    <option value="SMART_RETRY">SMART_RETRY (Automated Background Pull)</option>
                    <option value="WAIT">WAIT (Circadian Delay / Bank Cool-off)</option>
                    <option value="METHOD_SWITCH">METHOD_SWITCH (Card to UPI Switch)</option>
                  </select>
                </div>
              </div>
            </div>
          </div>

          {/* Results Column (7 cols) */}
          <div className="lg:col-span-7 space-y-5">
            {/* EV Strategy Comparison Cards */}
            {result && (
              <div className="grid grid-cols-3 gap-3">
                <div className="glass-panel rounded-xl p-3.5 border-slate-800 bg-slate-950/80 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase">Standard EV</div>
                  <div className="text-base sm:text-lg font-bold text-slate-200">
                    ₹{result.ev_curve.ev_standard_rupees.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-slate-500">Base recovery</div>
                </div>

                <div className="glass-panel rounded-xl p-3.5 border-purple-500/40 bg-purple-950/20 space-y-1 shadow-inner">
                  <div className="text-[10px] font-mono text-purple-300 uppercase flex items-center gap-1">
                    <Zap className="h-3 w-3" /> Offer Net EV
                  </div>
                  <div className="text-base sm:text-lg font-bold text-purple-200">
                    ₹{result.ev_curve.ev_offer_rupees.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-purple-400">
                    +{Math.round(((result.ev_curve.ev_offer_rupees - result.ev_curve.ev_standard_rupees) / Math.max(1, result.ev_curve.ev_standard_rupees)) * 100)}% Lift
                  </div>
                </div>

                <div className="glass-panel rounded-xl p-3.5 border-slate-800 bg-slate-950/80 space-y-1">
                  <div className="text-[10px] font-mono text-slate-400 uppercase">Smart Retry EV</div>
                  <div className="text-base sm:text-lg font-bold text-slate-200">
                    ₹{result.ev_curve.ev_retry_rupees.toLocaleString()}
                  </div>
                  <div className="text-[10px] text-slate-500">Gateway direct</div>
                </div>
              </div>
            )}

            {/* 50-Persona Shadow Simulator Matrix Card */}
            {result && (
              <div className="glass-panel rounded-2xl p-5 sm:p-6 space-y-4 border-cyan-500/30 bg-gradient-to-r from-cyan-950/20 to-blue-950/20">
                <div className="flex items-center justify-between border-b border-cyan-500/20 pb-3">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-mono font-bold text-cyan-300 uppercase tracking-wider">
                      50-Persona Shadow Simulator
                    </span>
                    <span className="text-[10px] font-mono px-2 py-0.5 rounded-full bg-cyan-950/80 border border-cyan-500/40 text-cyan-200">
                      Consensus: {result.shadow_simulation.consensus_index_pct}%
                    </span>
                  </div>
                  <span
                    className={`text-xs font-mono font-bold px-2.5 py-0.5 rounded-full border ${
                      result.shadow_simulation.friction_score_pct > 45
                        ? "bg-rose-950/80 border-rose-500/50 text-rose-300"
                        : "bg-emerald-950/80 border-emerald-500/50 text-emerald-300"
                    }`}
                  >
                    Friction: {result.shadow_simulation.friction_score_pct}%
                  </span>
                </div>

                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                  {result.shadow_simulation.personas_sample.map((p, idx) => (
                    <div key={idx} className="bg-slate-950/80 border border-slate-800 rounded-lg p-2.5 space-y-1 text-xs">
                      <div className="text-[10px] font-mono text-cyan-400 font-bold truncate">{p.trait}</div>
                      <div className="text-[11px] font-mono text-slate-300">Pref: {p.preferred_action}</div>
                      <div className="text-[10px] font-mono text-slate-500">Friction: {p.friction_pct}%</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Policy Firewall & Sentinel Grid */}
            {result && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {/* Policy Firewall Card */}
                <div className="glass-panel rounded-2xl p-4 space-y-3 bg-slate-950/70 border-slate-800">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                      <ShieldCheck className="h-4 w-4 text-blue-400" /> Policy Firewall
                    </span>
                    <span
                      className={`text-[10px] font-mono px-2 py-0.5 rounded-full border ${
                        result.policy_firewall.approved_action === proposedAction
                          ? "bg-emerald-950/80 border-emerald-500/40 text-emerald-300"
                          : "bg-amber-950/80 border-amber-500/40 text-amber-300"
                      }`}
                    >
                      Approved: {result.policy_firewall.approved_action}
                    </span>
                  </div>

                  <div className="space-y-1.5 max-h-36 overflow-y-auto pr-1">
                    {result.policy_firewall.checks.map((c, i) => (
                      <div key={i} className="flex items-center justify-between text-[11px] font-mono py-1 border-b border-slate-900">
                        <span className="text-slate-300 truncate">{c.rule_name}</span>
                        <span className={c.passed ? "text-emerald-400 font-bold" : "text-rose-400 font-bold"}>
                          {c.passed ? "PASSED" : "VETOED"}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>

                {/* WhatsApp UPI 1-Click Interactive Preview */}
                <div className="glass-panel rounded-2xl p-4 space-y-3 bg-slate-950/70 border-slate-800 flex flex-col justify-between">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-slate-200 flex items-center gap-1.5">
                      <Smartphone className="h-4 w-4 text-emerald-400" /> WhatsApp 1-Click Preview
                    </span>
                    <span className="text-[10px] font-mono text-emerald-400 bg-emerald-950/60 px-2 py-0.5 rounded-full border border-emerald-800">
                      NPCI UPI Deep Link
                    </span>
                  </div>

                  {/* Chat bubble simulation */}
                  <div className="bg-emerald-950/20 border border-emerald-700/30 rounded-xl p-3 space-y-2.5 text-xs text-slate-200">
                    <p className="text-[11px] leading-relaxed text-slate-300 whitespace-pre-line">
                      {result.whatsapp_preview.interactive.body.text}
                    </p>

                    <UpiQrPattern amount={amount} />

                    <div className="flex gap-1.5 pt-1">
                      {result.whatsapp_preview.interactive.action.buttons.map((btn, i) => (
                        <div
                          key={i}
                          className="flex-1 bg-emerald-600/30 border border-emerald-500/40 text-emerald-300 font-semibold py-1 px-2 rounded-lg text-center text-[10px]"
                        >
                          ⚡ {btn.reply.title}
                        </div>
                      ))}
                    </div>
                  </div>

                  <div className="text-[10px] font-mono text-slate-500 truncate">
                    UPI URI: {result.whatsapp_preview.metadata.upi_deep_link}
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </DashboardShell>
  );
}
