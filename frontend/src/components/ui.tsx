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
        <header className="mb-4 flex items-start justify-between gap-4">
          <div>
            {title && <h2 className="text-sm font-semibold text-white">{title}</h2>}
            {subtitle && <p className="mt-1 text-xs text-slate-500">{subtitle}</p>}
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
        <h1 className="text-xl font-semibold tracking-tight text-white">{title}</h1>
        {description && <p className="mt-1 max-w-2xl text-sm text-slate-400">{description}</p>}
      </div>
      {children}
    </div>
  );
}

export function Empty({ message, hint }: { message: string; hint?: string }) {
  return (
    <div className="rounded-lg border border-dashed border-white/10 px-6 py-10 text-center">
      <p className="text-sm text-slate-400">{message}</p>
      {hint && <p className="mt-1 text-xs text-slate-600">{hint}</p>}
    </div>
  );
}

export function Skeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="shimmer h-12 rounded-lg bg-base-850" />
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
    <div className={clsx("flex gap-3 rounded-lg border px-4 py-3 text-sm", styles)}>
      <Icon size={16} className="mt-0.5 shrink-0" />
      <div className="min-w-0">
        {title && <p className="font-semibold">{title}</p>}
        {children && <div className="text-slate-300/90 [&_p]:mt-1">{children}</div>}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- badges

const QUESTION_STATUS_STYLE: Record<QuestionStatus, string> = {
  DRAFT: "border-slate-600/40 bg-slate-500/10 text-slate-400",
  SUBMITTED: "border-warn/30 bg-warn/10 text-warn",
  UNDER_REVIEW: "border-warn/30 bg-warn/10 text-warn",
  APPROVED: "border-ok/30 bg-ok/10 text-ok",
  REJECTED: "border-danger/30 bg-danger/10 text-danger",
  AVAILABLE_FOR_SYNTHESIS: "border-ok/30 bg-ok/10 text-ok",
  SELECTED: "border-accent/30 bg-accent/10 text-accent",
  USED_IN_PAPER: "border-locked/30 bg-locked/10 text-locked",
  RETIRED: "border-slate-600/40 bg-slate-500/10 text-slate-500",
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
        "inline-flex items-center rounded-full border px-2 py-0.5 text-[11px] font-medium",
        QUESTION_STATUS_STYLE[status],
      )}
    >
      {QUESTION_STATUS_LABEL[status]}
    </span>
  );
}

const PAPER_STATUS_STYLE: Record<PaperStatus, string> = {
  DRAFT: "border-slate-600/40 bg-slate-500/10 text-slate-400",
  PENDING_APPROVAL: "border-warn/30 bg-warn/10 text-warn",
  APPROVED: "border-ok/30 bg-ok/10 text-ok",
  ENCRYPTED: "border-accent/30 bg-accent/10 text-accent",
  BLOCKCHAIN_REGISTERED: "border-accent/30 bg-accent/10 text-accent",
  LOCKED: "border-locked/40 bg-locked/10 text-locked",
  RELEASED: "border-ok/30 bg-ok/10 text-ok",
};

export function PaperBadge({ status }: { status: PaperStatus }) {
  const Icon = status === "LOCKED" ? Lock : status === "RELEASED" ? Unlock : null;
  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-medium",
        PAPER_STATUS_STYLE[status],
      )}
    >
      {Icon && <Icon size={11} />}
      {status.replace(/_/g, " ").toLowerCase()}
    </span>
  );
}

const DIFFICULTY_STYLE: Record<Difficulty, string> = {
  EASY: "border-ok/25 bg-ok/10 text-ok",
  MEDIUM: "border-warn/25 bg-warn/10 text-warn",
  HARD: "border-danger/25 bg-danger/10 text-danger",
};

export function DifficultyBadge({ difficulty }: { difficulty: Difficulty }) {
  return (
    <span
      className={clsx(
        "inline-flex rounded border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
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
      HIGH: "border-danger/30 bg-danger/10 text-danger",
      MEDIUM: "border-warn/30 bg-warn/10 text-warn",
      LOW: "border-ok/25 bg-ok/10 text-ok",
      NEGLIGIBLE: "border-slate-600/40 bg-slate-500/10 text-slate-400",
    }[risk] ?? "border-slate-600/40 bg-slate-500/10 text-slate-400";
  return (
    <span className={clsx("inline-flex rounded border px-2 py-0.5 text-[11px] font-medium", style)}>
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
              : "bg-base-800 text-slate-600 ring-1 ring-white/5",
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
      className="group inline-flex items-center gap-1.5 font-mono text-[11px] text-slate-400 transition hover:text-accent"
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
  icon: Icon,
}: {
  label: string;
  value: React.ReactNode;
  hint?: string;
  tone?: "default" | "ok" | "warn" | "danger" | "accent";
  icon?: LucideIcon;
}) {
  const toneClass = {
    default: "text-white",
    ok: "text-ok",
    warn: "text-warn",
    danger: "text-danger",
    accent: "text-accent",
  }[tone];
  return (
    <div className="panel panel-hover p-4">
      <div className="flex items-start justify-between">
        <p className="label">{label}</p>
        {Icon && <Icon size={15} className="text-slate-600" />}
      </div>
      <p className={clsx("mt-2 text-2xl font-semibold tabular-nums", toneClass)}>{value}</p>
      {hint && <p className="mt-1 text-[11px] text-slate-600">{hint}</p>}
    </div>
  );
}

export function CheckRow({ name, ok, detail }: { name: string; ok: boolean; detail: string }) {
  return (
    <div className="flex items-center justify-between gap-4 border-b border-white/5 py-2.5 last:border-0">
      <div className="min-w-0">
        <p className="truncate text-sm text-slate-200">{name}</p>
        <p className="truncate text-[11px] text-slate-500">{detail}</p>
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
        <span className="text-xs text-slate-400">{label}</span>
        <span className="text-xs font-semibold tabular-nums text-slate-200">{value}%</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-base-800">
        <div
          className={clsx("h-full rounded-full transition-all duration-700", tone)}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}
