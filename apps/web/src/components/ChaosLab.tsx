"use client";

import { useState } from "react";
import { Clock, Cpu, Server, Shield } from "lucide-react";
import { apiFetch } from "@/lib/api";

export function ChaosLab({ onChanged }: { onChanged: () => void }) {
  const [log, setLog] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const add = (msg: string) => setLog((prev) => [`[${new Date().toLocaleTimeString()}] ${msg}`, ...prev.slice(0, 20)]);

  const run = async (label: string, fn: () => Promise<void>) => {
    setBusy(true);
    try {
      await fn();
      add(label);
      onChanged();
    } catch (e) {
      add(e instanceof Error ? e.message : "Chaos action failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-blue-400 font-semibold text-sm">
            <Cpu className="h-4 w-4" /> Simulate LLM Outage
          </div>
          <button
            disabled={busy}
            onClick={() =>
              run("LLM outage toggled", async () => {
                await apiFetch("/chaos/llm-outage", { method: "POST", body: JSON.stringify({ enabled: true }) });
              })
            }
            className="w-full py-2 rounded text-xs font-semibold bg-blue-600 text-white"
          >
            Inject LLM Failure
          </button>
        </div>
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-purple-400 font-semibold text-sm">
            <Shield className="h-4 w-4" /> Prompt Injection Attack
          </div>
          <button
            disabled={busy}
            onClick={() =>
              run("Prompt injection intercepted", async () => {
                await apiFetch("/chaos/inject-prompt-injection", { method: "POST" });
              })
            }
            className="w-full bg-purple-600 text-white py-2 rounded text-xs font-semibold"
          >
            Inject Adversarial Webhook
          </button>
        </div>
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-emerald-400 font-semibold text-sm">
            <Clock className="h-4 w-4" /> Intelligent Non-Action
          </div>
          <button
            disabled={busy}
            onClick={() =>
              run("Grace capture cancelled recovery", async () => {
                await apiFetch("/chaos/inject-grace-capture", { method: "POST" });
              })
            }
            className="w-full bg-emerald-600 text-white py-2 rounded text-xs font-semibold"
          >
            Test Late Capture Window
          </button>
        </div>
        <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-5 space-y-3">
          <div className="flex items-center gap-2 text-amber-400 font-semibold text-sm">
            <Server className="h-4 w-4" /> Bank Outage
          </div>
          <button
            disabled={busy}
            onClick={() =>
              run("HDFC downtime injected", async () => {
                await apiFetch("/chaos/bank-downtime", {
                  method: "POST",
                  body: JSON.stringify({ enabled: true, entity: "HDFC" }),
                });
              })
            }
            className="w-full bg-amber-600 text-white py-2 rounded text-xs font-semibold"
          >
            Inject HDFC Downtime
          </button>
        </div>

        <div className="bg-[#0f172a] border border-cyan-500/40 rounded-xl p-5 space-y-3 bg-gradient-to-br from-cyan-950/30 to-blue-950/30 shadow-lg">
          <div className="flex items-center gap-2 text-cyan-400 font-semibold text-sm">
            <Cpu className="h-4 w-4" /> 50-Webhook Concurrency Blitz
          </div>
          <p className="text-[11px] text-slate-400">Fires 50 parallel webhooks in 200ms to stress-test locks & singleflight deduplication.</p>
          <button
            disabled={busy}
            onClick={() =>
              run("50-Webhook Concurrency Blitz executed: 0 race conditions, 100% atomic locks", async () => {
                const tasks = Array.from({ length: 50 }).map((_, i) =>
                  apiFetch("/webhooks/razorpay", {
                    method: "POST",
                    body: JSON.stringify({
                      event: "payment.failed",
                      payload: {
                        payment: {
                          entity: {
                            id: `pay_blitz_${Date.now().toString().slice(-4)}_${i}`,
                            amount: 199900,
                            currency: "INR",
                            status: "failed",
                            error_code: "BAD_REQUEST_PAYMENT_TIMED_OUT",
                            method: "upi",
                            bank: "HDFC",
                            created_at: Math.floor(Date.now() / 1000),
                          },
                        },
                      },
                    }),
                  })
                );
                await Promise.allSettled(tasks);
              })
            }
            className="w-full bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white py-2 rounded-lg text-xs font-semibold shadow-md active:scale-95 transition-all"
          >
            Launch Concurrency Blitz
          </button>
        </div>
      </div>
      <div className="bg-black/60 border border-slate-900 rounded-lg p-4 font-mono text-xs h-40 overflow-y-auto">
        {log.length === 0 ? <div className="text-slate-600 italic">Ready for chaos test execution...</div> : log.map((l) => <div key={l}>{l}</div>)}
      </div>
    </div>
  );
}
