import Link from "next/link";
import Seal from "@/components/Seal";

/** The custody chain, as a register reads it: what happened, and what it left behind. */
const CUSTODY = [
  ["01", "Question written", "Encrypted with its own AES-256-GCM key before it touches disk"],
  ["02", "Identity fixed", "SHA-256 digest of the plaintext, anchored on chain"],
  ["03", "Version opened", "Edits append. Nothing overwrites, so nothing edited can pose as original"],
  ["04", "Reviewed", "APPROVE is granted on its own — a reviewer never needs WRITE"],
  ["05", "Paper assembled", "A seeded optimiser draws from the pool; no setter can predict the draw"],
  ["06", "Paper sealed", "Encrypted, its digest registered against a release hour"],
  ["07", "Access refused", "Every denial is written to the register and anchored"],
  ["08", "Opened at the hour", "The contract compares block.timestamp and permits the release"],
];

export default function Landing() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-baseline justify-between px-6 py-7">
        <span className="font-display text-lg font-semibold tracking-tight text-ink">SecureLock</span>
        <Link
          href="/login"
          className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-3 underline-offset-4 hover:text-ink hover:underline"
        >
          Sign in
        </Link>
      </header>

      {/* The register spread: the account on the left, the sealed object in the
          custody column on the right, a real rule between them. */}
      <section className="mx-auto max-w-6xl px-6 pb-20 pt-8 lg:pt-16">
        <div className="grid gap-12 lg:grid-cols-[minmax(0,1fr)_minmax(0,26rem)] lg:gap-16">
          <div className="lg:border-r lg:border-rule lg:pr-16">
            <h1 className="max-w-xl font-display text-[2.6rem] font-semibold leading-[1.08] tracking-tight text-ink sm:text-5xl">
              A question paper leaks weeks before the paper exists.
            </h1>

            <p className="mt-7 max-w-lg text-[15px] leading-relaxed text-ink-3">
              Most systems guard the finished PDF. By then the questions have already been written
              on somebody&rsquo;s laptop, mailed to a reviewer, and pasted into a draft.
            </p>

            <p className="mt-4 max-w-lg text-[15px] leading-relaxed text-ink-3">
              SecureLock seals each question with its own key the moment it is written. Every
              hand-off after that is recorded where a database administrator cannot quietly revise
              it. The assembled paper stays shut until the contract says the hour has come.
            </p>

            <div className="mt-9 flex flex-wrap items-center gap-5">
              <Link href="/login" className="btn-primary">
                Open the register
              </Link>
              <Link
                href="/timelock"
                className="text-sm text-ink-2 underline decoration-rule underline-offset-4 hover:text-ink hover:decoration-ink"
              >
                Watch a paper refuse to open &rarr;
              </Link>
            </div>
          </div>

          <Seal />
        </div>
      </section>

      {/* Custody chain: a logbook has columns, not cards. */}
      <section className="mx-auto max-w-6xl px-6 pb-20">
        <h2 className="colhead">Chain of custody</h2>
        <ol className="ruled mt-1">
          {CUSTODY.map(([n, event, detail]) => (
            <li
              key={n}
              className="grid grid-cols-[2rem_1fr] gap-x-5 py-3.5 sm:grid-cols-[2rem_13rem_1fr]"
            >
              <span className="font-mono text-[11px] text-ink-5 tabular-nums">{n}</span>
              <span className="text-sm text-ink">{event}</span>
              <span className="col-start-2 text-[13px] leading-relaxed text-ink-4 sm:col-start-3">
                {detail}
              </span>
            </li>
          ))}
        </ol>
      </section>

      <section className="mx-auto max-w-6xl px-6 pb-24">
        <h2 className="colhead">What this does not do</h2>
        <div className="mt-5 grid gap-x-16 gap-y-4 text-[13px] leading-relaxed text-ink-3 sm:grid-cols-2">
          <p>
            It does not make a leak impossible. Somebody authorised to read a question can still
            photograph the screen.
          </p>
          <p>
            It does not prove a human read anything. It proves an authorised account asked this
            system for it, at a recorded moment.
          </p>
          <p>
            <code className="font-mono text-ink-2">block.timestamp</code> is not a perfect clock.
            Validators have some leeway. The claim that holds is narrower: an end user cannot move
            it from their own device.
          </p>
          <p>
            The synthesis engine reduces how predictable a paper is. That is a change in odds, not a
            guarantee, and it is rule-based rather than a language model.
          </p>
        </div>
      </section>

      <footer className="border-t border-rule">
        <p className="mx-auto max-w-6xl px-6 py-7 font-mono text-[11px] text-ink-5">
          SecureLock — internal prototype, Smart India Hackathon. Runs offline on one machine.
        </p>
      </footer>
    </div>
  );
}
