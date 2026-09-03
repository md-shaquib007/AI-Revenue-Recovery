"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { 
  Search, 
  Home, 
  Activity, 
  ShieldAlert, 
  Sliders, 
  BarChart3, 
  Flame, 
  Sparkles, 
  X,
  Command
} from "lucide-react";

type NavItem = {
  name: string;
  href: string;
  icon: any;
  category: string;
  badge?: string;
};

const ITEMS: NavItem[] = [
  { name: "Mission Control Dashboard", href: "/", icon: Home, category: "Navigation" },
  { name: "Active Recovery Pipeline", href: "/cases", icon: Activity, category: "Navigation" },
  { name: "Human Ops Review Queue", href: "/ops", icon: ShieldAlert, category: "Governance", badge: "RBAC" },
  { name: "AI What-If Simulation Studio", href: "/sandbox", icon: Sliders, category: "AI Studio", badge: "NEW" },
  { name: "Empirical Performance Benchmark", href: "/benchmark", icon: BarChart3, category: "Analytics" },
  { name: "Chaos Engineering Laboratory", href: "/chaos", icon: Flame, category: "Resilience" },
  { name: "AI Copilot & Pulse Intelligence", href: "/intel", icon: Sparkles, category: "Intelligence" },
];

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setOpen(false);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  if (!open) return null;

  const filtered = query
    ? ITEMS.filter((item) => item.name.toLowerCase().includes(query.toLowerCase()) || item.category.toLowerCase().includes(query.toLowerCase()))
    : ITEMS;

  const navigate = (href: string) => {
    setOpen(false);
    setQuery("");
    router.push(href);
  };

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-start justify-center pt-20 p-4 fade-in">
      <div className="glass-panel rounded-2xl max-w-xl w-full p-4 space-y-3 glow-border shadow-2xl border-blue-500/50 bg-slate-950/95">
        <div className="flex items-center gap-3 border-b border-slate-800 pb-3 px-2">
          <Search className="h-4 w-4 text-blue-400" />
          <input
            autoFocus
            aria-label="Universal Command Palette"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Type a command or jump to page... (Esc to close)"
            className="w-full bg-transparent text-sm text-slate-100 placeholder-slate-500 focus:outline-none font-sans"
          />
          <button
            onClick={() => setOpen(false)}
            className="text-slate-500 hover:text-slate-300 p-1 rounded-lg bg-slate-900 border border-slate-800"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="max-h-72 overflow-y-auto space-y-1 pr-1 scrollbar-none">
          {filtered.length === 0 ? (
            <div className="py-6 text-center text-xs text-slate-500 font-sans">No matching commands or pages found.</div>
          ) : (
            filtered.map((item) => {
              const Icon = item.icon;
              return (
                <button
                  key={item.href}
                  onClick={() => navigate(item.href)}
                  className="w-full flex items-center justify-between p-2.5 rounded-xl hover:bg-slate-900/90 transition-colors text-left group"
                >
                  <div className="flex items-center gap-3">
                    <div className="p-1.5 rounded-lg bg-slate-900 group-hover:bg-blue-600/20 text-slate-400 group-hover:text-blue-400 transition-colors border border-slate-800">
                      <Icon className="h-4 w-4" />
                    </div>
                    <div>
                      <div className="text-xs font-bold text-slate-200 group-hover:text-white transition-colors">
                        {item.name}
                      </div>
                      <div className="text-[10px] text-slate-500 font-mono">{item.category}</div>
                    </div>
                  </div>
                  {item.badge && (
                    <span className="text-[10px] font-mono font-bold px-2 py-0.5 rounded-full bg-blue-950 border border-blue-500/40 text-blue-300">
                      {item.badge}
                    </span>
                  )}
                </button>
              );
            })
          )}
        </div>

        <div className="flex justify-between items-center text-[10px] font-mono text-slate-500 pt-2 border-t border-slate-900 px-2">
          <span>Navigate with mouse or enter</span>
          <span className="flex items-center gap-1">
            <Command className="h-3 w-3" /> + K to open anytime
          </span>
        </div>
      </div>
    </div>
  );
}
