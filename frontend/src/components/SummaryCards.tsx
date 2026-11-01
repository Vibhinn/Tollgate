import { Activity, Database, Server, ShieldAlert } from "lucide-react";
import { clock, duration, pretty } from "../format";
import type { Point } from "../metrics/history";
import type { Snapshot } from "../types";
import { MetricCard, MetricFoot, Sparkline } from "./ui";

type Props = {
  snapshot: Snapshot | null;
  points: Point[];
  lastSeen: Date | null;
  counts: { teams: number; users: number; tokens: number };
};

export function SummaryCards({ snapshot, points, lastSeen, counts }: Props) {
  const hasRate = points.length > 1;
  const requestSeries = points.map((p) => p.rps);
  const cacheRate = snapshot?.cache?.hit_rate;
  const totalTokens = Object.values(snapshot?.tokens ?? {}).reduce((sum, t) => sum + t.input_tokens + t.output_tokens, 0);

  return (
    <div className="metrics-grid">
      <MetricCard title="GATEWAY REQUESTS" value={pretty(snapshot?.requests?.total ?? 0)} icon={Activity} detail="All clients · cumulative count">
        <div className="mini-chart"><Sparkline values={requestSeries} label="Recent gateway request rate" /></div>
        <MetricFoot label="LIVE RATE">{hasRate ? `${requestSeries.at(-1)?.toFixed(2)} req/s` : "— req/s"}</MetricFoot>
      </MetricCard>

      <MetricCard title="NO MODEL RESPONSES" value={pretty(snapshot?.requests?.no_model_available)} icon={ShieldAlert} detail="Policy requests answered with 503">
        <MetricFoot label="TEAMS / USERS / TOKENS">
          {counts.teams} <small>teams · {counts.users} users · {counts.tokens} tokens</small>
        </MetricFoot>
      </MetricCard>

      <MetricCard title="BACKPRESSURE REJECTIONS" value={pretty(snapshot?.requests?.rejected_by_backpressure)} icon={Activity} detail="Gateway-wide · 503 overloaded">
        <MetricFoot label="RECENT · LAST INTERVAL">{hasRate ? pretty(points.at(-1)?.backpressure) : "—"}</MetricFoot>
      </MetricCard>

      <MetricCard
        title="CACHE HIT RATE"
        value={cacheRate == null ? "—" : (cacheRate * 100).toFixed(1)}
        suffix={cacheRate == null ? "" : "%"}
        icon={Database}
        detail="Gateway-wide exact and semantic hits"
      >
        <div className="rate-track"><span style={{ width: `${Math.max(0, Math.min(100, (cacheRate ?? 0) * 100))}%` }} /></div>
        <MetricFoot label="TOTAL TOKENS USED">{pretty(totalTokens)}</MetricFoot>
      </MetricCard>

      <MetricCard title="GATEWAY UPTIME" value={snapshot ? duration(snapshot.uptime_seconds) : "—"} icon={Server} detail="Time since gateway process start">
        <div className="uptime-decoration">{Array.from({ length: 16 }, (_, i) => <span key={i} />)}</div>
        <MetricFoot label="LAST SNAPSHOT">{lastSeen ? clock(lastSeen) : "WAITING"}</MetricFoot>
      </MetricCard>
    </div>
  );
}
