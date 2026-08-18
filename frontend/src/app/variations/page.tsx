"use client";

import { ArrowRight, Check, Sparkles, X } from "lucide-react";
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
} from "@/components/ui";
import { api, type Variation } from "@/lib/api";

export default function VariationsPage() {
  const [items, setItems] = useState<Variation[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api.variations().then(setItems).catch((e) => setError(e.message));
  }, []);

  useEffect(load, [load]);

  async function decide(id: number, approve: boolean) {
    try {
      await api.reviewVariation(id, approve);
      load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Decision failed.");
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Question Variations"
        description="Engine-generated rewordings awaiting human approval. The engine restates the instruction verb only — the substantive clause is copied verbatim, so the expected answer cannot drift."
      />

      {error && <div className="mb-5"><Alert kind="danger" title="Error">{error}</Alert></div>}

      <div className="mb-5">
        <Alert kind="info" title="This is a deterministic rule engine, not a language model">
          <p>
            Every variation carries its original hash, generated hash, similarity score and the
            exact rule applied. No variation reaches a paper without a reviewer decision.
          </p>
        </Alert>
      </div>

      {!items ? (
        <Skeleton rows={4} />
      ) : items.length === 0 ? (
        <Panel>
          <Empty
            message="No variations generated yet."
            hint="Generate a paper with variations enabled in the Paper Builder."
          />
        </Panel>
      ) : (
        <div className="space-y-4">
          {items.map((v) => (
            <Panel key={v.id}>
              <div className="mb-3.5 flex flex-wrap items-center justify-between gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Sparkles size={14} className="text-locked" />
                  <span className="font-mono text-sm text-accent">{v.question_uid}</span>
                  <DifficultyBadge difficulty={v.difficulty} />
                  <span className="text-xs text-slate-500">{v.topic}</span>
                </div>
                <span
                  className={`rounded px-2 py-0.5 text-[11px] font-medium ${
                    v.review_status === "APPROVED"
                      ? "bg-ok/12 text-ok"
                      : v.review_status === "REJECTED"
                        ? "bg-danger/12 text-danger"
                        : "bg-warn/12 text-warn"
                  }`}
                >
                  {v.review_status}
                </span>
              </div>

              <div className="grid gap-3 lg:grid-cols-[1fr_auto_1fr]">
                <div>
                  <p className="label mb-1.5">Original</p>
                  <p className="rounded-lg border border-white/[0.06] bg-base-950/60 p-3.5 text-[13px] leading-relaxed text-slate-300">
                    {v.original}
                  </p>
                  <div className="mt-1.5">
                    <Hash value={v.original_hash} chars={16} />
                  </div>
                </div>

                <div className="flex items-center justify-center">
                  <ArrowRight size={16} className="text-slate-700" />
                </div>

                <div>
                  <p className="label mb-1.5">Generated variation</p>
                  <p className="rounded-lg border border-locked/20 bg-locked/[0.04] p-3.5 text-[13px] leading-relaxed text-slate-200">
                    {v.variation}
                  </p>
                  <div className="mt-1.5">
                    <Hash value={v.generated_hash} chars={16} />
                  </div>
                </div>
              </div>

              <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.06] pt-3.5">
                <div className="flex flex-wrap items-center gap-4 text-[11px] text-slate-500">
                  <span>
                    Similarity{" "}
                    <span className="font-mono text-slate-300">
                      {(v.similarity_score * 100).toFixed(0)}%
                    </span>
                  </span>
                  <span>
                    Rule <span className="font-mono text-slate-400">{v.generation_method}</span>
                  </span>
                </div>
                {v.review_status === "PENDING" && (
                  <div className="flex gap-2">
                    <button onClick={() => decide(v.id, true)} className="btn-primary !py-2 text-xs">
                      <Check size={13} />
                      Approve
                    </button>
                    <button onClick={() => decide(v.id, false)} className="btn-danger !py-2 text-xs">
                      <X size={13} />
                      Reject
                    </button>
                  </div>
                )}
              </div>
            </Panel>
          ))}
        </div>
      )}
    </Shell>
  );
}
