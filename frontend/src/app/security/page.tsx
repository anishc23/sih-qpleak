"use client";

import { ShieldCheck } from "lucide-react";
import { useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Alert, CheckRow, Hash, PageHeader, Panel, Skeleton } from "@/components/ui";
import { api, type BlockchainStatus, type SecurityCheck } from "@/lib/api";

const THREATS = [
  ["T1", "User changes system clock", "Contract reads block.timestamp"],
  ["T2", "User changes browser clock", "Contract reads block.timestamp"],
  ["T3", "Unauthorised question access", "RBAC + per-question grants, server-side"],
  ["T4", "Setter edits an approved question", "Frozen status + append-only versions"],
  ["T5", "Database audit record modified", "Hash chain + on-chain anchor"],
  ["T6", "Insider opens the paper early", "AES-256-GCM + contract time lock"],
  ["T7", "Setter leaks their own question", "Pool synthesis + provenance + access audit"],
  ["T8", "Duplicates make the paper predictable", "TF-IDF detection + seeded selection"],
  ["T9", "Frontend is modified by the user", "Every check re-runs on the server"],
  ["T10", "Direct API call bypassing the UI", "Same authorisation and contract check"],
];

export default function SecurityPage() {
  const [data, setData] = useState<{
    checks: SecurityCheck[];
    audit_chain: { intact: boolean; head: string };
    blockchain: BlockchainStatus;
  } | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const load = () => api.securityStatus().then(setData).catch((e) => setError(e.message));
    load();
    const id = setInterval(load, 10000);
    return () => clearInterval(id);
  }, []);

  const failing = data?.checks.filter((c) => !c.ok).length ?? 0;

  return (
    <Shell>
      <PageHeader
        title="Security Dashboard"
        description="Every row is a live check against the running system, re-evaluated on each load — not a static list of ticks."
      />

      {error && <div className="mb-5"><Alert kind="danger" title="Could not load">{error}</Alert></div>}

      <div className="grid gap-5 lg:grid-cols-[1.2fr_1fr]">
        <Panel title="Live security posture">
          {!data ? (
            <Skeleton rows={8} />
          ) : (
            <>
              <div className="mb-3">
                {failing === 0 ? (
                  <Alert kind="ok" title="All checks passing">
                    <p>{data.checks.length} controls verified.</p>
                  </Alert>
                ) : (
                  <Alert kind="warn" title={`${failing} check${failing === 1 ? "" : "s"} failing`}>
                    <p>Usually the blockchain node is not running.</p>
                  </Alert>
                )}
              </div>
              <div>
                {data.checks.map((c) => (
                  <CheckRow key={c.name} name={c.name} ok={c.ok} detail={c.detail} />
                ))}
              </div>
            </>
          )}
        </Panel>

        <div className="space-y-5">
          <Panel title="Audit chain">
            {!data ? (
              <Skeleton rows={2} />
            ) : (
              <>
                <div className="flex items-center justify-between text-xs">
                  <span className="text-ink-4">Status</span>
                  <span className={data.audit_chain.intact ? "text-ok" : "text-danger"}>
                    {data.audit_chain.intact ? "INTACT" : "BROKEN"}
                  </span>
                </div>
                <div className="mt-2 flex items-center justify-between text-xs">
                  <span className="text-ink-4">Chain head</span>
                  <Hash value={data.audit_chain.head} chars={18} />
                </div>
              </>
            )}
          </Panel>

          <Panel title="Cryptography in use">
            <div className="space-y-2 text-xs">
              {[
                ["Content encryption", "AES-256-GCM"],
                ["Key wrapping", "AES-256-GCM under master key"],
                ["Content identity", "SHA-256"],
                ["On-chain identifiers", "keccak256"],
                ["Passwords", "Argon2id"],
                ["Sessions", "JWT HS256, 8h"],
              ].map(([k, v]) => (
                <div
                  key={k}
                  className="flex items-center justify-between border-b border-rule-soft pb-1.5 last:border-0"
                >
                  <span className="text-ink-4">{k}</span>
                  <span className="font-mono text-[11px] text-ink-2">{v}</span>
                </div>
              ))}
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-ink-5">
              No primitive is implemented by hand. AES-GCM is authenticated encryption, so a
              tampered ciphertext fails to decrypt rather than returning garbage.
            </p>
          </Panel>
        </div>
      </div>

      <div className="mt-5">
        <Panel title="Threat model" subtitle="What we defend against, and with what">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-rule text-left">
                  {["", "Threat", "Countermeasure"].map((h) => (
                    <th
                      key={h}
                      className="px-2 py-2 text-[11px] font-medium uppercase tracking-wider text-ink-4"
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {THREATS.map(([id, threat, counter]) => (
                  <tr key={id} className="border-b border-rule-soft">
                    <td className="px-2 py-2 font-mono text-[11px] text-accent">{id}</td>
                    <td className="px-2 py-2 text-ink-2">{threat}</td>
                    <td className="px-2 py-2 text-ink-3">{counter}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <div className="mt-5">
        <Panel title="Limitations we state openly">
          <ul className="space-y-2.5 text-[13px] leading-relaxed text-ink-3">
            {[
              "Whoever holds the master key can decrypt the database. In production that key belongs in a KMS or HSM; the key-vault interface is deliberately narrow so it can be swapped.",
              "A local development chain is not a real trust anchor. It demonstrates the mechanism; production would use a permissioned chain with independent validators.",
              "block.timestamp is not a perfect clock. The defensible claim is that an end user cannot bypass the release condition from their own device.",
              "Question variation is rule-based, not a language model. It restates the instruction verb and leaves the substantive clause untouched, which is why the expected answer cannot drift.",
              "If the blockchain is unreachable, decryption is refused rather than falling back to a server clock. That is the correct failure direction, but it is a real operational dependency.",
              "Nothing here prevents an authorised person from photographing a question. The goal is to reduce exposure, trace access, and make tampering evident.",
            ].map((x) => (
              <li key={x} className="flex gap-2.5">
                <ShieldCheck size={14} className="mt-0.5 shrink-0 text-ink-5" />
                {x}
              </li>
            ))}
          </ul>
        </Panel>
      </div>
    </Shell>
  );
}
