"use client";

import { DashboardShell, useShellData } from "@/components/DashboardShell";
import { MissionControl } from "@/components/MissionControl";

function OverviewBody() {
  const { metrics, banks, pulse, cases } = useShellData();
  return <MissionControl metrics={metrics} banks={banks} pulse={pulse} cases={cases} />;
}

export default function OverviewPage() {
  return (
    <DashboardShell>
      <OverviewBody />
    </DashboardShell>
  );
}
