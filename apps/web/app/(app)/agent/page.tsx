"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Bot, ShieldAlert, Wrench } from "lucide-react";
import { api } from "@/lib/api";
import { fmtDate, statusColor } from "@/lib/format";
import { useAuthStore } from "@/lib/store";
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState,
  Input, Skeleton, Tabs, Table, Td, Th, useToast,
} from "@/components/ui";
import type { AgentChatResult, AgentExecution, AgentTool, Page } from "@/lib/types";

interface Turn {
  role: "user" | "assistant" | "system";
  content: string;
  tools?: { tool: string; status: string }[];
  planner?: string;
  approval?: { tool: string; executionId: number } | null;
}

export default function AgentPage() {
  const qc = useQueryClient();
  const { show, node } = useToast();
  const user = useAuthStore((s) => s.user);
  const canApprove = user?.role === "owner" || user?.role === "admin";
  const [tab, setTab] = useState("chat");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");

  const tools = useQuery({
    queryKey: ["agent-tools"],
    queryFn: () => api.get<{ tools: AgentTool[]; max_iterations: number; note: string }>("/api/v1/agent/tools"),
  });
  const executions = useQuery({
    queryKey: ["agent-executions"],
    queryFn: () => api.get<Page<AgentExecution>>("/api/v1/agent/executions?page_size=20"),
  });

  const run = useMutation({
    mutationFn: (message: string) => api.post<AgentChatResult>("/api/v1/agent/chat", { message }),
    onSuccess: (res) => {
      const answer =
        res.status === "awaiting_approval"
          ? `⏸ Tool **${res.approval_required?.tool}** requires human approval before it can run.\n\nExecution #${res.execution_id} is parked in 'awaiting_approval'. ${canApprove ? "You can approve below (Approvals tab)." : "An admin/owner must approve it."}`
          : res.answer ?? "(no answer text)";
      setTurns((t) => [
        ...t,
        {
          role: "assistant",
          content: answer,
          tools: res.tool_results.map((t) => ({ tool: t.tool, status: t.status })),
          planner: res.planner,
          approval:
            res.status === "awaiting_approval"
              ? { tool: res.approval_required?.tool ?? "", executionId: res.execution_id }
              : null,
        },
      ]);
    },
    onError: (e) => show("error", (e as Error).message),
  });

  const decide = useMutation({
    mutationFn: ({ executionId, approve }: { executionId: number; approve: boolean }) =>
      api.post(`/api/v1/agent/approvals/${executionId}`, { approve }),
    onSuccess: (_d, v) => {
      show("success", v.approve ? "Approved — tool executed" : "Rejected — no action taken");
      qc.invalidateQueries({ queryKey: ["agent-executions"] });
    },
    onError: (e) => show("error", (e as Error).message),
  });

  function send() {
    const msg = input.trim();
    if (!msg) return;
    setTurns((t) => [...t, { role: "user", content: msg }]);
    setInput("");
    run.mutate(msg);
  }

  return (
    <div className="space-y-4">
      {node}
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "chat", label: "Agent workspace" },
          { key: "executions", label: `Executions (${executions.data?.total ?? 0})` },
          { key: "tools", label: "Tools" },
        ]}
      />

      {tab === "chat" && (
        <div className="grid gap-4 lg:grid-cols-3">
          <Card className="flex flex-col lg:col-span-2" style={{ height: "calc(100vh - 230px)", minHeight: 440 }}>
            <CardHeader className="border-b border-[var(--border)]">
              <CardTitle className="flex items-center gap-2">
                <Bot className="h-4 w-4" /> Operations Agent
                <Badge>planner: LLM or rule-based</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent className="flex-1 space-y-3 overflow-y-auto">
              {turns.length === 0 && (
                <EmptyState
                  title="Ask the agent to operate"
                  hint="Try: 'what is the status of machine 1', 'predict failure for machine 1', 'create a maintenance request for machine 1 urgent'. Sensitive actions require human approval."
                  icon="🤖"
                />
              )}
              {turns.map((t, i) => (
                <div key={i} className={`flex ${t.role === "user" ? "justify-end" : "justify-start"}`}>
                  <div
                    className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                      t.role === "user"
                        ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                        : "border border-[var(--border)] bg-[var(--card)]"
                    }`}
                  >
                    <div className="whitespace-pre-wrap">{t.content}</div>
                    {t.tools && t.tools.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1">
                        {t.tools.map((tl, j) => (
                          <Badge key={j} className={tl.status === "error" ? "bg-[var(--danger)]/15 text-[var(--danger)]" : "bg-[var(--success)]/15 text-[var(--success)]"}>
                            {tl.tool}
                          </Badge>
                        ))}
                        {t.planner && <Badge>planner: {t.planner}</Badge>}
                      </div>
                    )}
                    {t.approval && canApprove && (
                      <div className="mt-2 flex gap-2">
                        <Button
                          size="sm"
                          variant="accent"
                          onClick={() => decide.mutate({ executionId: t.approval!.executionId, approve: true })}
                          disabled={decide.isPending}
                        >
                          <ShieldAlert className="h-3.5 w-3.5" /> Approve & execute
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => decide.mutate({ executionId: t.approval!.executionId, approve: false })}
                          disabled={decide.isPending}
                        >
                          Reject
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {run.isPending && <div className="text-xs text-[var(--muted-foreground)]">Agent planning & executing tools…</div>}
            </CardContent>
            <div className="border-t border-[var(--border)] p-3">
              <div className="flex gap-2">
                <Input
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && send()}
                  placeholder="Give the agent an operational task…"
                />
                <Button variant="accent" onClick={send} disabled={run.isPending || !input.trim()}>
                  Run
                </Button>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Tool catalog</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 text-xs">
              {tools.data?.tools.map((t) => (
                <div key={t.name} className="rounded-lg border border-[var(--border)] p-2">
                  <div className="flex items-center justify-between gap-1">
                    <span className="flex items-center gap-1 font-mono font-medium">
                      <Wrench className="h-3 w-3" /> {t.name}
                    </span>
                    {t.requires_approval && (
                      <Badge className="bg-[var(--warning)]/15 text-[var(--warning)]">approval</Badge>
                    )}
                  </div>
                  <div className="mt-1 text-[var(--muted-foreground)]">{t.description}</div>
                </div>
              ))}
              <div className="text-[10px] text-[var(--muted-foreground)]">
                {tools.data?.note} Max iterations: {tools.data?.max_iterations}. Tool
                timeout: 30s. All tool calls are logged per execution.
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {tab === "executions" && (
        <Card>
          <CardHeader><CardTitle>Agent executions (audit trail)</CardTitle></CardHeader>
          <CardContent>
            {executions.isLoading && <Skeleton className="h-40" />}
            {executions.data && executions.data.items.length === 0 && (
              <EmptyState title="No executions yet" icon="🤖" />
            )}
            {executions.data && executions.data.items.length > 0 && (
              <Table>
                <thead>
                  <tr>
                    <Th>#</Th><Th>Input</Th><Th>Status</Th><Th>Planner</Th>
                    <Th>Iterations</Th><Th>Started</Th><Th>Finished</Th>
                  </tr>
                </thead>
                <tbody>
                  {executions.data.items.map((e) => (
                    <tr key={e.id} className="hover:bg-[var(--border)]/25">
                      <Td>{e.id}</Td>
                      <Td className="max-w-[260px] truncate">{e.input}</Td>
                      <Td><Badge className={statusColor[e.status]}>{e.status}</Badge></Td>
                      <Td><Badge>{e.planner}</Badge></Td>
                      <Td>{e.iterations}</Td>
                      <Td className="text-[11px]">{fmtDate(e.started_at)}</Td>
                      <Td className="text-[11px]">{fmtDate(e.finished_at)}</Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}

      {tab === "tools" && (
        <Card>
          <CardHeader><CardTitle>Tool catalog & permissions</CardTitle></CardHeader>
          <CardContent>
            <Table>
              <thead>
                <tr><Th>Tool</Th><Th>Description</Th><Th>Args</Th><Th>Approval</Th></tr>
              </thead>
              <tbody>
                {tools.data?.tools.map((t) => (
                  <tr key={t.name}>
                    <Td className="font-mono text-xs">{t.name}</Td>
                    <Td className="text-xs">{t.description}</Td>
                    <Td className="text-[10px]">{t.args_schema.join(", ")}</Td>
                    <Td>{t.requires_approval ? <Badge className="bg-[var(--warning)]/15 text-[var(--warning)]">required</Badge> : <Badge>auto</Badge>}</Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
