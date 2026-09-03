"use client";

import { useState } from "react";
import { Zap, Play, CheckCircle2, AlertTriangle, ShieldCheck, RefreshCw } from "lucide-react";
import { apiFetch } from "@/lib/api";

type Scenario = {
  id: string;
  name: string;
  bank: string;
  amount_rupees: number;
  failure_code?: string;
  event: string;
  tag: string;
  color: string;
  desc: string;
};

const SCENARIOS: Scenario[] = [
  {
    id: "3ds_dropout",
    name: "HDFC 3DS Dropout",
    bank: "HDFC",
    amount_rupees: 2499,
    failure_code: "BAD_REQUEST_PAYMENT_TIMED_OUT",
    event: "payment.failed",
    tag: "SMART_WAIT",
    color: "from-blue-600/20 to-cyan-600/20 border-cyan-500/40 text-cyan-300",
    desc: "Simulates customer OTP timeout. AI Reasoner schedules smart delay without spam.",
  },
  {
    id: "nsf_offer",
    name: "SBI Low Balance NSF",
    bank: "SBI",
    amount_rupees: 999,
    failure_code: "INSUFFICIENT_FUNDS",
    event: "payment.failed",
    tag: "DYNAMIC_OFFER",
    color: "from-purple-600/20 to-pink-600/20 border-purple-500/40 text-purple-300",
    desc: "Simulates insufficient balance. Triggers Dynamic Offer Engine with ₹50 micro-discount.",
  },
  {
    id: "vip_escalation",
    name: "ICICI VIP ₹75,000 High-Value",
    bank: "ICICI",
    amount_rupees: 75000,
    failure_code: "BAD_REQUEST_AUTHENTICATION_FAILED",
    event: "payment.failed",
    tag: "HUMAN_ESCALATION",
    color: "from-amber-600/20 to-orange-600/20 border-amber-500/40 text-amber-300",
    desc: "Exceeds ₹50k policy threshold. Policy Firewall vetoes auto-retry and escalates to Ops Queue.",
  },
  {
    id: "sentinel_cooloff",
    name: "Axis Gateway Outage Wave",
    bank: "AXIS",
    amount_rupees: 4500,
    failure_code: "GATEWAY_ERROR",
    event: "payment.failed",
    tag: "SENTINEL_COOLOFF",
    color: "from-red-600/20 to-rose-600/20 border-red-500/40 text-red-300",
    desc: "Simulates bank infrastructure degradation. Sentinel triggers Rule 7 circuit cool-off.",
  },
  {
    id: "organic_capture",
    name: "Organic Payment Captured",
    bank: "HDFC",
    amount_rupees: 1999,
    event: "payment.captured",
    tag: "AUTO_RESOLVE",
    color: "from-emerald-600/20 to-teal-600/20 border-emerald-500/40 text-emerald-300",
    desc: "Simulates successful capture. Auto-resolves state machine and self-heals Sentinel.",
  },
];

export function WebhookSimulator({ onInjected }: { onInjected?: () => void }) {
  const [loadingId, setLoadingId] = useState<string | null>(null);
  const [lastResult, setLastResult] = useState<string | null>(null);

  const injectScenario = async (s: Scenario) => {
    setLoadingId(s.id);
    setLastResult(null);
    try {
      const paymentId = `pay_live_sim_${Date.now().toString().slice(-6)}`;
      const payload = {
        event: s.event,
        payload: {
          payment: {
            entity: {
              id: paymentId,
              order_id: `order_${paymentId}`,
              amount: s.amount_rupees * 100,
              currency: "INR",
              status: s.event === "payment.captured" ? "captured" : "failed",
              error_code: s.failure_code,
              error_description: s.desc,
              method: "upi",
              bank: s.bank,
              created_at: Math.floor(Date.now() / 1000),
            },
          },
        },
      };

      await apiFetch("/webhooks/razorpay", {
        method: "POST",
        body: JSON.stringify(payload),
      });

      setLastResult(`Injected ${s.name} (${paymentId}) successfully!`);
      if (onInjected) onInjected();
    } catch (err: any) {
      setLastResult(`Injection error: ${err?.message || "Failed"}`);
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-5 sm:p-6 space-y-4 glow-border border-blue-500/30">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-slate-800/80 pb-3.5">
        <div className="flex items-center gap-2">
          <div className="p-1.5 rounded-lg bg-blue-600/20 text-blue-400 border border-blue-500/30">
            <Zap className="h-4 w-4" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-slate-100 tracking-tight">1-Click Live Webhook Event Simulator</h3>
            <p className="text-xs text-slate-400">Inject real Razorpay webhook scenarios to observe instant AI pipeline reactions</p>
          </div>
        </div>
        {lastResult && (
          <span className="text-[11px] font-mono px-3 py-1 rounded-full bg-slate-900 border border-slate-800 text-blue-300 flex items-center gap-1.5 fade-in">
            <CheckCircle2 className="h-3 w-3 text-emerald-400" /> {lastResult}
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {SCENARIOS.map((s) => (
          <div
            key={s.id}
            className="bg-slate-950/70 border border-slate-800/80 rounded-xl p-3.5 flex flex-col justify-between space-y-2.5 hover:border-slate-700/90 transition-all hover:bg-slate-900/40 group"
          >
            <div className="space-y-1.5">
              <div className="flex items-center justify-between">
                <span className={`text-[10px] font-mono font-bold px-2 py-0.5 rounded-md border ${s.color}`}>
                  {s.tag}
                </span>
                <span className="text-xs font-bold text-slate-200 font-sans">₹{s.amount_rupees.toLocaleString()}</span>
              </div>
              <h4 className="text-xs font-bold text-slate-100 group-hover:text-blue-300 transition-colors">{s.name}</h4>
              <p className="text-[11px] text-slate-400 leading-relaxed line-clamp-2">{s.desc}</p>
            </div>

            <button
              onClick={() => injectScenario(s)}
              disabled={loadingId === s.id}
              className="w-full mt-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium py-1.5 px-3 rounded-lg text-xs flex items-center justify-center gap-1.5 transition-all shadow-md active:scale-95 disabled:opacity-50"
            >
              {loadingId === s.id ? (
                <RefreshCw className="h-3 w-3 animate-spin" />
              ) : (
                <Play className="h-3 w-3 fill-current" />
              )}
              {loadingId === s.id ? "Injecting..." : "Simulate Webhook"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
