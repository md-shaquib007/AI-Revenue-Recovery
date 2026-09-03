"use client";

import { useState, useEffect } from "react";
import { Users, AlertTriangle, CheckCircle, RefreshCw, Zap } from "lucide-react";
import { apiFetch } from "@/lib/api";

type PersonaSample = {
  persona_id: string;
  archetype: string;
  score: number;
  channel: string;
};

type ShadowSimResult = {
  consensus_index_pct: number;
  friction_score_pct: number;
  high_friction_personas_count: number;
  recommended_pivot?: string | null;
  personas_sample: PersonaSample[];
  total_simulated_personas: number;
};

type Props = {
  caseId: string;
  /** Pre-loaded sim from a decision trace's diagnosis.shadow_simulation field */
  embeddedSim?: ShadowSimResult;
  /** Whether a route pivot was applied based on this sim */
  pivotApplied?: boolean;
  pivotFrom?: string;
  pivotTo?: string;
};

export function ShadowSimPanel({ caseId, embeddedSim, pivotApplied, pivotFrom, pivotTo }: Props) {
  const [data, setData] = useState<ShadowSimResult | null>(embeddedSim ?? null);
  const [loading, setLoading] = useState(!embeddedSim);
  const [error, setError] = useState<string | null>(null);

  const runSim = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{ shadow_simulation: ShadowSimResult }>("/intel/shadow-sim", {
        method: "POST",
        body: JSON.stringify({ case_id: caseId, proposed_action: "PAYMENT_LINK" }),
      });
      setData(res.shadow_simulation);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Shadow simulation error");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!embeddedSim && caseId) runSim();
  }, [caseId]);

  if (loading) {
    return (
      <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 text-xs text-slate-400 flex items-center gap-2">
        <RefreshCw className="h-4 w-4 text-cyan-400 animate-spin" />
        Simulating 50 prospective customer shadow personas...
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="bg-slate-950/80 p-4 rounded-xl border border-slate-800 text-xs text-slate-500 flex justify-between items-center">
        <span>Multi-Agent Shadow Simulation ready.</span>
        <button onClick={runSim} className="text-cyan-400 font-mono underline hover:text-cyan-300">
          Run 50-Persona Sim
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-3 font-sans">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-xs font-mono font-bold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5">
          <Users className="h-4 w-4 text-cyan-400" />
          50-Persona Shadow Simulation
          {embeddedSim && (
            <span className="ml-2 text-[10px] font-normal text-slate-500 normal-case tracking-normal bg-slate-900 px-2 py-0.5 rounded-md border border-slate-800">
              from decision trace
            </span>
          )}
        </div>
        {!embeddedSim && (
          <button
            onClick={runSim}
            className="text-[11px] font-mono text-slate-400 hover:text-cyan-300 flex items-center gap-1"
          >
            <RefreshCw className="h-3 w-3" /> Re-sim
          </button>
        )}
      </div>

      {/* AI Route Pivot Badge — only shown when Shadow AI actually changed the routing */}
      {pivotApplied && pivotFrom && pivotTo && (
        <div className="bg-violet-950/50 border border-violet-500/40 text-violet-200 px-3 py-2 rounded-xl text-xs flex items-center gap-2">
          <Zap className="h-4 w-4 text-violet-400 flex-shrink-0" />
          <span>
            <strong>Shadow AI changed route:</strong>{" "}
            <span className="font-mono line-through text-slate-400">{pivotFrom}</span>
            {" → "}
            <span className="font-mono text-violet-300">{pivotTo}</span>
          </span>
        </div>
      )}

      {/* Metric grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-2 text-xs font-mono">
        <div className="bg-slate-900/90 border border-slate-800 p-2.5 rounded-xl">
          <div className="text-slate-400 text-[10px]">Consensus Index</div>
          <div className="text-lg font-bold text-emerald-400 mt-0.5">{data.consensus_index_pct}%</div>
        </div>
        <div className="bg-slate-900/90 border border-slate-800 p-2.5 rounded-xl">
          <div className="text-slate-400 text-[10px]">Friction Score</div>
          <div
            className={`text-lg font-bold mt-0.5 ${
              data.friction_score_pct > 45
                ? "text-red-400"
                : data.friction_score_pct > 30
                ? "text-amber-400"
                : "text-emerald-400"
            }`}
          >
            {data.friction_score_pct}%
          </div>
        </div>
        <div className="bg-slate-900/90 border border-slate-800 p-2.5 rounded-xl col-span-2 sm:col-span-1">
          <div className="text-slate-400 text-[10px]">Friction Personas</div>
          <div className="text-lg font-bold text-slate-200 mt-0.5">
            {data.high_friction_personas_count} / 50
          </div>
        </div>
      </div>

      {/* Pivot recommendation (non-applied) */}
      {data.recommended_pivot && !pivotApplied && (
        <div className="bg-amber-950/40 border border-amber-900/50 p-2.5 rounded-xl text-xs text-amber-300 flex items-center gap-2">
          <AlertTriangle className="h-4 w-4 flex-shrink-0" />
          <span>
            High friction detected. AI recommends pivoting to:{" "}
            <strong className="font-mono">{data.recommended_pivot}</strong>
          </span>
        </div>
      )}

      {/* Persona grid */}
      <div className="space-y-1.5">
        <div className="text-[11px] text-slate-400 font-mono">
          Simulated Personas Sample ({data.personas_sample.length}):
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-1.5">
          {data.personas_sample.map((p) => {
            const happy = p.score >= 0.65;
            return (
              <div
                key={p.persona_id}
                className={`p-2 rounded-lg border text-[11px] font-mono flex flex-col justify-between ${
                  happy
                    ? "bg-emerald-950/20 border-emerald-900/40 text-emerald-300"
                    : "bg-red-950/20 border-red-900/40 text-red-300"
                }`}
              >
                <div className="truncate font-semibold text-[10px] text-slate-300">{p.archetype}</div>
                <div className="flex justify-between items-center mt-1">
                  <span>Score: {Math.round(p.score * 100)}%</span>
                  {happy ? (
                    <CheckCircle className="h-3 w-3 text-emerald-400" />
                  ) : (
                    <AlertTriangle className="h-3 w-3 text-red-400" />
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}
