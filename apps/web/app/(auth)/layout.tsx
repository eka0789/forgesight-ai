"use client";

import { Wrench } from "lucide-react";

export default function AuthLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-[var(--primary)] to-[#0d1224] p-4">
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center gap-3 text-white">
          <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-[var(--accent)]">
            <Wrench className="h-6 w-6" />
          </div>
          <div>
            <div className="text-xl font-bold tracking-tight">ForgeSight AI</div>
            <div className="text-xs text-slate-300">
              Intelligence That Powers Smarter Manufacturing.
            </div>
          </div>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-6 shadow-2xl fsg-fade-in">
          {children}
        </div>
        <p className="mt-4 text-center text-[11px] text-slate-400">
          Industrial AI Intelligence Platform · CV Inspection · Predictive
          Maintenance · RAG · AI Agents · MLOps
        </p>
      </div>
    </div>
  );
}
