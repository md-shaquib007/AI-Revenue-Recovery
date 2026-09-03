"use client";

import { useEffect, useState } from "react";
import { ShieldCheck, AlertOctagon } from "lucide-react";
import { apiFetch } from "@/lib/api";

type SentinelItem = {
  entity_key: string;
  predictive_outage_risk_pct: number;
  failure_velocity_per_min: number;
  status: string;
  circuit_triggered: boolean;
};

export function SentinelBadge() {
  const [sentinels, setSentinels] = useState<SentinelItem[]>([]);

  useEffect(() => {
    async function load() {
      try {
        const res = await apiFetch<{ sentinel_analytics: SentinelItem[] }>("/intel/sentinel");
        setSentinels(res.sentinel_analytics || []);
      } catch {
        // silent fallback
      }
    }
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, []);

  const alertItem = sentinels.find((s) => s.circuit_triggered || s.predictive_outage_risk_pct > 40);

  if (alertItem) {
    return (
      <div className="bg-amber-950/60 border border-amber-500/40 text-amber-300 px-3 py-1.5 rounded-lg text-xs font-mono flex items-center gap-2 shadow-md animate-pulse">
        <AlertOctagon className="h-4 w-4 text-amber-400 flex-shrink-0" />
        <span>
          Bank Sentinel: <strong>{alertItem.entity_key}</strong> Predictive Outage Risk ({alertItem.predictive_outage_risk_pct}%) — Cool-off Active
        </span>
      </div>
    );
  }

  return (
    <div className="bg-slate-900/90 border border-slate-800 text-slate-300 px-3 py-1.5 rounded-lg text-xs font-mono flex items-center gap-2 shadow-inner">
      <ShieldCheck className="h-3.5 w-3.5 text-cyan-400 flex-shrink-0" />
      <span>Bank Sentinel: All Gateways Stable</span>
    </div>
  );
}
