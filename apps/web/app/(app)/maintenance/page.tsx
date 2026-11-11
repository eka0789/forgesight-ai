"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { api } from "@/lib/api";
import { fmtDate, fmtNum, fmtPct, riskColor, statusColor } from "@/lib/format";
import { useAuthStore } from "@/lib/store";
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, Dialog, EmptyState,
  ErrorState, Input, Label, Select, Skeleton, Table, Td, Textarea, Th, useToast,
} from "@/components/ui";
import type { Machine, MachineHealth, MaintenanceRequest, Page, Prediction } from "@/lib/types";

interface SensorReadingRow {
  ts: string;
  air_temperature: number;
  process_temperature: number;
  rotational_speed: number;
  torque: number;
  tool_wear: number;
}

export default function MaintenancePage() {
  const qc = useQueryClient();
  const { show, node } = useToast();
  const user = useAuthStore((s) => s.user);
  const canManage = user?.role === "owner" || user?.role === "admin" || user?.role === "engineer";
  const canApprove = user?.role === "owner" || user?.role === "admin";

  const [healthFor, setHealthFor] = useState<number | null>(null);
  const [chartFor, setChartFor] = useState<number | null>(null);
  const [reqOpen, setReqOpen] = useState(false);
  const [reqForm, setReqForm] = useState({ machine_id: "", title: "", description: "", priority: "medium" });

  const machines = useQuery({
    queryKey: ["machines"],
    queryFn: () => api.get<Page<Machine>>("/api/v1/machines?page_size=100"),
  });
  const predictions = useQuery({
    queryKey: ["predictions"],
    queryFn: () => api.get<Page<Prediction>>("/api/v1/predictions?page_size=10"),
  });
  const requests = useQuery({
    queryKey: ["mreqs"],
    queryFn: () => api.get<Page<MaintenanceRequest>>("/api/v1/maintenance-requests?page_size=15"),
  });

  const health = useQuery({
    queryKey: ["health", healthFor],
    queryFn: () => api.get<MachineHealth>(`/api/v1/machines/${healthFor}/health`),
    enabled: healthFor !== null,
  });

  const readings = useQuery({
    queryKey: ["readings", chartFor],
    queryFn: () =>
      api.get<Page<SensorReadingRow>>(`/api/v1/machines/${chartFor}/readings?page_size=48&days=3`),
    enabled: chartFor !== null,
  });

  const predictAll = useMutation({
    mutationFn: async () => {
      const items = machines.data?.items ?? [];
      const results = [];
      for (const m of items.slice(0, 8)) {
        try {
          const r = await api.post<{ failure_probability: number; risk_level: string }>(
            "/api/v1/predictions/failure",
            { machine_id: m.id },
          );
          results.push({ code: m.code, ...r });
        } catch (e) {
          results.push({ code: m.code, error: (e as Error).message });
        }
      }
      return results;
    },
    onSuccess: () => {
      show("success", "Predictions refreshed from latest sensor readings");
      qc.invalidateQueries({ queryKey: ["predictions"] });
    },
  });

  const createRequest = useMutation({
    mutationFn: () =>
      api.post<MaintenanceRequest>("/api/v1/maintenance-requests", {
        machine_id: Number(reqForm.machine_id),
        title: reqForm.title,
        description: reqForm.description || undefined,
        priority: reqForm.priority,
      }),
    onSuccess: () => {
      show("success", "Maintenance request created");
      setReqOpen(false);
      qc.invalidateQueries({ queryKey: ["mreqs"] });
    },
    onError: (e) => show("error", (e as Error).message),
  });

  const decide = useMutation({
    mutationFn: ({ id, approve }: { id: number; approve: boolean }) =>
      api.post<MaintenanceRequest>(`/api/v1/maintenance-requests/${id}/${approve ? "approve" : "reject"}`),
    onSuccess: (_d, v) => {
      show("success", v.approve ? "Request approved" : "Request rejected");
      qc.invalidateQueries({ queryKey: ["mreqs"] });
    },
    onError: (e) => show("error", (e as Error).message),
  });

  const chartData = (readings.data?.items ?? [])
    .slice()
    .reverse()
    .map((r) => ({
      ...r,
      ts: r.ts.slice(5, 16).replace("T", " "),
      temp_delta: Number((r.process_temperature - r.air_temperature).toFixed(2)),
    }));

  return (
    <div className="space-y-4">
      {node}
      <div className="flex items-center justify-between">
        <div className="text-xs text-[var(--muted-foreground)]">
          Failure classification & RUL come from trained artifacts (RandomForest /
          GradientBoosting on AI4I-style features). Run &ldquo;Predict all&rdquo; to
          refresh predictions from the latest sensor readings.
        </div>
        <div className="flex gap-2">
          {canManage && (
            <Button variant="accent" onClick={() => predictAll.mutate()} disabled={predictAll.isPending}>
              {predictAll.isPending ? "Predicting…" : "Predict all"}
            </Button>
          )}
          {canManage && (
            <Button onClick={() => setReqOpen(true)}>+ Request</Button>
          )}
        </div>
      </div>

      {/* Machine cards */}
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
        {machines.isLoading && Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-36" />)}
        {machines.data?.items.length === 0 && (
          <EmptyState title="No machines" hint="Create machines first (API or seed)." icon="⚙️" />
        )}
        {machines.data?.items.map((m) => (
          <Card key={m.id} className="fsg-fade-in">
            <CardContent className="p-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="text-sm font-semibold">{m.code}</div>
                  <div className="text-xs text-[var(--muted-foreground)]">{m.name}</div>
                </div>
                <Badge className={statusColor[m.status]}>{m.status}</Badge>
              </div>
              <div className="mt-3 flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setHealthFor(m.id)}>
                  Health check
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setChartFor(m.id)}>
                  Sensor history
                </Button>
              </div>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Predictions table */}
      <Card>
        <CardHeader><CardTitle>Latest predictions</CardTitle></CardHeader>
        <CardContent>
          {predictions.data && predictions.data.items.length === 0 && (
            <EmptyState title="No predictions yet" hint="Click Predict all to run the trained model." icon="🔮" />
          )}
          {predictions.data && predictions.data.items.length > 0 && (
            <Table>
              <thead>
                <tr>
                  <Th>#</Th><Th>Machine</Th><Th>p(failure)</Th><Th>Risk</Th>
                  <Th>Health</Th><Th>RUL (h)</Th><Th>Top modes</Th><Th>When</Th>
                </tr>
              </thead>
              <tbody>
                {predictions.data.items.map((p) => (
                  <tr key={p.id} className="hover:bg-[var(--border)]/25">
                    <Td>{p.id}</Td>
                    <Td>{p.machine_id}</Td>
                    <Td>{fmtPct(p.failure_probability)}</Td>
                    <Td><span className={riskColor[p.risk_level]}>{p.risk_level}</span></Td>
                    <Td>{fmtNum(p.health_score, 1)}</Td>
                    <Td>{p.rul_hours !== null ? fmtNum(p.rul_hours, 0) : "—"}</Td>
                    <Td className="text-[10px] max-w-[180px] truncate">
                      {p.predicted_modes
                        ? Object.entries(p.predicted_modes)
                            .filter(([, v]) => v > 0.05)
                            .map(([k, v]) => `${k} ${fmtPct(v, 0)}`)
                            .join(" · ") || "nominal"
                        : "—"}
                    </Td>
                    <Td className="text-[11px]">{fmtDate(p.created_at)}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Requests */}
      <Card>
        <CardHeader><CardTitle>Maintenance requests</CardTitle></CardHeader>
        <CardContent>
          {requests.data && requests.data.items.length === 0 && (
            <EmptyState title="No requests" icon="📋" />
          )}
          {requests.data && requests.data.items.length > 0 && (
            <Table>
              <thead>
                <tr>
                  <Th>#</Th><Th>Machine</Th><Th>Title</Th><Th>Priority</Th>
                  <Th>Status</Th><Th>Source</Th><Th>Actions</Th>
                </tr>
              </thead>
              <tbody>
                {requests.data.items.map((r) => (
                  <tr key={r.id} className="hover:bg-[var(--border)]/25">
                    <Td>{r.id}</Td>
                    <Td>{r.machine_id}</Td>
                    <Td className="max-w-[240px] truncate">{r.title}</Td>
                    <Td>{r.priority}</Td>
                    <Td><Badge className={statusColor[r.status]}>{r.status}</Badge></Td>
                    <Td><Badge>{r.source}</Badge></Td>
                    <Td>
                      {canApprove && r.status === "open" && (
                        <div className="flex gap-1">
                          <Button size="sm" variant="outline" onClick={() => decide.mutate({ id: r.id, approve: true })}>
                            Approve
                          </Button>
                          <Button size="sm" variant="ghost" onClick={() => decide.mutate({ id: r.id, approve: false })}>
                            Reject
                          </Button>
                        </div>
                      )}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Health dialog */}
      <Dialog open={healthFor !== null} onClose={() => setHealthFor(null)} title={`Machine health — ${health.data?.machine_code ?? ""}`}>
        {health.isLoading && <Skeleton className="h-48" />}
        {health.data && (
          <div className="space-y-3 text-sm">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div className="rounded-lg border border-[var(--border)] p-3">
                <div className="text-2xl font-bold">{fmtNum(health.data.health_score, 1)}</div>
                <div className="text-[10px] text-[var(--muted-foreground)]">health score</div>
              </div>
              <div className="rounded-lg border border-[var(--border)] p-3">
                <div className={`text-2xl font-bold ${riskColor[health.data.risk_level]}`}>
                  {fmtPct(health.data.failure_probability, 0)}
                </div>
                <div className="text-[10px] text-[var(--muted-foreground)]">p(failure)</div>
              </div>
              <div className="rounded-lg border border-[var(--border)] p-3">
                <div className="text-2xl font-bold">
                  {health.data.rul_hours !== null ? fmtNum(health.data.rul_hours, 0) : "—"}
                </div>
                <div className="text-[10px] text-[var(--muted-foreground)]">RUL hours</div>
              </div>
            </div>
            {health.data.note && <div className="rounded-lg bg-[var(--warning)]/10 p-2 text-xs text-[var(--warning)]">{health.data.note}</div>}
            {health.data.predicted_modes && (
              <div className="text-xs">
                <b>Failure modes:</b>{" "}
                {Object.entries(health.data.predicted_modes).map(([k, v]) => (
                  <Badge key={k} className="mr-1">{k} {fmtPct(v, 0)}</Badge>
                ))}
              </div>
            )}
            {health.data.recommendations && (
              <ul className="list-disc space-y-1 pl-4 text-xs">
                {health.data.recommendations.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
            )}
            <div className="text-[10px] text-[var(--muted-foreground)]">
              model: {health.data.model_version} {health.data.is_prediction_available ? "(trained artifact)" : "(rules fallback)"}
            </div>
          </div>
        )}
        {health.error && <ErrorState message={(health.error as Error).message} />}
      </Dialog>

      {/* Sensor chart dialog */}
      <Dialog open={chartFor !== null} onClose={() => setChartFor(null)} title="Sensor history (last 3 days)" wide>
        {readings.isLoading && <Skeleton className="h-64" />}
        {chartData.length === 0 && !readings.isLoading && <EmptyState title="No readings" icon="📉" />}
        {chartData.length > 0 && (
          <div className="h-72">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="ts" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", fontSize: 11, borderRadius: 8 }} />
                <Legend wrapperStyle={{ fontSize: 10 }} />
                <Line type="monotone" dataKey="temp_delta" name="ΔT (K)" stroke="var(--danger)" dot={false} strokeWidth={1.5} />
                <Line type="monotone" dataKey="torque" name="torque (Nm)" stroke="var(--accent)" dot={false} strokeWidth={1.5} />
                <Line type="monotone" dataKey="rotational_speed" name="rpm" stroke="var(--success)" dot={false} strokeWidth={1.5} />
                <Line type="monotone" dataKey="tool_wear" name="wear (min)" stroke="var(--warning)" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        )}
        {readings.error && <ErrorState message={(readings.error as Error).message} />}
      </Dialog>

      {/* Create request dialog */}
      <Dialog open={reqOpen} onClose={() => setReqOpen(false)} title="Create maintenance request">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            createRequest.mutate();
          }}
          className="space-y-3"
        >
          <div>
            <Label>Machine</Label>
            <Select required value={reqForm.machine_id} onChange={(e) => setReqForm({ ...reqForm, machine_id: e.target.value })}>
              <option value="">— select —</option>
              {machines.data?.items.map((m) => (
                <option key={m.id} value={m.id}>{m.code} · {m.name}</option>
              ))}
            </Select>
          </div>
          <div>
            <Label>Title</Label>
            <Input required minLength={3} value={reqForm.title} onChange={(e) => setReqForm({ ...reqForm, title: e.target.value })} />
          </div>
          <div>
            <Label>Description</Label>
            <Textarea value={reqForm.description} onChange={(e) => setReqForm({ ...reqForm, description: e.target.value })} />
          </div>
          <div>
            <Label>Priority</Label>
            <Select value={reqForm.priority} onChange={(e) => setReqForm({ ...reqForm, priority: e.target.value })}>
              <option value="low">low</option>
              <option value="medium">medium</option>
              <option value="high">high</option>
              <option value="urgent">urgent</option>
            </Select>
          </div>
          <Button type="submit" variant="accent" className="w-full" disabled={createRequest.isPending}>
            {createRequest.isPending ? "Creating…" : "Create request"}
          </Button>
        </form>
      </Dialog>
    </div>
  );
}
