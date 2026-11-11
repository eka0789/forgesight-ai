"use client";

import { AuthGuard } from "@/components/providers";
import { AppShell } from "@/components/layout/app-shell";

export function AuthShell({ children }: { children: React.ReactNode }) {
  return (
    <AuthGuard>
      <AppShell>{children}</AppShell>
    </AuthGuard>
  );
}
