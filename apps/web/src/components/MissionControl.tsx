"use client";

import { useState } from "react";
import { Activity, Radio, Clock, Award } from "lucide-react";
import type { Pulse, RecoveryCase } from "@/lib/types";
import { BankMatrix } from "@/components/BankMatrix";
import { CopilotBar } from "@/components/CopilotBar";
import { KpiCards } from "@/components/KpiCards";
import { TraceModal } from "@/components/TraceModal";
import { WebhookSimulator } from "@/components/WebhookSimulator";
import { apiFetch } from "@/lib/api";
import type { CaseDetail, Metrics } from "@/lib/types";

const STATE_COLOR: Record<string, string> = {
  TRIAGING: "#64748b",
  IN_GRACE_WINDOW: "#38bdf8",
  SCHEDULED_RETRY: "#818cf8",
  LINK_SENT: "#34d399",
  ESCALATED_HUMAN: "#fbbf24",
  RECOVERED: "#22c55e",
  EXPIRED: "#64748b",
  CANCELLED: "#94a3b8",
};

function hashPos(id: string, i: number) {
  let h = 0;
  for (let c = 0; c < id.length; c++) h = (h * 31 + id.charCodeAt(c)) >>> 0;
  const x = 8 + ((h + i * 17) % 84);
  const y = 10 + (((h >> 8) + i * 13) % 72);
  return { x, y };
}

