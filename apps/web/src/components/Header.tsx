"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { ShieldCheck, Zap, LogOut, LogIn } from "lucide-react";
import { clearToken, getToken } from "@/lib/api";
import type { SystemStatus } from "@/lib/types";

export function Header({ system }: { system: SystemStatus | null }) {
  const router = useRouter();
  const authed = typeof window !== "undefined" && !!getToken();

  return (
    <header className="border-b border-slate-800/80 bg-[#090d16]/90 backdrop-blur-md sticky top-0 z-40 px-4 sm:px-6 py-3.5 flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 shadow-xl">
      <Link href="/" className="flex items-center gap-3 group">
        <div className="h-9 w-9 rounded-xl bg-gradient-to-tr from-blue-600 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/25 group-hover:scale-105 transition-transform">
          <Zap className="h-5 w-5 text-white" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold text-lg tracking-tight bg-gradient-to-r from-blue-400 via-indigo-300 to-emerald-400 bg-clip-text text-transparent">
              REVIVE
            </span>
            <span className="text-[10px] bg-blue-500/10 text-blue-400 border border-blue-500/30 px-2 py-0.5 rounded-full font-mono font-medium">
              {system?.app_env || "dev"}
            </span>
          </div>
          <p className="text-[11px] text-slate-400 font-medium">Autonomous Revenue Recovery Agent</p>
        </div>
      </Link>

      <div className="flex flex-wrap items-center gap-2 sm:gap-3 text-xs font-mono">
        <div className="flex items-center gap-2 bg-slate-900/90 border border-slate-800/90 px-3 py-1.5 rounded-lg shadow-inner">
          <div className={`h-2 w-2 rounded-full ${system?.llm_outage_simulated ? "bg-amber-400 animate-pulse" : "bg-emerald-400"}`} />
          <span className="text-slate-300 text-[11px]">
            {system?.llm_outage_simulated ? "Mode: DETERMINISTIC FALLBACK" : "Mode: AI REASONER"}
          </span>
        </div>

        <div className="flex items-center gap-1.5 bg-emerald-950/30 border border-emerald-500/30 px-3 py-1.5 rounded-lg text-emerald-400 shadow-inner">
          <ShieldCheck className="h-3.5 w-3.5 flex-shrink-0" />
          <span className="text-[11px] font-semibold">Firewall: STRICT</span>
        </div>

        {system?.auth_required && (
          <button
            onClick={() => {
              if (authed) clearToken();
              router.push("/login");
            }}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-slate-800/80 hover:bg-slate-800 text-slate-300 hover:text-white transition-colors border border-slate-700/60"
          >
            {authed ? (
              <>
                <LogOut className="h-3.5 w-3.5" /> Sign out
              </>
            ) : (
              <>
                <LogIn className="h-3.5 w-3.5" /> Sign in
              </>
            )}
          </button>
        )}
      </div>
    </header>
  );
}

const TABS = [
  { href: "/", id: "overview", label: "Overview" },
  { href: "/sandbox", id: "sandbox", label: "AI Sandbox" },
  { href: "/intel", id: "intel", label: "Intelligence" },
  { href: "/cases", id: "cases", label: "Cases" },
  { href: "/ops", id: "ops", label: "Human Ops" },
  { href: "/chaos", id: "chaos", label: "Chaos Lab" },
  { href: "/benchmark", id: "benchmark", label: "Benchmark" },
];

export function TabNav({ chaosEnabled, opsCount }: { chaosEnabled: boolean; opsCount: number }) {
  const pathname = usePathname();

  return (
    <nav className="overflow-x-auto scrollbar-none border-b border-slate-800/80 pb-2 pt-1 -mx-4 px-4 sm:mx-0 sm:px-0">
      <div className="flex items-center gap-1.5 min-w-max" role="tablist" aria-label="Command center">
        {TABS.filter((tab) => chaosEnabled || (tab.id !== "chaos" && tab.id !== "benchmark")).map((tab) => {
          const active = pathname === tab.href;
          const label = tab.id === "ops" ? `Human Ops (${opsCount})` : tab.label;

          return (
            <Link
              key={tab.id}
              href={tab.href}
              role="tab"
              aria-selected={active}
              className={`flex items-center gap-2 px-3.5 py-2 rounded-xl text-xs sm:text-sm font-medium transition-all duration-200 ${
                active
                  ? "bg-blue-600/20 text-blue-300 border border-blue-500/40 shadow-sm shadow-blue-500/10 font-semibold"
                  : "text-slate-400 hover:text-slate-200 hover:bg-slate-900/60"
              }`}
            >
              {label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
