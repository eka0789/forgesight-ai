"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { Button, ErrorState, Input, Label } from "@/components/ui";

export default function RegisterPage() {
  const router = useRouter();
  const setSession = useAuthStore((s) => s.setSession);
  const [form, setForm] = useState({
    organization_name: "",
    full_name: "",
    email: "",
    password: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function set(key: keyof typeof form) {
    return (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((f) => ({ ...f, [key]: e.target.value }));
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await api.post<import("@/lib/types").LoginResponse>(
        "/api/v1/auth/register",
        form,
      );
      setSession(res.access_token, res.user, res.organization);
      router.replace("/dashboard");
    } catch (err) {
      const msg =
        err instanceof Error
          ? err.message.replace(/^\[|\]$/g, "")
          : "Registration failed";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={submit} className="space-y-4">
      <h1 className="text-lg font-semibold">Create your organization</h1>
      <p className="text-xs text-[var(--muted-foreground)]">
        You will be the owner. Invite engineers and operators afterwards in
        Settings → Users.
      </p>
      {error && <ErrorState message={error} />}
      <div>
        <Label>Organization name</Label>
        <Input required minLength={2} value={form.organization_name} onChange={set("organization_name")} placeholder="PT Maju Manufaktur" />
      </div>
      <div>
        <Label>Full name</Label>
        <Input required value={form.full_name} onChange={set("full_name")} placeholder="Your name" />
      </div>
      <div>
        <Label>Email</Label>
        <Input required type="email" value={form.email} onChange={set("email")} placeholder="you@company.com" />
      </div>
      <div>
        <Label>Password (min 8 characters)</Label>
        <Input required minLength={8} type="password" value={form.password} onChange={set("password")} placeholder="••••••••" />
      </div>
      <Button type="submit" variant="accent" className="w-full" disabled={loading}>
        {loading ? "Creating…" : "Create organization"}
      </Button>
      <p className="text-center text-xs text-[var(--muted-foreground)]">
        Already registered?{" "}
        <Link href="/login" className="text-[var(--accent)] hover:underline">
          Sign in
        </Link>
      </p>
    </form>
  );
}
