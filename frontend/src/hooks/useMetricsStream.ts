import { useEffect, useState } from "react";
import { readServerSentEvents } from "../api/sse";
import { appendEntityHistory, appendPoint, STREAM_INTERVAL_SECONDS, type EntityHistory, type Point } from "../metrics/history";
import type { Connection, Snapshot } from "../types";

export type MetricsState = {
  snapshot: Snapshot | null;
  points: Point[];
  entityHistory: EntityHistory;
  lastSeen: Date | null;
};

const EMPTY: MetricsState = { snapshot: null, points: [], entityHistory: {}, lastSeen: null };

/** Streams admin metrics while `sessionToken` is set. `onUnauthorized` must be stable (useCallback). */
export function useMetricsStream(sessionToken: string, onUnauthorized: () => void) {
  const [connection, setConnection] = useState<Connection>("idle");
  const [error, setError] = useState("");
  const [metrics, setMetrics] = useState<MetricsState>(EMPTY);

  useEffect(() => {
    setMetrics(EMPTY);
    setError("");
    setConnection(sessionToken ? "connecting" : "idle");
    if (!sessionToken) return;

    const controller = new AbortController();
    const fail = (message: string) => {
      if (controller.signal.aborted) return;
      setConnection("error");
      setError(message);
    };

    const stream = async () => {
      const response = await fetch(`/api/v1/metrics?interval=${STREAM_INTERVAL_SECONDS}`, {
        headers: { Authorization: `Bearer ${sessionToken}`, Accept: "text/event-stream" },
        signal: controller.signal,
      });
      if (response.status === 401) return onUnauthorized();
      if (!response.ok) throw new Error(`Metrics endpoint returned ${response.status}.`);
      if (!response.body) throw new Error("This browser does not support streaming responses.");
      setConnection("live");

      let prev: Snapshot | null = null;
      let prevAt = 0;
      for await (const { event, data } of readServerSentEvents(response.body)) {
        if (controller.signal.aborted) return;
        if (event !== "metrics" || !data) continue;
        const now = Date.now();
        const next = JSON.parse(data) as Snapshot;
        const seconds = prev ? Math.max((now - prevAt) / 1000, 0.25) : STREAM_INTERVAL_SECONDS;
        const before = prev;
        setMetrics((old) => ({
          snapshot: next,
          points: appendPoint(old.points, next, before, seconds),
          entityHistory: appendEntityHistory(old.entityHistory, next, before, seconds),
          lastSeen: new Date(now),
        }));
        prev = next;
        prevAt = now;
      }
      fail("The metrics stream ended. Reconnect by signing in again.");
    };

    stream().catch((caught: unknown) => fail(caught instanceof Error ? caught.message : "Could not connect to admin metrics."));
    return () => controller.abort();
  }, [sessionToken, onUnauthorized]);

  return { connection, error, ...metrics };
}
