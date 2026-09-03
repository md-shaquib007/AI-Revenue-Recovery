"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { apiFetch, setToken } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [username, setUsername] = useState("ops");
  const [password, setPassword] = useState("revive-ops-2026");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const onSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await apiFetch<{ access_token: string }>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username, password }),
      });
      setToken(res.access_token);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen bg-[#080c14] flex items-center justify-center p-6">
      <form onSubmit={onSubmit} className="w-full max-w-sm bg-[#0f172a] border border-slate-800 rounded-xl p-6 space-y-4">
        <h1 className="text-lg font-bold">REVIVE operator sign-in</h1>
        <p className="text-xs text-slate-400">Required when AUTH_REQUIRED or APP_ENV=production.</p>
        {error && (
          <div role="alert" className="text-sm text-red-400">
            {error}
          </div>
        )}
        <label className="block text-xs text-slate-400">
          Username
          <input
            className="mt-1 w-full bg-slate-900 border border-slate-800 rounded px-3 py-2 text-sm"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
          />
        </label>
        <label className="block text-xs text-slate-400">
          Password
          <input
            type="password"
            className="mt-1 w-full bg-slate-900 border border-slate-800 rounded px-3 py-2 text-sm"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
          />
        </label>
        <button disabled={busy} className="w-full bg-blue-600 text-white rounded py-2 text-sm font-semibold">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
