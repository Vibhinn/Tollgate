import type { ReactNode } from "react";
import { Activity, type LucideIcon } from "lucide-react";
import { HISTORY_SECONDS, STREAM_INTERVAL_SECONDS } from "../metrics/history";

export function BrandMark({ small = false }: { small?: boolean }) {
  return <span className={small ? "brand-mark small" : "brand-mark"}><span /><span /><i /></span>;
}

export function SectionKicker({ children, rule = false }: { children: string; rule?: boolean }) {
  return <div className="section-kicker"><span>{children}</span>{rule && <span className="kicker-rule" />}</div>;
}

export function EmptyState({ children }: { children: string }) {
  return <div className="empty-models"><Activity size={19} /><span>{children}</span></div>;
}

export function Sparkline({ values, color = "#10b981", fill = false, label }: { values: number[]; color?: string; fill?: boolean; label: string }) {
  const width = 600, height = 150, pad = 8;
  const max = Math.max(1, ...values), min = Math.min(0, ...values), range = max - min || 1;
  const step = (width - pad * 2) / Math.max(values.length - 1, 1);
  const coords = values.map((v, i) => [pad + i * step, height - pad - ((v - min) / range) * (height - pad * 2)] as const);
  const line = coords.map(([x, y]) => `${x},${y}`).join(" ");
  const last = coords.at(-1);
  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} preserveAspectRatio="none">
      {[0.25, 0.5, 0.75].map((v) => <line key={v} x1="0" x2={width} y1={height * v} y2={height * v} className="chart-grid" />)}
      {fill && <polygon points={`${pad},${height - pad} ${line} ${width - pad},${height - pad}`} fill={color} opacity=".12" />}
      <polyline points={line} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      {last && <circle cx={last[0]} cy={last[1]} r="4" fill={color} />}
    </svg>
  );
}

type MetricCardProps = { title: string; value: string; suffix?: string; icon: LucideIcon; detail: string; children?: ReactNode };

export function MetricCard({ title, value, suffix, icon: Icon, detail, children }: MetricCardProps) {
  return (
    <section className="panel metric-card">
      <div className="metric-top"><span className="eyebrow">{title}</span><Icon size={16} /></div>
      <div className="metric-value">{value}<small>{suffix}</small></div>
      <div className="metric-detail">{detail}</div>
      {children}
    </section>
  );
}

export function MetricFoot({ label, children }: { label: string; children: ReactNode }) {
  return <div className="metric-foot"><span>{label}</span><b>{children}</b></div>;
}

export function ChartPanel({ title, subtitle, children, tag }: { title: string; subtitle: string; children: ReactNode; tag?: string }) {
  return (
    <section className="panel chart-panel">
      <header className="panel-heading">
        <div><h2>{title}</h2><p>{subtitle}</p></div>
        {tag && <span className="chart-tag">{tag}</span>}
      </header>
      {children}
    </section>
  );
}

export const LIVE_TAG = `LIVE · ${HISTORY_SECONDS} SEC`;

type RateChartProps = { legend: string; current: string; values: number[]; label: string };

/** Legend, filled sparkline and time axis: the body of the two per-second rate charts. */
export function RateChart({ legend, current, values, label }: RateChartProps) {
  return (
    <>
      <div className="chart-legend">
        <span><i className="legend-dot emerald" />{legend}</span>
        <span className="legend-current">{current}</span>
      </div>
      <div className="large-chart"><Sparkline values={values} label={label} fill /></div>
      <div className="chart-axis"><span>OLDEST SAMPLE</span><span>UPDATES EVERY {STREAM_INTERVAL_SECONDS} SEC</span><span>NOW</span></div>
    </>
  );
}