function formatCountdown(seconds: number) {
  if (seconds <= 0) return "live";
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m}m to 10:00 IST`;
  return `${m}m to 10:00 IST`;
}

export function MissionControl({
  metrics,
  banks,
  pulse,
  cases,
}: {
  metrics: Metrics;
  banks: Parameters<typeof BankMatrix>[0]["banks"];
  pulse: Pulse;
  cases: RecoveryCase[];
}) {
  const [selected, setSelected] = useState<CaseDetail | null>(null);
  const maxFunnel = Math.max(...pulse.funnel.map((f) => f.amount_rupees), 1);
  const peak = Math.max(...pulse.circadian_curve.map((c) => c.conversion_index), 1);
  const constellation = (pulse.at_risk.length ? pulse.at_risk : cases).slice(0, 24);

  const open = async (id: string) => {
    const detail = await apiFetch<CaseDetail>(`/recovery/cases/${id}`);
    setSelected(detail);
  };

  return (
    <div className="space-y-6">
      <KpiCards metrics={metrics} />

      <WebhookSimulator onInjected={() => {}} />

      {/* Vertical Feature Directory & Quick Access */}
      <div className="glass-panel rounded-2xl p-6 bg-slate-900/90 border border-slate-800 shadow-2xl space-y-4">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <span className="text-xl">🚀</span>
            <div>
              <h3 className="text-base font-extrabold text-white tracking-tight">REVIVE Feature Directory & Quick Launch</h3>
              <p className="text-xs text-slate-400">All 8 core recovery studios and compliance tools accessible in 1 click</p>
            </div>
          </div>
          <span className="text-[11px] font-mono bg-emerald-500/10 text-emerald-400 border border-emerald-500/30 px-3 py-1 rounded-full font-bold">100% Active</span>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <a href="/connect" className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-emerald-500/50 hover:bg-slate-900 transition-all space-y-2 group block">
            <div className="flex items-center justify-between">
              <span className="text-2xl">🔌</span>
              <span className="text-[10px] font-mono bg-emerald-500/20 text-emerald-300 px-2 py-0.5 rounded font-bold">60s Setup</span>
            </div>
            <h4 className="font-bold text-sm text-white group-hover:text-emerald-400 transition-colors">1-Click Merchant Connect</h4>
            <p className="text-xs text-slate-400">Razorpay/Stripe keys + Shadow Mode silent telemetry</p>
          </a>

          <a href="/simulator" className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-cyan-500/50 hover:bg-slate-900 transition-all space-y-2 group block">
            <div className="flex items-center justify-between">
              <span className="text-2xl">⚡</span>
              <span className="text-[10px] font-mono bg-cyan-500/20 text-cyan-300 px-2 py-0.5 rounded font-bold">44.9x ROI</span>
            </div>
            <h4 className="font-bold text-sm text-white group-hover:text-cyan-400 transition-colors">CFO Recovery Simulator</h4>
            <p className="text-xs text-slate-400">Quantify counterfactual ARR lift & net rupee return</p>
          </a>

          <a href="/pay/demo-case" className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-purple-500/50 hover:bg-slate-900 transition-all space-y-2 group block">
            <div className="flex items-center justify-between">
              <span className="text-2xl">🛍️</span>
              <span className="text-[10px] font-mono bg-purple-500/20 text-purple-300 px-2 py-0.5 rounded font-bold">4 Choices</span>
            </div>
            <h4 className="font-bold text-sm text-white group-hover:text-purple-400 transition-colors">Customer Self-Service Portal</h4>
            <p className="text-xs text-slate-400">33% Partial Split, 14-Day Pause & Plan Downsell</p>
          </a>

          <a href="/sandbox" className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-blue-500/50 hover:bg-slate-900 transition-all space-y-2 group block">
            <div className="flex items-center justify-between">
              <span className="text-2xl">🧠</span>
              <span className="text-[10px] font-mono bg-blue-500/20 text-blue-300 px-2 py-0.5 rounded font-bold">EV Scorer</span>
            </div>
            <h4 className="font-bold text-sm text-white group-hover:text-blue-400 transition-colors">State Graph & Scorer</h4>
            <p className="text-xs text-slate-400">Behavioral state machine & Expected Value engine</p>
          </a>

          <a href="/intel" className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-amber-500/50 hover:bg-slate-900 transition-all space-y-2 group block">
            <div className="flex items-center justify-between">
              <span className="text-2xl">📡</span>
              <span className="text-[10px] font-mono bg-amber-500/20 text-amber-300 px-2 py-0.5 rounded font-bold">Sentinel</span>
            </div>
            <h4 className="font-bold text-sm text-white group-hover:text-amber-400 transition-colors">Bank Outage Radar</h4>
            <p className="text-xs text-slate-400">Real-time HDFC/SBI core banking health radar</p>
          </a>

          <a href="/docs" target="_blank" className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-teal-500/50 hover:bg-slate-900 transition-all space-y-2 group block">
            <div className="flex items-center justify-between">
              <span className="text-2xl">📖</span>
              <span className="text-[10px] font-mono bg-teal-500/20 text-teal-300 px-2 py-0.5 rounded font-bold">OpenAPI</span>
            </div>
            <h4 className="font-bold text-sm text-white group-hover:text-teal-400 transition-colors">Swagger API Documentation</h4>
            <p className="text-xs text-slate-400">Interactive REST API contracts & schemas</p>
          </a>

          <a href="/metrics" target="_blank" className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-rose-500/50 hover:bg-slate-900 transition-all space-y-2 group block">
            <div className="flex items-center justify-between">
              <span className="text-2xl">📊</span>
              <span className="text-[10px] font-mono bg-rose-500/20 text-rose-300 px-2 py-0.5 rounded font-bold">Grafana</span>
            </div>
            <h4 className="font-bold text-sm text-white group-hover:text-rose-400 transition-colors">Prometheus /metrics</h4>
            <p className="text-xs text-slate-400">OpenTelemetry standard exposition format</p>
          </a>

          <a href="https://github.com/md-shaquib007/AI-Revenue-Recovery" target="_blank" className="p-4 rounded-xl bg-slate-950/80 border border-slate-800 hover:border-indigo-500/50 hover:bg-slate-900 transition-all space-y-2 group block">
            <div className="flex items-center justify-between">
              <span className="text-2xl">📦</span>
              <span className="text-[10px] font-mono bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded font-bold">101 Tests</span>
            </div>
            <h4 className="font-bold text-sm text-white group-hover:text-indigo-400 transition-colors">GitHub Source Code</h4>
            <p className="text-xs text-slate-400">Complete codebase, tests & documentation</p>
          </a>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
        <div className="lg:col-span-2 glass-panel rounded-2xl p-5 sm:p-6 relative overflow-hidden flex flex-col justify-between">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-4">
            <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2 tracking-tight">
              <Radio className="h-4 w-4 text-cyan-400 pulse-dot" />
              Recovery Constellation Network
            </h3>
            <div className="text-xs font-mono text-slate-400 bg-slate-950/80 px-3 py-1 rounded-lg border border-slate-800/80">
              {pulse.active_cases} live · ₹{Number(pulse.active_rupees || 0).toLocaleString()} at risk
            </div>
          </div>

          <div className="relative h-56 sm:h-64 bg-slate-950/80 rounded-xl border border-slate-800/80 constellation-grid">
            {constellation.length === 0 ? (
              <div className="absolute inset-0 flex items-center justify-center text-xs text-slate-500 font-sans">
                No active recovery cases. Inject a webhook or chaos scenario to populate.
              </div>
            ) : (
              constellation.map((c, i) => {
                const { x, y } = hashPos(c.id, i);
                const size = Math.min(24, 8 + Math.log10(Math.max(c.amount_in_rupees, 1)) * 4);
                return (
                  <button
                    key={c.id}
                    type="button"
                    title={`${c.payment_id} · ${c.state} · ₹${c.amount_in_rupees.toLocaleString()}`}
                    onClick={() => open(c.id)}
                    className="absolute rounded-full star-node shadow-lg"
                    style={{
                      left: `${x}%`,
                      top: `${y}%`,
                      width: size,
                      height: size,
                      background: STATE_COLOR[c.state] || "#64748b",
                      opacity: 0.9,
                    }}
                  />
                );
              })
            )}
          </div>

          <div className="flex flex-wrap gap-3 mt-4 text-[11px] font-mono text-slate-400 pt-2 border-t border-slate-800/60">
            {Object.entries(STATE_COLOR)
              .slice(0, 5)
              .map(([state, color]) => (
                <span key={state} className="flex items-center gap-1.5 bg-slate-950/60 px-2.5 py-1 rounded-md border border-slate-800/80">
                  <span className="h-2 w-2 rounded-full flex-shrink-0" style={{ background: color }} />
                  {state}
                </span>
              ))}
          </div>
        </div>

        <div className="glass-panel rounded-2xl p-5 sm:p-6 space-y-4 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs font-mono text-slate-400">
              <span className="uppercase tracking-wider font-semibold">India Send Window Clock</span>
              <Clock className="h-3.5 w-3.5 text-cyan-400" />
            </div>
            <div className="text-xl font-bold text-slate-100 mt-1 font-sans">{pulse.ist_now || "—"}</div>
            <div className={`text-xs font-mono mt-1.5 px-2.5 py-1 rounded-lg border ${
              pulse.quiet_hours
                ? "bg-amber-950/40 border-amber-900/50 text-amber-300"
                : "bg-emerald-950/40 border-emerald-900/50 text-emerald-300"
            }`}>
              {pulse.quiet_hours
                ? `Quiet hours · ${formatCountdown(pulse.seconds_until_send_window)}`
                : `Send window open · conversion ${Math.round((pulse.circadian_multiplier || 0) * 100)}% of peak`}
            </div>
          </div>

          <div className="space-y-1.5 pt-2">
            <div className="flex items-end gap-1 h-16 bg-slate-950/80 p-2 rounded-xl border border-slate-800/80">
              {pulse.circadian_curve.map((pt) => {
                const active = pt.hour === pulse.ist_hour;
                return (
                  <div
                    key={pt.hour}
                    title={`${pt.label} IST · ${Math.round(pt.conversion_index * 100)}%`}
                    className={`flex-1 rounded-t transition-all ${active ? "bg-cyan-400 shadow-lg shadow-cyan-400/50" : "bg-slate-800 hover:bg-slate-700"}`}
                    style={{ height: `${Math.max(10, (pt.conversion_index / peak) * 100)}%` }}
                  />
                );
              })}
            </div>
            <div className="text-[10px] text-slate-500 font-mono text-center">00 — IST Hour — 23 · Peak 20:00–21:00 IST</div>
          </div>

          <div className="grid grid-cols-2 gap-2 text-xs pt-1 font-sans">
            <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3">
              <div className="text-slate-400 text-[11px] font-medium">Oracle EV Predicted</div>
              <div className="font-extrabold text-emerald-400 text-base mt-0.5">
                ₹{Number(pulse.predicted_recover_rupees || 0).toLocaleString()}
              </div>
            </div>
            <div className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-3">
              <div className="text-slate-400 text-[11px] font-medium">Recovered Total</div>
              <div className="font-extrabold text-slate-100 text-base mt-0.5">
                ₹{Number(pulse.recovered_rupees || 0).toLocaleString()}
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
        <div className="glass-panel rounded-2xl p-5 sm:p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-100 tracking-tight">Recovery State Funnel</h3>
          {pulse.funnel.length === 0 ? (
            <p className="text-xs text-slate-500 py-6 text-center font-sans">Pipeline is empty.</p>
          ) : (
            <div className="space-y-3">
              {pulse.funnel.map((row) => (
                <div key={row.state} className="space-y-1.5">
                  <div className="flex justify-between text-xs font-mono">
                    <span className="text-slate-300 font-medium">{row.state}</span>
                    <span className="text-slate-200">
                      {row.count} cases · <span className="font-bold text-slate-100">₹{Number(row.amount_rupees).toLocaleString()}</span>
                    </span>
                  </div>
                  <div className="h-2.5 bg-slate-950 rounded-full overflow-hidden p-0.5 border border-slate-800">
                    <div
                      className="h-full bg-gradient-to-r from-blue-600 to-indigo-500 rounded-full transition-all duration-500"
                      style={{ width: `${Math.max(5, (row.amount_rupees / maxFunnel) * 100)}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="glass-panel rounded-2xl p-5 sm:p-6 space-y-4">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2 tracking-tight">
            <Activity className="h-4 w-4 text-blue-400" />
            Live Event Stream
          </h3>
          <div className="space-y-2 max-h-64 overflow-y-auto pr-1 scrollbar-none">
            {(pulse.live_feed || []).length === 0 ? (
              <p className="text-xs text-slate-500 py-6 text-center font-sans">Awaiting inbound webhooks & worker ticks...</p>
            ) : (
              pulse.live_feed.map((ev, idx) => (
                <div key={`${ev.ts}-${idx}`} className="text-xs font-mono border-l-2 border-blue-500/60 pl-3 py-1.5 bg-slate-950/40 rounded-r-lg">
                  <div className="flex justify-between items-center">
                    <span className="text-blue-400 font-bold">{ev.type || "event"}</span>
                    {ev.ts && <span className="text-[10px] text-slate-500">{ev.ts}</span>}
                  </div>
                  <div className="text-slate-300 text-[11px] mt-0.5">
                    {ev.state && <span className="text-indigo-300">State: {ev.state}</span>}
                    {ev.action && <span className="text-emerald-400 ml-2">Action: {ev.action}</span>}
                    {ev.case_id && <span className="text-slate-500 ml-2">[{ev.case_id.substring(0, 8)}]</span>}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {pulse.at_risk.length > 0 && (
        <div className="glass-panel rounded-2xl overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-800/80 text-sm font-bold text-slate-100 flex items-center justify-between">
            <span>Highest Heat At-Risk Invoices</span>
            <span className="text-xs font-mono font-normal text-slate-400">Click row to inspect trace</span>
          </div>
          <div className="overflow-x-auto scrollbar-none">
            <table className="w-full text-left text-xs min-w-[650px]">
              <thead className="bg-slate-950/90 text-slate-400 uppercase font-mono text-[10px] border-b border-slate-800">
                <tr>
                  <th className="py-3 px-4">Payment</th>
                  <th className="py-3 px-4">Customer</th>
                  <th className="py-3 px-4">Amount</th>
                  <th className="py-3 px-4">P(recovery)</th>
                  <th className="py-3 px-4">Oracle Recommended</th>
                  <th className="py-3 px-4">Churn Risk</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {pulse.at_risk.slice(0, 6).map((c) => (
                  <tr key={c.id} className="hover:bg-slate-900/60 cursor-pointer transition-colors" onClick={() => open(c.id)}>
                    <td className="py-3 px-4 font-semibold text-blue-400">{c.payment_id}</td>
                    <td className="py-3 px-4 text-slate-300 font-sans font-medium">{c.customer?.name}</td>
                    <td className="py-3 px-4 font-bold text-slate-100">₹{Number(c.amount_in_rupees).toLocaleString()}</td>
                    <td className="py-3 px-4 text-emerald-400 font-bold">{c.p_recover != null ? `${Math.round(c.p_recover * 100)}%` : "—"}</td>
                    <td className="py-3 px-4 text-indigo-300">{c.recommended_action || "—"}</td>
                    <td className="py-3 px-4 text-amber-400">{c.churn_risk != null ? `${Math.round(c.churn_risk * 100)}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <CopilotBar onOpenCase={open} />

      <div className="glass-panel rounded-2xl p-6 sm:p-8 bg-gradient-to-r from-blue-950/40 via-slate-900/80 to-indigo-950/40 border border-blue-500/30 shadow-xl">
        <div className="flex items-center gap-2 text-xs uppercase font-mono tracking-wider text-blue-400 font-bold">
          <Award className="h-4 w-4" /> Architectural Core Axiom
        </div>
        <div className="text-xl sm:text-2xl font-extrabold text-slate-100 mt-2 font-sans tracking-tight">&ldquo;AI proposes. Policy decides. Systems execute.&rdquo;</div>
        <p className="text-xs sm:text-sm text-slate-300 mt-2 leading-relaxed max-w-3xl">
          The Oracle ranks counterfactual strategies under Expected Value theorems. The policy firewall has sole veto authority over money movement and customer fatigue limits. The system worker executes retries and payment links deterministically.
        </p>
      </div>

      <BankMatrix banks={banks} />
      {selected && <TraceModal detail={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
