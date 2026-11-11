"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { fmtDate, statusColor } from "@/lib/format";
import { useAuthStore } from "@/lib/store";
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, Dialog,
  ErrorState, Input, Label, Select, Skeleton, Table, Td, Th, useToast,
} from "@/components/ui";
import type { Page, User } from "@/lib/types";

export default function SettingsPage() {
  const qc = useQueryClient();
  const { show, node } = useToast();
  const { user, organization } = useAuthStore();
  const [inviteOpen, setInviteOpen] = useState(false);
  const [invite, setInvite] = useState({ email: "", full_name: "", role: "viewer", password: "" });

  const users = useQuery({
    queryKey: ["users"],
    queryFn: () => api.get<Page<User>>("/api/v1/users?page_size=100"),
    enabled: user?.role === "owner" || user?.role === "admin",
  });

  const createUser = useMutation({
    mutationFn: () => api.post<User>("/api/v1/users", invite),
    onSuccess: () => {
      show("success", "User created");
      setInviteOpen(false);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (e) => show("error", (e as Error).message),
  });

  const updateUser = useMutation({
    mutationFn: ({ id, patch }: { id: number; patch: Partial<User> }) =>
      api.patch<User>(`/api/v1/users/${id}`, patch),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["users"] }),
    onError: (e) => show("error", (e as Error).message),
  });

  const isManager = user?.role === "owner" || user?.role === "admin";

  return (
    <div className="space-y-4">
      {node}
      <Card>
        <CardHeader><CardTitle>Organization</CardTitle></CardHeader>
        <CardContent className="grid gap-3 text-sm md:grid-cols-3">
          <div className="rounded-lg border border-[var(--border)] p-3">
            <div className="text-[10px] text-[var(--muted-foreground)]">Name</div>
            <div className="font-medium">{organization?.name ?? "—"}</div>
          </div>
          <div className="rounded-lg border border-[var(--border)] p-3">
            <div className="text-[10px] text-[var(--muted-foreground)]">Slug</div>
            <div className="font-mono text-xs">{organization?.slug ?? "—"}</div>
          </div>
          <div className="rounded-lg border border-[var(--border)] p-3">
            <div className="text-[10px] text-[var(--muted-foreground)]">Mode</div>
            {organization?.is_demo ? (
              <Badge className="bg-[var(--warning)]/15 text-[var(--warning)]">DEMO DATA</Badge>
            ) : (
              <Badge className={statusColor.healthy}>production</Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {isManager && (
        <Card>
          <CardHeader className="flex items-center justify-between">
            <CardTitle>User management</CardTitle>
            <Button variant="accent" onClick={() => setInviteOpen(true)}>+ Add user</Button>
          </CardHeader>
          <CardContent>
            {users.isLoading && <Skeleton className="h-40" />}
            {users.error && <ErrorState message={(users.error as Error).message} />}
            {users.data && (
              <Table>
                <thead>
                  <tr>
                    <Th>#</Th><Th>Email</Th><Th>Name</Th><Th>Role</Th>
                    <Th>Active</Th><Th>Joined</Th>
                  </tr>
                </thead>
                <tbody>
                  {users.data.items.map((u) => (
                    <tr key={u.id} className="hover:bg-[var(--border)]/25">
                      <Td>{u.id}</Td>
                      <Td>{u.email}</Td>
                      <Td>{u.full_name}</Td>
                      <Td>
                        <Select
                          className="h-7 text-xs"
                          value={u.role}
                          disabled={u.id === user?.id || u.role === "owner"}
                          onChange={(e) => updateUser.mutate({ id: u.id, patch: { role: e.target.value as User["role"] } })}
                        >
                          <option value="admin">admin</option>
                          <option value="engineer">engineer</option>
                          <option value="operator">operator</option>
                          <option value="viewer">viewer</option>
                        </Select>
                      </Td>
                      <Td>
                        <Badge className={u.is_active ? statusColor.completed : statusColor.failed}>
                          {u.is_active ? "active" : "disabled"}
                        </Badge>
                      </Td>
                      <Td className="text-[11px]">{fmtDate(u.created_at)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
            <p className="mt-2 text-[10px] text-[var(--muted-foreground)]">
              RBAC: owner/admin manage users & approve requests; engineer manages
              machines, inspections, predictions, documents; operator runs
              inspections; viewer read-only.
            </p>
          </CardContent>
        </Card>
      )}

      {!isManager && (
        <Card>
          <CardContent className="p-6 text-sm text-[var(--muted-foreground)]">
            Your role ({user?.role}) does not include user management. Contact an
            organization admin.
          </CardContent>
        </Card>
      )}

      <Dialog open={inviteOpen} onClose={() => setInviteOpen(false)} title="Add user">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createUser.mutate();
          }}
          className="space-y-3"
        >
          <div><Label>Email</Label><Input required type="email" value={invite.email} onChange={(e) => setInvite({ ...invite, email: e.target.value })} /></div>
          <div><Label>Full name</Label><Input required value={invite.full_name} onChange={(e) => setInvite({ ...invite, full_name: e.target.value })} /></div>
          <div><Label>Temporary password (min 8 chars)</Label><Input required minLength={8} type="text" value={invite.password} onChange={(e) => setInvite({ ...invite, password: e.target.value })} /></div>
          <div>
            <Label>Role</Label>
            <Select value={invite.role} onChange={(e) => setInvite({ ...invite, role: e.target.value })}>
              <option value="admin">admin</option>
              <option value="engineer">engineer</option>
              <option value="operator">operator</option>
              <option value="viewer">viewer</option>
            </Select>
          </div>
          <Button type="submit" variant="accent" className="w-full" disabled={createUser.isPending}>
            {createUser.isPending ? "Creating…" : "Create user"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
