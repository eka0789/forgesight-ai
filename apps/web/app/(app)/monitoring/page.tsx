"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { fmtNum } from "@/lib/format";
import {
  Badge, Card, CardContent, CardHeader, CardTitle, EmptyState, ErrorState, Skeleton, Table, Td, Th,
} from "@/components/ui";
import type { DriftReport, HealthStatus } from "@/lib/types";

interface MetricsSnapshot {
  uptime_seconds: number;
  ts: string;
  org: Record<string, number>;
}

export default function MonitoringPage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.get<HealthStatus>("/api/v1/monitoring/health"),
    refetchInterval: 15_000,
  });
  const snapshot = useQuery({
    queryKey: ["monitoring-metrics"],
    queryFn: () => api.get<MetricsSnapshot>("/api/v1/monitoring/metrics"),
    refetchInterval: 15_000,
  });
  const drift = useQuery({
    queryKey: ["drift"],
    queryFn: () => api.get<DriftReport>("/api/v1/monitoring/drift?days=7"),
  });

  const dot = (v: string) =>
    v === "up" || v === "ok" || v === "healthy"
      ? "text-[var(--success)]"
      : v === "down" || v === "missing"
        ? "text-[var(--danger)]"
        : "text-[var(--warning)]";

  return (
    <div className="space-y-4">
      {/* Health */}
      <Card>
        <CardHeader>
          <CardTitle>System health</CardTitle>
        </CardHeader>
        <CardContent>
          {health.isLoading && <Skeleton className="h-32" />}
          {health.data && (
            <div className="grid grid-cols-2 gap-3 text-sm md:grid-cols-4">
              <div className="rounded-lg border border-[var(--border)] p-3">
                <div className={`text-lg font-bold ${dot(health.data.status)}`}>{health.data.status}</div>
                <div className="text-[10px] text-[var(--muted-foreground)]">overall · v{health.data.version}</div>
              </div>
              {[
                ["Database", health.data.database],
                ["Redis", health.data.redis],
                ["Storage", health.data.storage],
                ["Artifacts", health.data.artifacts],
              ].map(([label, v]) => (
                <div key={label} className="rounded-lg border border-[var(--border)] p-3">
                  <div className={`font-semibold ${dot(v)}`}>{v}</div>
                  <div className="text-[10px] text-[var(--muted-foreground)]">{label}</div>
                </div>
              ))}
              <div className="col-span-2 rounded-lg border border-[var(--border)] p-3 text-xs md:col-span-4">
                <Badge>LLM: {health.data.llm_provider}</Badge>{" "}
                <Badge>Embeddings: {health.data.embedding_provider}</Badge>{" "}
                <Badge>Prometheus: <code>/metrics</code> scrape target</Badge>{" "}
                <Badge>Grafana: :3001 (compose)</Badge>
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Org metrics snapshot */}
      <Card>
        <CardHeader><CardTitle>Live counters (this organization)</CardTitle></CardHeader>
        <CardContent>
          {snapshot.data ? (
            <div className="grid grid-cols-2 gap-3 md:grid-cols-6">
              {Object.entries(snapshot.data.org).map(([k, v]) => (
                <div key={k} className="rounded-lg border border-[var(--border)] p-3 text-center">
                  <div className="text-xl font-bold">{v}</div>
                  <div className="text-[10px] text-[var(--muted-foreground)]">{k.replace(/_/g, " ")}</div>
                </div>
              ))}
              <div className="col-span-2 text-[10px] text-[var(--muted-foreground)] md:col-span-6">
                uptime {fmtNum(snapshot.data.uptime_seconds / 60, 1)} min · updated {snapshot.data.ts.slice(11, 19)} UTC
              </div>
            </div>
          ) : (
            <Skeleton className="h-24" />
          )}
        </CardContent>
      </Card>

      {/* Drift */}
      <Card>
        <CardHeader>
          <CardTitle>Data drift (PSI vs training reference)</CardTitle>
        </CardHeader>
        <CardContent>
          {drift.isLoading && <Skeleton className="h-32" />}
          {drift.error && <ErrorState message={(drift.error as Error).message} />}
          {drift.data && !drift.data.available && (
            <EmptyState title="Drift not available" hint={drift.data.note} icon="📉" />
          )}
          {drift.data?.available && (
            <>
              <div className="mb-3 flex gap-2 text-xs">
                <Badge
                  className={
                    drift.data.verdict === "stable"
                      ? "bg-[var(--success)]/15 text-[var(--success)]"
                      : "bg-[var(--warning)]/15 text-[var(--warning)]"
                  }
                >
                  {drift.data.verdict}
                </Badge>
                <Badge>max PSI {drift.data.max_psi}</Badge>
                <Badge>{drift.data.n_readings} readings / {drift.data.window_days}d</Badge>
              </div>
              <Table>
                <thead>
                  <tr><Th>Feature</Th><Th>PSI</Th><Th>Interpretation</Th></tr>
                </thead>
                <tbody>
                  {Object.entries(drift.data.psi_per_feature ?? {}).map(([k, v]) => (
                    <tr key={k}>
                      <Td className="font-mono text-xs">{k}</Td>
                      <Td>{fmtNum(v, 4)}</Td>
                      <Td className="text-xs text-[var(--muted-foreground)]">
                        {v < 0.1 ? "stable" : v < 0.25 ? "moderate" : "significant"}
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <p className="mt-2 text-[10px] text-[var(--muted-foreground)]">{drift.data.note}</p>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
