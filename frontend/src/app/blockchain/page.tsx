"use client";

import { Blocks, Radio } from "lucide-react";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Alert, Empty, Hash, PageHeader, Panel, Skeleton, Stat } from "@/components/ui";
import { api, type BlockchainStatus } from "@/lib/api";
import { formatDateTime, formatUnix } from "@/lib/format";

type Tx = {
  tx_hash: string | null;
  contract: string;
  method: string;
  resource_type: string;
  resource_id: string;
  status: string;
  block_number: number | null;
  gas_used: number | null;
  error: string | null;
  created_at: string;
};

type ChainEvent = {
  contract: string;
  event: string;
  block_number: number;
  tx_hash: string;
  args: Record<string, unknown>;
};

export default function BlockchainPage() {
  const [status, setStatus] = useState<BlockchainStatus | null>(null);
  const [txs, setTxs] = useState<Tx[] | null>(null);
  const [events, setEvents] = useState<ChainEvent[] | null>(null);
  const [eventsError, setEventsError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => {
      api.blockchainStatus().then(setStatus).catch(() => {});
      api.blockchainTransactions().then(setTxs).catch(() => setTxs([]));
      api
        .blockchainEvents()
        .then((e) => {
          setEvents(e);
          setEventsError(null);
        })
        .catch((e) => setEventsError(e.message));
    };
    load();
    const id = setInterval(load, 8000);
    return () => clearInterval(id);
  }, []);

  const confirmed = txs?.filter((t) => t.status === "CONFIRMED").length ?? 0;
  const unavailable = txs?.filter((t) => t.status === "UNAVAILABLE").length ?? 0;

  return (
    <Shell>
      <PageHeader
        title="Blockchain Explorer"
        description="Transactions we submitted, and events read back directly from the chain rather than from our database."
      >
        {status && (
          <span
            className={`inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-xs ${
              status.connected
                ? "border-ok/30 bg-ok/[0.06] text-ok"
                : "border-danger/30 bg-danger/[0.06] text-danger"
            }`}
          >
            <Radio size={13} />
            {status.network_label}
          </span>
        )}
      </PageHeader>

      {status && !status.connected && (
        <div className="mb-5">
          <Alert kind="danger" title="Blockchain node unreachable">
            <p>{status.error}</p>
            <p className="mt-2 text-slate-400">
              Start it with <code className="font-mono">cd blockchain &amp;&amp; npm run node</code>,
              then deploy with <code className="font-mono">npm run deploy:local</code>.
            </p>
          </Alert>
        </div>
      )}

      {status?.connected && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <Stat label="Latest block" value={status.latest_block ?? "--"} icon={Blocks} />
            <Stat label="Chain ID" value={status.chain_id ?? "--"} />
            <Stat label="Confirmed txs" value={confirmed} tone="ok" />
            <Stat
              label="Unavailable"
              value={unavailable}
              tone={unavailable ? "warn" : "default"}
              hint="recorded, never faked"
            />
          </div>

          <div className="mt-5">
            <Panel title="Deployed contracts">
              <div className="space-y-2.5 text-xs">
                {Object.entries(status.contracts ?? {}).map(([name, addr]) => (
                  <div
                    key={name}
                    className="flex items-center justify-between border-b border-white/[0.04] pb-2 last:border-0"
                  >
                    <span className="text-slate-300">{name}.sol</span>
                    <Hash value={addr} chars={30} />
                  </div>
                ))}
                <div className="flex items-center justify-between pt-1">
                  <span className="text-slate-500">Chain time</span>
                  <span className="text-slate-400">{formatUnix(status.blockchain_time)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-slate-500">Relayer</span>
                  <Hash value={status.sender} chars={24} />
                </div>
              </div>
            </Panel>
          </div>
        </>
      )}

      <div className="mt-5 grid gap-5 lg:grid-cols-2">
        <Panel title="Submitted transactions" subtitle="From our database, including failures">
          {!txs ? (
            <Skeleton rows={5} />
          ) : txs.length === 0 ? (
            <Empty message="No transactions yet." />
          ) : (
            <div className="max-h-[28rem] space-y-1.5 overflow-auto">
              {txs.map((t, i) => (
                <div key={i} className="rounded-lg border border-white/[0.06] px-3 py-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-mono text-[11px] text-slate-300">
                      {t.contract}.{t.method}
                    </span>
                    <span
                      className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${
                        t.status === "CONFIRMED"
                          ? "bg-ok/12 text-ok"
                          : t.status === "UNAVAILABLE"
                            ? "bg-warn/12 text-warn"
                            : "bg-danger/12 text-danger"
                      }`}
                    >
                      {t.status}
                    </span>
                  </div>
                  <div className="mt-1 flex flex-wrap items-center gap-3 text-[10px] text-slate-600">
                    <span className="font-mono">{t.resource_id}</span>
                    {t.block_number !== null && <span>block #{t.block_number}</span>}
                    {t.gas_used !== null && <span>{t.gas_used.toLocaleString()} gas</span>}
                    <span>{formatDateTime(t.created_at)}</span>
                  </div>
                  {t.tx_hash ? (
                    <div className="mt-1">
                      <Hash value={t.tx_hash} chars={32} />
                    </div>
                  ) : (
                    <p className="mt-1 text-[10px] italic text-warn">
                      No hash — the transaction never reached the chain.
                    </p>
                  )}
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Contract events" subtitle="Read from the chain, not from our records">
          {eventsError ? (
            <Alert kind="warn" title="Cannot read events">{eventsError}</Alert>
          ) : !events ? (
            <Skeleton rows={5} />
          ) : events.length === 0 ? (
            <Empty message="No events emitted yet." />
          ) : (
            <div className="max-h-[28rem] space-y-1.5 overflow-auto">
              {events.map((e, i) => (
                <div key={i} className="rounded-lg border border-white/[0.06] px-3 py-2.5">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="text-[11px] font-medium text-accent">{e.event}</span>
                    <span className="text-[10px] text-slate-600">block #{e.block_number}</span>
                  </div>
                  <p className="mt-0.5 text-[10px] text-slate-600">{e.contract}</p>
                  <div className="mt-1">
                    <Hash value={e.tx_hash} chars={28} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>
      </div>

      <div className="mt-5">
        <Panel title="What is on chain — and what deliberately is not">
          <div className="grid gap-5 text-[13px] md:grid-cols-2">
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-ok">On chain</p>
              <ul className="space-y-1 text-slate-400">
                {[
                  "SHA-256 content hashes",
                  "keccak256 of question and paper IDs",
                  "Pseudonymous actor fingerprints",
                  "Timestamps and version numbers",
                  "Access and lifecycle events",
                  "Release times and release state",
                ].map((x) => (
                  <li key={x}>· {x}</li>
                ))}
              </ul>
            </div>
            <div>
              <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-danger">
                Never on chain
              </p>
              <ul className="space-y-1 text-slate-400">
                {[
                  "Question text, plaintext or ciphertext",
                  "Answers",
                  "Encryption keys",
                  "Names, emails or any personal data",
                  "Readable question or paper identifiers",
                ].map((x) => (
                  <li key={x}>· {x}</li>
                ))}
              </ul>
            </div>
          </div>
        </Panel>
      </div>
    </Shell>
  );
}
