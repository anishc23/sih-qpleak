"use client";

import { Check, Eye, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import {
  Alert,
  DifficultyBadge,
  Empty,
  Hash,
  PageHeader,
  Panel,
  Skeleton,
  StatusBadge,
} from "@/components/ui";
import { api, type Question } from "@/lib/api";

export default function ReviewQueuePage() {
  const [queue, setQueue] = useState<Question[] | null>(null);
  const [contents, setContents] = useState<Record<string, string>>({});
  const [comment, setComment] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([
      api.questions({ status: "SUBMITTED", limit: 100 }),
      api.questions({ status: "UNDER_REVIEW", limit: 100 }),
    ])
      .then(([a, b]) => setQueue([...a, ...b]))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function reveal(uid: string) {
    try {
      const res = await api.readQuestion(uid);
      setContents((c) => ({ ...c, [uid]: res.content }));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Read denied.");
    }
  }

  async function decide(uid: string, approve: boolean) {
    setError(null);
    try {
      await api.reviewQuestion(uid, approve, comment[uid] || undefined);
      setNotice(`${uid} ${approve ? "approved and released into the synthesis pool" : "rejected"}.`);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed.");
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Review Queue"
        description="Approve or reject submitted questions. You can read and approve, but never edit — and you cannot approve a question you authored."
      />

      {error && <div className="mb-5"><Alert kind="danger" title="Action refused">{error}</Alert></div>}
      {notice && <div className="mb-5"><Alert kind="ok" title="Recorded">{notice}</Alert></div>}

      {!queue ? (
        <Skeleton rows={4} />
      ) : queue.length === 0 ? (
        <Panel>
          <Empty message="Nothing awaiting review." hint="Submitted questions appear here." />
        </Panel>
      ) : (
        <div className="space-y-4">
          {queue.map((q) => (
            <Panel key={q.question_uid}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm text-accent">{q.question_uid}</span>
                    <StatusBadge status={q.status} />
                    <DifficultyBadge difficulty={q.difficulty} />
                    <span className="text-xs text-slate-500">{q.marks} marks</span>
                  </div>
                  <p className="mt-1.5 text-xs text-slate-500">
                    {q.topic} &middot; by {q.creator_name} &middot; v{q.version}
                  </p>
                </div>
                <Hash value={q.content_hash} chars={16} />
              </div>

              <div className="mt-4">
                {contents[q.question_uid] ? (
                  <p className="whitespace-pre-wrap rounded-lg border border-white/[0.06] bg-base-950/60 p-4 text-[13px] leading-relaxed text-slate-200">
                    {contents[q.question_uid]}
                  </p>
                ) : (
                  <button onClick={() => reveal(q.question_uid)} className="btn-ghost !py-2 text-xs">
                    <Eye size={13} />
                    Reveal content (logged as a READ)
                  </button>
                )}
              </div>

              <div className="mt-4 flex flex-wrap items-center gap-2">
                <input
                  value={comment[q.question_uid] ?? ""}
                  onChange={(e) => setComment((c) => ({ ...c, [q.question_uid]: e.target.value }))}
                  placeholder="Review comment (optional)"
                  className="field min-w-48 flex-1"
                />
                <button onClick={() => decide(q.question_uid, true)} className="btn-primary">
                  <Check size={14} />
                  Approve
                </button>
                <button onClick={() => decide(q.question_uid, false)} className="btn-danger">
                  <X size={14} />
                  Reject
                </button>
              </div>
            </Panel>
          ))}
        </div>
      )}
    </Shell>
  );
}
