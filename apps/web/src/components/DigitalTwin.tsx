"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/api";
import type { DigitalTwin } from "@/lib/types";

export function DigitalTwinPanel({ caseId }: { caseId: string }) {
  const [twin, setTwin] = useState<DigitalTwin | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    apiFetch<DigitalTwin>(`/intel/cases/${caseId}/twin`)
      .then((data) => {
        if (!cancelled) setTwin(data);
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err.message : "Twin unavailable");
      });
    return () => {
      cancelled = true;
    };
  }, [caseId]);

  if (error) return <p className="text-xs text-amber-300">{error}</p>;
  if (!twin) return <p className="text-xs text-slate-500">Simulating counterfactuals…</p>;

  const maxEv = Math.max(...twin.strategies.map((s) => s.expected_value_rupees), 1);

  return (
    <div className="space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="text-[10px] uppercase tracking-wider text-violet-300 font-semibold">Digital Twin</div>
          <p className="text-sm text-slate-200 mt-1">{twin.narrative}</p>
        </div>
        <div className="text-right text-[10px] font-mono text-slate-400">
          <div>{twin.ist_now}</div>
          <div>Bank {Math.round(twin.bank_health * 100)}%</div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-slate-950 border border-slate-800 rounded p-2">
          <div className="text-[10px] text-slate-500">P(recover)</div>
          <div className="text-lg font-bold text-violet-300">{Math.round(twin.winner.p_recover * 100)}%</div>
        </div>
        <div className="bg-slate-950 border border-slate-800 rounded p-2">
          <div className="text-[10px] text-slate-500">Lift vs wait</div>
          <div className="text-lg font-bold text-emerald-400">₹{twin.lift_vs_wait_rupees.toLocaleString()}</div>
        </div>
        <div className="bg-slate-950 border border-slate-800 rounded p-2">
          <div className="text-[10px] text-slate-500">Preferred rail</div>
          <div className="text-sm font-bold text-cyan-300 mt-1">{twin.preferred_rail}</div>
        </div>
      </div>
      <div className="space-y-1.5">
        {twin.strategies.map((s) => {
          const win = s.action === twin.winner.action;
          return (
            <div key={s.action} className="space-y-0.5">
              <div className="flex justify-between text-[10px] font-mono">
                <span className={win ? "text-violet-300" : "text-slate-400"}>
                  {s.action}
                  {!s.policy_allowed ? " · policy rewrite → " + s.approved_action : ""}
                </span>
                <span className="text-slate-300">
                  {Math.round(s.p_recover * 100)}% · ₹{s.expected_value_rupees.toLocaleString()}
                </span>
              </div>
              <div className="h-1.5 bg-slate-900 rounded overflow-hidden">
                <div
                  className={`h-full ${win ? "bg-violet-400" : s.policy_allowed ? "bg-slate-600" : "bg-amber-700/70"}`}
                  style={{ width: `${Math.max(4, (s.expected_value_rupees / maxEv) * 100)}%` }}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
