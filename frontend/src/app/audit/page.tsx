"use client";

import { AlertTriangle, Link2, RotateCcw, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Alert, Empty, Hash, PageHeader, Panel, Skeleton } from "@/components/ui";
import { api, type AuditEvent, type ChainVerification } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDateTime } from "@/lib/format";

const FILTERS = [
  { label: "All", value: "" },
  { label: "Questions", value: "QUESTION" },
  { label: "Papers", value: "PAPER" },
  { label: "Users", value: "USER" },
];

export default function AuditPage() {
  const { user } = useAuth();
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [verification, setVerification] = useState<ChainVerification | null>(null);
  const [resourceType, setResourceType] = useState("");
  const [onlyFailures, setOnlyFailures] = useState(false);
  const [tamperResult, setTamperResult] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .audit({
        limit: 300,
        resource_type: resourceType || undefined,
        success: onlyFailures ? false : undefined,
      })
      .then(setEvents)
      .catch((e) => setError(e.message));
    api.verifyAudit().then(setVerification).catch(() => {});
  }, [resourceType, onlyFailures]);

  useEffect(load, [load]);

  async function tamper() {
    if (!events?.length) return;
    const victim = events.find((e) => e.event_type === "QUESTION_CREATED") ?? events[events.length - 1];
    try {
      setTamperResult(await api.tamperAudit(victim.event_uid));
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Demo failed.");
    }
  }

  async function reset() {
    try {
      await api.resetTamper();
      setTamperResult(null);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Reset failed.");
    }
  }

  const canDemo = user?.role === "SUPER_ADMIN" || user?.role === "AUDITOR";

  return (
    <Shell>
      <PageHeader
        title="Audit Trail"
        description="Every event is hash-chained to its predecessor. Editing any historical row breaks the chain from that point forward — which is exactly what the verification below detects."
      />

      {error && <div className="mb-5"><Alert kind="danger" title="Error">{error}</Alert></div>}

      <div className="mb-5 grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <Panel title="Chain integrity" subtitle="Recomputed from stored fields on every check">
          {!verification ? (
            <Skeleton rows={1} />
          ) : verification.intact ? (
            <Alert kind="ok" title="Hash chain intact">
              <p>
                {verification.total_events} events verified. Head:{" "}
                <span className="font-mono text-[11px]">{verification.chain_head.slice(0, 24)}...</span>
              </p>
            </Alert>
          ) : (
            <Alert kind="danger" title="TAMPERING DETECTED">
              <p>
                {verification.broken_count} broken link
                {verification.broken_count === 1 ? "" : "s"}, first at{" "}
                <span className="font-mono">{verification.first_broken_at}</span>.
              </p>
              <p className="mt-2 text-slate-400">
                The database row was modified after it was written. The blockchain anchor is
                unchanged and was never reachable from the database.
              </p>
            </Alert>
          )}
        </Panel>

        {canDemo && (
          <Panel
            title="Tamper demonstration"
            subtitle="Edits one row of our own database — it cannot touch the chain"
          >
            <div className="flex flex-wrap gap-2">
              <button onClick={tamper} className="btn-danger">
                <AlertTriangle size={14} />
                Simulate insider edit
              </button>
              {user?.role === "SUPER_ADMIN" && (
                <button onClick={reset} className="btn-ghost">
                  <RotateCcw size={14} />
                  Rebuild chain
                </button>
              )}
            </div>
            {tamperResult && (
              <div className="mt-3.5 space-y-1.5 rounded-lg border border-danger/25 bg-danger/[0.05] px-3.5 py-3 text-xs">
                <p className="text-slate-400">
                  Database now reads:{" "}
                  <span className="font-mono text-danger">{String(tamperResult.new_value)}</span>
                </p>
                <p className="text-slate-400">
                  Originally:{" "}
                  <span className="font-mono text-slate-300">{String(tamperResult.original_value)}</span>
                </p>
                <p className="pt-1 font-semibold text-danger">{String(tamperResult.verdict)}</p>
                <p className="leading-relaxed text-slate-500">{String(tamperResult.explanation)}</p>
              </div>
            )}
          </Panel>
        )}
      </div>

      <Panel
        title="Event timeline"
        action={
          <div className="flex flex-wrap items-center gap-2">
            {FILTERS.map((f) => (
              <button
                key={f.value}
                onClick={() => setResourceType(f.value)}
                className={`rounded-lg border px-2.5 py-1 text-[11px] transition ${
                  resourceType === f.value
                    ? "border-accent/40 bg-accent/10 text-accent"
                    : "border-white/10 text-slate-500 hover:text-slate-300"
                }`}
              >
                {f.label}
              </button>
            ))}
            <button
              onClick={() => setOnlyFailures((v) => !v)}
              className={`rounded-lg border px-2.5 py-1 text-[11px] transition ${
                onlyFailures
                  ? "border-danger/40 bg-danger/10 text-danger"
                  : "border-white/10 text-slate-500 hover:text-slate-300"
              }`}
            >
              Denials only
            </button>
          </div>
        }
      >
        {!events ? (
          <Skeleton rows={8} />
        ) : events.length === 0 ? (
          <Empty message="No events match." />
        ) : (
          <ol className="relative space-y-0 border-l border-white/[0.07] pl-5">
            {events.map((e) => (
              <li key={e.event_uid} className="relative py-2.5">
                <span
                  className={`absolute -left-[25px] top-4 h-2 w-2 rounded-full ring-4 ring-base-950 ${
                    e.success ? "bg-ok" : "bg-danger"
                  }`}
                />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-sm text-slate-200">
                      {e.event_type.replace(/_/g, " ").toLowerCase()}
                      {!e.success && (
                        <span className="ml-2 rounded bg-danger/12 px-1.5 py-0.5 text-[10px] font-semibold text-danger">
                          DENIED
                        </span>
                      )}
                    </p>
                    <p className="mt-0.5 text-[11px] text-slate-500">
                      <span className="font-mono">{e.resource_id}</span>
                      {e.actor_role && <> &middot; {e.actor_role.replace(/_/g, " ").toLowerCase()}</>}
                      {e.actor_uid && <> &middot; <span className="font-mono">{e.actor_uid}</span></>}
                    </p>
                    {typeof e.detail?.reason === "string" && (
                      <p className="mt-1 text-[11px] italic text-slate-600">{e.detail.reason}</p>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-3">
                    {e.blockchain_tx && <Hash value={e.blockchain_tx} chars={10} />}
                    <span title="event hash" className="flex items-center gap-1">
                      <Link2 size={10} className="text-slate-700" />
                      <Hash value={e.event_hash} chars={8} />
                    </span>
                    <span className="text-[10px] text-slate-600">
                      {formatDateTime(e.created_at)}
                    </span>
                  </div>
                </div>
              </li>
            ))}
          </ol>
        )}
        <p className="mt-4 flex items-center gap-1.5 text-[11px] text-slate-600">
          <ShieldCheck size={11} />
          {events?.length ?? 0} events shown. Each row&rsquo;s hash incorporates the hash of the row
          before it.
        </p>
      </Panel>
    </Shell>
  );
}
