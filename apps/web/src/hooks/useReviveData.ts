"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE, apiFetch, getToken } from "@/lib/api";
import type { BankEntity, Metrics, OpsItem, Pulse, RecoveryCase, SystemStatus } from "@/lib/types";

const emptyMetrics: Metrics = {
  total_revenue_at_risk_rupees: 0,
  total_revenue_recovered_rupees: 0,
  recovery_rate_pct: 0,
  active_cases_count: 0,
  escalated_human_count: 0,
};

const emptyPulse: Pulse = {
  generated_at: "",
  ist_now: "",
  ist_hour: 0,
  quiet_hours: false,
  circadian_multiplier: 0,
  seconds_until_send_window: 0,
  funnel: [],
  failure_mix: [],
  at_risk: [],
  active_cases: 0,
  active_rupees: 0,
  predicted_recover_rupees: 0,
  recovered_rupees: 0,
  circadian_curve: [],
  live_feed: [],
};

export function useReviveData() {
  const [metrics, setMetrics] = useState<Metrics>(emptyMetrics);
  const [cases, setCases] = useState<RecoveryCase[]>([]);
  const [opsQueue, setOpsQueue] = useState<OpsItem[]>([]);
  const [banks, setBanks] = useState<BankEntity[]>([]);
  const [pulse, setPulse] = useState<Pulse>(emptyPulse);
  const [system, setSystem] = useState<SystemStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [stale, setStale] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const status = await apiFetch<SystemStatus>("/system/status");
      setSystem(status);
      const [m, c, q, b, p] = await Promise.all([
        apiFetch<Metrics>("/recovery/metrics/summary"),
        apiFetch<{ cases: RecoveryCase[] }>("/recovery/cases?limit=50"),
        apiFetch<{ queue: OpsItem[] }>("/ops/queue"),
        apiFetch<{ entities: BankEntity[] }>("/recovery/bank-health"),
        apiFetch<Pulse>("/intel/pulse"),
      ]);
      setMetrics(m);
      setCases(c.cases || []);
      setOpsQueue(q.queue || []);
      setBanks(b.entities || []);
      setPulse(p);
      setError(null);
      setStale(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reach the REVIVE API");
      setStale(true);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();

    // Optimize polling: pause when browser tab is inactive/hidden to save compute & network
    const interval = setInterval(() => {
      if (typeof document !== "undefined" && document.visibilityState === "visible") {
        refresh();
      }
    }, 8000);

    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        refresh();
      }
    };
    document.addEventListener("visibilitychange", onVisibilityChange);

    const token = getToken();
    const url = `${API_BASE}/stream/events${token ? `?access_token=${token}` : ""}`;
    let source: EventSource | null = null;
    try {
      source = new EventSource(url);
      source.addEventListener("revive", () => {
        refresh();
      });
    } catch {
      /* polling remains */
    }
    return () => {
      clearInterval(interval);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      source?.close();
    };
  }, [refresh]);

  return { metrics, cases, opsQueue, banks, pulse, system, error, loading, stale, refresh };
}
