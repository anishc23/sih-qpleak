"use client";

import clsx from "clsx";
import {
  AlertTriangle,
  CheckCircle2,
  Copy,
  Lock,
  ShieldAlert,
  Unlock,
  XCircle,
  type LucideIcon,
} from "lucide-react";
import { useState } from "react";
import type { Difficulty, PaperStatus, QuestionStatus } from "@/lib/api";

// ---------------------------------------------------------------- layout

export function Panel({
  title,
  subtitle,
  action,
  className,
  children,
}: {
  title?: string;
  subtitle?: string;
  action?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <section className={clsx("panel p-5", className)}>
      {(title || action) && (
        <header className="mb-4 flex items-start justify-between gap-4 border-b border-rule-soft pb-3">
          <div>
            {title && (
              <h2 className="font-mono text-[10px] uppercase tracking-[0.18em] text-ink-4">
                {title}
              </h2>
            )}
            {subtitle && <p className="mt-1.5 text-xs text-ink-4">{subtitle}</p>}
          </div>
          {action}
        </header>
      )}
      {children}
    </section>
  );
}

export function PageHeader({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-ink">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-ink-3">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export function Empty({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="rounded-sm border border-dashed border-rule px-6 py-10 text-center">
      <p className="text-sm text-ink-3">{message}</p>
      {hint && <p className="mt-1 text-xs text-ink-5">{hint}</p>}
    </div>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="shimmer h-12 rounded-sm bg-sunk" />
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- feedback

export function Alert({
  kind = "info",
  title,
  children,
}: {
  kind?: "info" | "ok" | "warn" | "danger" | "locked";
  title?: string;
  children?: React.ReactNode;
}) {
  const styles = {
    info: "border-accent/25 bg-accent/[0.06] text-accent-soft",
    ok: "border-ok/25 bg-ok/[0.06] text-ok",
    warn: "border-warn/25 bg-warn/[0.06] text-warn",
    danger: "border-danger/30 bg-danger/[0.07] text-danger",
    locked: "border-locked/30 bg-locked/[0.07] text-locked",
  }[kind];
  const Icon = {
    info: CheckCircle2,
    ok: CheckCircle2,
    warn: AlertTriangle,
    danger: ShieldAlert,
    locked: Lock,
  }[kind];

  return (
    <div className={clsx("flex gap-3 rounded-sm border px-4 py-3 text-sm", styles)}>
      <Icon size={16} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="text-ink-3 [&_p]:mt-1">{children}</div>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- badges

const QUESTION_STATUS_STYLE: Record<QuestionStatus, string> = {
  DRAFT: "text-ink-3",
  SUBMITTED: "text-warn",
  UNDER_REVIEW: "text-warn",
  APPROVED: "text-ok",
  REJECTED: "text-danger",
  AVAILABLE_FOR_SYNTHESIS: "text-ok",
  SELECTED: "text-accent",
  USED_IN_PAPER: "text-locked",
  RETIRED: "text-ink-4",
};

const QUESTION_STATUS_LABEL: Record<QuestionStatus, string> = {
  DRAFT: "Draft",
  SUBMITTED: "Submitted",
  UNDER_REVIEW: "Under review",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  AVAILABLE_FOR_SYNTHESIS: "In pool",
  SELECTED: "Selected",
  USED_IN_PAPER: "Used in paper",
  RETIRED: "Retired",
};

export function StatusBadge({ status }: { status: QuestionStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center font-mono text-[10px] uppercase tracking-[0.12em]",
        QUESTION_STATUS_STYLE[status],
      )}
    >
      {QUESTION_STATUS_LABEL[status]}
    </span>
  );
}

const PAPER_STATUS_STYLE: Record<PaperStatus, string> = {
  DRAFT: "text-ink-3",
  PENDING_APPROVAL: "text-warn",
  APPROVED: "text-ok",
  ENCRYPTED: "text-accent",
  BLOCKCHAIN_REGISTERED: "text-accent",
  LOCKED: "text-locked",
  RELEASED: "text-ok",
};

export function PaperBadge({ status }: { status: PaperStatus }) {
  const Icon = status === "LOCKED" ? Lock : status === "RELEASED" ? Unlock : null;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-[0.12em]",
        PAPER_STATUS_STYLE[status],
      )}
    >
      {Icon && <Icon size={11} />}
      {status.replace(/_/g, " ").toLowerCase()}
    </span>
  );
}

const DIFFICULTY_STYLE: Record<Difficulty, string> = {
  EASY: "text-ok",
  MEDIUM: "text-warn",
  HARD: "text-danger",
};

export function DifficultyBadge({ difficulty }: { difficulty: Difficulty }) {
  return (
    <span
      className={clsx(
        "inline-flex font-mono text-[10px] uppercase tracking-[0.12em]",
        DIFFICULTY_STYLE[difficulty],
      )}
    >
      {difficulty}
    </span>
  );
}

export function RiskBadge({ risk }: { risk: string }) {
  const style =
    {
      HIGH: "text-danger",
      MEDIUM: "text-warn",
      LOW: "text-ok",
      NEGLIGIBLE: "text-ink-4",
    }[risk] ?? "text-ink-4";
  return (
    <span className={clsx("inline-flex font-mono text-[10px] uppercase tracking-[0.12em]", style)}>
      {risk}
    </span>
  );
}

/** Permission triple, shown as three independent lights rather than one flag. */
export function PermissionPips({
  permissions,
}: {
  permissions: { read: boolean; write: boolean; approve: boolean };
}) {
  const items = [
    { key: "R", on: permissions.read, label: "READ" },
    { key: "W", on: permissions.write, label: "WRITE" },
    { key: "A", on: permissions.approve, label: "APPROVE" },
  ];
  return (
    <div className="flex gap-1">
      {items.map((i) => (
        <span
          key={i.key}
          title={`${i.label}: ${i.on ? "granted" : "denied"}`}
          className={clsx(
            "flex h-5 w-5 items-center justify-center rounded text-[10px] font-bold",
            i.on
              ? "bg-ok/15 text-ok ring-1 ring-ok/30"
              : "bg-sunk text-ink-5 ring-1 ring-rule",
          )}
        >
          {i.key}
        </span>
      ))}
    </div>
  );
}

// ---------------------------------------------------------------- data bits

export function Hash({ value, chars = 16 }: { value: string | null | undefined; chars?: number }) {
  const [copied, setCopied] = useState(false);
  if (!value) return <span className="hash">--</span>;

  const shown = value.length > chars ? `${value.slice(0, chars)}...` : value;
  return (
    <button
      type="button"
      title={`${value}  (click to copy)`}
      onClick={() => {
        navigator.clipboard?.writeText(value);
        setCopied(true);
        setTimeout(() => setCopied(false), 1200);
      }}
      className="group inline-flex items-center gap-1.5 font-mono text-[11px] text-ink-3 transition hover:text-accent"
    >
      {shown}
      {copied ? (
        <CheckCircle2 size={11} className="text-ok" />
      ) : (
        <Copy size={11} className="opacity-0 transition group-hover:opacity-60" />
      )}
    </button>
  );
}

export function Stat({
  label,
  value,
  hint,
  tone = "default",
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "default" | "ok" | "warn" | "danger" | "accent";
  icon?: LucideIcon;
}) {
  const toneClass = {
    default: "text-ink",
    ok: "text-ok",
    warn: "text-warn",
    danger: "text-danger",
    accent: "text-lac",
  }[tone];
  return (
    <div className="border-l border-rule pl-4">
      <p className="label">{label}</p>
      <p className={clsx("mt-1.5 font-display text-3xl leading-none tabular-nums", toneClass)}>
        {value}
      </p>
      {hint && <p className="mt-1.5 text-[11px] text-ink-5">{hint}</p>}
    </div>
  );
}

export function CheckRow({ name, ok, detail }: { name: string; ok: boolean; detail: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-rule-soft py-2.5 last:border-0">
      <div className="min-w-0">
        <p className="truncate text-sm text-ink">{name}</p>
        <p className="truncate text-[11px] text-ink-4">{detail}</p>
      </div>
      <span
        className={clsx(
          "inline-flex shrink-0 items-center gap-1.5 text-xs font-medium",
          ok ? "text-ok" : "text-danger",
        )}
      >
        {ok ? <CheckCircle2 size={14} /> : <XCircle size={14} />}
        {ok ? "PASS" : "FAIL"}
      </span>
    </div>
  );
}

/** Horizontal compliance meter, 0-100. */
export function Meter({ label, value }: { label: string; value: number }) {
  const tone = value >= 90 ? "bg-ok" : value >= 70 ? "bg-warn" : "bg-danger";
  return (
    <div>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-xs text-ink-3">{label}</span>
        <span className="text-xs font-semibold tabular-nums text-ink">{value}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-sunk">
        <div
          className={clsx("h-full rounded-full transition-all duration-700", tone)}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}
