"use client";

import { Eye, History, ShieldCheck } from "lucide-react";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import {
  Alert,
  DifficultyBadge,
  Empty,
  Hash,
  PageHeader,
  Panel,
  PermissionPips,
  Skeleton,
  StatusBadge,
} from "@/components/ui";
import { api, type AuditEvent, type Question } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

export default function QuestionDetailPage() {
  const { uid } = useParams<{ uid: string }>();
  const [question, setQuestion] = useState<Question | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [readError, setReadError] = useState<string | null>(null);
  const [versions, setVersions] = useState<
    Array<{ version: number; content_hash: string; change_note: string | null; created_at: string }>
  >([]);
  const [accessLog, setAccessLog] = useState<
    Array<{
      access_type: string;
      granted: boolean;
      reason: string | null;
      user_name: string;
      role: string;
      created_at: string;
    }>
  >([]);
  const [trail, setTrail] = useState<AuditEvent[]>([]);
  const [verification, setVerification] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.question(uid).then(setQuestion).catch((e) => setError(e.message));
    api.questionVersions(uid).then(setVersions).catch(() => {});
    api.questionAccessLog(uid).then(setAccessLog).catch(() => {});
    api.questionAudit(uid).then(setTrail).catch(() => {});
  }, [uid]);

  useEffect(load, [load]);

  async function reveal() {
    setReadError(null);
    try {
      const res = await api.readQuestion(uid);
      setContent(res.content);
    } catch (e) {
      setReadError(e instanceof Error ? e.message : "Read denied.");
    }
    load();
  }

  if (error) {
    return (
      <Shell>
        <Alert kind="danger" title="Could not load question">{error}</Alert>
      </Shell>
    );
  }
  if (!question) {
    return (
      <Shell>
        <Skeleton rows={5} />
      </Shell>
    );
  }

  return (
    <Shell>
      <PageHeader
        title={question.question_uid}
        description={`${question.topic} · ${question.subject} · version ${question.version}`}
      >
        <div className="flex items-center gap-2">
          <StatusBadge status={question.status} />
          <DifficultyBadge difficulty={question.difficulty} />
        </div>
      </PageHeader>

      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-5">
          <Panel
            title="Question content"
            subtitle="Reading is a security event: it is authorised, logged and anchored on chain"
            action={
              !content && (
                <button onClick={reveal} className="btn-ghost !px-3 !py-1.5 text-xs">
                  <Eye size={13} />
                  Reveal
                </button>
              )
            }
          >
            {readError ? (
              <Alert kind="danger" title="READ denied">
                <p>{readError}</p>
                <p className="mt-2 text-ink-3">
                  This refusal has been recorded in the access log and the audit trail.
                </p>
              </Alert>
            ) : content ? (
              <>
                <p className="whitespace-pre-wrap rounded-sm border border-rule-soft bg-register/60 p-4 text-[13px] leading-relaxed text-ink">
                  {content}
                </p>
                <p className="mt-2.5 text-[11px] text-ink-5">
                  Decrypted in memory for this request. A QUESTION_READ event was written and a
                  provenance event anchored on chain.
                </p>
              </>
            ) : (
              <div className="rounded-sm border border-dashed border-rule py-8 text-center">
                <p className="text-sm text-ink-4">Content is encrypted at rest.</p>
                <p className="mt-1 text-[11px] text-ink-5">
                  Your permissions: READ {question.permissions.read ? "granted" : "denied"}
                </p>
              </div>
            )}
          </Panel>

          <Panel title="Version history" subtitle="Append-only — an edit never overwrites its predecessor">
            {versions.length === 0 ? (
              <Empty message="No versions recorded." />
            ) : (
              <ol className="space-y-2">
                {versions.map((v) => (
                  <li
                    key={v.version}
                    className="flex flex-wrap items-center justify-between gap-2 rounded-sm border border-rule-soft px-3.5 py-2.5"
                  >
                    <div className="flex items-center gap-3">
                      <span className="font-mono text-xs text-accent">v{v.version}</span>
                      <span className="text-xs text-ink-3">
                        {v.change_note ?? "No note"}
                      </span>
                    </div>
                    <div className="flex items-center gap-3">
                      <Hash value={v.content_hash} chars={14} />
                      <span className="text-[10px] text-ink-5">
                        {formatDateTime(v.created_at)}
                      </span>
                    </div>
                  </li>
                ))}
              </ol>
            )}
          </Panel>

          <Panel title="Lifecycle audit" subtitle="Hash-chained events for this question">
            {trail.length === 0 ? (
              <Empty message="No audit events." />
            ) : (
              <ol className="space-y-1.5">
                {trail.map((e) => (
                  <li key={e.event_uid} className="flex items-center gap-3 py-1 text-xs">
                    <span
                      className={`h-1.5 w-1.5 shrink-0 rounded-full ${e.success ? "bg-ok" : "bg-danger"}`}
                    />
                    <span className="flex-1 text-ink-2">
                      {e.event_type.replace(/_/g, " ").toLowerCase()}
                    </span>
                    {e.blockchain_tx && <Hash value={e.blockchain_tx} chars={10} />}
                    <span className="shrink-0 text-[10px] text-ink-5">
                      {formatDateTime(e.created_at)}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </Panel>
        </div>

        <div className="space-y-5">
          <Panel title="Cryptographic identity">
            <div className="space-y-2.5 text-xs">
              <Row label="Content hash" value={<Hash value={question.content_hash} chars={22} />} />
              <Row label="Author" value={<span className="text-ink-2">{question.creator_name}</span>} />
              <Row label="Author UID" value={<span className="font-mono text-ink-3">{question.creator_uid}</span>} />
              <Row label="Marks" value={<span className="text-ink-2">{question.marks}</span>} />
              <Row label="Type" value={<span className="text-ink-2">{question.question_type.replace(/_/g, " ").toLowerCase()}</span>} />
              <Row label="Created" value={<span className="text-ink-3">{formatDateTime(question.created_at)}</span>} />
              <Row label="Approved" value={<span className="text-ink-3">{formatDateTime(question.approved_at)}</span>} />
            </div>
          </Panel>

          <Panel title="Your permissions" subtitle="READ, WRITE and APPROVE are independent">
            <div className="flex items-center justify-between">
              <PermissionPips permissions={question.permissions} />
              <button
                onClick={async () => setVerification(await api.verifyQuestion(uid))}
                className="btn-ghost !px-3 !py-1.5 text-xs"
              >
                <ShieldCheck size={13} />
                Verify integrity
              </button>
            </div>

            {verification && (
              <div className="mt-4">
                {verification.verdict === "VERIFIED" ? (
                  <Alert kind="ok" title="Integrity verified">
                    <p>The stored hash matches the blockchain anchor.</p>
                  </Alert>
                ) : verification.verdict === "TAMPERING_DETECTED" ? (
                  <Alert kind="danger" title="Tampering detected">
                    <p>The recomputed hash does not match what was anchored.</p>
                  </Alert>
                ) : (
                  <Alert kind="warn" title="Cannot verify">
                    <p>The blockchain node is unreachable, so the anchor cannot be checked.</p>
                  </Alert>
                )}
              </div>
            )}
          </Panel>

          <Panel title="Access log" subtitle="Including refusals">
            {accessLog.length === 0 ? (
              <Empty message="No access recorded." />
            ) : (
              <ul className="space-y-1.5">
                {accessLog.slice(0, 12).map((a, i) => (
                  <li key={i} className="flex items-center gap-2.5 text-xs">
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                        a.granted ? "bg-ok/12 text-ok" : "bg-danger/12 text-danger"
                      }`}
                    >
                      {a.access_type}
                    </span>
                    <span className="flex-1 truncate text-ink-3">{a.user_name}</span>
                    <span className="shrink-0 text-[10px] text-ink-5">
                      {a.granted ? "granted" : "denied"}
                    </span>
                  </li>
                ))}
              </ul>
            )}
            <p className="mt-3 flex items-center gap-1.5 text-[11px] text-ink-5">
              <History size={11} />
              Reading a question is itself a security-sensitive event.
            </p>
          </Panel>
        </div>
      </div>
    </Shell>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-rule-soft pb-2 last:border-0">
      <span className="shrink-0 text-ink-4">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  );
}
