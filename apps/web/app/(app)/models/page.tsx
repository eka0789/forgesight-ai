"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { api } from "@/lib/api";
import { fmtDate, fmtNum, statusColor } from "@/lib/format";
import {
  Badge, Card, CardContent, CardHeader, CardTitle, EmptyState, Skeleton, Table, Td, Th,
} from "@/components/ui";
import type { MLModel, Page } from "@/lib/types";

export default function ModelsPage() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["models"],
    queryFn: () => api.get<Page<MLModel>>("/api/v1/models?page_size=50"),
  });

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Model registry</CardTitle>
          <p className="text-[11px] text-[var(--muted-foreground)]">
            Registered from trained artifacts (ml/artifacts). Production models
            serve the API; staging models are tracked but gated.
          </p>
        </CardHeader>
        <CardContent>
          {error && <div className="text-sm text-[var(--danger)]">{(error as Error).message}</div>}
          {isLoading && <Skeleton className="h-40" />}
          {data && data.items.length === 0 && (
            <EmptyState
              title="Registry empty"
              hint="Run ml/training scripts and restart — the registry reads metrics.json from artifacts."
              icon="📦"
            />
          )}
          {data && data.items.length > 0 && (
            <Table>
              <thead>
                <tr>
                  <Th>Model</Th><Th>Task</Th><Th>Latest version</Th><Th>Status</Th>
                  <Th>Framework</Th><Th>Key metrics</Th><Th>Registered</Th><Th></Th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((m) => {
                  const v = m.versions[m.versions.length - 1];
                  return (
                    <tr key={m.id} className="hover:bg-[var(--border)]/25">
                      <Td className="font-medium">{m.name}</Td>
                      <Td><Badge>{m.task}</Badge></Td>
                      <Td>{v?.version ?? "—"}</Td>
                      <Td>
                        {v && <Badge className={statusColor[v.status]}>{v.status}</Badge>}
                      </Td>
                      <Td>{v?.framework ?? "—"}</Td>
                      <Td className="max-w-[220px] truncate text-[10px]">
                        {v?.metrics
                          ? Object.entries(v.metrics)
                              .filter(([, x]) => typeof x === "number")
                              .slice(0, 3)
                              .map(([k, x]) => `${k}=${fmtNum(x as number, 3)}`)
                              .join("  ")
                          : "—"}
                      </Td>
                      <Td className="text-[11px]">{fmtDate(v?.created_at)}</Td>
                      <Td>
                        <Link href={`/models/${m.id}`} className="text-xs text-[var(--accent)] hover:underline">
                          Detail →
                        </Link>
                      </Td>
                    </tr>
                  );
                })}
              </tbody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
