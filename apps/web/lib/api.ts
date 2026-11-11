"use client";

import { useAuthStore } from "@/lib/store";
import type { Page } from "@/lib/types";

export const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = useAuthStore.getState().token;
  const headers: Record<string, string> = {
    ...(options.headers as Record<string, string>),
  };
  if (!(options.body instanceof FormData) && options.body) {
    headers["Content-Type"] = "application/json";
  }
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (res.status === 401 && !path.startsWith("/api/v1/auth/login")) {
    useAuthStore.getState().logout();
    if (typeof window !== "undefined") window.location.replace("/login");
    throw new ApiError(401, "Session expired");
  }
  if (!res.ok) {
    let detail: unknown = null;
    try {
      const body = await res.json();
      detail = body.detail ?? body;
    } catch {
      detail = res.statusText;
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
  upload: <T>(path: string, form: FormData) =>
    request<T>(path, { method: "POST", body: form }),
  login: async (email: string, password: string) => {
    const form = new URLSearchParams({ username: email, password });
    const res = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: form.toString(),
    });
    if (!res.ok) {
      let detail = "Login failed";
      try {
        const body = await res.json();
        detail = body.detail ?? detail;
      } catch {}
      throw new ApiError(res.status, detail);
    }
    return (await res.json()) as import("@/lib/types").LoginResponse;
  },
  /** Fetch binary (e.g., annotated images) with auth; returns object URL. */
  blob: async (path: string): Promise<string> => {
    const token = useAuthStore.getState().token;
    const res = await fetch(`${API_URL}${path}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new ApiError(res.status, "Failed to load binary");
    const blob = await res.blob();
    return URL.createObjectURL(blob);
  },
};

export function qs(params: Record<string, string | number | undefined>) {
  const entries = Object.entries(params).filter(
    ([, v]) => v !== undefined && v !== "",
  );
  const s = new URLSearchParams(
    entries.map(([k, v]) => [k, String(v)]),
  ).toString();
  return s ? `?${s}` : "";
}

export function unwrap<T>(page: Page<T>): T[] {
  return page.items;
}
