import {
  Activity,
  Blocks,
  Fingerprint,
  KeyRound,
  LockKeyhole,
  ShieldCheck,
  Sparkles,
  Timer,
} from "lucide-react";
import Link from "next/link";

const PILLARS = [
  {
    icon: KeyRound,
    title: "Question Encryption",
    body: "Every question gets its own AES-256-GCM key. Plaintext is never written to the database.",
  },
  {
    icon: Fingerprint,
    title: "Question Provenance",
    body: "SHA-256 identity and append-only version history, anchored on chain. Edits cannot masquerade as originals.",
  },
  {
    icon: ShieldCheck,
    title: "Granular Access",
    body: "READ, WRITE and APPROVE are independent grants, enforced server-side on every request.",
  },
  {
    icon: Sparkles,
    title: "Paper Synthesis",
    body: "TF-IDF duplicate detection and a seeded optimiser assemble the paper, spreading authorship.",
  },
  {
    icon: Timer,
    title: "Smart Time Lock",
    body: "Release is gated on block.timestamp. A changed device clock does not move it.",
  },
  {
    icon: Activity,
    title: "Immutable Audit",
    body: "A hash-chained log whose head is anchored on chain, so silent edits become visible.",
  },
];

const FLOW = [
  "Question created",
  "Encrypted + hashed",
  "Provenance anchored",
  "Reviewed",
  "Synthesised",
  "Paper encrypted",
  "Time locked",
  "Released at exam time",
];

export default function Landing() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/12 ring-1 ring-accent/25">
            <LockKeyhole size={18} className="text-accent" />
          </div>
          <span className="text-base font-semibold tracking-tight text-white">SecureLock</span>
        </div>
        <Link href="/login" className="btn-ghost">
          Sign in
        </Link>
      </header>

      <section className="mx-auto max-w-6xl px-6 pb-16 pt-10 lg:pt-20">
        <div className="inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/[0.06] px-3 py-1 text-[11px] font-medium uppercase tracking-wider text-accent">
          <Blocks size={12} />
          Smart India Hackathon prototype
        </div>

        <h1 className="mt-6 max-w-3xl text-4xl font-semibold leading-[1.1] tracking-tight text-white lg:text-6xl">
          Blockchain + AI powered{" "}
          <span className="bg-gradient-to-r from-accent to-locked bg-clip-text text-transparent">
            examination security
          </span>
        </h1>

        <p className="mt-5 max-w-2xl text-lg text-slate-400">
          Secure every question. Trace every access. Lock every paper.
        </p>

        <p className="mt-4 max-w-2xl text-sm leading-relaxed text-slate-500">
          Most systems protect the final question paper. But a paper can be compromised long before
          it exists &mdash; while questions are being written, reviewed and assembled. SecureLock
          secures that entire lifecycle.
        </p>

        <div className="mt-8 flex flex-wrap gap-3">
          <Link href="/login" className="btn-primary">
            Enter Secure Examination Portal
          </Link>
          <Link href="/timelock" className="btn-ghost">
            <Timer size={15} />
            See the time-lock demo
          </Link>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-16">
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {PILLARS.map(({ icon: Icon, title, body }) => (
            <div key={title} className="panel panel-hover p-5">
              <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-accent/10 ring-1 ring-accent/20">
                <Icon size={16} className="text-accent" />
              </div>
              <h3 className="mt-3.5 text-sm font-semibold text-white">{title}</h3>
              <p className="mt-1.5 text-[13px] leading-relaxed text-slate-500">{body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-20">
        <div className="panel p-6">
          <h2 className="text-sm font-semibold text-white">The secured lifecycle</h2>
          <ol className="mt-5 flex flex-wrap items-center gap-x-2 gap-y-3">
            {FLOW.map((step, i) => (
              <li key={step} className="flex items-center gap-2">
                <span className="rounded-lg border border-white/[0.07] bg-base-850 px-3 py-1.5 text-xs text-slate-300">
                  <span className="mr-2 font-mono text-[10px] text-accent">{i + 1}</span>
                  {step}
                </span>
                {i < FLOW.length - 1 && <span className="text-slate-700">&rarr;</span>}
              </li>
            ))}
          </ol>
        </div>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-20">
        <div className="panel border-warn/15 bg-warn/[0.03] p-6">
          <h2 className="text-sm font-semibold text-warn">What we do not claim</h2>
          <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-slate-400">
            SecureLock does not make examination leaks impossible. A person who is authorised to see
            a question can still photograph it. Blockchain does not prove a human read anything
            &mdash; only that an authorised account requested it through the system. And{" "}
            <code className="font-mono text-slate-300">block.timestamp</code> is not a perfect
            clock; the accurate claim is that an end user cannot bypass the release condition from
            their own device.
          </p>
          <p className="mt-3 max-w-3xl text-[13px] leading-relaxed text-slate-400">
            What the system does provide: reduced exposure, traceable provenance, tamper-evident
            records, and a release condition no single administrator can quietly override.
          </p>
        </div>
      </section>

      <footer className="border-t border-white/[0.06] py-8">
        <p className="text-center text-xs text-slate-600">
          SecureLock &mdash; SIH internal hackathon prototype. Runs entirely offline.
        </p>
      </footer>
    </div>
  );
}
