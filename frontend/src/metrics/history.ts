import type { EntityKind, EntityMetrics, Snapshot } from "../types";

// The server sends cumulative counters; the charts show per-second rates between two snapshots.

export const STREAM_INTERVAL_SECONDS = 2;
export const MAX_POINTS = 36;
export const HISTORY_SECONDS = STREAM_INTERVAL_SECONDS * MAX_POINTS;

export type Point = { rps: number; backpressure: number };
export type EntityHistory = Record<string, number[]>;   // `${kind}:${id}` -> requests/sec samples

const ENTITY_KINDS: EntityKind[] = ["tokens", "users", "teams"];

export const entityKey = (kind: EntityKind, id: string) => `${kind}:${id}`;

const rate = (current: number | undefined, previous: number | undefined, seconds: number) =>
  current === undefined || previous === undefined ? 0 : Math.max(0, current - previous) / seconds;

const keepRecent = <T,>(series: T[], sample: T) => [...series, sample].slice(-MAX_POINTS);

export function appendPoint(points: Point[], next: Snapshot, prev: Snapshot | null, seconds: number): Point[] {
  return keepRecent(points, {
    rps: prev ? rate(next.requests?.total, prev.requests?.total, seconds) : 0,
    backpressure: prev ? rate(next.requests?.rejected_by_backpressure, prev.requests?.rejected_by_backpressure, seconds) : 0,
  });
}

export function appendEntityHistory(history: EntityHistory, next: Snapshot, prev: Snapshot | null, seconds: number): EntityHistory {
  const updated = { ...history };
  for (const kind of ENTITY_KINDS) {
    const current: Record<string, EntityMetrics> = next[kind] ?? {};
    const before: Record<string, EntityMetrics> = prev?.[kind] ?? {};
    for (const id of new Set([...Object.keys(current), ...Object.keys(before)])) {
      const key = entityKey(kind, id);
      updated[key] = keepRecent(updated[key] ?? [], rate(current[id]?.requests, before[id]?.requests, seconds));
    }
  }
  return updated;
}
