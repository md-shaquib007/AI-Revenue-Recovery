"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, X, CheckCircle2, Download, FileCode } from "lucide-react";
import type { CaseDetail } from "@/lib/types";
import { DigitalTwinPanel } from "@/components/DigitalTwin";
import { ShadowSimPanel } from "@/components/ShadowSimPanel";
import { apiFetch } from "@/lib/api";

export function TraceModal({ detail, onClose }: { detail: CaseDetail; onClose: () => void }) {
  const [downloading, setDownloading] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const downloadCertificate = async () => {
    setDownloading(true);
    try {
      const cert = await apiFetch<any>(`/recovery/cases/${detail.id}/export`);
      const blob = new Blob([JSON.stringify(cert, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `REVIVE_AUDIT_CERTIFICATE_${detail.payment_id}.json`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Export certificate error:", err);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-3 sm:p-4 fade-in">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="trace-title"
        className="glass-panel rounded-2xl max-w-3xl w-full max-h-[90vh] overflow-y-auto p-5 sm:p-6 space-y-4 glow-border shadow-2xl border-blue-500/40"
      >
        <div className="flex justify-between items-start border-b border-slate-800/80 pb-4">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-xs text-blue-400 font-mono font-bold tracking-wider">EXPLAINABLE DECISION TRACE</span>
              {detail.audit_chain_verified !== undefined && (
                <span
                  className={`text-[10px] font-mono font-semibold px-2.5 py-0.5 rounded-full border flex items-center gap-1 ${
                    detail.audit_chain_verified
                      ? "bg-emerald-950/80 border-emerald-500/40 text-emerald-300 shadow-sm"
                      : "bg-rose-950/80 border-rose-500/40 text-rose-300"
                  }`}
                >
                  <CheckCircle2 className="h-3 w-3" />
                  {detail.audit_chain_verified ? "SHA-256 Audit Verified" : "Audit Warning"}
                </span>
              )}
              {detail.version && (
                <span className="text-[10px] font-mono text-slate-400 bg-slate-900 border border-slate-800 px-2 py-0.5 rounded-full">
                  v{detail.version}
                </span>
              )}
            </div>
            <h3 id="trace-title" className="text-base sm:text-lg font-bold text-slate-100 mt-1 font-sans">
              Payment {detail.payment_id} · <span className="text-emerald-400 font-extrabold">₹{detail.amount_in_rupees.toLocaleString()}</span>
            </h3>
          </div>
          <div className="flex items-center gap-2">
            <button
              onClick={downloadCertificate}
              disabled={downloading}
              title="Download Signed Cryptographic Audit Certificate"
              className="text-xs font-mono font-medium text-blue-300 bg-blue-950/60 hover:bg-blue-900/60 border border-blue-500/40 px-3 py-1.5 rounded-xl flex items-center gap-1.5 transition-colors shadow-sm active:scale-95"
            >
              <Download className="h-3.5 w-3.5" />
              <span className="hidden sm:inline">{downloading ? "Generating..." : "Export Certificate"}</span>
            </button>
            <button
              onClick={onClose}
              aria-label="Close modal"
              className="text-slate-400 hover:text-white bg-slate-900 hover:bg-slate-800 p-1.5 rounded-xl border border-slate-800 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>

        <div className="bg-gradient-to-r from-cyan-950/20 to-blue-950/20 border border-cyan-500/30 rounded-xl p-4 shadow-inner">
          {/* Prefer the simulation stored in the latest decision trace (deterministic, audit-safe) */}
          {(() => {
            const latestTrace = [...(detail.decision_traces || [])].sort(
              (a, b) => (b.step_number || 0) - (a.step_number || 0)
            )[0];
            const embeddedSim = latestTrace?.diagnosis?.shadow_simulation as any;
            const pivotApplied = latestTrace?.diagnosis?.shadow_pivot_applied === true;
            const proposed = latestTrace?.diagnosis?.proposed_action as string | undefined;
            const approved = latestTrace?.diagnosis?.approved_action as string | undefined;
            return (
              <ShadowSimPanel
                caseId={detail.id}
                embeddedSim={embeddedSim}
                pivotApplied={pivotApplied}
                pivotFrom={pivotApplied ? proposed : undefined}
                pivotTo={pivotApplied ? approved : undefined}
              />
            );
          })()}
        </div>

        <div className="bg-gradient-to-r from-violet-950/30 to-indigo-950/30 border border-violet-500/30 rounded-xl p-4 shadow-inner">
          <DigitalTwinPanel caseId={detail.id} />
        </div>

        <div className="space-y-3.5">
          {(detail.decision_traces || []).map((t) => (
            <div key={t.id} className="bg-slate-950/80 border border-slate-800/80 rounded-xl p-4 space-y-3 text-xs">
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-1.5 font-mono">
                <div className="flex items-center gap-2">
                  <span className="text-blue-400 font-bold">
                    STEP #{t.step_number}: {t.raw_event_type}
                  </span>
                  {t.record_hash && (
                    <span className="text-[10px] text-slate-400 bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
                      #{t.record_hash.substring(0, 10)}…
                    </span>
                  )}
                </div>
                <span className="text-slate-500 text-[11px]">
                  {t.agent_mode} · {t.latency_ms}ms
                </span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 font-mono text-[11px]">
                <div className="bg-slate-900/90 p-2.5 rounded-lg border border-slate-800">
                  <span className="text-slate-500 text-[10px] block font-sans">AI PROPOSAL</span>
                  <span className="text-slate-200 font-semibold">{String(t.proposed_action || t.diagnosis?.proposed_action || "—")}</span>
                </div>
                <div className="bg-emerald-950/30 p-2.5 rounded-lg border border-emerald-900/40 text-emerald-300">
                  <span className="text-emerald-500/80 text-[10px] block font-sans">POLICY APPROVED & EXECUTED</span>
                  <span className="font-bold">{t.approved_action || t.final_action}</span>
                </div>
              </div>

              <div className="bg-slate-900/90 p-3 rounded-lg border border-slate-800/80 leading-relaxed font-sans">
                <div className="text-slate-400 font-mono text-[10px] uppercase font-bold tracking-wider mb-1">AI Reasoning Diagnosis</div>
                <p className="text-slate-200 text-xs">
                  {String(t.diagnosis?.explanation || t.diagnosis?.reason || JSON.stringify(t.diagnosis))}
                </p>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 font-sans">
                {(t.policy_checks || []).map((pc, idx) => (
                  <div
                    key={idx}
                    className={`p-2.5 rounded-lg border flex items-center gap-2 ${
                      pc.passed
                        ? "bg-emerald-950/20 border-emerald-900/40 text-emerald-300"
                        : "bg-amber-950/20 border-amber-900/40 text-amber-300"
                    }`}
                  >
                    <ShieldCheck className="h-3.5 w-3.5 flex-shrink-0" />
                    <div className="truncate text-xs">
                      <span className="font-mono font-semibold">{pc.rule_name}:</span> {pc.detail}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
