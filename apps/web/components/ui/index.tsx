"use client";

// ForgeSight AI — compact shadcn-style primitives (no Radix dependency).
import * as React from "react";
import { cn } from "@/lib/cx";

/* ---------- Button ---------- */
type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "outline" | "ghost" | "danger" | "accent";
  size?: "sm" | "md" | "icon";
};

export function Button({
  className,
  variant = "primary",
  size = "md",
  ...props
}: ButtonProps) {
  return (
    <button
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg font-medium transition-all",
        "disabled:pointer-events-none disabled:opacity-50 cursor-pointer",
        "focus-visible:outline-2 focus-visible:outline-[var(--accent)]",
        size === "sm" && "h-8 px-3 text-xs",
        size === "md" && "h-9 px-4 text-sm",
        size === "icon" && "h-9 w-9",
        variant === "primary" &&
          "bg-[var(--primary)] text-[var(--primary-foreground)] hover:opacity-90 shadow-sm",
        variant === "accent" &&
          "bg-[var(--accent)] text-[var(--accent-foreground)] hover:opacity-90 shadow-sm",
        variant === "outline" &&
          "border border-[var(--border)] bg-transparent hover:bg-[var(--border)]/40",
        variant === "ghost" && "hover:bg-[var(--border)]/40 bg-transparent",
        variant === "danger" &&
          "bg-[var(--danger)] text-white hover:opacity-90",
        className,
      )}
      {...props}
    />
  );
}

/* ---------- Card ---------- */
export function Card({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cn(
        "rounded-xl border border-[var(--border)] bg-[var(--card)] text-[var(--card-foreground)] shadow-sm",
        className,
      )}
      {...props}
    />
  );
}

export function CardHeader({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4 pb-2", className)} {...props} />;
}

export function CardTitle({
  className,
  ...props
}: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-sm font-semibold tracking-tight", className)}
      {...props}
    />
  );
}

export function CardContent({
  className,
  ...props
}: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4 pt-2", className)} {...props} />;
}

/* ---------- Input / Select / Textarea ---------- */
const fieldCls =
  "w-full rounded-lg border border-[var(--border)] bg-transparent px-3 py-2 text-sm " +
  "placeholder:text-[var(--muted-foreground)] focus:outline-2 focus:outline-[var(--accent)] " +
  "disabled:opacity-50";

export const Input = React.forwardRef<
  HTMLInputElement,
  React.InputHTMLAttributes<HTMLInputElement>
>(({ className, ...props }, ref) => (
  <input ref={ref} className={cn(fieldCls, "h-9", className)} {...props} />
));
Input.displayName = "Input";

export const Select = React.forwardRef<
  HTMLSelectElement,
  React.SelectHTMLAttributes<HTMLSelectElement>
>(({ className, ...props }, ref) => (
  <select
    ref={ref}
    className={cn(fieldCls, "h-9 cursor-pointer", className)}
    {...props}
  />
));
Select.displayName = "Select";

export const Textarea = React.forwardRef<
  HTMLTextAreaElement,
  React.TextareaHTMLAttributes<HTMLTextAreaElement>
>(({ className, ...props }, ref) => (
  <textarea ref={ref} className={cn(fieldCls, "min-h-[90px]", className)} {...props} />
));
Textarea.displayName = "Textarea";

export function Label({
  className,
  ...props
}: React.LabelHTMLAttributes<HTMLLabelElement>) {
  return (
    <label
      className={cn(
        "text-xs font-medium text-[var(--muted-foreground)] mb-1 block",
        className,
      )}
      {...props}
    />
  );
}

/* ---------- Badge ---------- */
export function Badge({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLSpanElement>) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-[11px] font-medium",
        "bg-[var(--muted)]/15 text-[var(--muted-foreground)]",
        className,
      )}
      {...props}
    >
      {children}
    </span>
  );
}

/* ---------- Skeleton ---------- */
export function Skeleton({
  className,
}: {
  className?: string;
}) {
  return (
    <div
      className={cn("animate-pulse rounded-lg bg-[var(--border)]/60", className)}
    />
  );
}

