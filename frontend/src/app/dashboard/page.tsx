"use client";

import {
  Activity,
  Blocks,
  CheckCircle2,
  Clock,
  FileStack,
  Lock,
  ShieldAlert,
  Unlock,
  Vault,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Alert, Hash, PageHeader, Panel, Skeleton, Stat } from "@/components/ui";
import { api, type AuditEvent, type DashboardStats, type Paper } from "@/lib/api";
import { ROLE_LABEL, useAuth } from "@/lib/auth";
import { formatDateTime, relativeTime } from "@/lib/format";

export default function DashboardPage() {
  const { user } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [chainIntact, setChainIntact] = useState<boolean | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      api.dashboardStats(),
      api.papers().catch(() => []),
      api.audit({ limit: 12 }).catch(() => []),
      api.verifyAudit().catch(() => null),
    ])
      .then(([s, p, e, v]) => {
        setStats(s);
        setPapers(p);
        setEvents(e);
        setChainIntact(v ? v.intact : null);
      })
      .catch((err) => setError(err.message));
  }, []);

  const locked = papers.filter((p) => p.status === "LOCKED");

  return (
    <Shell>
      <PageHeader
        title={`Welcome, ${user?.name ?? ""}`}
        description={`Signed in as ${user ? ROLE_LABEL[user.role] : ""}. You see only what your role permits — enforced by the server, not by hidden buttons.`}
      />

      {error && (
        <div className="mb-5">
          <Alert kind="danger" title="Could not load dashboard">{error}</Alert>
        </div>
      )}

      {chainIntact === false && (
        <div className="mb-5">
          <Alert kind="danger" title="Audit chain integrity failure">
            The hash chain is broken — an audit record has been modified since it was written.{" "}
            <Link href="/audit" className="underline">
              Investigate
            </Link>
            .
          </Alert>
        </div>
      )}

      {!stats ? (
        <Skeleton rows={4} />
      ) : (
        <>
          {locked.length > 0 ? (
            <section className="seal mb-6 p-6 lg:p-7">
              <div className="flex items-baseline justify-between gap-4">
                <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-register/60">
                  Under seal
                </span>
                <Link
                  href="/timelock"
                  className="font-mono text-[10px] uppercase tracking-[0.18em] text-register/60 underline-offset-4 hover:text-register hover:underline"
                >
                  Try to open it
                </Link>
              </div>
              <div className="mt-6 space-y-6">
                {locked.map((p) => (
                  <Link key={p.paper_uid} href={`/timelock?paper=${p.paper_uid}`} className="block">
                    <p className="font-display text-3xl leading-none text-register">{p.paper_uid}</p>
                    <p className="mt-2 text-[13px] text-register/70">{p.exam_title}</p>
                    <p className="mt-1 break-all font-mono text-[11px] text-register/50">
                      {p.paper_hash}
                    </p>
                    {p.release_time && (
                      <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.14em] text-register/70">
                        Opens {formatDateTime(p.release_time)}
                      </p>
                    )}
                  </Link>
                ))}
              </div>
              <p className="mt-6 font-mono text-[11px] text-register/60">
                Release is decided by the contract. This page cannot open it.
              </p>
            </section>
          ) : (
            <p className="mb-6 border-t border-rule pt-4 font-mono text-[11px] uppercase tracking-[0.18em] text-ink-5">
              Nothing is under seal right now
            </p>
          )}

          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Questions" value={stats.total_questions} icon={Vault} hint="all encrypted at rest" />
            <Stat label="In pool" value={stats.approved_questions} tone="ok" icon={CheckCircle2} hint="approved for synthesis" />
            <Stat label="Pending review" value={stats.pending_review} tone="warn" icon={Clock} />
            <Stat label="Papers locked" value={stats.papers_locked} tone="accent" icon={Lock} />
            <Stat label="Papers released" value={stats.papers_released} tone="ok" icon={Unlock} />
            <Stat label="Chain transactions" value={stats.blockchain_transactions} icon={Blocks} />
            <Stat
              label="Denied attempts"
              value={stats.security_events}
              tone={stats.security_events > 0 ? "warn" : "default"}
              icon={ShieldAlert}
              hint="access refusals, recorded"
            />
            <Stat label="Audit events" value={stats.audit_events} icon={Activity} hint="hash chained" />
          </div>

          <div className="mt-5">
            <Panel
              title="Recent activity"
              subtitle="Every entry is hash-chained to its predecessor"
              action={
                <Link href="/audit" className="text-xs text-accent hover:underline">
                  Full trail
                </Link>
              }
            >
              {events.length === 0 ? (
                <p className="py-6 text-center text-sm text-ink-5">No activity yet.</p>
              ) : (
                <ul className="space-y-1.5">
                  {events.map((e) => (
                    <li key={e.event_uid} className="flex items-center gap-3 py-1">
                      <span
                        className={`h-1.5 w-1.5 shrink-0 rounded-full ${e.success ? "bg-ok" : "bg-danger"}`}
                      />
                      <span className="min-w-0 flex-1 truncate text-xs text-ink-2">
                        {e.event_type.replace(/_/g, " ").toLowerCase()}
                        <span className="ml-1.5 text-ink-5">{e.resource_id}</span>
                      </span>
                      <span className="shrink-0 text-[10px] text-ink-5">
                        {relativeTime(e.created_at)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Panel>
          </div>

          <div className="mt-5">
            <Panel title="Papers" subtitle="Lifecycle status across all examinations">
              {papers.length === 0 ? (
                <p className="py-6 text-center text-sm text-ink-5">
                  No papers generated yet.
                </p>
              ) : (
                <div className="space-y-2">
                  {papers.slice(0, 6).map((p) => (
                    <Link
                      key={p.paper_uid}
                      href={`/papers/${p.paper_uid}`}
                      className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-rule-soft px-3.5 py-3 transition hover:border-accent/25"
                    >
                      <div className="min-w-0">
                        <p className="flex items-center gap-2 text-sm text-ink">
                          <FileStack size={13} className="text-ink-5" />
                          {p.paper_uid}
                        </p>
                        <p className="mt-0.5 truncate text-[11px] text-ink-4">
                          {p.exam_title} &middot; {p.question_count} questions
                        </p>
                      </div>
                      <span className="text-[11px] text-ink-4">{p.status.replace(/_/g, " ")}</span>
                    </Link>
                  ))}
                </div>
              )}
            </Panel>
          </div>
        </>
      )}
    </Shell>
  );
}
