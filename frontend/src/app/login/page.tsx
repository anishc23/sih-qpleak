"use client";

import { LockKeyhole, LogIn } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Alert } from "@/components/ui";
import { useAuth } from "@/lib/auth";

const DEMO_ACCOUNTS = [
  { email: "authority@securelock.demo", role: "Exam Authority", note: "assembles and releases papers" },
  { email: "setter1@securelock.demo", role: "Question Setter", note: "writes questions, sees nothing else" },
  { email: "reviewer@securelock.demo", role: "Reviewer", note: "reads and approves, never edits" },
  { email: "auditor@securelock.demo", role: "Auditor", note: "verifies hashes, no plaintext" },
  { email: "admin@securelock.demo", role: "Super Admin", note: "manages users, not content" },
];

const DEMO_PASSWORD = "SecureLock#2026";

export default function LoginPage() {
  const { user, login } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (user) router.replace("/dashboard");
  }, [user, router]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email.trim(), password);
      router.replace("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sign-in failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center p-6">
      <div className="grid w-full max-w-4xl gap-6 lg:grid-cols-[1fr_1.1fr]">
        <div className="panel p-7">
          <div className="flex items-center gap-2.5">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-accent/12 ring-1 ring-accent/25">
              <LockKeyhole size={19} className="text-accent" />
            </div>
            <div>
              <h1 className="text-lg font-semibold tracking-tight text-white">SecureLock</h1>
              <p className="text-[11px] uppercase tracking-wider text-slate-600">
                Examination Security Platform
              </p>
            </div>
          </div>

          <form onSubmit={submit} className="mt-7 space-y-4">
            <div>
              <label htmlFor="email" className="label mb-1.5 block">
                Email
              </label>
              <input
                id="email"
                type="email"
                required
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="field"
                placeholder="you@institution.gov.in"
              />
            </div>

            <div>
              <label htmlFor="password" className="label mb-1.5 block">
                Password
              </label>
              <input
                id="password"
                type="password"
                required
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="field"
                placeholder="••••••••••••"
              />
            </div>

            {error && <Alert kind="danger" title="Sign-in failed">{error}</Alert>}

            <button type="submit" disabled={busy} className="btn-primary w-full">
              <LogIn size={15} />
              {busy ? "Verifying..." : "Sign in"}
            </button>
          </form>

          <p className="mt-5 text-[11px] leading-relaxed text-slate-600">
            Passwords are hashed with Argon2id. Sessions are short-lived JWTs. Account creation is
            an administrative action, never self-service &mdash; an open registration endpoint would
            let anyone mint a question-setter account.
          </p>
        </div>

        <div className="panel p-7">
          <h2 className="text-sm font-semibold text-white">Demo accounts</h2>
          <p className="mt-1 text-xs text-slate-500">
            Click to fill. Each role sees a genuinely different system.
          </p>

          <div className="mt-4 space-y-2">
            {DEMO_ACCOUNTS.map((a) => (
              <button
                key={a.email}
                type="button"
                onClick={() => {
                  setEmail(a.email);
                  setPassword(DEMO_PASSWORD);
                  setError(null);
                }}
                className="w-full rounded-lg border border-white/[0.07] bg-base-850/50 px-3.5 py-2.5 text-left transition hover:border-accent/30 hover:bg-base-800"
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="font-mono text-[12px] text-slate-300">{a.email}</span>
                  <span className="shrink-0 text-[10px] font-medium uppercase tracking-wider text-accent">
                    {a.role}
                  </span>
                </div>
                <p className="mt-0.5 text-[11px] text-slate-600">{a.note}</p>
              </button>
            ))}
          </div>

          <div className="mt-4 rounded-lg border border-warn/20 bg-warn/[0.05] px-3.5 py-2.5">
            <p className="text-[11px] text-warn">
              Password for all demo accounts:{" "}
              <code className="font-mono font-semibold">{DEMO_PASSWORD}</code>
            </p>
            <p className="mt-1 text-[11px] text-slate-500">
              Deliberately obvious. Local demonstration data only &mdash; these are not real
              credentials.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
