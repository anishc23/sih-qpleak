"use client";

import { useEffect, useState } from "react";

/**
 * THE SEAL.
 *
 * The one dark object in the system, and the only thing on this page that is
 * not read from our own server. It talks to the chain directly over JSON-RPC,
 * which is the whole argument of the product made checkable: the page does not
 * ask SecureLock what time it is, and neither does the lock.
 *
 * `text/plain` is deliberate. It is a CORS-safelisted content type, so the
 * request skips preflight -- the Hardhat node only advertises OPTIONS and GET
 * in Access-Control-Allow-Methods, and an application/json POST would be
 * refused by the browser before it was ever sent.
 */
const RPC = process.env.NEXT_PUBLIC_RPC_URL ?? "http://127.0.0.1:8545";
const PAPER_CONTRACT =
  process.env.NEXT_PUBLIC_PAPER_CONTRACT ?? "0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512";

async function rpc<T>(method: string, params: unknown[]): Promise<T> {
  const res = await fetch(RPC, {
    method: "POST",
    headers: { "Content-Type": "text/plain;charset=UTF-8" },
    body: JSON.stringify({ jsonrpc: "2.0", id: 1, method, params }),
  });
  const json = await res.json();
  if (json.error) throw new Error(json.error.message);
  return json.result as T;
}

function clock(unix: number) {
  const d = new Date(unix * 1000);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

type ChainState = { block: number; time: number; hasCode: boolean };

export default function Seal() {
  const [chain, setChain] = useState<ChainState | null>(null);
  const [failed, setFailed] = useState(false);
  const [device, setDevice] = useState(() => Math.floor(Date.now() / 1000));

  useEffect(() => {
    let alive = true;

    const read = async () => {
      try {
        const [head, code] = await Promise.all([
          rpc<{ number: string; timestamp: string }>("eth_getBlockByNumber", ["latest", false]),
          rpc<string>("eth_getCode", [PAPER_CONTRACT, "latest"]),
        ]);
        if (!alive) return;
        setChain({
          block: parseInt(head.number, 16),
          time: parseInt(head.timestamp, 16),
          hasCode: code !== "0x",
        });
        setFailed(false);
      } catch {
        if (alive) setFailed(true);
      }
    };

    read();
    const poll = setInterval(read, 2000);
    const tick = setInterval(() => setDevice(Math.floor(Date.now() / 1000)), 1000);
    return () => {
      alive = false;
      clearInterval(poll);
      clearInterval(tick);
    };
  }, []);

  return (
    <figure className="seal p-7 sm:p-9">
      <figcaption className="font-mono text-[10px] uppercase tracking-[0.18em] text-register/60">
        Under seal
      </figcaption>

      {/* The chain's own clock. The lock reads this line and no other. */}
      <p className="mt-7 font-mono text-[10px] uppercase tracking-[0.18em] text-register/60">
        Chain time
      </p>
      <p className="font-display text-[3.25rem] leading-none tracking-tight text-register tabular-nums sm:text-6xl">
        {failed ? "--:--:--" : chain ? clock(chain.time) : " "}
      </p>
      <p className="mt-2 font-mono text-[11px] text-register/70">
        {failed
          ? "chain unreachable — the seal cannot be read"
          : chain
            ? `block #${chain.block.toLocaleString()}`
            : "reading the chain…"}
      </p>

      <hr className="my-6 border-register/20" />

      {/* The visitor's own clock, printed and then set aside. */}
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-register/50">
        This device
      </p>
      <p className="font-display text-2xl leading-none tracking-tight text-register/40 line-through tabular-nums">
        {clock(device)}
      </p>
      <p className="mt-2 font-mono text-[11px] text-register/50">
        not consulted — change it and nothing here moves
      </p>

      <hr className="my-6 border-register/20" />

      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-register/50">
        Release is gated on this contract
      </p>
      <p className="mt-1.5 break-all font-mono text-[11px] leading-relaxed text-register/80">
        {PAPER_CONTRACT}
      </p>
      {chain?.hasCode && (
        <p className="mt-1 font-mono text-[11px] text-register/60">
          code present at address — verified over JSON-RPC
        </p>
      )}
    </figure>
  );
}
