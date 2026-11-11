"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { Organization, User } from "@/lib/types";

interface AuthState {
  token: string | null;
  user: User | null;
  organization: Organization | null;
  setSession: (
    token: string,
    user: User,
    organization: Organization,
  ) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      organization: null,
      setSession: (token, user, organization) =>
        set({ token, user, organization }),
      logout: () => set({ token: null, user: null, organization: null }),
    }),
    { name: "forgesight-auth" },
  ),
);

interface ThemeState {
  dark: boolean;
  toggle: () => void;
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      dark: true,
      toggle: () =>
        set((s) => {
          const next = !s.dark;
          if (typeof document !== "undefined") {
            document.documentElement.classList.toggle("dark", next);
          }
          return { dark: next };
        }),
    }),
    {
      name: "forgesight-theme",
      onRehydrateStorage: () => (state) => {
        if (typeof document !== "undefined" && state?.dark) {
          document.documentElement.classList.add("dark");
        }
      },
    },
  ),
);
