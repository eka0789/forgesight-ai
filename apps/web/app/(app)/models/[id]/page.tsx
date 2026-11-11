"use client";

import { useQuery } from "@tanstack/react-query";
import { useParams } from "next/navigation";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { api } from "@/lib/api";
import { statusColor } from "@/lib/format";
import { Badge, Card, CardContent, CardHeader, CardTitle, ErrorState, Skeleton, Table, Td, Th } from "@/components/ui";
import type { MLModel } from "@/lib/types";

interface MetricsResponse {
  model_id: number;
  versions: {
    version: string;
    status: string;
    framework: string;
    metrics: Record<string, unknown> | null;
    params: Record<string, unknown> | null;
  }[];
  metric_rows: { version_id: number; split: string; name: string; value: number }[];
}

export default function ModelDetailPage() {
  const params = useParams<{ id: string }>();
  const id = Number(params.id);

  const model = useQuery({
    queryKey: ["model", id],
    queryFn: () => api.get<MLModel>(`/api/v1/models/${id}`),
  });
  const metrics = useQuery({
    queryKey: ["model-metrics", id],
    queryFn: () => api.get<MetricsResponse>(`/api/v1/models/${id}/metrics`),
  });

  if (model.isLoading) return <Skeleton className="h-64" />;
  if (model.error) return <ErrorState message={(model.error as Error).message} />;
  const m = model.data;
  if (!m) return null;

  const chartData = (metrics.data?.metric_rows ?? [])
    .filter((r) => ["accuracy", "f1", "recall", "precision", "roc_auc", "r2", "mae", "rmse", "silhouette"].includes(r.name))
    .map((r) => ({ name: `${r.name} (${r.split})`, value: r.value }));

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-bold">{m.name}</h1>
        <p className="text-xs text-[var(--muted-foreground)]">{m.description}</p>
      </div>

      <Card>
        <CardHeader><CardTitle>Versions</CardTitle></CardHeader>
        <CardContent>
          <Table>
            <thead>
              <tr><Th>Version</Th><Th>Status</Th><Th>Framework</Th><Th>Artifact</Th></tr>
            </thead>
            <tbody>
              {m.versions.map((v) => (
                <tr key={v.id}>
                  <Td className="font-medium">{v.version}</Td>
                  <Td><Badge className={statusColor[v.status]}>{v.status}</Badge></Td>
                  <Td>{v.framework}</Td>
                  <Td className="max-w-[260px] truncate text-[10px] text-[var(--muted-foreground)]">{v.artifact_path ?? "—"}</Td>
                </tr>
              ))}
            </tbody>
          </Table>
        </CardContent>
      </Card>

      {chartData.length > 0 && (
        <Card>
          <CardHeader><CardTitle>Metric rows (per split)</CardTitle></CardHeader>
          <CardContent className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={chartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                <XAxis dataKey="name" tick={{ fontSize: 9 }} />
                <YAxis tick={{ fontSize: 9 }} />
                <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", fontSize: 11, borderRadius: 8 }} />
                <Bar dataKey="value" fill="var(--accent)" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}

      {metrics.data?.versions.some((v) => v.metrics) && (
        <Card>
          <CardHeader><CardTitle>Full metrics & params (JSON)</CardTitle></CardHeader>
          <CardContent className="space-y-3">
            {metrics.data.versions.filter((v) => v.metrics).map((v) => (
              <div key={v.version}>
                <div className="mb-1 text-xs font-semibold">{v.version} <Badge className={statusColor[v.status]}>{v.status}</Badge></div>
                <pre className="max-h-72 overflow-auto rounded-lg border border-[var(--border)] bg-[var(--border)]/20 p-3 text-[10px] leading-relaxed">
                  {JSON.stringify({ metrics: v.metrics, params: v.params }, null, 2)}
                </pre>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
