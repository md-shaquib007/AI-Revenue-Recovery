"use client";

import { ShieldAlert, CheckCircle, RefreshCw, XCircle } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { OpsItem } from "@/lib/types";
import { EmptyState } from "@/components/Status";

export function OpsQueue({
  queue,
  onChanged,
}: {
  queue: OpsItem[];
  onChanged: () => void;
}) {
  const decide = async (caseId: string, action: string) => {
    await apiFetch(`/ops/cases/${caseId}/decision`, {
      method: "POST",
      body: JSON.stringify({ action, operator_notes: "Authorized via Command Center" }),
    });
    onChanged();
  };

  if (queue.length === 0) {
    return <EmptyState>No high-value cases pending human review. System is operating safely.</EmptyState>;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      {queue.map((item) => (
        <div key={item.case_id} className="glass-panel rounded-2xl p-5 sm:p-6 space-y-4 glow-amber transition-all">
          <div className="flex justify-between items-start">
            <div>
              <div className="text-[11px] font-mono text-amber-400 font-bold uppercase tracking-wider flex items-center gap-1.5">
                <ShieldAlert className="h-3.5 w-3.5" /> High-Value Governance Review
              </div>
              <div className="text-2xl sm:text-3xl font-extrabold text-amber-400 mt-1 font-sans">
                ₹{item.amount_in_rupees.toLocaleString()}
              </div>
            </div>
            <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-amber-950/60 border border-amber-500/30 text-amber-300">
              {item.risk_tier} RISK
            </span>
          </div>

          <div className="text-xs text-slate-300 space-y-1.5 font-sans">
            <div className="flex justify-between">
              <span className="text-slate-400">Payment ID:</span>
              <span className="font-mono text-blue-400">{item.payment_id}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Customer:</span>
              <span className="text-slate-100 font-medium">{item.customer_name}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-slate-400">Failure Reason:</span>
              <span className="font-mono text-slate-300">{item.failure_code}</span>
            </div>
            <div className="text-amber-300/90 font-mono text-[11px] bg-amber-950/40 p-2.5 rounded-xl border border-amber-900/50 mt-2">
              {item.escalated_reason}
            </div>
          </div>

          <div className="flex flex-col sm:flex-row gap-2 pt-1 font-medium text-xs">
            <button
              onClick={() => decide(item.case_id, "APPROVE_LINK")}
              className="flex-1 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white py-2.5 px-3 rounded-xl transition-all shadow-md shadow-blue-500/20 flex items-center justify-center gap-1.5"
            >
              <CheckCircle className="h-3.5 w-3.5" /> Approve 1-Click Link
            </button>
            <button
              onClick={() => decide(item.case_id, "RETRY_CHARGE")}
              className="bg-slate-900 hover:bg-slate-800 text-slate-200 py-2.5 px-3 rounded-xl border border-slate-800 transition-colors flex items-center justify-center gap-1.5"
            >
              <RefreshCw className="h-3.5 w-3.5" /> Retry
            </button>
            <button
              onClick={() => decide(item.case_id, "DISMISS")}
              className="bg-slate-900 hover:bg-rose-950/40 text-rose-400 hover:text-rose-300 py-2.5 px-3 rounded-xl border border-slate-800 hover:border-rose-900/50 transition-colors flex items-center justify-center gap-1.5"
            >
              <XCircle className="h-3.5 w-3.5" /> Dismiss
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
