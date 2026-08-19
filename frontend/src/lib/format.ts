/**
 * The API serialises naive UTC datetimes ("2026-08-18T18:49:49.515877") with no
 * trailing Z, and `new Date` reads those as *local* time -- which showed every
 * fresh audit entry as hours old for anyone east of Greenwich. Anything without
 * an explicit designator is UTC, so say so before parsing.
 */
function parseTs(iso: string): number {
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(iso);
  return new Date(hasZone ? iso : `${iso}Z`).getTime();
}

export function relativeTime(iso: string): string {
  const then = parseTs(iso);
  const secs = Math.round((Date.now() - then) / 1000);
  if (Number.isNaN(secs)) return "--";
  if (secs < 60) return `${Math.max(secs, 0)}s ago`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
  if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
  return `${Math.floor(secs / 86400)}d ago`;
}

export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "--";
  return new Date(parseTs(iso)).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Unix seconds -> readable local time. */
export function formatUnix(seconds: number | undefined): string {
  if (seconds === undefined) return "--";
  return new Date(seconds * 1000).toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}

/** Seconds -> HH:MM:SS, the countdown format. */
export function countdown(seconds: number): string {
  const s = Math.max(0, Math.floor(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  return [h, m, sec].map((n) => String(n).padStart(2, "0")).join(":");
}

export function titleCase(value: string): string {
  return value
    .replace(/_/g, " ")
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}
