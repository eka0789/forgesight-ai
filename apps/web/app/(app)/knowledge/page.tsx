"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { fmtBytes, fmtDate, statusColor } from "@/lib/format";
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, EmptyState,
  ErrorState, Input, Skeleton, Tabs, Table, Td, Th, useToast,
} from "@/components/ui";
import type { ChatResponse, Citation, DocumentOut, Page } from "@/lib/types";

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  citations?: Citation[];
  provider?: string;
  hasContext?: boolean;
}

export default function KnowledgePage() {
  const qc = useQueryClient();
  const { show, node } = useToast();
  const [tab, setTab] = useState("chat");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [input, setInput] = useState("");
  const [conversationId, setConversationId] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);

  const docs = useQuery({
    queryKey: ["documents"],
    queryFn: () => api.get<Page<DocumentOut>>("/api/v1/knowledge/documents?page_size=50"),
    refetchInterval: (q) =>
      q.state.data?.items.some((d) => d.status === "processing" || d.status === "pending")
        ? 2500
        : false,
  });

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<DocumentOut>("/api/v1/knowledge/upload", form);
    },
    onSuccess: (d) => {
      show("success", `${d.filename} queued for indexing`);
      qc.invalidateQueries({ queryKey: ["documents"] });
    },
    onError: (e) => show("error", (e as Error).message),
  });

  const chat = useMutation({
    mutationFn: (message: string) =>
      api.post<ChatResponse>("/api/v1/knowledge/chat", {
        message,
        conversation_id: conversationId,
      }),
    onSuccess: (res) => {
      setConversationId(res.conversation_id);
      setMessages((m) => [
        ...m,
        {
          role: "assistant",
          content: res.answer,
          citations: res.citations,
          provider: res.llm_provider,
          hasContext: res.has_context,
        },
      ]);
    },
    onError: (e) => show("error", (e as Error).message),
  });

  const removeDoc = useMutation({
    mutationFn: (id: number) => api.delete(`/api/v1/knowledge/documents/${id}`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["documents"] }),
  });

  function send() {
    const msg = input.trim();
    if (!msg) return;
    setMessages((m) => [...m, { role: "user", content: msg }]);
    setInput("");
    chat.mutate(msg);
  }

  return (
    <div className="space-y-4">
      {node}
      <Tabs
        value={tab}
        onChange={setTab}
        tabs={[
          { key: "chat", label: "RAG Chat" },
          { key: "docs", label: `Documents (${docs.data?.total ?? 0})` },
        ]}
      />

      {tab === "chat" && (
        <Card className="flex flex-col" style={{ height: "calc(100vh - 220px)", minHeight: 420 }}>
          <CardHeader className="border-b border-[var(--border)]">
            <CardTitle>Industrial Knowledge Assistant</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 space-y-3 overflow-y-auto">
            {messages.length === 0 && (
              <EmptyState
                title="Ask anything about your uploaded documents"
                hint="Answers are grounded in retrieved chunks with citations. When the answer is not in your documents, the assistant says so — it never fabricates."
                icon="📚"
              />
            )}
            {messages.map((m, i) => (
              <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
                <div
                  className={`max-w-[85%] rounded-xl px-3 py-2 text-sm ${
                    m.role === "user"
                      ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
                      : "border border-[var(--border)] bg-[var(--card)]"
                  }`}
                >
                  <div className="whitespace-pre-wrap">{m.content}</div>
                  {m.citations && m.citations.length > 0 && (
                    <div className="mt-2 space-y-1 border-t border-[var(--border)] pt-2">
                      <div className="text-[10px] font-semibold text-[var(--muted-foreground)]">SOURCES</div>
                      {m.citations.map((c) => (
                        <div key={c.index} className="rounded border border-[var(--border)] bg-[var(--border)]/25 p-1.5 text-[10px]">
                          <span className="font-medium">[{c.index}] {c.document_title}</span>
                          {c.page_number && <span className="text-[var(--muted-foreground)]"> · page {c.page_number}</span>}
                          {c.quote && <div className="mt-0.5 line-clamp-2 text-[var(--muted-foreground)]">“{c.quote}”</div>}
                        </div>
                      ))}
                    </div>
                  )}
                  {m.provider && (
                    <div className="mt-1 text-[9px] text-[var(--muted-foreground)]">
                      provider: {m.provider}
                      {m.hasContext === false && " · refused (no context)"}
                    </div>
                  )}
                </div>
              </div>
            ))}
            {chat.isPending && (
              <div className="text-xs text-[var(--muted-foreground)]">Retrieving & generating…</div>
            )}
            <div ref={chatEndRef} />
          </CardContent>
          <div className="border-t border-[var(--border)] p-3">
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    send();
                  }
                }}
                placeholder="e.g. What is the maintenance interval for pump FP-200?"
              />
              <Button variant="accent" onClick={send} disabled={chat.isPending || !input.trim()}>
                Send
              </Button>
            </div>
          </div>
        </Card>
      )}

      {tab === "docs" && (
        <Card>
          <CardHeader className="flex items-center justify-between">
            <CardTitle>Knowledge documents</CardTitle>
            <div>
              <input
                ref={fileRef}
                type="file"
                hidden
                accept=".pdf,.txt,.docx,.csv,.md"
                onChange={(e) => {
                  const f = e.target.files?.[0];
                  if (f) upload.mutate(f);
                  e.target.value = "";
                }}
              />
              <Button variant="accent" onClick={() => fileRef.current?.click()} disabled={upload.isPending}>
                {upload.isPending ? "Uploading…" : "+ Upload document"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            <p className="mb-3 text-[11px] text-[var(--muted-foreground)]">
              Supported: PDF, TXT, DOCX, CSV, MD (max 50 MB). Ingestion runs in the
              background: text extraction → chunking → embeddings → hybrid index
              (vector + keyword, RRF fusion).
            </p>
            {docs.isLoading && <Skeleton className="h-40" />}
            {docs.error && <ErrorState message={(docs.error as Error).message} />}
            {docs.data && docs.data.items.length === 0 && (
              <EmptyState title="No documents" hint="Upload manuals, SOPs, or specs — the RAG chat uses them as its knowledge base." icon="📄" />
            )}
            {docs.data && docs.data.items.length > 0 && (
              <Table>
                <thead>
                  <tr>
                    <Th>#</Th><Th>Title</Th><Th>Status</Th><Th>Chunks</Th>
                    <Th>Pages</Th><Th>Size</Th><Th>Uploaded</Th><Th></Th>
                  </tr>
                </thead>
                <tbody>
                  {docs.data.items.map((d) => (
                    <tr key={d.id} className="hover:bg-[var(--border)]/25">
                      <Td>{d.id}{d.is_demo && <Badge className="ml-1">demo</Badge>}</Td>
                      <Td className="max-w-[220px] truncate font-medium">{d.title}</Td>
                      <Td>
                        <Badge className={statusColor[d.status]}>{d.status}</Badge>
                        {d.status === "failed" && d.error && (
                          <div className="mt-1 max-w-[200px] truncate text-[10px] text-[var(--danger)]" title={d.error}>
                            {d.error}
                          </div>
                        )}
                      </Td>
                      <Td>{d.chunk_count}</Td>
                      <Td>{d.page_count ?? "—"}</Td>
                      <Td>{fmtBytes(d.size_bytes)}</Td>
                      <Td className="text-[11px]">{fmtDate(d.created_at)}</Td>
                      <Td>
                        <Button size="sm" variant="ghost" onClick={() => removeDoc.mutate(d.id)}>
                          Delete
                        </Button>
                      </Td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
