"use client";

import { DashboardShell, useShellData } from "@/components/DashboardShell";
import { OpsQueue } from "@/components/OpsQueue";

function Body() {
  const { opsQueue, refresh } = useShellData();
  return (
    <div className="bg-[#0f172a] border border-slate-800 rounded-xl p-6 space-y-4">
      <h3 className="font-semibold text-base">Human-in-the-Loop Escalation Queue</h3>
      <p className="text-xs text-slate-400">Transactions &gt; ₹50,000 or low confidence are gated here for operator signoff.</p>
      <OpsQueue queue={opsQueue} onChanged={refresh} />
    </div>
  );
}

export default function OpsPage() {
  return (
    <DashboardShell>
      <Body />
    </DashboardShell>
  );
}
