"use client";

// ML Laboratory (Module G): experiment browser + an educational,
// clearly-separated reinforcement-learning simulation for maintenance
// scheduling. The RL sim runs entirely in the browser on synthetic dynamics —
// it is NOT connected to production recommendations.
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Line, LineChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Legend } from "recharts";
import { api } from "@/lib/api";
import { fmtNum } from "@/lib/format";
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState, Skeleton, Table, Td, Th,
} from "@/components/ui";
import type { Experiment, Page } from "@/lib/types";

/** Tiny tabular Q-learning demo: schedule (inspect/ignore) for a degrading machine.
 * Educational only — synthetic reward, no production coupling. */
function rlSimulation(episodes: number, alpha = 0.1, gamma = 0.95, epsDecay = 0.995) {
  // State: wear bucket 0..4. Actions: 0 = keep running, 1 = maintain (reset wear, cost 8).
  // Reward: production +3/step when running; breakdown costs -25, ends episode.
  const nStates = 5;
  const Q = Array.from({ length: nStates }, () => [0, 0]);
  let epsilon = 1.0;
  const history: { episode: number; reward: number; epsilon: number }[] = [];
  let rngState = 12345;
  const rand = () => {
    rngState = (rngState * 1103515245 + 12345) % 2147483648;
    return rngState / 2147483648;
  };

  for (let ep = 0; ep < episodes; ep++) {
    let s = Math.floor(rand() * 3); // start moderately worn
    let total = 0;
    for (let t = 0; t < 40; t++) {
      const a = rand() < epsilon ? (rand() < 0.5 ? 0 : 1) : Q[s][0] >= Q[s][1] ? 0 : 1;
      let r: number;
      let s2: number;
      if (a === 1) {
        r = -8;
        s2 = 0;
      } else {
        if (s >= 4 && rand() < 0.5) {
          r = -25;
          history.push({ episode: ep, reward: total - 25, epsilon });
          total = -1e9; // mark breakdown
          break;
        }
        r = 3;
        s2 = Math.min(4, s + 1);
      }
      total += r;
      Q[s][a] += alpha * (r + gamma * Math.max(...Q[s2]) - Q[s][a]);
      s = s2;
    }
    epsilon = Math.max(0.05, epsilon * epsDecay);
    if (total !== -1e9) history.push({ episode: ep, reward: total, epsilon });
  }
  const last50 = history.slice(-50).map((h) => h.reward);
  return {
    Q,
    history: history.filter((_, i) => i % Math.max(1, Math.floor(episodes / 60)) === 0),
    avgRewardLast50: last50.reduce((a, b) => a + b, 0) / Math.max(1, last50.length),
  };
}

export default function LabPage() {
  const experiments = useQuery({
    queryKey: ["experiments"],
    queryFn: () => api.get<Page<Experiment>>("/api/v1/experiments?page_size=50"),
  });
  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api.get<Page<{ id: number; name: string; kind: string; rows: number | null; description: string | null }>>("/api/v1/datasets?page_size=50"),
  });

  const [episodes, setEpisodes] = useState(600);
  const [sim, setSim] = useState<ReturnType<typeof rlSimulation> | null>(null);
  const simData = useMemo(() => (sim ? sim.history : []), [sim]);

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Experiments (tracked training runs)</CardTitle>
        </CardHeader>
        <CardContent>
          {experiments.isLoading && <Skeleton className="h-40" />}
          {experiments.data && experiments.data.items.length === 0 && (
            <EmptyState
              title="No experiments recorded"
              hint="Experiments are written by ml/training scripts (JSON reports + optional MLflow)."
              icon="🧪"
            />
          )}
          {experiments.data && experiments.data.items.length > 0 && (
            <Table>
              <thead>
                <tr><Th>Name</Th><Th>Kind</Th><Th>Status</Th><Th>Metrics</Th><Th>Params</Th></tr>
              </thead>
              <tbody>
                {experiments.data.items.map((e) => (
                  <tr key={e.id} className="hover:bg-[var(--border)]/25">
                    <Td className="font-medium">{e.name}</Td>
                    <Td><Badge>{e.kind}</Badge></Td>
                    <Td>{e.status}</Td>
                    <Td className="max-w-[260px] truncate text-[10px] font-mono">
                      {e.metrics ? JSON.stringify(e.metrics).slice(0, 120) : "—"}
                    </Td>
                    <Td className="max-w-[180px] truncate text-[10px]">
                      {e.params ? JSON.stringify(e.params).slice(0, 90) : "—"}
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Datasets</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-xs">
            {datasets.data?.items.map((d) => (
              <div key={d.id} className="rounded-lg border border-[var(--border)] p-2">
                <div className="flex justify-between font-medium">
                  {d.name} <Badge>{d.kind}</Badge>
                </div>
                <div className="text-[var(--muted-foreground)]">
                  {d.rows ? `${d.rows.toLocaleString()} rows` : ""} {d.description ? `· ${d.description}` : ""}
                </div>
              </div>
            ))}
            {datasets.data && datasets.data.items.length === 0 && (
              <EmptyState title="No datasets registered" icon="🗃️" />
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>RL demo — maintenance scheduling (educational)</CardTitle>
            <p className="text-[10px] text-[var(--muted-foreground)]">
              Tabular Q-learning on a synthetic degrading machine. Runs in your
              browser only — deliberately NOT connected to production maintenance
              recommendations.
            </p>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center gap-2">
              <label className="text-xs text-[var(--muted-foreground)]">Episodes: {episodes}</label>
              <input
                type="range"
                min={100}
                max={2000}
                step={100}
                value={episodes}
                onChange={(e) => setEpisodes(Number(e.target.value))}
                className="flex-1 cursor-pointer"
              />
              <Button
                size="sm"
                variant="accent"
                onClick={() => setSim(rlSimulation(episodes))}
              >
                Run
              </Button>
            </div>
            {sim && (
              <>
                <div className="h-48">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={simData}>
                      <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
                      <XAxis dataKey="episode" tick={{ fontSize: 9 }} />
                      <YAxis tick={{ fontSize: 9 }} />
                      <Tooltip contentStyle={{ background: "var(--card)", border: "1px solid var(--border)", fontSize: 10, borderRadius: 8 }} />
                      <Legend wrapperStyle={{ fontSize: 9 }} />
                      <Line type="monotone" dataKey="reward" name="episode reward" stroke="var(--accent)" dot={false} strokeWidth={1.5} />
                      <Line type="monotone" dataKey="epsilon" name="ε" stroke="var(--warning)" dot={false} strokeWidth={1} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="text-xs">
                  Avg reward (last 50): <b>{fmtNum(sim.avgRewardLast50, 1)}</b> · learned policy:{" "}
                  {sim.Q.map((q, s) => (
                    <Badge key={s} className="mr-1">
                      s{s}:{q[1] > q[0] ? "maintain" : "run"}
                    </Badge>
                  ))}
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
