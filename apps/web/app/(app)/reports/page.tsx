"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import {
  Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend,
  Line, LineChart,
} from "recharts";
import { api } from "@/lib/api";
import { fmtNum, fmtPct, statusColor } from "@/lib/format";
import {
  Badge, Card, CardContent, CardHeader, CardTitle, EmptyState, Skeleton, Tabs, Table, Td, Th,
} from "@/components/ui";

interface ProductionReport {
  report: string;
  trend: { date: string; inspections: number; defects: number }[];
  machine_status: { status: string; count: number }[];
  kpis: { total_inspections: number; defect_detection_rate: number; avg_machine_health: number };
}
interface QualityReport {
  report: string;
  defect_distribution: { label: string; count: number }[];
  kpis: { total_defects: number; total_inspections: number };
}
interface MaintenanceReport {
  report: string;
  by_status: Record<string, number>;
  by_priority: Record<string, number>;
  recent: { id: number; title: string; status: string; priority: string; source: string }[];
}

export default function ReportsPage() {
  const [tab, setTab] = useState("production");

  const production = useQuery({
    queryKey: ["report-production"],
    queryFn: () => api.get<ProductionReport>("/api/v1/reports/production"),
  });
  const quality = useQuery({
    queryKey: ["report-quality"],
    queryFn: () => api.get<QualityReport>("/api/v1/reports/quality"),
  });
  const maintenance = useQuery({
    queryKey: ["report-maintenance"],
    queryFn: () => api.get<MaintenanceReport>("/api/v1/reports/maintenance"),
  });

  return (
    <div className="space-y-4">
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "production", label: "Production" },
          { key: "quality", label: "Quality" },
          { key: "maintenance", label: "Maintenance" },
        ]}
      />

      {tab === "production" && (
        <div className="space-y-4">
          <Card>
            <CardHeader><CardTitle>Inspections & defects — 14 days</CardTitle></CardHeader>
            <CardContent className="h-72">
              {production.isLoading ? (
                <Skeleton className="h-full" />
              ) : production.data?.trend.every((p) => p.inspections === 0) ? (
                <EmptyState title="No data" icon="📊" />
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={production.data?.trend ?? []}>
                    <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                    <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(v: string) => v.slice(5)} />
                    <YAxis tick={{ fontSize: 9 }} allowDecimals={false} />
                    <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", fontSize: 11, borderRadius: 8 }} />
                    <Legend wrapperStyle={{ fontSize: 10 }} />
                    <Line type="monotone" dataKey="inspections" stroke="var(--accent)" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="defects" stroke="var(--danger)" strokeWidth={2} dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </CardContent>
          </Card>
          <div className="grid gap-3 md:grid-cols-3">
            {production.data && (
              <>
                <Card><CardContent className="p-4 text-center">
                  <div className="text-2xl font-bold">{production.data.kpis.total_inspections}</div>
                  <div className="text-[10px] text-[var(--muted-foreground)]">total inspections</div>
                </CardContent></Card>
                <Card><CardContent className="p-4 text-center">
                  <div className="text-2xl font-bold">{fmtPct(production.data.kpis.defect_detection_rate)}</div>
                  <div className="text-[10px] text-[var(--muted-foreground)]">defect rate</div>
                </CardContent></Card>
                <Card><CardContent className="p-4 text-center">
                  <div className="text-2xl font-bold">{fmtNum(production.data.kpis.avg_machine_health, 1)}</div>
                  <div className="text-[10px] text-[var(--muted-foreground)]">avg machine health</div>
                </CardContent></Card>
              </>
            )}
          </div>
        </div>
      )}

      {tab === "quality" && (
        <Card>
          <CardHeader><CardTitle>Defect distribution</CardTitle></CardHeader>
          <CardContent className="h-80">
            {quality.isLoading ? (
              <Skeleton className="h-full" />
            ) : quality.data?.defect_distribution.length === 0 ? (
              <EmptyState title="No defects recorded" icon="✅" />
            ) : (
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={quality.data?.defect_distribution ?? []}>
                  <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                  <XAxis dataKey="label" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                  <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", fontSize: 11, borderRadius: 8 }} />
                  <Bar dataKey="count" fill="var(--danger)" radius={[6, 6, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "maintenance" && (
        <div className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2">
            <Card>
              <CardHeader><CardTitle>By status</CardTitle></CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {Object.entries(maintenance.data?.by_status ?? {}).map(([k, v]) => (
                  <Badge key={k} className={statusColor[k]}>{k}: {v}</Badge>
                ))}
                {maintenance.data && Object.keys(maintenance.data.by_status).length === 0 && (
                  <EmptyState title="No requests" icon="📋" />
                )}
              </CardContent>
            </Card>
            <Card>
              <CardHeader><CardTitle>By priority</CardTitle></CardHeader>
              <CardContent className="flex flex-wrap gap-2">
                {Object.entries(maintenance.data?.by_priority ?? {}).map(([k, v]) => (
                  <Badge key={k}>{k}: {v}</Badge>
                ))}
              </CardContent>
            </Card>
          </div>
          <Card>
            <CardHeader><CardTitle>Recent requests</CardTitle></CardHeader>
            <CardContent>
              <Table>
                <thead>
                  <tr><Th>#</Th><Th>Title</Th><Th>Status</Th><Th>Priority</Th><Th>Source</Th></tr>
                </thead>
                <tbody>
                  {maintenance.data?.recent.map((r) => (
                    <tr key={r.id}>
                      <Td>{r.id}</Td>
                      <Td className="max-w-[260px] truncate">{r.title}</Td>
                      <Td><Badge className={statusColor[r.status]}>{r.status}</Badge></Td>
                      <Td>{r.priority}</Td>
                      <Td><Badge>{r.source}</Badge></Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
