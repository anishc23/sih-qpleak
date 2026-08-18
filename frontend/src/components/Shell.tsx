"use client";

import clsx from "clsx";
import {
  Activity,
  Blocks,
  FilePlus2,
  FileStack,
  LayoutDashboard,
  LockKeyhole,
  LogOut,
  ShieldCheck,
  Sparkles,
  Timer,
  Vault,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { api, type BlockchainStatus } from "@/lib/api";
import { ROLE_LABEL, ROLE_NAV, useAuth, useRequireAuth } from "@/lib/auth";

const NAV = {
  dashboard: { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  vault: { href: "/vault", label: "Question Vault", icon: Vault },
  create: { href: "/vault/create", label: "Create Question", icon: FilePlus2 },
  review: { href: "/review", label: "Review Queue", icon: ShieldCheck },
  variations: { href: "/variations", label: "Variations", icon: Sparkles },
  builder: { href: "/builder", label: "Paper Builder", icon: Sparkles },
  papers: { href: "/papers", label: "Papers", icon: FileStack },
  timelock: { href: "/timelock", label: "Time-Lock Demo", icon: Timer },
  audit: { href: "/audit", label: "Audit Trail", icon: Activity },
  blockchain: { href: "/blockchain", label: "Blockchain", icon: Blocks },
  security: { href: "/security", label: "Security", icon: ShieldCheck },
} as const;

function ChainPill() {
  const [status, setStatus] = useState<BlockchainStatus | null>(null);

  useEffect(() => {
    let alive = true;
    const tick = () =>
      api
        .blockchainStatus()
        .then((s) => alive && setStatus(s))
        .catch(() => alive && setStatus({ connected: false, rpc_url: "", network_label: "OFFLINE" }));
    tick();
    const id = setInterval(tick, 10000);
    return () => {
      alive = false;
      clearInterval(id);
    };
  }, []);

  const connected = status?.connected ?? false;
  return (
    <div className="flex items-center gap-2 rounded-lg border border-white/[0.07] bg-base-900/70 px-3 py-1.5">
      <span className="relative flex h-2 w-2">
        {connected && (
          <span className="absolute inline-flex h-full w-full animate-pulse-ring rounded-full bg-ok" />
        )}
        <span
          className={clsx(
            "relative inline-flex h-2 w-2 rounded-full",
            connected ? "bg-ok" : "bg-danger",
          )}
        />
      </span>
      <div className="leading-tight">
        <p className="text-[10px] font-medium uppercase tracking-wider text-slate-500">
          {connected ? status?.network_label : "Blockchain offline"}
        </p>
        {connected && status?.latest_block !== undefined && (
          <p className="font-mono text-[10px] text-slate-400">block #{status.latest_block}</p>
        )}
      </div>
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
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <LockKeyhole size={16} className="animate-pulse text-accent" />
          Verifying session...
        </div>
      </div>
    );
  }
  if (!user) return null;

  const items = ROLE_NAV[user.role].map((k) => NAV[k as keyof typeof NAV]).filter(Boolean);

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-white/[0.06] bg-base-900/50 lg:flex">
        <Link href="/dashboard" className="flex items-center gap-2.5 px-5 py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent/12 ring-1 ring-accent/25">
            <LockKeyhole size={16} className="text-accent" />
          </div>
          <div className="leading-tight">
            <p className="text-sm font-semibold tracking-tight text-white">SecureLock</p>
            <p className="text-[10px] uppercase tracking-wider text-slate-600">Exam Security</p>
          </div>
        </Link>

        <nav className="flex-1 space-y-0.5 px-3 py-2">
          {items.map(({ href, label, icon: Icon }) => {
            const active = pathname === href || (href !== "/dashboard" && pathname.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={clsx(
                  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition",
                  active
                    ? "bg-accent/10 text-accent ring-1 ring-accent/20"
                    : "text-slate-400 hover:bg-white/[0.03] hover:text-slate-200",
                )}
              >
                <Icon size={15} className="shrink-0" />
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-white/[0.06] p-3">
          <div className="rounded-lg bg-base-850/60 px-3 py-2.5">
            <p className="truncate text-sm font-medium text-slate-200">{user.name}</p>
            <p className="mt-0.5 text-[11px] text-accent">{ROLE_LABEL[user.role]}</p>
            <p className="hash mt-1">{user.user_uid}</p>
          </div>
          <button
            onClick={logout}
            className="mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-500 transition hover:bg-danger/10 hover:text-danger"
          >
            <LogOut size={14} />
            Sign out
          </button>
        </div>
      </aside>

      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-white/[0.06] bg-base-950/80 px-5 py-3 backdrop-blur">
          <div className="flex items-center gap-3 lg:hidden">
            <LockKeyhole size={16} className="text-accent" />
            <span className="text-sm font-semibold text-white">SecureLock</span>
          </div>
          <div className="hidden lg:block" />
          <div className="flex items-center gap-3">
            <ChainPill />
            <button
              onClick={logout}
              className="rounded-lg border border-white/10 p-2 text-slate-500 transition hover:text-danger lg:hidden"
            >
              <LogOut size={14} />
            </button>
          </div>
        </header>

        <main className="animate-slide-up p-5 lg:p-7">{children}</main>
      </div>
    </div>
  );
}
