"use client";

import { DashboardShell, useShellData } from "@/components/DashboardShell";
import { BenchmarkPanel } from "@/components/BenchmarkPanel";

function Body() {
  const { system } = useShellData();
  if (system && !system.chaos_enabled) {
    return <div className="text-sm text-slate-400">Benchmark lab is disabled in this environment.</div>;
  }
  return <BenchmarkPanel />;
}

export default function BenchmarkPage() {
  return (
    <DashboardShell>
      <Body />
    </DashboardShell>
  );
}
