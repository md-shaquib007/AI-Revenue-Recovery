"use client";

import { useState } from "react";
import { Play } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { BenchmarkResult } from "@/lib/types";

export function BenchmarkPanel() {
  const [data, setData] = useState<BenchmarkResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await apiFetch<BenchmarkResult>("/benchmark/run?seed=42&customers=1000&events=5000");
      setData(result);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Benchmark failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-6 flex justify-between items-center">
        <div>
          <h3 className="text-base font-semibold">Reproducible Benchmark Evaluation</h3>
          <p className="text-xs text-slate-400">5,000 synthetic events, seed=42, Revive vs naive baseline.</p>
        </div>
        <button
          onClick={run}
          disabled={busy}
          className="flex items-center gap-2 bg-blue-600 text-white px-5 py-2.5 rounded-lg text-xs font-semibold"
        >
          <Play className="h-4 w-4" />
          {busy ? "Running…" : "Run Benchmark (Seed 42)"}
        </button>
      </div>
      {error && <div className="text-sm text-red-400">{error}</div>}
      {data && (
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-left text-xs font-mono">
            <thead className="bg-slate-900 text-slate-400 uppercase text-[10px]">
              <tr>
                <th className="py-3 px-4">Metric</th>
                <th className="py-3 px-4">Baseline</th>
                <th className="py-3 px-4">REVIVE</th>
                <th className="py-3 px-4">Delta</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800">
              <tr>
                <td className="py-3 px-4">Recovered</td>
                <td className="py-3 px-4">₹{(data.baseline.total_recovered_amount_paise / 100).toLocaleString()}</td>
                <td className="py-3 px-4 text-emerald-400">₹{(data.revive.total_recovered_amount_paise / 100).toLocaleString()}</td>
                <td className="py-3 px-4 text-emerald-400">+₹{data.comparison.net_incremental_recovered_rupees.toLocaleString()}</td>
              </tr>
              <tr>
                <td className="py-3 px-4">Recovery rate</td>
                <td className="py-3 px-4">{data.baseline.recovery_rate_pct}%</td>
                <td className="py-3 px-4 text-emerald-400">{data.revive.recovery_rate_pct}%</td>
                <td className="py-3 px-4 text-emerald-400">+{data.comparison.recovery_rate_lift_pct}%</td>
              </tr>
              <tr>
                <td className="py-3 px-4">Spam nudges</td>
                <td className="py-3 px-4 text-red-400">{data.baseline.unnecessary_nudges_count}</td>
                <td className="py-3 px-4 text-emerald-400">{data.revive.unnecessary_nudges_count}</td>
                <td className="py-3 px-4">-{data.comparison.unnecessary_nudges_reduced_count}</td>
              </tr>
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
