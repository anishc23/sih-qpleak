"use client";

import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type BlockchainStatus } from "@/lib/api";
import { ROLE_LABEL, ROLE_NAV, useAuth, useRequireAuth } from "@/lib/auth";

/** The register's index. Numbered entries, no icons -- a logbook has neither. */
const NAV = {
  dashboard: { href: "/dashboard", label: "Dashboard" },
  vault: { href: "/vault", label: "Question Vault" },
  create: { href: "/vault/create", label: "Create Question" },
  review: { href: "/review", label: "Review Queue" },
  variations: { href: "/variations", label: "Variations" },
  builder: { href: "/builder", label: "Paper Builder" },
  papers: { href: "/papers", label: "Papers" },
  timelock: { href: "/timelock", label: "Time Lock" },
  audit: { href: "/audit", label: "Audit Trail" },
  blockchain: { href: "/blockchain", label: "Blockchain" },
  security: { href: "/security", label: "Security" },
} as const;

function ChainPill() {
  const [status, setStatus] = useState<BlockchainStatus | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () =>
      api
        .blockchainStatus()
        .then((s) => alive && setStatus(s))
        .catch(
          () => alive && setStatus({ connected: false, rpc_url: "", network_label: "OFFLINE" }),
        );
    tick();
    const id = setInterval(tick, 10000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const connected = status?.connected ?? false;
  return (
    <div className="flex items-baseline gap-2.5 font-mono text-[11px]">
      <span className={clsx("inline-block h-1.5 w-1.5 rounded-full", connected ? "bg-ok" : "bg-danger")} />
      <span className="hidden uppercase tracking-[0.14em] text-ink-4 sm:inline">
        {connected ? status?.network_label : "chain offline"}
      </span>
      {connected && status?.latest_block !== undefined && (
        <span className="text-ink-3 tabular-nums">block #{status.latest_block}</span>
      )}
    </div>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const { user, loading } = useRequireAuth();
  const { logout } = useAuth();
  const pathname = usePathname();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-ink-4">
          Verifying session
        </p>
      </div>
    );
  }
  if (!user) return null;

  const items = ROLE_NAV[user.role].map((k) => NAV[k as keyof typeof NAV]).filter(Boolean);

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col border-r border-rule lg:flex">
        <Link href="/dashboard" className="block px-6 py-6">
          <p className="font-display text-lg font-semibold tracking-tight text-ink">SecureLock</p>
          <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.18em] text-ink-5">
            Custody register
          </p>
        </Link>

        <nav className="flex-1 px-3">
          {items.map(({ href, label }, i) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                aria-current={active ? "page" : undefined}
                className={clsx(
                  "flex items-baseline gap-3 border-l-2 py-2 pl-4 pr-3 text-sm transition-colors",
                  active
                    ? "border-lac font-medium text-ink"
                    : "border-transparent text-ink-3 hover:border-rule hover:text-ink",
                )}
              >
                <span className="font-mono text-[10px] text-ink-5 tabular-nums">
                  {String(i + 1).padStart(2, "0")}
                </span>
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-rule px-6 py-5">
          <p className="truncate text-sm font-medium text-ink">{user.name}</p>
          <p className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.18em] text-lac">
            {ROLE_LABEL[user.role]}
          </p>
          <p className="hash mt-1.5">{user.user_uid}</p>
          <button
            onClick={logout}
            className="mt-4 font-mono text-[11px] uppercase tracking-[0.14em] text-ink-4 underline-offset-4 transition hover:text-danger hover:underline"
          >
            Sign out
          </button>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-rule bg-register px-5 py-3.5 lg:px-7">
          <span className="font-display text-base font-semibold text-ink lg:hidden">SecureLock</span>
          <div className="hidden lg:block" />
          <div className="flex items-center gap-5">
            <ChainPill />
            <button
              onClick={logout}
              className="font-mono text-[11px] uppercase tracking-[0.14em] text-ink-4 transition hover:text-danger lg:hidden"
            >
              Sign out
            </button>
          </div>
        </header>

        <main className="animate-slide-up p-5 lg:p-7">{children}</main>
      </div>
    </div>
  );
}
