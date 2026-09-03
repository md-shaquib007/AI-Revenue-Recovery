"use client";

import { useState, useEffect } from "react";
import { Search, ShieldCheck, AlertOctagon, TrendingUp } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { CaseDetail, RecoveryCase } from "@/lib/types";
import { EmptyState } from "@/components/Status";
import { TraceModal } from "@/components/TraceModal";

type SentinelItem = {
  entity_key: string;
  status: string;
  circuit_triggered: boolean;
  predictive_outage_risk_pct: number;
};

function SentinelPill({ bankKey }: { bankKey?: string | null }) {
  const [sentinel, setSentinel] = useState<SentinelItem | null>(null);

  useEffect(() => {
    if (!bankKey) return;
    apiFetch<{ sentinel_analytics: SentinelItem[] }>("/intel/sentinel")
      .then((res) => {
        const match = (res.sentinel_analytics || []).find(
          (s) => s.entity_key === bankKey?.toUpperCase()
        );
        setSentinel(match ?? null);
      })
      .catch(() => null);
  }, [bankKey]);

  if (!sentinel) {
    return (
      <span className="text-[10px] font-mono text-slate-600">—</span>
    );
  }

  if (sentinel.circuit_triggered || sentinel.status === "PREDICTIVE_COOLOFF") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-red-950/40 border border-red-700/40 text-red-300 text-[10px] font-mono">
        <AlertOctagon className="h-2.5 w-2.5" /> COOLOFF
      </span>
    );
  }
  if (sentinel.status === "ELEVATED_RISK") {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-950/40 border border-amber-700/40 text-amber-300 text-[10px] font-mono">
        <TrendingUp className="h-2.5 w-2.5" /> ELEVATED
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/30 border border-emerald-800/40 text-emerald-400 text-[10px] font-mono">
      <ShieldCheck className="h-2.5 w-2.5" /> STABLE
    </span>
  );
}

export function CasesTable({ cases }: { cases: RecoveryCase[] }) {
  const [selected, setSelected] = useState<CaseDetail | null>(null);
  const [filter, setFilter] = useState("");

  const open = async (id: string) => {
    const detail = await apiFetch<CaseDetail>(`/recovery/cases/${id}`);
    setSelected(detail);
  };

  const visible = filter
    ? cases.filter(
        (c) =>
          c.payment_id.toLowerCase().includes(filter.toLowerCase()) ||
          c.customer.name.toLowerCase().includes(filter.toLowerCase()) ||
          c.state.toLowerCase().includes(filter.toLowerCase())
      )
    : cases;

  return (
    <div className="glass-panel rounded-2xl overflow-hidden">
      <div className="p-4 sm:p-5 border-b border-slate-800/80 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
        <div>
          <h3 className="font-bold text-sm sm:text-base text-slate-100 tracking-tight">Active Recovery Pipeline</h3>
          <p className="text-xs text-slate-400">Live subscription recovery state machine cases</p>
        </div>
        <div className="relative w-full sm:w-72">
          <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-500 pointer-events-none" />
          <input
            aria-label="Filter cases"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="Filter by payment, customer, state..."
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl pl-8 pr-3 py-1.5 text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
          />
        </div>
      </div>

      <div className="overflow-x-auto scrollbar-none">
        <table className="w-full text-left text-xs min-w-[800px]">
          <thead className="bg-slate-950/90 text-slate-400 uppercase font-mono text-[10px] border-b border-slate-800">
            <tr>
              <th scope="col" className="py-3.5 px-4">Payment ID</th>
              <th scope="col" className="py-3.5 px-4">Customer</th>
              <th scope="col" className="py-3.5 px-4">Amount</th>
              <th scope="col" className="py-3.5 px-4">Failure</th>
              <th scope="col" className="py-3.5 px-4">State</th>
              <th scope="col" className="py-3.5 px-4">Next Action</th>
              <th scope="col" className="py-3.5 px-4">Risk</th>
              <th scope="col" className="py-3.5 px-4">Sentinel</th>
              <th scope="col" className="py-3.5 px-4">Fatigue</th>
              <th scope="col" className="py-3.5 px-4 text-right">Action</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 font-mono">
            {visible.length === 0 ? (
              <tr>
                <td colSpan={10} className="py-8">
                  <EmptyState>No active cases match filter. Inject a webhook or chaos scenario to populate pipeline.</EmptyState>
                </td>
              </tr>
            ) : (
              visible.map((c) => (
                <tr key={c.id} className="hover:bg-slate-900/60 transition-colors group">
                  <td className="py-3.5 px-4 font-semibold text-blue-400 group-hover:text-blue-300">{c.payment_id}</td>
                  <td className="py-3.5 px-4 text-slate-300 font-sans font-medium">{c.customer.name}</td>
                  <td className="py-3.5 px-4 font-bold text-slate-100">₹{c.amount_in_rupees.toLocaleString()}</td>
                  <td className="py-3.5 px-4 text-slate-400 truncate max-w-[130px]">{c.failure_code || "—"}</td>
                  <td className="py-3.5 px-4">
                    <span className="px-2.5 py-1 rounded-md text-[10px] font-semibold bg-slate-900 border border-slate-800 text-slate-300">
                      {c.state}
                    </span>
                  </td>
                  <td className="py-3.5 px-4 text-slate-400">
                    {c.next_action_at ? new Date(c.next_action_at).toLocaleTimeString() : "—"}
                  </td>
                  <td className="py-3.5 px-4">{c.risk_tier}</td>
                  <td className="py-3.5 px-4">
                    <SentinelPill bankKey={c.bank_key} />
                  </td>
                  <td className="py-3.5 px-4 text-slate-400">{c.customer.tokens_remaining}/2</td>
                  <td className="py-3.5 px-4 text-right font-sans">
                    <button
                      onClick={() => open(c.id)}
                      className="bg-blue-600/20 text-blue-300 hover:bg-blue-600/30 border border-blue-500/30 px-3 py-1.5 rounded-lg text-xs font-medium transition-colors shadow-sm"
                    >
                      Inspect Trace
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {selected && <TraceModal detail={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
