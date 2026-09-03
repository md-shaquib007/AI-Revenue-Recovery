"use client";

import { createContext, useContext } from "react";
import { Header, TabNav } from "@/components/Header";
import { ErrorBanner, LoadingBlock } from "@/components/Status";
import { useReviveData } from "@/hooks/useReviveData";

import { CommandPalette } from "@/components/CommandPalette";
import { ShortcutsModal } from "@/components/ShortcutsModal";

type ShellData = ReturnType<typeof useReviveData>;
const ReviveContext = createContext<ShellData | null>(null);

export function useShellData(): ShellData {
  const ctx = useContext(ReviveContext);
  if (!ctx) throw new Error("useShellData must be used inside DashboardShell");
  return ctx;
}

export function DashboardShell({ children }: { children: React.ReactNode }) {
  const data = useReviveData();
  return (
    <ReviveContext.Provider value={data}>
      <div className="min-h-screen bg-[#060911] text-slate-100 flex flex-col antialiased">
        <CommandPalette />
        <ShortcutsModal />
        <Header system={data.system} />
        <main className="flex-1 max-w-7xl w-full mx-auto p-4 sm:p-6 space-y-6 fade-in">
          <TabNav chaosEnabled={data.system?.chaos_enabled !== false} opsCount={data.opsQueue.length} />
          <ErrorBanner message={data.error} stale={data.stale} />
          {data.loading ? <LoadingBlock label="Connecting to REVIVE API Engine…" /> : children}
        </main>
      </div>
    </ReviveContext.Provider>
  );
}