/* ---------- Dialog ---------- */
export function Dialog({
  open,
  onClose,
  title,
  children,
  wide,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
  wide?: boolean;
}) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
      />
      <div
        className={cn(
          "relative z-10 w-full rounded-xl border border-[var(--border)] bg-[var(--card)] shadow-xl fsg-fade-in",
          "max-h-[85vh] overflow-y-auto",
          wide ? "max-w-3xl" : "max-w-lg",
        )}
      >
        <div className="flex items-center justify-between border-b border-[var(--border)] p-4">
          <h2 className="text-sm font-semibold">{title}</h2>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close">
            ✕
          </Button>
        </div>
        <div className="p-4">{children}</div>
      </div>
    </div>
  );
}

/* ---------- Table ---------- */
export function Table({
  className,
  ...props
}: React.TableHTMLAttributes<HTMLTableElement>) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table
        className={cn("w-full text-left text-sm", className)}
        {...props}
      />
    </div>
  );
}

export function Th({
  className,
  ...props
}: React.ThHTMLAttributes<HTMLTableCellElement>) {
  return (
    <th
      className={cn(
        "border-b border-[var(--border)] bg-[var(--border)]/25 px-3 py-2 text-xs font-semibold text-[var(--muted-foreground)]",
        className,
      )}
      {...props}
    />
  );
}

export function Td({
  className,
  ...props
}: React.TdHTMLAttributes<HTMLTableCellElement>) {
  return (
    <td
      className={cn("border-b border-[var(--border)]/60 px-3 py-2", className)}
      {...props}
    />
  );
}

/* ---------- Tabs ---------- */
export function Tabs({
  tabs,
  value,
  onChange,
}: {
  tabs: { key: string; label: string }[];
  value: string;
  onChange: (key: string) => void;
}) {
  return (
    <div className="flex gap-1 rounded-lg border border-[var(--border)] p-1 w-fit">
      {tabs.map((t) => (
        <button
          key={t.key}
          onClick={() => onChange(t.key)}
          className={cn(
            "rounded-md px-3 py-1.5 text-xs font-medium transition cursor-pointer",
            value === t.key
              ? "bg-[var(--accent)] text-[var(--accent-foreground)]"
              : "text-[var(--muted-foreground)] hover:bg-[var(--border)]/40",
          )}
        >
          {t.label}
        </button>
      ))}
    </div>
  );
}

/* ---------- Empty / Error states ---------- */
export function EmptyState({
  title,
  hint,
  icon = "📭",
}: {
  title: string;
  hint?: string;
  icon?: string;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-[var(--border)] py-10 text-center">
      <div className="text-2xl mb-2">{icon}</div>
      <p className="text-sm font-medium">{title}</p>
      {hint && (
        <p className="mt-1 text-xs text-[var(--muted-foreground)] max-w-xs">{hint}</p>
      )}
    </div>
  );
}

export function ErrorState({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-[var(--danger)]/40 bg-[var(--danger)]/10 p-4 text-sm text-[var(--danger)]">
      ⚠ {message}
    </div>
  );
}

/* ---------- Toast (minimal) ---------- */
export function Toast({
  toast,
}: {
  toast: { kind: "success" | "error"; message: string } | null;
}) {
  if (!toast) return null;
  return (
    <div
      className={cn(
        "fixed bottom-4 right-4 z-[60] rounded-lg px-4 py-3 text-sm shadow-lg fsg-fade-in",
        toast.kind === "success"
          ? "bg-[var(--success)] text-white"
          : "bg-[var(--danger)] text-white",
      )}
    >
      {toast.kind === "success" ? "✓ " : "⚠ "}
      {toast.message}
    </div>
  );
}

export function useToast() {
  const [toast, setToast] = React.useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);
  const show = React.useCallback(
    (kind: "success" | "error", message: string) => {
      setToast({ kind, message });
      setTimeout(() => setToast(null), 3200);
    },
    [],
  );
  const node = <Toast toast={toast} />;
  return { show, node };
}
