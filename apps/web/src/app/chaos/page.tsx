"use client";

import { DashboardShell, useShellData } from "@/components/DashboardShell";
import { ChaosLab } from "@/components/ChaosLab";

function Body() {
  const { refresh, system } = useShellData();
  if (system && !system.chaos_enabled) {
    return <div className="text-sm text-slate-400">Chaos lab is disabled in this environment.</div>;
  }
  return <ChaosLab onChanged={refresh} />;
}

export default function ChaosPage() {
  return (
    <DashboardShell>
      <Body />
    </DashboardShell>
  );
}
