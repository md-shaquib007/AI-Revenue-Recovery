"use client";

export default function Error({ error, reset }: { error: Error; reset: () => void }) {
  return (
    <div className="min-h-screen bg-[#080c14] text-slate-100 flex items-center justify-center p-8">
      <div className="max-w-md space-y-3 text-center">
        <h2 className="text-lg font-semibold">Command Center hit an error</h2>
        <p className="text-sm text-slate-400">{error.message}</p>
        <button onClick={reset} className="bg-blue-600 text-white text-sm px-4 py-2 rounded">
          Try again
        </button>
      </div>
    </div>
  );
}
