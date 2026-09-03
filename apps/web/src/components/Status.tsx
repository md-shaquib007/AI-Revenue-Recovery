"use client";

export function ErrorBanner({ message, stale }: { message: string | null; stale?: boolean }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="rounded-lg border border-amber-500/40 bg-amber-950/40 px-4 py-3 text-sm text-amber-200"
    >
      {stale ? "Showing last known data. " : ""}
      {message}
    </div>
  );
}

export function LoadingBlock({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="animate-pulse rounded-xl border border-slate-800 bg-[#0f172a] p-8 text-sm text-slate-400">
      {label}
    </div>
  );
}

export function EmptyState({ children }: { children: React.ReactNode }) {
  return (
    <div className="text-center py-12 border border-dashed border-slate-800 rounded-lg text-slate-500 text-sm">
      {children}
    </div>
  );
}
