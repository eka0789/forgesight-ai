"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Activity, Bot, BrainCircuit, Factory, FileSearch, LayoutDashboard,
  LineChart, Moon, ScanSearch, Settings, Sun, Wrench, Boxes, LogOut,
} from "lucide-react";
import { useAuthStore, useThemeStore } from "@/lib/store";
import { Button } from "@/components/ui";
import { cn } from "@/lib/cx";

const NAV = [
  { href: "/dashboard", label: "Overview", icon: LayoutDashboard },
  { href: "/vision", label: "Vision Inspection", icon: ScanSearch },
  { href: "/maintenance", label: "Predictive Maintenance", icon: Activity },
  { href: "/knowledge", label: "Knowledge AI", icon: FileSearch },
  { href: "/agent", label: "AI Agent", icon: Bot },
  { href: "/lab", label: "ML Laboratory", icon: BrainCircuit },
  { href: "/models", label: "Model Management", icon: Boxes },
  { href: "/monitoring", label: "Monitoring", icon: LineChart },
  { href: "/reports", label: "Reports", icon: Factory },
  { href: "/settings", label: "Settings", icon: Settings },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, organization, logout } = useAuthStore();
  const { dark, toggle } = useThemeStore();

  return (
    <div className="flex min-h-screen">
      {/* Sidebar */}
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-60 flex-col border-r border-[var(--border)] bg-[var(--card)] lg:flex">
        <div className="flex items-center gap-2 px-4 py-5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)] text-[var(--accent-foreground)]">
            <Wrench className="h-5 w-5" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight">ForgeSight AI</div>
            <div className="text-[10px] text-[var(--muted-foreground)]">
              Industrial AI Intelligence
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-0.5 px-2">
          {NAV.map(({ href, label, icon: Icon }) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
                pathname === href
                  ? "bg-[var(--accent)]/12 font-medium text-[var(--accent)]"
                  : "text-[var(--muted-foreground)] hover:bg-[var(--border)]/40 hover:text-[var(--foreground)]",
              )}
            >
              <Icon className="h-4 w-4 shrink-0" />
              {label}
            </Link>
          ))}
        </nav>
        <div className="border-t border-[var(--border)] p-3 text-xs text-[var(--muted-foreground)]">
          <div className="font-medium text-[var(--foreground)]">
            {organization?.name ?? "—"}
          </div>
          <div className="mt-0.5">
            {user?.email} · {user?.role}
          </div>
          {organization?.is_demo && (
            <div className="mt-1 inline-block rounded bg-[var(--warning)]/15 px-1.5 py-0.5 text-[10px] text-[var(--warning)]">
              DEMO DATA
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 lg:pl-60">
        <header className="sticky top-0 z-30 flex h-14 items-center justify-between border-b border-[var(--border)] bg-[var(--card)]/90 px-4 backdrop-blur">
          <div className="flex items-center gap-2 overflow-x-auto lg:hidden">
            {NAV.slice(0, 5).map(({ href, label }) => (
              <Link
                key={href}
                href={href}
                className={cn(
                  "whitespace-nowrap rounded px-2 py-1 text-xs",
                  pathname === href
                    ? "text-[var(--accent)] font-semibold"
                    : "text-[var(--muted-foreground)]",
                )}
              >
                {label}
              </Link>
            ))}
          </div>
          <div className="hidden text-sm font-medium lg:block">
            {NAV.find((n) => n.href === pathname)?.label ?? "ForgeSight AI"}
          </div>
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" onClick={toggle} aria-label="Toggle theme">
              {dark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                logout();
                router.push("/login");
              }}
            >
              <LogOut className="h-3.5 w-3.5" /> Sign out
            </Button>
          </div>
        </header>
        <main className="p-4 lg:p-6 max-w-[1400px] mx-auto">{children}</main>
      </div>
    </div>
  );
}
