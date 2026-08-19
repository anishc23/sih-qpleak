"use client";

import clsx from "clsx";
import {
  AlertTriangle,
  Clock,
  Cpu,
  Lock,
  Monitor,
  ShieldAlert,
  Unlock,
  Zap,
} from "lucide-react";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import Shell from "@/components/Shell";
import { Alert, Hash, PageHeader, Panel, Skeleton } from "@/components/ui";
import { ApiError, api, type Paper, type TimeLockState } from "@/lib/api";
import { countdown, formatUnix } from "@/lib/format";

/** Offsets the demo can apply to the *displayed* client clock. Display only. */
const CLOCK_PRESETS = [
  { label: "Real time", offset: 0 },
  { label: "+1 hour", offset: 3600 },
  { label: "+1 day", offset: 86400 },
  { label: "Year 2099", offset: 4070908800 - Math.floor(Date.now() / 1000) },
];

function TimeLockDemo() {
  const params = useSearchParams();
  const [papers, setPapers] = useState<Paper[]>([]);
  const [selected, setSelected] = useState<string | null>(params.get("paper"));
  const [lock, setLock] = useState<TimeLockState | null>(null);
  const [clientOffset, setClientOffset] = useState(0);
  const [clientNow, setClientNow] = useState(() => Math.floor(Date.now() / 1000));
  const [attempt, setAttempt] = useState<{
    kind: "denied" | "released" | "error";
    message: string;
  } | null>(null);
  const [content, setContent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .papers()
      .then((all) => {
        const lockable = all.filter((p) => p.status === "LOCKED" || p.status === "RELEASED");
        setPapers(lockable);
        if (!selected && lockable.length) setSelected(lockable[0].paper_uid);
      })
      .catch((e) => setError(e.message));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const refresh = useCallback(async () => {
    if (!selected) return;
    try {
      setLock(await api.timeLock(selected));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to read lock state");
    }
  }, [selected]);

  // The chain is polled; the local ticker only animates the display between polls.
  useEffect(() => {
    refresh();
    const poll = setInterval(refresh, 2000);
    const tick = setInterval(() => setClientNow(Math.floor(Date.now() / 1000)), 1000);
    return () => {
      clearInterval(poll);
      clearInterval(tick);
    };
  }, [refresh]);

  async function attemptDecrypt() {
    if (!selected) return;
    setBusy(true);
    setAttempt(null);
    setContent(null);
    try {
      const res = await api.decryptPaper(selected);
      setContent(res.content);
      setAttempt({ kind: "released", message: "Blockchain verified the release condition." });
    } catch (e) {
      if (e instanceof ApiError && e.isTimeLocked) {
        setAttempt({ kind: "denied", message: e.message });
      } else {
        setAttempt({
          kind: "error",
          message: e instanceof Error ? e.message : "Request failed",
        });
      }
    } finally {
      setBusy(false);
      refresh();
    }
  }

  async function requestRelease() {
    if (!selected) return;
    setBusy(true);
    setAttempt(null);
    try {
      await api.releasePaper(selected);
      setAttempt({ kind: "released", message: "The contract permitted release." });
    } catch (e) {
      if (e instanceof ApiError && e.isTimeLocked) {
        setAttempt({ kind: "denied", message: e.message });
      } else {
        setAttempt({ kind: "error", message: e instanceof Error ? e.message : "Failed" });
      }
    } finally {
      setBusy(false);
      refresh();
    }
  }

  const released = lock?.released ?? false;
  const reached = lock?.release_time_reached ?? false;
  const remaining = lock?.seconds_remaining ?? 0;
  const displayedClientClock = clientNow + clientOffset;
  const clockIsFaked = clientOffset !== 0;

  return (
    <>
      <PageHeader
        title="Time-Lock Security Demonstration"
        description="The countdown below is cosmetic. Access is decided by the smart contract evaluating block.timestamp — so changing your device clock changes nothing."
      >
        {papers.length > 1 && (
          <select
            value={selected ?? ""}
            onChange={(e) => {
              setSelected(e.target.value);
              setContent(null);
              setAttempt(null);
            }}
            className="field w-auto"
          >
            {papers.map((p) => (
              <option key={p.paper_uid} value={p.paper_uid}>
                {p.paper_uid}
              </option>
            ))}
          </select>
        )}
      </PageHeader>

      {error && <Alert kind="danger" title="Error">{error}</Alert>}

      {papers.length === 0 && !error && (
        <Alert kind="info" title="No locked paper yet">
          Generate a paper in the Paper Builder, encrypt it, then register it on the blockchain with
          a short release window to run this demonstration.
        </Alert>
      )}

      {!lock && selected && <Skeleton rows={3} />}

      {lock && lock.registered && (
        <>
          <div className="grid gap-5 lg:grid-cols-[1.1fr_1fr]">
            {/* ---------------------------------------------------- the lock */}
            <section
              className={clsx(
                "rounded-sm p-7",
                released ? "border border-ok/40 bg-leaf shadow-deboss" : "seal",
              )}
            >
              <div className="flex flex-col py-2">
                {/* Sealed is rendered as ink you cannot see into. Released is
                    paper: the state change is a change of value, not a badge. */}
                <p
                  className={clsx(
                    "font-mono text-[10px] uppercase tracking-[0.18em]",
                    released ? "text-ok" : "text-register/60",
                  )}
                >
                  {released ? "Seal broken" : "Under seal"}
                </p>

                <p
                  className={clsx(
                    "mt-6 font-display leading-none tabular-nums",
                    released ? "text-4xl text-ok" : "text-6xl text-register",
                  )}
                >
                  {released ? "OPEN" : countdown(remaining)}
                </p>
                <p
                  className={clsx(
                    "mt-3 font-mono text-[11px]",
                    released ? "text-ink-4" : "text-register/70",
                  )}
                >
                  {released
                    ? "the contract permitted the release"
                    : "remaining, measured by the chain and by nothing else"}
                </p>

                <div
                  className={clsx(
                    "mt-7 w-full space-y-2 border-t pt-5 text-xs",
                    released ? "border-rule" : "border-register/20",
                  )}
                >
                  <div className="flex justify-between">
                    <span className={released ? "text-ink-4" : "text-register/50"}>Paper</span>
                    <span
                      className={clsx("font-mono", released ? "text-ink-2" : "text-register/90")}
                    >
                      {lock.paper_uid}
                    </span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className={released ? "text-ink-4" : "text-register/50"}>Paper hash</span>
                    {released ? (
                      <Hash value={lock.paper_hash} chars={14} />
                    ) : (
                      <span className="truncate font-mono text-register/80">
                        {lock.paper_hash}
                      </span>
                    )}
                  </div>
                  <div className="flex justify-between">
                    <span className={released ? "text-ink-4" : "text-register/50"}>Release at</span>
                    <span className={released ? "text-ink-2" : "text-register/90"}>
                      {formatUnix(lock.release_time)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className={released ? "text-ink-4" : "text-register/50"}>Decided by</span>
                    <span className={clsx("font-mono", released ? "text-lac" : "text-register")}>
                      block.timestamp
                    </span>
                  </div>
                </div>
              </div>
            </section>

            {/* ------------------------------------------------- the two clocks */}
            <div className="space-y-5">
              <Panel
                title="Two clocks, one authority"
                subtitle="Only one of these can affect the decision"
              >
                <div className="space-y-3">
                  <div
                    className={clsx(
                      "rounded-sm border px-4 py-3",
                      clockIsFaked
                        ? "border-danger/30 bg-danger/[0.06]"
                        : "border-rule bg-sunk/50",
                    )}
                  >
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2 text-xs text-ink-3">
                        <Monitor size={13} />
                        Your device clock
                      </span>
                      {clockIsFaked && (
                        <span className="rounded bg-danger/15 px-1.5 py-0.5 text-[10px] font-semibold text-danger">
                          MANIPULATED
                        </span>
                      )}
                    </div>
                    <p
                      className={clsx(
                        "mt-1.5 font-mono text-sm",
                        clockIsFaked ? "text-danger" : "text-ink-2",
                      )}
                    >
                      {formatUnix(displayedClientClock)}
                    </p>
                    <p className="mt-1 text-[10px] text-ink-5">
                      Not consulted by any decision in this system.
                    </p>
                  </div>

                  <div className="rounded-sm border border-accent/25 bg-accent/[0.05] px-4 py-3">
                    <div className="flex items-center justify-between">
                      <span className="flex items-center gap-2 text-xs text-accent">
                        <Cpu size={13} />
                        Blockchain clock
                      </span>
                      <span className="rounded bg-accent/15 px-1.5 py-0.5 text-[10px] font-semibold text-accent">
                        AUTHORITATIVE
                      </span>
                    </div>
                    <p className="mt-1.5 font-mono text-sm text-accent-soft">
                      {formatUnix(lock.blockchain_time)}
                    </p>
                    <p className="mt-1 text-[10px] text-ink-4">
                      Supplied by the chain. Unreachable from your machine.
                    </p>
                  </div>
                </div>

                <div className="mt-4">
                  <p className="label mb-2">Simulate a clock attack</p>
                  <div className="flex flex-wrap gap-2">
                    {CLOCK_PRESETS.map((p) => (
                      <button
                        key={p.label}
                        onClick={() => setClientOffset(p.offset)}
                        className={clsx(
                          "rounded-sm border px-2.5 py-1.5 text-xs transition",
                          clientOffset === p.offset
                            ? "border-accent/40 bg-accent/10 text-accent"
                            : "border-rule text-ink-3 hover:border-accent/25 hover:text-ink",
                        )}
                      >
                        {p.label}
                      </button>
                    ))}
                  </div>
                  <p className="mt-2 text-[11px] text-ink-5">
                    This changes only what the browser displays &mdash; exactly the leverage a real
                    attacker has over their own machine.
                  </p>
                </div>
              </Panel>

              <Panel title="Attack the system" subtitle="These call the real API, not a mock">
                <div className="flex flex-wrap gap-2">
                  <button onClick={attemptDecrypt} disabled={busy} className="btn-primary">
                    <Zap size={14} />
                    {busy ? "Requesting..." : "Attempt decryption"}
                  </button>
                  {!released && reached && (
                    <button onClick={requestRelease} disabled={busy} className="btn-ghost">
                      <Unlock size={14} />
                      Request release
                    </button>
                  )}
                </div>

                {attempt && (
                  <div className="mt-4">
                    {attempt.kind === "denied" && (
                      <Alert kind="locked" title="DECRYPTION BLOCKED">
                        <p>{attempt.message}</p>
                        <p className="mt-2 text-ink-3">
                          Your computer clock has no bearing on this check.
                        </p>
                      </Alert>
                    )}
                    {attempt.kind === "released" && (
                      <Alert kind="ok" title="TIME LOCK EXPIRED">
                        <p>{attempt.message}</p>
                      </Alert>
                    )}
                    {attempt.kind === "error" && (
                      <Alert kind="danger" title="Request refused">
                        {attempt.message}
                      </Alert>
                    )}
                  </div>
                )}

                {clockIsFaked && !released && (
                  <div className="mt-4 flex gap-2.5 rounded-sm border border-danger/25 bg-danger/[0.05] px-3.5 py-2.5">
                    <AlertTriangle size={14} className="mt-0.5 shrink-0 text-danger" />
                    <p className="text-[11px] leading-relaxed text-ink-3">
                      Your displayed clock says{" "}
                      <span className="font-mono text-danger">
                        {new Date(displayedClientClock * 1000).getFullYear()}
                      </span>
                      , but the chain still says{" "}
                      <span className="font-mono text-accent">
                        {new Date((lock.blockchain_time ?? 0) * 1000).getFullYear()}
                      </span>
                      . The paper stays locked.
                    </p>
                  </div>
                )}
              </Panel>
            </div>
          </div>

          {content && (
            <div className="mt-5">
              <Panel
                title="Released paper"
                subtitle="Decrypted only after the contract transitioned the paper to RELEASED"
              >
                <pre className="max-h-96 overflow-auto rounded-sm border border-rule-soft bg-leaf p-4 font-mono text-[11px] leading-relaxed text-ink-2">
                  {content}
                </pre>
              </Panel>
            </div>
          )}

          <div className="mt-5">
            <Panel title="Why this holds" subtitle="The honest version, for judges">
              <div className="grid gap-4 text-[13px] leading-relaxed text-ink-3 md:grid-cols-2">
                <div>
                  <p className="mb-1.5 flex items-center gap-2 font-medium text-ink">
                    <ShieldAlert size={14} className="text-accent" />
                    What is actually guaranteed
                  </p>
                  <p>
                    The decrypt endpoint queries the contract before it will unwrap the key. There is
                    no code path that unwraps a locked paper&rsquo;s key. Calling the API directly
                    with curl, editing the frontend, or changing your clock all reach the same check.
                  </p>
                </div>
                <div>
                  <p className="mb-1.5 flex items-center gap-2 font-medium text-ink">
                    <Clock size={14} className="text-warn" />
                    What is not
                  </p>
                  <p>
                    <code className="font-mono text-ink-2">block.timestamp</code> is not a
                    perfect atomic clock &mdash; validators have some leeway, and on a permissioned
                    chain the validator set is a trust assumption. The claim is narrower: an ordinary
                    end user cannot bypass the condition from their own device.
                  </p>
                </div>
              </div>
            </Panel>
          </div>
        </>
      )}
    </>
  );
}

export default function TimeLockPage() {
  return (
    <Shell>
      <Suspense fallback={<Skeleton rows={4} />}>
        <TimeLockDemo />
      </Suspense>
    </Shell>
  );
}
