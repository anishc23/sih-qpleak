"use client";

import { CheckCircle2, KeyRound, Send, Shield } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import Shell from "@/components/Shell";
import { Alert, Hash, PageHeader, Panel } from "@/components/ui";
import { api, type ChainReceipt, type Question } from "@/lib/api";

const TOPICS = [
  "Data Structures",
  "Algorithms",
  "DBMS",
  "Operating Systems",
  "Computer Networks",
  "Cybersecurity",
];

const TYPES = ["SHORT_ANSWER", "LONG_ANSWER", "MCQ", "NUMERICAL", "PROBLEM"];

export default function CreateQuestionPage() {
  const [form, setForm] = useState({
    content: "",
    subject: "Computer Science",
    topic: TOPICS[0],
    difficulty: "MEDIUM",
    question_type: "SHORT_ANSWER",
    marks: 5,
    learning_objective: "",
  });
  const [result, setResult] = useState<{
    question: Question;
    encryption: Record<string, unknown>;
    blockchain: ChainReceipt;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api.createQuestion({
        ...form,
        learning_objective: form.learning_objective || null,
      });
      setResult(res);
      setForm((f) => ({ ...f, content: "", learning_objective: "" }));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create question.");
    } finally {
      setBusy(false);
    }
  }

  async function submitForReview() {
    if (!result) return;
    try {
      await api.submitQuestion(result.question.question_uid);
      setResult(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit.");
    }
  }

  return (
    <Shell>
      <PageHeader
        title="Create Question"
        description="On submission the text is encrypted with a fresh AES-256 key, hashed with SHA-256, and its fingerprint anchored on the blockchain. The plaintext is never stored."
      />

      <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
        <Panel>
          <form onSubmit={submit} className="space-y-4">
            <div>
              <label htmlFor="content" className="label mb-1.5 block">
                Question
              </label>
              <textarea
                id="content"
                required
                minLength={10}
                rows={6}
                value={form.content}
                onChange={(e) => setForm({ ...form, content: e.target.value })}
                className="field resize-y font-mono text-[13px]"
                placeholder="Explain how a Merkle tree enables efficient membership proofs."
              />
              <p className="mt-1.5 text-[11px] text-slate-600">
                {form.content.length} characters. Encrypted before it reaches the database.
              </p>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div>
                <label htmlFor="topic" className="label mb-1.5 block">
                  Topic
                </label>
                <select
                  id="topic"
                  value={form.topic}
                  onChange={(e) => setForm({ ...form, topic: e.target.value })}
                  className="field"
                >
                  {TOPICS.map((t) => (
                    <option key={t}>{t}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="difficulty" className="label mb-1.5 block">
                  Difficulty
                </label>
                <select
                  id="difficulty"
                  value={form.difficulty}
                  onChange={(e) => setForm({ ...form, difficulty: e.target.value })}
                  className="field"
                >
                  {["EASY", "MEDIUM", "HARD"].map((d) => (
                    <option key={d}>{d}</option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="type" className="label mb-1.5 block">
                  Question type
                </label>
                <select
                  id="type"
                  value={form.question_type}
                  onChange={(e) => setForm({ ...form, question_type: e.target.value })}
                  className="field"
                >
                  {TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t.replace(/_/g, " ").toLowerCase()}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label htmlFor="marks" className="label mb-1.5 block">
                  Marks
                </label>
                <input
                  id="marks"
                  type="number"
                  min={1}
                  max={100}
                  value={form.marks}
                  onChange={(e) => setForm({ ...form, marks: Number(e.target.value) })}
                  className="field"
                />
              </div>
            </div>

            <div>
              <label htmlFor="objective" className="label mb-1.5 block">
                Learning objective <span className="text-slate-700">(optional)</span>
              </label>
              <input
                id="objective"
                value={form.learning_objective}
                onChange={(e) => setForm({ ...form, learning_objective: e.target.value })}
                className="field"
                placeholder="Assess understanding of cryptographic accumulators"
              />
            </div>

            {error && <Alert kind="danger" title="Could not create question">{error}</Alert>}

            <button type="submit" disabled={busy} className="btn-primary">
              <Shield size={15} />
              {busy ? "Encrypting and anchoring..." : "Encrypt and register"}
            </button>
          </form>
        </Panel>

        <div className="space-y-5">
          {result ? (
            <>
              <Panel title="Question secured" subtitle="Every value below is real, not illustrative">
                <div className="space-y-2.5 text-xs">
                  <Row label="Question ID" value={<span className="font-mono text-accent">{result.question.question_uid}</span>} />
                  <Row label="SHA-256" value={<Hash value={result.question.content_hash} chars={20} />} />
                  <Row label="Cipher" value={<span className="text-slate-300">{String(result.encryption.algorithm)}</span>} />
                  <Row label="Ciphertext" value={<span className="text-slate-300">{String(result.encryption.ciphertext_bytes)} bytes</span>} />
                  <Row label="Key storage" value={<span className="text-slate-400">wrapped, never bare</span>} />
                  <Row label="Version" value={<span className="text-slate-300">v{result.question.version}</span>} />
                  <Row label="Status" value={<span className="text-slate-300">{result.question.status}</span>} />
                </div>
              </Panel>

              <Panel title="Blockchain anchor">
                {result.blockchain.confirmed ? (
                  <>
                    <Alert kind="ok" title="Provenance recorded">
                      <p>Block #{result.blockchain.block_number}</p>
                    </Alert>
                    <div className="mt-3">
                      <p className="label mb-1">Transaction hash</p>
                      <Hash value={result.blockchain.tx_hash} chars={40} />
                    </div>
                  </>
                ) : (
                  <Alert kind="warn" title="Blockchain node unavailable">
                    <p>{result.blockchain.error ?? result.blockchain.message}</p>
                    <p className="mt-2">
                      The question is still encrypted and hashed. No transaction hash is shown
                      because none exists &mdash; the system does not fabricate one.
                    </p>
                  </Alert>
                )}
              </Panel>

              <div className="flex gap-2">
                <button onClick={submitForReview} className="btn-primary flex-1">
                  <Send size={14} />
                  Submit for review
                </button>
                <Link href={`/vault/${result.question.question_uid}`} className="btn-ghost">
                  View
                </Link>
              </div>
            </>
          ) : (
            <Panel title="What happens on submit">
              <ol className="space-y-3 text-[13px] text-slate-400">
                {[
                  ["Generate a fresh AES-256 key", "unique to this question, never reused"],
                  ["Encrypt with AES-256-GCM", "authenticated, so tampering is detectable"],
                  ["Compute SHA-256 of the canonical text", "the question's cryptographic identity"],
                  ["Wrap the key under the master key", "the bare key never touches the database"],
                  ["Anchor the hash on chain", "provenance that a DBA cannot silently rewrite"],
                  ["Write two audit events", "hash-chained to everything before them"],
                ].map(([title, sub], i) => (
                  <li key={title} className="flex gap-3">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded bg-accent/10 font-mono text-[10px] text-accent">
                      {i + 1}
                    </span>
                    <div>
                      <p className="text-slate-300">{title}</p>
                      <p className="text-[11px] text-slate-600">{sub}</p>
                    </div>
                  </li>
                ))}
              </ol>
              <div className="mt-4 flex gap-2.5 rounded-lg border border-white/[0.07] bg-base-850/50 px-3.5 py-2.5">
                <KeyRound size={14} className="mt-0.5 shrink-0 text-slate-600" />
                <p className="text-[11px] leading-relaxed text-slate-500">
                  There is no <code className="font-mono">content</code> column on the questions
                  table &mdash; only ciphertext. Plaintext cannot be written by mistake.
                </p>
              </div>
            </Panel>
          )}
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
