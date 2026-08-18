"use client";

import { Blocks, Lock, ShieldCheck, Timer } from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import {
  Alert,
  DifficultyBadge,
  Empty,
  Hash,
  Meter,
  PageHeader,
  PaperBadge,
  Panel,
  RiskBadge,
  Skeleton,
} from "@/components/ui";
import { api, type AuditEvent, type Paper } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

const RELEASE_PRESETS = [15, 30, 60, 300];

export default function PaperDetailPage() {
  const { uid } = useParams<{ uid: string }>();
  const [paper, setPaper] = useState<Paper | null>(null);
  const [trail, setTrail] = useState<AuditEvent[]>([]);
  const [verification, setVerification] = useState<Record<string, unknown> | null>(null);
  const [releaseIn, setReleaseIn] = useState(30);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    api.paper(uid).then(setPaper).catch((e) => setError(e.message));
    api.paperAudit(uid).then(setTrail).catch(() => {});
  }, [uid]);

  useEffect(load, [load]);

  async function run(action: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await action();
      setNotice(success);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }

  if (error && !paper) {
    return (
      <Shell>
        <Alert kind="danger" title="Could not load paper">{error}</Alert>
      </Shell>
    );
  }
  if (!paper) {
    return (
      <Shell>
        <Skeleton rows={5} />
      </Shell>
    );
  }

  const compliance = paper.blueprint_compliance;

  return (
    <Shell>
      <PageHeader title={paper.paper_uid} description={paper.exam_title}>
        <div className="flex items-center gap-2">
          <PaperBadge status={paper.status} />
          {(paper.status === "LOCKED" || paper.status === "RELEASED") && (
            <Link href={`/timelock?paper=${paper.paper_uid}`} className="btn-ghost !px-3 !py-1.5 text-xs">
              <Timer size={13} />
              Time-lock demo
            </Link>
          )}
        </div>
      </PageHeader>

      {error && <div className="mb-5"><Alert kind="danger" title="Action refused">{error}</Alert></div>}
      {notice && <div className="mb-5"><Alert kind="ok" title="Done">{notice}</Alert></div>}

      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <div className="space-y-5">
          <Panel title="Paper security" subtitle="Assemble, encrypt, then arm the time lock">
            <div className="space-y-2.5 text-xs">
              <Row label="Paper hash" value={<Hash value={paper.paper_hash} chars={24} />} />
              <Row label="Contract" value={<Hash value={paper.contract_address} chars={20} />} />
              <Row label="Registration tx" value={<Hash value={paper.registration_tx} chars={20} />} />
              <Row label="Release tx" value={<Hash value={paper.release_tx} chars={20} />} />
              <Row label="Release time" value={<span className="text-slate-300">{formatDateTime(paper.release_time)}</span>} />
              <Row label="Released at" value={<span className="text-slate-300">{formatDateTime(paper.released_at)}</span>} />
            </div>

            <div className="mt-5 flex flex-wrap items-center gap-2 border-t border-white/[0.06] pt-4">
              {(paper.status === "DRAFT" || paper.status === "PENDING_APPROVAL") && (
                <button
                  onClick={() => run(() => api.encryptPaper(uid), "Paper encrypted with AES-256-GCM.")}
                  disabled={busy}
                  className="btn-primary"
                >
                  <ShieldCheck size={14} />
                  Approve and encrypt
                </button>
              )}

              {paper.status === "ENCRYPTED" && (
                <>
                  <select
                    value={releaseIn}
                    onChange={(e) => setReleaseIn(Number(e.target.value))}
                    className="field w-auto"
                  >
                    {RELEASE_PRESETS.map((s) => (
                      <option key={s} value={s}>
                        Release in {s < 60 ? `${s}s` : `${s / 60}m`}
                      </option>
                    ))}
                  </select>
                  <button
                    onClick={() =>
                      run(
                        () => api.registerPaper(uid, releaseIn),
                        "Registered on chain. The time lock is armed.",
                      )
                    }
                    disabled={busy}
                    className="btn-primary"
                  >
                    <Lock size={14} />
                    Register and lock
                  </button>
                </>
              )}

              <button
                onClick={async () => setVerification(await api.verifyPaper(uid))}
                className="btn-ghost"
              >
                <ShieldCheck size={14} />
                Verify integrity
              </button>
            </div>

            {verification && (
              <div className="mt-4">
                {verification.verdict === "VERIFIED" ? (
                  <Alert kind="ok" title="Paper integrity verified">
                    <p>The encrypted artifact&rsquo;s hash matches the blockchain anchor.</p>
                  </Alert>
                ) : verification.verdict === "PAPER_INTEGRITY_FAILURE" ? (
                  <Alert kind="danger" title="PAPER INTEGRITY FAILURE">
                    <p>The stored ciphertext no longer matches what was registered.</p>
                  </Alert>
                ) : (
                  <Alert kind="warn" title="Cannot verify">
                    <p>Blockchain unreachable, so the anchor cannot be checked.</p>
                  </Alert>
                )}
              </div>
            )}
          </Panel>

          <Panel title="Questions in this paper">
            {!paper.questions?.length ? (
              <Empty message="No questions recorded." />
            ) : (
              <div className="space-y-2">
                {paper.questions.map((q) => (
                  <div key={q.sequence} className="rounded-lg border border-white/[0.06] px-3.5 py-2.5">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-mono text-[11px] text-accent">Q{q.sequence}</span>
                      <span className="font-mono text-[11px] text-slate-500">{q.question_uid}</span>
                      <DifficultyBadge difficulty={q.difficulty} />
                      <span className="text-[11px] text-slate-500">{q.topic}</span>
                      <span className="text-[11px] text-slate-500">{q.marks} marks</span>
                      {q.used_variation && (
                        <span className="rounded bg-locked/12 px-1.5 py-0.5 text-[10px] text-locked">
                          variation queued
                        </span>
                      )}
                    </div>
                    {q.selection_reason && (
                      <p className="mt-1.5 text-[11px] text-slate-600">{q.selection_reason}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Panel>
        </div>

        <div className="space-y-5">
          {compliance && (
            <Panel title="Blueprint compliance">
              <div className="space-y-3.5">
                <Meter label="Difficulty" value={compliance.difficulty_compliance} />
                <Meter label="Topic" value={compliance.topic_compliance} />
                <Meter label="Marks" value={compliance.marks_compliance} />
              </div>
              <div className="mt-4 flex items-center justify-between border-t border-white/[0.06] pt-3 text-xs">
                <span className="text-slate-500">Duplicate risk</span>
                <RiskBadge risk={compliance.duplicate_risk} />
              </div>
            </Panel>
          )}

          <Panel title="Lifecycle audit" subtitle="Including every denied attempt">
            {trail.length === 0 ? (
              <Empty message="No events." />
            ) : (
              <ol className="space-y-1.5">
                {trail.map((e) => (
                  <li key={e.event_uid} className="flex items-center gap-2.5 text-xs">
                    <span
                      className={`h-1.5 w-1.5 shrink-0 rounded-full ${e.success ? "bg-ok" : "bg-danger"}`}
                    />
                    <span className="flex-1 truncate text-slate-300">
                      {e.event_type.replace(/_/g, " ").toLowerCase()}
                    </span>
                    {e.blockchain_tx && <Blocks size={11} className="shrink-0 text-accent" />}
                    <span className="shrink-0 text-[10px] text-slate-600">
                      {formatDateTime(e.created_at).split(", ")[1]}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </Panel>
        </div>
      </div>
    </Shell>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-white/[0.04] pb-2 last:border-0">
      <span className="shrink-0 text-slate-500">{label}</span>
      <span className="text-right">{value}</span>
    </div>
  );
}
