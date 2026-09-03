"use client";

import { useState } from "react";
import { Sparkles, Search, ArrowRight } from "lucide-react";
import { apiFetch } from "@/lib/api";
import type { CopilotResponse, PulseCase } from "@/lib/types";

const HINTS = [
  "show stuck high-value cases",
  "VIP unpaid links",
  "3DS grace windows",
  "summary",
  "cases over 25000",
];

export function CopilotBar({
  onOpenCase,
}: {
  onOpenCase?: (id: string) => void;
}) {
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<CopilotResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async (text: string) => {
    const q = text.trim();
    if (!q) return;
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch<CopilotResponse>("/intel/copilot", {
        method: "POST",
        body: JSON.stringify({ query: q }),
      });
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Copilot unavailable");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="glass-panel rounded-2xl p-4 sm:p-5 space-y-3.5 glow-border">
      <div className="flex items-center gap-2 text-cyan-300 text-xs font-mono font-bold uppercase tracking-wider">
        <Sparkles className="h-4 w-4 text-cyan-400" />
        REVIVE AI Ops Copilot
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          run(query);
        }}
        className="flex flex-col sm:flex-row gap-2"
      >
        <div className="relative flex-1">
          <Search className="absolute left-3 top-3 h-4 w-4 text-slate-500 pointer-events-none" />
          <input
            aria-label="Ask the recovery copilot"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Ask anything: show stuck high-value cases, VIP unpaid links..."
            className="w-full bg-slate-950/80 border border-slate-800 rounded-xl pl-9 pr-3 py-2.5 text-xs sm:text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:border-cyan-500/60 focus:ring-1 focus:ring-cyan-500/40 transition-all font-sans"
          />
        </div>
        <button
          type="submit"
          disabled={busy}
          className="bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-medium text-xs sm:text-sm px-5 py-2.5 rounded-xl disabled:opacity-50 transition-all flex items-center justify-center gap-1.5 shadow-md shadow-cyan-500/20"
        >
          {busy ? "Analyzing…" : <>Ask <ArrowRight className="h-3.5 w-3.5" /></>}
        </button>
      </form>

      <div className="flex flex-wrap items-center gap-1.5 pt-1">
        <span className="text-[11px] text-slate-400 font-mono">Suggestions:</span>
        {HINTS.map((h) => (
          <button
            key={h}
            type="button"
            onClick={() => {
              setQuery(h);
              run(h);
            }}
            className="text-[11px] font-mono px-2.5 py-1 rounded-full bg-slate-900/80 border border-slate-800 text-slate-400 hover:text-cyan-300 hover:border-cyan-500/50 transition-all"
          >
            {h}
          </button>
        ))}
      </div>

      {error && <p className="text-xs text-amber-300 bg-amber-950/40 p-2.5 rounded-lg border border-amber-900/50">{error}</p>}

      {result && (
        <div className="space-y-3 pt-2 border-t border-slate-800/80 fade-in">
          <div className="bg-slate-950/80 p-3.5 rounded-xl border border-slate-800 text-xs sm:text-sm text-slate-200 leading-relaxed font-sans">
            {result.answer}
          </div>

          {result.matches.length > 0 && (
            <div className="space-y-1.5">
              <div className="text-[11px] font-mono text-slate-400">Matched Cases ({result.matches.length}):</div>
              <ul className="divide-y divide-slate-800/80 border border-slate-800/80 rounded-xl overflow-hidden bg-slate-950/60">
                {result.matches.slice(0, 6).map((m: PulseCase) => (
                  <li key={m.id}>
                    <button
                      type="button"
                      onClick={() => onOpenCase?.(m.id)}
                      className="w-full text-left px-3.5 py-2.5 text-xs hover:bg-slate-900/80 flex flex-wrap items-center justify-between gap-2 transition-colors"
                    >
                      <span className="font-mono text-blue-400 font-medium">{m.payment_id}</span>
                      <span className="text-slate-300 truncate max-w-[150px]">{m.customer?.name}</span>
                      <span className="text-slate-100 font-bold">₹{Number(m.amount_in_rupees).toLocaleString()}</span>
                      <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-slate-800 text-slate-400">{m.state}</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
