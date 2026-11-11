"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { UploadCloud } from "lucide-react";
import { api, qs } from "@/lib/api";
import { fmtNum, fmtPct, statusColor, fmtDate } from "@/lib/format";
import {
  Badge, Button, Card, CardContent, CardHeader, CardTitle, Dialog, EmptyState,
  ErrorState, Select, Skeleton, Table, Td, Th, useToast,
} from "@/components/ui";
import type { Inspection, InspectionDetail, Machine, Page } from "@/lib/types";

export default function VisionPage() {
  const qc = useQueryClient();
  const { show, node } = useToast();
  const imageRef = useRef<HTMLInputElement>(null);
  const videoRef = useRef<HTMLInputElement>(null);
  const [machineId, setMachineId] = useState("");
  const [detailId, setDetailId] = useState<number | null>(null);
  const [annotatedUrl, setAnnotatedUrl] = useState<string | null>(null);
  const [originalUrl, setOriginalUrl] = useState<string | null>(null);

  const machines = useQuery({
    queryKey: ["machines-mini"],
    queryFn: () => api.get<Page<Machine>>("/api/v1/machines?page_size=100"),
  });
  const history = useQuery({
    queryKey: ["inspections"],
    queryFn: () => api.get<Page<Inspection>>("/api/v1/vision/inspections?page_size=20"),
    refetchInterval: (q) =>
      q.state.data?.items.some((i) => i.status === "processing" || i.status === "pending")
        ? 3000
        : false,
  });

  const inspectImage = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<InspectionDetail>(
        `/api/v1/vision/inspect${qs({ machine_id: machineId || undefined })}`,
        form,
      );
    },
    onSuccess: (res) => {
      show(
        res.defect_count > 0 ? "error" : "success",
        res.defect_count > 0
          ? `${res.defect_count} defect(s) detected (${res.method_used})`
          : "No defects detected",
      );
      setDetailId(res.id);
      qc.invalidateQueries({ queryKey: ["inspections"] });
    },
    onError: (e) => show("error", (e as Error).message),
  });

  const inspectVideo = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api.upload<Inspection>(
        `/api/v1/vision/video${qs({ machine_id: machineId || undefined })}`,
        form,
      );
    },
    onSuccess: () => {
      show("success", "Video queued — processing frames in background");
      qc.invalidateQueries({ queryKey: ["inspections"] });
    },
    onError: (e) => show("error", (e as Error).message),
  });

  const detail = useQuery({
    queryKey: ["inspection", detailId],
    queryFn: () => api.get<InspectionDetail>(`/api/v1/vision/inspections/${detailId}`),
    enabled: detailId !== null,
  });

  async function openDetail(id: number) {
    setAnnotatedUrl(null);
    setOriginalUrl(null);
    setDetailId(id);
    try {
      const [ann, orig] = await Promise.all([
        api.blob(`/api/v1/vision/inspections/${id}/annotated`),
        api.blob(`/api/v1/vision/inspections/${id}/image`),
      ]);
      setAnnotatedUrl(ann);
      setOriginalUrl(orig);
    } catch {
      /* binary may be missing for demo rows */
    }
  }

  function onPick(e: React.ChangeEvent<HTMLInputElement>, video: boolean) {
    const file = e.target.files?.[0];
    if (!file) return;
    if (video) inspectVideo.mutate(file);
    else inspectImage.mutate(file);
    e.target.value = "";
  }

  return (
    <div className="space-y-4">
      {node}
      <div className="grid gap-4 lg:grid-cols-3">
        {/* Upload panel */}
        <Card>
          <CardHeader>
            <CardTitle>Run inspection</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <Select value={machineId} onChange={(e) => setMachineId(e.target.value)}>
              <option value="">— Link to machine (optional) —</option>
              {machines.data?.items.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.code} · {m.name}
                </option>
              ))}
            </Select>

            <button
              onClick={() => imageRef.current?.click()}
              disabled={inspectImage.isPending}
              className="flex w-full cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-[var(--border)] py-8 transition hover:border-[var(--accent)] hover:bg-[var(--accent)]/5 disabled:opacity-60"
            >
              <UploadCloud className="h-7 w-7 text-[var(--accent)]" />
              <span className="text-sm font-medium">
                {inspectImage.isPending ? "Running inference…" : "Upload product image"}
              </span>
              <span className="text-[11px] text-[var(--muted-foreground)]">
                PNG · JPG · BMP · TIFF · WEBP · max 10 MB
              </span>
            </button>
            <input ref={imageRef} type="file" accept=".png,.jpg,.jpeg,.bmp,.tif,.tiff,.webp" hidden onChange={(e) => onPick(e, false)} />

            <button
              onClick={() => videoRef.current?.click()}
              disabled={inspectVideo.isPending}
              className="flex w-full cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-[var(--border)] py-6 transition hover:border-[var(--accent)] hover:bg-[var(--accent)]/5 disabled:opacity-60"
            >
              <UploadCloud className="h-5 w-5 text-[var(--muted-foreground)]" />
              <span className="text-xs font-medium">
                {inspectVideo.isPending ? "Uploading video…" : "Upload video (async, frame sampling)"}
              </span>
              <span className="text-[10px] text-[var(--muted-foreground)]">MP4 · AVI · MOV · max 150 MB</span>
            </button>
            <input ref={videoRef} type="file" accept=".mp4,.avi,.mov,.mkv,.webm" hidden onChange={(e) => onPick(e, true)} />

            <p className="text-[11px] text-[var(--muted-foreground)]">
              Pipeline: OpenCV preprocessing → anomaly detection → classification
              (CNN if trained) → optional OCR. Every result labels the exact method
              used. Real-time camera streams are NOT claimed in this build.
            </p>
          </CardContent>
        </Card>

        {/* Result panel */}
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Latest result</CardTitle>
          </CardHeader>
          <CardContent>
            {detail.isLoading && <Skeleton className="h-64" />}
            {detail.error && <ErrorState message={(detail.error as Error).message} />}
            {detail.data && (
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-2">
                  {annotatedUrl ? (
                    // eslint-disable-next-line @next/next/no-img-element
                    <img src={annotatedUrl} alt="annotated" className="w-full rounded-lg border border-[var(--border)]" />
                  ) : (
                    <div className="flex h-48 items-center justify-center rounded-lg border border-dashed border-[var(--border)] text-xs text-[var(--muted-foreground)]">
                      Annotated image unavailable
                    </div>
                  )}
                  {originalUrl && (
                    <a href={originalUrl} target="_blank" rel="noreferrer" className="text-xs text-[var(--accent)] hover:underline">
                      View original image ↗
                    </a>
                  )}
                </div>
                <div className="space-y-2 text-sm">
                  <div className="flex flex-wrap gap-2">
                    <Badge className={statusColor[detail.data.status]}>
                      {detail.data.status}
                    </Badge>
                    {detail.data.result && (
                      <Badge className={statusColor[detail.data.result]}>{detail.data.result}</Badge>
                    )}
                    <Badge>method: {detail.data.method_used}</Badge>
                    <Badge>{detail.data.processing_ms} ms</Badge>
                    {detail.data.model_version && <Badge>v: {detail.data.model_version}</Badge>}
                  </div>
                  <div className="text-xs">
                    <b>{detail.data.defect_count}</b> defect(s) · avg confidence{" "}
                    {fmtPct(detail.data.avg_confidence)}
                  </div>
                  {detail.data.anomaly && (
                    <div className="rounded-lg border border-[var(--border)] p-2 text-xs">
                      <b>Anomaly</b> ({detail.data.anomaly.method}): score{" "}
                      {fmtNum(detail.data.anomaly.score, 4)}
                      {detail.data.anomaly.is_anomalous !== undefined && (
                        <span className={detail.data.anomaly.is_anomalous ? " text-[var(--danger)]" : " text-[var(--success)]"}>
                          {" "}· {detail.data.anomaly.is_anomalous ? "ANOMALOUS" : "normal"}
                        </span>
                      )}
                    </div>
                  )}
                  {detail.data.ocr?.available && (
                    <div className="rounded-lg border border-[var(--border)] p-2 text-xs">
                      <b>OCR</b>: <pre className="mt-1 whitespace-pre-wrap">{detail.data.ocr.text || "(no text)"}</pre>
                    </div>
                  )}
                  <div className="max-h-40 overflow-y-auto rounded-lg border border-[var(--border)]">
                    <Table>
                      <thead>
                        <tr>
                          <Th>Label</Th>
                          <Th>Conf.</Th>
                          <Th>Severity</Th>
                          <Th>BBox</Th>
                        </tr>
                      </thead>
                      <tbody>
                        {detail.data.defects.length === 0 ? (
                          <tr>
                            <Td className="text-center text-[var(--muted-foreground)]" colSpan={4}>
                              No defects detected
                            </Td>
                          </tr>
                        ) : (
                          detail.data.defects.map((d, i) => (
                            <tr key={i}>
                              <Td>{d.label}{d.frame_index !== undefined ? ` (f${d.frame_index})` : ""}</Td>
                              <Td>{fmtPct(d.confidence)}</Td>
                              <Td>{d.severity ?? "—"}</Td>
                              <Td className="text-[10px]">{d.bbox_x1 !== null ? `${d.bbox_x1},${d.bbox_y1}-${d.bbox_x2},${d.bbox_y2}` : "—"}</Td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </Table>
                  </div>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* History */}
      <Card>
        <CardHeader>
          <CardTitle>Inspection history</CardTitle>
        </CardHeader>
        <CardContent>
          {history.isLoading && <Skeleton className="h-40" />}
          {history.data && history.data.items.length === 0 && (
            <EmptyState title="No inspections yet" hint="Upload an image above — the pipeline runs real inference." icon="🖼️" />
          )}
          {history.data && history.data.items.length > 0 && (
            <Table>
              <thead>
                <tr>
                  <Th>ID</Th><Th>Kind</Th><Th>File</Th><Th>Result</Th>
                  <Th>Defects</Th><Th>Method</Th><Th>ms</Th><Th>When</Th><Th></Th>
                </tr>
              </thead>
              <tbody>
                {history.data.items.map((i) => (
                  <tr key={i.id} className="hover:bg-[var(--border)]/25">
                    <Td>{i.id}{i.is_demo && <Badge className="ml-1">demo</Badge>}</Td>
                    <Td>{i.kind}</Td>
                    <Td className="max-w-[160px] truncate">{i.filename}</Td>
                    <Td>
                      <Badge className={statusColor[i.status]}>{i.status}</Badge>{" "}
                      {i.result && <Badge className={statusColor[i.result]}>{i.result}</Badge>}
                    </Td>
                    <Td>{i.defect_count}</Td>
                    <Td className="text-[11px]">{i.method_used ?? "—"}</Td>
                    <Td>{i.processing_ms ?? "—"}</Td>
                    <Td className="text-[11px]">{fmtDate(i.created_at)}</Td>
                    <Td>
                      <Button size="sm" variant="outline" onClick={() => openDetail(i.id)}>
                        View
                      </Button>
                    </Td>
                  </tr>
                ))}
              </tbody>
            </Table>
          )}
        </CardContent>
      </Card>

      {/* Detail dialog */}
      <Dialog open={detailId !== null} onClose={() => setDetailId(null)} title={`Inspection #${detailId}`} wide>
        {detail.data && (
          <div className="space-y-3 text-sm">
            <div className="flex flex-wrap gap-2">
              <Badge className={statusColor[detail.data.status]}>{detail.data.status}</Badge>
              {detail.data.result && <Badge className={statusColor[detail.data.result]}>{detail.data.result}</Badge>}
              <Badge>method: {detail.data.method_used}</Badge>
              <Badge>{detail.data.processing_ms} ms</Badge>
              <Badge>{fmtDate(detail.data.completed_at)}</Badge>
            </div>
            {annotatedUrl && (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={annotatedUrl} alt="annotated" className="w-full rounded-lg border border-[var(--border)]" />
            )}
            <div className="grid gap-2 sm:grid-cols-2">
              {detail.data.anomaly && (
                <div className="rounded-lg border border-[var(--border)] p-2 text-xs">
                  <b>Anomaly</b> ({detail.data.anomaly.method}): {fmtNum(detail.data.anomaly.score, 4)}
                </div>
              )}
              {detail.data.ocr && (
                <div className="rounded-lg border border-[var(--border)] p-2 text-xs">
                  <b>OCR</b> ({detail.data.ocr.method}): {detail.data.ocr.text?.slice(0, 120) || "—"}
                </div>
              )}
            </div>
          </div>
        )}
      </Dialog>
    </div>
  );
}
