"use client";

import { FileStack } from "lucide-react";
import Link from "next/link";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Alert, Empty, Hash, PageHeader, PaperBadge, Panel, Skeleton } from "@/components/ui";
import { api, type Paper } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

export default function PapersPage() {
  const [papers, setPapers] = useState<Paper[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.papers().then(setPapers).catch((e) => setError(e.message));
  }, []);

  return (
    <Shell>
      <PageHeader
        title="Papers"
        description="Every assembled paper and its lifecycle position, from draft through encryption, blockchain registration and release."
      />

      {error && <Alert kind="danger" title="Could not load papers">{error}</Alert>}

      <Panel>
        {!papers ? (
          <Skeleton rows={4} />
        ) : papers.length === 0 ? (
          <Empty message="No papers yet." hint="Generate one in the Paper Builder." />
        ) : (
          <div className="space-y-2">
            {papers.map((p) => (
              <Link
                key={p.paper_uid}
                href={`/papers/${p.paper_uid}`}
                className="block rounded-lg border border-white/[0.06] px-4 py-3.5 transition hover:border-accent/25 hover:bg-white/[0.02]"
              >
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <FileStack size={15} className="text-slate-600" />
                    <div>
                      <p className="font-mono text-sm text-slate-200">{p.paper_uid}</p>
                      <p className="mt-0.5 text-[11px] text-slate-500">
                        {p.exam_title} &middot; {p.question_count} questions
                      </p>
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-4">
                    <Hash value={p.paper_hash} chars={14} />
                    <span className="text-[11px] text-slate-600">
                      {formatDateTime(p.created_at)}
                    </span>
                    <PaperBadge status={p.status} />
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </Panel>
    </Shell>
  );
}
