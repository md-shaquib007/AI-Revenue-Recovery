"use client";

import { useState } from "react";
import { DashboardShell, useShellData } from "@/components/DashboardShell";
import { CopilotBar } from "@/components/CopilotBar";
import { DigitalTwinPanel } from "@/components/DigitalTwin";
import { TraceModal } from "@/components/TraceModal";
import { apiFetch } from "@/lib/api";
import type { CaseDetail } from "@/lib/types";

function Body() {
  const { pulse, cases } = useShellData();
  const [selected, setSelected] = useState<CaseDetail | null>(null);
  const [twinId, setTwinId] = useState<string | null>(pulse.at_risk[0]?.id || cases[0]?.id || null);

  const open = async (id: string) => {
    setTwinId(id);
    const detail = await apiFetch<CaseDetail>(`/recovery/cases/${id}`);
    setSelected(detail);
  };

  return (
    <div className="space-y-6">
      <div className="bg-[#0f172a] border border-violet-500/25 rounded-xl p-5 space-y-2">
        <h2 className="text-lg font-semibold text-slate-100">Recovery Intelligence</h2>
        <p className="text-sm text-slate-400">
          Deterministic Oracle — no LLM in the loop. It scores IST send windows, ranks WAIT vs RETRY vs LINK vs SWITCH,
          and shows the lift versus doing nothing. Policy still has the last word.
        </p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 pt-2">
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
            <div className="text-[10px] text-slate-500 uppercase">IST now</div>
            <div className="text-sm font-mono text-cyan-300">{pulse.ist_now || "—"}</div>
          </div>
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
            <div className="text-[10px] text-slate-500 uppercase">Quiet hours</div>
            <div className="text-sm font-mono">{pulse.quiet_hours ? "Yes · defer outbound" : "No · send live"}</div>
          </div>
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
            <div className="text-[10px] text-slate-500 uppercase">Predicted recover</div>
            <div className="text-sm font-semibold text-emerald-400">
              ₹{Number(pulse.predicted_recover_rupees || 0).toLocaleString()}
            </div>
          </div>
          <div className="bg-slate-950 border border-slate-800 rounded-lg p-3">
            <div className="text-[10px] text-slate-500 uppercase">Live cases</div>
            <div className="text-sm font-semibold">{pulse.active_cases}</div>
          </div>
        </div>
      </div>

      <CopilotBar onOpenCase={open} />

      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4">
        <div className="lg:col-span-2 bg-[#0f172a] border border-slate-800 rounded-xl overflow-hidden">
          <div className="px-4 py-3 border-b border-slate-800 text-sm font-semibold">Pick a case to twin</div>
          <ul className="divide-y divide-slate-800/70 max-h-[28rem] overflow-y-auto">
            {(pulse.at_risk.length ? pulse.at_risk : cases).map((c) => (
              <li key={c.id}>
                <button
                  type="button"
                  onClick={() => setTwinId(c.id)}
                  className={`w-full text-left px-4 py-3 text-xs hover:bg-slate-900/60 ${
                    twinId === c.id ? "bg-violet-950/40" : ""
                  }`}
                >
                  <div className="flex justify-between gap-2">
                    <span className="font-mono text-blue-400">{c.payment_id}</span>
                    <span>₹{Number(c.amount_in_rupees).toLocaleString()}</span>
                  </div>
                  <div className="text-slate-500 mt-1">
                    {c.customer?.name} · {c.state}
                  </div>
                </button>
              </li>
            ))}
          </ul>
        </div>
        <div className="lg:col-span-3 bg-[#0f172a] border border-slate-800 rounded-xl p-5">
          {twinId ? (
            <DigitalTwinPanel caseId={twinId} />
          ) : (
            <p className="text-sm text-slate-500">No cases yet. The twin needs a live recovery file.</p>
          )}
        </div>
      </div>

      {selected && <TraceModal detail={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}

export default function IntelPage() {
  return (
    <DashboardShell>
      <Body />
    </DashboardShell>
  );
}
