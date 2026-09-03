"use client";

import { useEffect, useState } from "react";
import { Keyboard, X, Command } from "lucide-react";
import { useRouter } from "next/navigation";

export function ShortcutsModal() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      // Don't trigger if typing in an input/textarea
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) {
        return;
      }

      if (e.key === "?" || (e.shiftKey && e.key === "/")) {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
      if (e.key === "Escape") {
        setOpen(false);
      }

      // Quick numbers 1-5 navigation
      if (!e.metaKey && !e.ctrlKey && !e.altKey) {
        if (e.key === "1") router.push("/");
        if (e.key === "2") router.push("/sandbox");
        if (e.key === "3") router.push("/intel");
        if (e.key === "4") router.push("/cases");
        if (e.key === "5") router.push("/ops");
      }
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [router]);

  if (!open) return null;

  const SHORTCUTS = [
    { key: "Ctrl + K / ⌘K", desc: "Universal Command Palette" },
    { key: "?", desc: "Toggle this Keyboard Shortcuts Guide" },
    { key: "Esc", desc: "Close any open modal or inspection window" },
    { key: "1", desc: "Jump to Overview Dashboard" },
    { key: "2", desc: "Jump to AI What-If Simulation Sandbox" },
    { key: "3", desc: "Jump to Intelligence & Copilot" },
    { key: "4", desc: "Jump to Active Recovery Pipeline" },
    { key: "5", desc: "Jump to Human Ops Review Queue" },
  ];

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-md z-50 flex items-center justify-center p-4 fade-in">
      <div className="glass-panel rounded-2xl max-w-lg w-full p-6 space-y-4 glow-border shadow-2xl border-blue-500/50 bg-slate-950/95">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Keyboard className="h-4 w-4 text-blue-400" />
            <h3 className="text-sm font-bold text-slate-100 font-sans">Command Center Keyboard Shortcuts</h3>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="text-slate-500 hover:text-slate-300 p-1 rounded-lg bg-slate-900 border border-slate-800"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>

        <div className="space-y-2 max-h-80 overflow-y-auto pr-1">
          {SHORTCUTS.map((s, i) => (
            <div key={i} className="flex items-center justify-between py-1.5 px-2 rounded-lg hover:bg-slate-900/60 transition-colors">
              <span className="text-xs text-slate-300 font-sans">{s.desc}</span>
              <kbd className="px-2 py-0.5 text-[11px] font-mono font-bold bg-slate-900 border border-slate-700/80 rounded-md text-cyan-300 shadow-sm">
                {s.key}
              </kbd>
            </div>
          ))}
        </div>

        <div className="text-[10px] font-mono text-slate-500 pt-2 border-t border-slate-900 text-center">
          Press <kbd className="px-1 py-0.5 bg-slate-900 rounded border border-slate-800 text-slate-400">?</kbd> anywhere to view shortcuts
        </div>
      </div>
    </div>
  );
}
