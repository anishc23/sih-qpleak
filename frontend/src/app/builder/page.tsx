"use client";

import { Copy, Layers, Sparkles, Users } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import {
  Alert,
  DifficultyBadge,
  Empty,
  Meter,
  PageHeader,
  Panel,
  RiskBadge,
  Skeleton,
  Stat,
} from "@/components/ui";
import { api, type DuplicatePair, type Exam, type Paper } from "@/lib/api";

export default function PaperBuilderPage() {
  const [exams, setExams] = useState<Exam[] | null>(null);
  const [examUid, setExamUid] = useState("");
  const [applyVariations, setApplyVariations] = useState(true);
  const [duplicates, setDuplicates] = useState<{
    pool_size: number;
    threshold: number;
    method: string;
    pairs: DuplicatePair[];
    high_risk: number;
  } | null>(null);
  const [paper, setPaper] = useState<Paper | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .exams()
      .then((e) => {
        setExams(e);
        if (e.length) setExamUid(e[0].exam_uid);
      })
      .catch((err) => setError(err.message));
    api.duplicates().then(setDuplicates).catch(() => {});
  }, []);

  async function generate() {
    setBusy(true);
    setError(null);
    setPaper(null);
    try {
      setPaper(await api.generatePaper(examUid, applyVariations));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Generation failed.");
    } finally {
      setBusy(false);
    }
  }

  const exam = exams?.find((e) => e.exam_uid === examUid);
  const compliance = paper?.blueprint_compliance;
  const report = paper?.synthesis_report;

  return (
    <Shell>
      <PageHeader
        title="Paper Builder"
        description="A seeded optimiser selects from the approved pool against the blueprint, penalising near-duplicates and spreading authorship. Same seed, same paper — reproducible for a demo."
      />

      {error && <div className="mb-5"><Alert kind="danger" title="Could not generate">{error}</Alert></div>}

      <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">
        <div className="space-y-5">
          <Panel title="Examination blueprint">
            {!exams ? (
              <Skeleton rows={3} />
            ) : exams.length === 0 ? (
              <Empty message="No exams configured." />
            ) : (
              <>
                <select value={examUid} onChange={(e) => setExamUid(e.target.value)} className="field">
                  {exams.map((e) => (
                    <option key={e.exam_uid} value={e.exam_uid}>
                      {e.title}
                    </option>
                  ))}
                </select>

                {exam && (
                  <div className="mt-4 space-y-2.5 text-xs">
                    <Row label="Subject" value={exam.subject} />
                    <Row label="Questions" value={String(exam.question_count)} />
                    <Row label="Total marks" value={String(exam.total_marks)} />
                    {exam.blueprint && (
                      <>
                        <div className="pt-2">
                          <p className="label mb-2">Difficulty mix</p>
                          <div className="flex flex-wrap gap-1.5">
                            {Object.entries(exam.blueprint.difficulty_distribution).map(([k, v]) => (
                              <span
                                key={k}
                                className="rounded border border-white/10 px-2 py-0.5 text-[11px] text-slate-400"
                              >
                                {k.toLowerCase()} {v}%
                              </span>
                            ))}
                          </div>
                        </div>
                        <div className="pt-1">
                          <p className="label mb-2">Topic mix</p>
                          <div className="flex flex-wrap gap-1.5">
                            {Object.entries(exam.blueprint.topic_distribution).map(([k, v]) => (
                              <span
                                key={k}
                                className="rounded border border-white/10 px-2 py-0.5 text-[11px] text-slate-400"
                              >
                                {k} {v}%
                              </span>
                            ))}
                          </div>
                        </div>
                      </>
                    )}
                  </div>
                )}

                <label className="mt-4 flex cursor-pointer items-start gap-2.5 rounded-lg border border-white/[0.07] px-3.5 py-2.5">
                  <input
                    type="checkbox"
                    checked={applyVariations}
                    onChange={(e) => setApplyVariations(e.target.checked)}
                    className="mt-0.5 accent-cyan-400"
                  />
                  <div>
                    <p className="text-xs text-slate-300">Generate question variations</p>
                    <p className="mt-0.5 text-[11px] text-slate-600">
                      Rule-based rewording, queued for reviewer approval. Not a language model.
                    </p>
                  </div>
                </label>

                <button onClick={generate} disabled={busy || !examUid} className="btn-primary mt-4 w-full">
                  <Sparkles size={15} />
                  {busy ? "Synthesising..." : "Generate secure paper"}
                </button>
              </>
            )}
          </Panel>

          <Panel
            title="Duplicate analysis"
            subtitle={duplicates?.method ?? "TF-IDF + cosine similarity"}
          >
            {!duplicates ? (
              <Skeleton rows={2} />
            ) : (
              <>
                <div className="mb-3 grid grid-cols-2 gap-2 text-xs">
                  <div className="rounded-lg bg-base-850/60 px-3 py-2">
                    <p className="text-slate-500">Pool</p>
                    <p className="mt-0.5 text-base font-semibold text-white">{duplicates.pool_size}</p>
                  </div>
                  <div className="rounded-lg bg-base-850/60 px-3 py-2">
                    <p className="text-slate-500">High risk</p>
                    <p
                      className={`mt-0.5 text-base font-semibold ${duplicates.high_risk ? "text-danger" : "text-ok"}`}
                    >
                      {duplicates.high_risk}
                    </p>
                  </div>
                </div>
                {duplicates.pairs.length === 0 ? (
                  <Empty message="No similar pairs above threshold." />
                ) : (
                  <ul className="space-y-1.5">
                    {duplicates.pairs.slice(0, 8).map((p, i) => (
                      <li key={i} className="flex items-center gap-2 text-xs">
                        <Copy size={11} className="shrink-0 text-slate-600" />
                        <span className="font-mono text-[11px] text-slate-400">
                          {p.left} ~ {p.right}
                        </span>
                        <span className="ml-auto tabular-nums text-slate-300">
                          {(p.similarity * 100).toFixed(0)}%
                        </span>
                        <RiskBadge risk={p.risk} />
                      </li>
                    ))}
                  </ul>
                )}
              </>
            )}
          </Panel>
        </div>

        <div className="space-y-5">
          {!paper ? (
            <Panel title="Selection pipeline">
              <ol className="space-y-3 text-[13px] text-slate-400">
                {[
                  ["Collect approved candidates", "only questions that passed review"],
                  ["Build TF-IDF vectors", "computed locally, no external model"],
                  ["Detect near-duplicates", "cosine similarity across every pair"],
                  ["Score against the blueprint", "topic + difficulty + marks fit"],
                  ["Penalise duplicates and author concentration", "spreads knowledge of the paper"],
                  ["Select with a seeded RNG", "reproducible, but not predictable to a setter"],
                  ["Queue variations for review", "a human approves every rewording"],
                ].map(([t, s], i) => (
                  <li key={t} className="flex gap-3">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-accent/10 font-mono text-[10px] text-accent">
                      {i + 1}
                    </span>
                    <div>
                      <p className="text-slate-300">{t}</p>
                      <p className="text-[11px] text-slate-600">{s}</p>
                    </div>
                  </li>
                ))}
              </ol>
              <div className="mt-4 rounded-lg border border-warn/20 bg-warn/[0.04] px-3.5 py-2.5">
                <p className="text-[11px] leading-relaxed text-slate-400">
                  This reduces how well any one setter can predict the final paper. It is a
                  probabilistic improvement, not a guarantee &mdash; and the system does not claim
                  otherwise.
                </p>
              </div>
            </Panel>
          ) : (
            <>
              <Alert kind="ok" title={`${paper.paper_uid} generated`}>
                <p>
                  {paper.question_count} questions selected.{" "}
                  <Link href={`/papers/${paper.paper_uid}`} className="underline">
                    Open paper
                  </Link>
                </p>
              </Alert>

              {compliance && (
                <Panel title="Blueprint compliance">
                  <div className="space-y-3.5">
                    <Meter label="Difficulty distribution" value={compliance.difficulty_compliance} />
                    <Meter label="Topic distribution" value={compliance.topic_compliance} />
                    <Meter label="Marks distribution" value={compliance.marks_compliance} />
                  </div>
                  <div className="mt-4 flex items-center justify-between border-t border-white/[0.06] pt-3.5 text-xs">
                    <span className="text-slate-500">Residual duplicate risk</span>
                    <RiskBadge risk={compliance.duplicate_risk} />
                  </div>
                  <div className="mt-2 flex items-center justify-between text-xs">
                    <span className="text-slate-500">Marks</span>
                    <span className="tabular-nums text-slate-300">
                      {compliance.marks_actual} / {compliance.marks_target}
                    </span>
                  </div>
                </Panel>
              )}

              {report && (
                <div className="grid gap-3 sm:grid-cols-3">
                  <Stat label="Pool" value={report.pool_size} icon={Layers} />
                  <Stat label="Contributors" value={report.distinct_contributors} tone="ok" icon={Users} />
                  <Stat label="Seed" value={report.seed} hint="reproducible" />
                </div>
              )}

              <Panel title="Selected questions" subtitle="With the engine's reasoning for each">
                <div className="max-h-96 space-y-2 overflow-auto">
                  {paper.questions?.map((q) => (
                    <div key={q.sequence} className="rounded-lg border border-white/[0.06] px-3.5 py-2.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-[11px] text-accent">Q{q.sequence}</span>
                        <span className="font-mono text-[11px] text-slate-500">{q.question_uid}</span>
                        <DifficultyBadge difficulty={q.difficulty} />
                        <span className="text-[11px] text-slate-500">{q.topic}</span>
                        <span className="ml-auto text-[11px] tabular-nums text-slate-400">
                          score {q.selection_score.toFixed(2)}
                        </span>
                      </div>
                      {q.selection_reason && (
                        <p className="mt-1.5 text-[11px] leading-relaxed text-slate-600">
                          {q.selection_reason}
                        </p>
                      )}
                    </div>
                  ))}
                </div>
              </Panel>
            </>
          )}
        </div>
      </div>
    </Shell>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-white/[0.04] pb-2 last:border-0">
      <span className="text-slate-500">{label}</span>
      <span className="text-slate-300">{value}</span>
    </div>
  );
}
