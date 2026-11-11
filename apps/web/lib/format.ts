export function fmtDate(iso?: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtNum(v: number | null | undefined, digits = 2): string {
  if (v === null || v === undefined) return "—";
  return v.toLocaleString(undefined, {
    maximumFractionDigits: digits,
    minimumFractionDigits: 0,
  });
}

export function fmtPct(v: number | null | undefined, digits = 1): string {
  if (v === null || v === undefined) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function fmtBytes(v: number | null | undefined): string {
  if (!v) return "—";
  const units = ["B", "KB", "MB", "GB"];
  let i = 0;
  let n = v;
  while (n >= 1024 && i < units.length - 1) {
    n /= 1024;
    i++;
  }
  return `${n.toFixed(1)} ${units[i]}`;
}

export const riskColor: Record<string, string> = {
  low: "text-[var(--success)]",
  medium: "text-[var(--warning)]",
  high: "text-[var(--danger)]",
  critical: "text-[var(--danger)] font-semibold",
};

export const statusColor: Record<string, string> = {
  healthy: "bg-[var(--success)]/15 text-[var(--success)]",
  warning: "bg-[var(--warning)]/15 text-[var(--warning)]",
  critical: "bg-[var(--danger)]/15 text-[var(--danger)]",
  offline: "bg-[var(--muted)]/15 text-[var(--muted)]",
  completed: "bg-[var(--success)]/15 text-[var(--success)]",
  ok: "bg-[var(--success)]/15 text-[var(--success)]",
  defect_detected: "bg-[var(--danger)]/15 text-[var(--danger)]",
  failed: "bg-[var(--danger)]/15 text-[var(--danger)]",
  processing: "bg-[var(--accent)]/15 text-[var(--accent)]",
  pending: "bg-[var(--muted)]/15 text-[var(--muted)]",
  indexed: "bg-[var(--success)]/15 text-[var(--success)]",
  open: "bg-[var(--warning)]/15 text-[var(--warning)]",
  approved: "bg-[var(--accent)]/15 text-[var(--accent)]",
  rejected: "bg-[var(--muted)]/15 text-[var(--muted)]",
  done: "bg-[var(--success)]/15 text-[var(--success)]",
  awaiting_approval: "bg-[var(--warning)]/15 text-[var(--warning)]",
  running: "bg-[var(--accent)]/15 text-[var(--accent)]",
  production: "bg-[var(--success)]/15 text-[var(--success)]",
  staging: "bg-[var(--warning)]/15 text-[var(--warning)]",
  registered: "bg-[var(--muted)]/15 text-[var(--muted)]",
  archived: "bg-[var(--muted)]/15 text-[var(--muted)]",
};
