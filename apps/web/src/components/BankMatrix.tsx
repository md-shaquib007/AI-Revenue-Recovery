"use client";

import { Server, Activity, TrendingUp, ShieldAlert, ShieldCheck } from "lucide-react";
import type { BankEntity } from "@/lib/types";

function VelocitySparkline({ isHealthy, score }: { isHealthy: boolean; score: number }) {
  // Generate deterministic SVG points based on health score
  const points = isHealthy
    ? [20, 18, 22, 15, 19, 14, 18, 12, 10]
    : [10, 14, 18, 26, 32, 28, 36, 40, 42];

  const max = Math.max(...points, 45);
  const pathD = points
    .map((val, idx) => {
      const x = (idx / (points.length - 1)) * 60;
      const y = 24 - (val / max) * 20;
      return `${idx === 0 ? "M" : "L"} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");

  return (
    <svg className="w-14 h-6 overflow-visible" viewBox="0 0 60 24" fill="none">
      <path
        d={pathD}
        stroke={isHealthy ? "#34d399" : "#f59e0b"}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export function BankMatrix({ banks }: { banks: BankEntity[] }) {
  return (
    <div className="glass-panel rounded-2xl p-5 sm:p-6 space-y-4 glow-border">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
        <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2 tracking-tight">
          <Server className="h-4 w-4 text-blue-400" />
          Live Bank & Gateway Telemetry Matrix
        </h3>
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-mono text-slate-400 bg-slate-900/90 px-2.5 py-1 rounded-md border border-slate-800 flex items-center gap-1.5 shadow-sm">
            <Activity className="h-3 w-3 text-emerald-400 pulse-dot" /> Sentinel Velocity Active
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
        {banks.length === 0 ? (
          <div className="text-xs text-slate-500 col-span-full py-4 text-center">No bank telemetry available.</div>
        ) : (
          banks.map((b) => {
            const score = b.health_score ?? (b.health_pct ? b.health_pct / 100 : 0.95);
            const isHealthy = b.status === "Healthy" || score >= 0.7;
            const isCooloff = b.status === "PREDICTIVE_COOLOFF" || score < 0.5;

            return (
              <div
                key={b.entity_key}
                className={`bg-slate-950/80 border rounded-xl p-3.5 transition-all duration-200 group hover:scale-[1.02] shadow-sm ${
                  isCooloff
                    ? "border-red-900/60 hover:border-red-500/50 bg-red-950/10"
                    : isHealthy
                    ? "border-slate-800/80 hover:border-emerald-500/40 hover:bg-slate-900/50"
                    : "border-amber-900/60 hover:border-amber-500/50 bg-amber-950/10"
                }`}
              >
                <div className="flex items-center justify-between">
                  <div className="text-xs text-slate-300 font-mono font-bold truncate">{b.entity_key}</div>
                  <VelocitySparkline isHealthy={isHealthy} score={score} />
                </div>

                <div className="flex items-baseline justify-between mt-2">
                  <div
                    className={`text-xl font-extrabold font-sans tracking-tight ${
                      isCooloff ? "text-red-400" : isHealthy ? "text-emerald-400" : "text-amber-400"
                    }`}
                  >
                    {Math.round(score * 100)}%
                  </div>
                  <span className="text-[10px] font-mono text-slate-500">dF/dt: {isHealthy ? "0.2/m" : "3.8/m"}</span>
                </div>

                <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-900/80">
                  <div className="flex items-center gap-1.5">
                    <div
                      className={`h-1.5 w-1.5 rounded-full ${
                        isCooloff ? "bg-red-400 animate-ping" : isHealthy ? "bg-emerald-400" : "bg-amber-400 animate-pulse"
                      }`}
                    />
                    <span className="text-[10px] font-mono text-slate-400 uppercase tracking-wider">
                      {isCooloff ? "COOLOFF" : isHealthy ? "HEALTHY" : "DEGRADED"}
                    </span>
                  </div>
                  {isHealthy ? (
                    <ShieldCheck className="h-3 w-3 text-emerald-500/70" />
                  ) : (
                    <ShieldAlert className="h-3 w-3 text-amber-500/80" />
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
