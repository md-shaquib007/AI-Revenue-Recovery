"use client";

import { Activity, ArrowUpRight, CheckCircle2, ShieldAlert } from "lucide-react";
import type { Metrics } from "@/lib/types";

export function KpiCards({ metrics }: { metrics: Metrics }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div className="glass-panel rounded-2xl p-5 glow-border transition-all">
        <div className="flex items-center justify-between text-slate-400 text-xs font-mono font-medium">
          <span>REVENUE AT RISK</span>
          <Activity className="h-4 w-4 text-sky-400" />
        </div>
        <div className="text-2xl sm:text-3xl font-extrabold text-slate-100 mt-2.5 tracking-tight font-sans">
          ₹{Number(metrics.total_revenue_at_risk_rupees || 0).toLocaleString()}
        </div>
        <div className="text-[11px] text-slate-400 mt-1.5 font-medium">
          {metrics.active_cases_count} active subscription cases
        </div>
      </div>

      <div className="glass-panel rounded-2xl p-5 glow-emerald transition-all">
        <div className="flex items-center justify-between text-emerald-400 text-xs font-mono font-medium">
          <span>RECOVERED REVENUE</span>
          <CheckCircle2 className="h-4 w-4 text-emerald-400" />
        </div>
        <div className="text-2xl sm:text-3xl font-extrabold text-emerald-400 mt-2.5 tracking-tight font-sans">
          ₹{Number(metrics.total_revenue_recovered_rupees || 0).toLocaleString()}
        </div>
        <div className="text-[11px] text-emerald-500/90 mt-1.5 font-medium">
          Automated intelligent non-action
        </div>
      </div>

      <div className="glass-panel rounded-2xl p-5 glow-border transition-all">
        <div className="flex items-center justify-between text-slate-400 text-xs font-mono font-medium">
          <span>NET RECOVERY RATE</span>
          <ArrowUpRight className="h-4 w-4 text-blue-400" />
        </div>
        <div className="text-2xl sm:text-3xl font-extrabold text-blue-400 mt-2.5 tracking-tight font-sans">
          {metrics.recovery_rate_pct}%
        </div>
        <div className="text-[11px] text-slate-400 mt-1.5 font-medium">
          EV calibration {metrics.ev_calibration_ratio ?? 0}x predicted
        </div>
      </div>

      <div className="glass-panel rounded-2xl p-5 glow-amber transition-all">
        <div className="flex items-center justify-between text-amber-400 text-xs font-mono font-medium">
          <span>HUMAN OPS ESCALATIONS</span>
          <ShieldAlert className="h-4 w-4 text-amber-400" />
        </div>
        <div className="text-2xl sm:text-3xl font-extrabold text-amber-400 mt-2.5 tracking-tight font-sans">
          {metrics.escalated_human_count}
        </div>
        <div className="text-[11px] text-amber-500/90 mt-1.5 font-medium">
          High-value ₹50k+ governance queue
        </div>
      </div>
    </div>
  );
}
