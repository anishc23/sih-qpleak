"use client";

import { FilePlus2, Search, Vault as VaultIcon } from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
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
import { api, type Question, type QuestionStatus } from "@/lib/api";
import { useAuth } from "@/lib/auth";

const STATUSES: QuestionStatus[] = [
  "DRAFT",
  "SUBMITTED",
  "UNDER_REVIEW",
  "AVAILABLE_FOR_SYNTHESIS",
  "REJECTED",
  "SELECTED",
  "USED_IN_PAPER",
];

export default function VaultPage() {
  const { user } = useAuth();
  const [questions, setQuestions] = useState<Question[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<string>("");

  useEffect(() => {
    api
      .questions({ limit: 300, status: status || undefined })
      .then(setQuestions)
      .catch((e) => setError(e.message));
  }, [status]);

  const filtered = useMemo(() => {
    if (!questions) return null;
    const q = query.trim().toLowerCase();
    if (!q) return questions;
    return questions.filter(
      (item) =>
        item.question_uid.toLowerCase().includes(q) ||
        item.topic.toLowerCase().includes(q) ||
        item.creator_name.toLowerCase().includes(q) ||
        item.content_hash.startsWith(q),
    );
  }, [questions, query]);

  return (
    <Shell>
      <PageHeader
        title="Question Vault"
        description="Metadata and cryptographic identity only. Question text is encrypted at rest and requires an explicit, audited read."
      >
        {user?.role === "QUESTION_SETTER" && (
          <Link href="/vault/create" className="btn-primary">
            <FilePlus2 size={15} />
            Create question
          </Link>
        )}
      </PageHeader>

      {error && <Alert kind="danger" title="Could not load questions">{error}</Alert>}

      <Panel>
        <div className="mb-4 flex flex-wrap gap-2">
          <div className="relative min-w-56 flex-1">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-600" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search by ID, topic, author or hash prefix"
              className="field pl-9"
            />
          </div>
          <select value={status} onChange={(e) => setStatus(e.target.value)} className="field w-auto">
            <option value="">All statuses</option>
            {STATUSES.map((s) => (
              <option key={s} value={s}>
                {s.replace(/_/g, " ")}
              </option>
            ))}
          </select>
        </div>

        {!filtered ? (
          <Skeleton rows={6} />
        ) : filtered.length === 0 ? (
          <Empty
            message="No questions match."
            hint={
              user?.role === "QUESTION_SETTER"
                ? "You only ever see your own questions — that is the access model, not a filter."
                : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-white/[0.07] text-left">
                  {["ID", "Topic", "Difficulty", "Marks", "Ver", "Status", "Author", "Hash", "Perms"].map(
                    (h) => (
                      <th key={h} className="px-2 py-2.5 text-[11px] font-medium uppercase tracking-wider text-slate-500">
                        {h}
                      </th>
                    ),
                  )}
                </tr>
              </thead>
              <tbody>
                {filtered.map((q) => (
                  <tr key={q.question_uid} className="border-b border-white/[0.04] transition hover:bg-white/[0.02]">
                    <td className="px-2 py-2.5">
                      <Link
                        href={`/vault/${q.question_uid}`}
                        className="font-mono text-xs text-accent hover:underline"
                      >
                        {q.question_uid}
                      </Link>
                    </td>
                    <td className="px-2 py-2.5 text-slate-300">{q.topic}</td>
                    <td className="px-2 py-2.5">
                      <DifficultyBadge difficulty={q.difficulty} />
                    </td>
                    <td className="px-2 py-2.5 tabular-nums text-slate-400">{q.marks}</td>
                    <td className="px-2 py-2.5 font-mono text-xs text-slate-500">v{q.version}</td>
                    <td className="px-2 py-2.5">
                      <StatusBadge status={q.status} />
                    </td>
                    <td className="px-2 py-2.5 text-xs text-slate-400">{q.creator_name}</td>
                    <td className="px-2 py-2.5">
                      <Hash value={q.content_hash} chars={10} />
                    </td>
                    <td className="px-2 py-2.5">
                      <PermissionPips permissions={q.permissions} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {filtered && (
          <p className="mt-4 flex items-center gap-2 text-[11px] text-slate-600">
            <VaultIcon size={12} />
            {filtered.length} question{filtered.length === 1 ? "" : "s"} visible to you. R/W/A shows
            your independent READ, WRITE and APPROVE grants on each.
          </p>
        )}
      </Panel>
    </Shell>
  );
}
