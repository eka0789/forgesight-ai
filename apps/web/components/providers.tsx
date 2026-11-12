"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { useAuthStore, useThemeStore } from "@/lib/store";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: { retry: 1, refetchOnWindowFocus: false, staleTime: 15_000 },
        },
      }),
  );
  const dark = useThemeStore((s) => s.dark);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
  }, [dark]);

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}

/** Client-side auth guard for the (app) route group.
 *
 * Redirect decisions read the store LIVE (getState) instead of render-captured
 * values: zustand persist rehydration can complete between render and effect,
 * and a stale (hydrated, token) pair once redirected logged-in users to
 * /login on every hard reload. `undefined` = still resolving (render nothing). */
export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [token, setToken] = useState<string | null | undefined>(undefined);

  useEffect(() => {
    const sync = () => setToken(useAuthStore.getState().token);
    sync(); // persist rehydrates at store init — token is available here
    const unsub = useAuthStore.subscribe(sync);
    return unsub;
  }, []);

  useEffect(() => {
    if (token === null) {
      router.replace(`/login?next=${encodeURIComponent(pathname)}`);
    }
  }, [token, pathname, router]);

  if (token === undefined || token === null) return null;
  return <>{children}</>;
}
