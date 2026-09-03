"use client";

import { DashboardShell, useShellData } from "@/components/DashboardShell";
import { CasesTable } from "@/components/CasesTable";

function Body() {
  const { cases } = useShellData();
  return <CasesTable cases={cases} />;
}

export default function CasesPage() {
  return (
    <DashboardShell>
      <Body />
    </DashboardShell>
  );
}
