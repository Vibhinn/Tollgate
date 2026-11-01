import { LogOut, ShieldAlert, ShieldCheck } from "lucide-react";
import { clock, pretty } from "../format";
import { STREAM_INTERVAL_SECONDS } from "../metrics/history";
import type { Connection, Snapshot } from "../types";
import { BrandMark, SectionKicker } from "./ui";

const CONNECTION_LABELS: Record<Connection, string> = {
  live: "LIVE STREAM",
  connecting: "CONNECTING",
  error: "STREAM ERROR",
  idle: "STREAM PAUSED",
};

export function TopBar({ connection, onSignOut }: { connection: Connection; onSignOut: () => void }) {
  return (
    <nav className="topbar">
      <div className="brand">
        <BrandMark /><span>TOLLGATE</span><span className="brand-divider">/</span><span className="brand-context">ADMIN OBSERVABILITY</span>
      </div>
      <div className="topbar-right">
        <span className="admin-badge"><ShieldCheck size={13} />ADMIN SESSION</span>
        <span className={`connection ${connection}`}><i />{CONNECTION_LABELS[connection]}</span>
        <span className="api-route">API / V1 / METRICS</span>
        <button className="logout-button" onClick={onSignOut}><LogOut size={13} />LOG OUT</button>
      </div>
    </nav>
  );
}

export function Hero({ live, lastSeen }: { live: boolean; lastSeen: Date | null }) {
  return (
    <header className="hero">
      <div>
        <SectionKicker rule>ADMINISTRATOR OVERVIEW</SectionKicker>
        <h1>Gateway <em>control.</em></h1>
        <p className="hero-copy">One live view across every team, user, and access token.</p>
      </div>
      <div className="hero-side">
        <div className="live-pulse">
          <span className={live ? "pulse-dot active" : "pulse-dot"} />
          <span>{live ? "ADMIN METRICS STREAMING" : "CONNECTING TO METRICS"}</span>
        </div>
        <div className="updated">{lastSeen ? `UPDATED ${clock(lastSeen, true)}` : `REFRESHING EVERY ${STREAM_INTERVAL_SECONDS} SECONDS`}</div>
      </div>
    </header>
  );
}

export function ErrorBanner({ message, onSignInAgain }: { message: string; onSignInAgain?: () => void }) {
  return (
    <div className="error-banner">
      <ShieldAlert size={16} /><span>{message}</span>
      {onSignInAgain && <button onClick={onSignInAgain}>Sign in again</button>}
    </div>
  );
}

export function OutageBanner({ snapshot }: { snapshot: Snapshot }) {
  return (
    <section className="model-outage-banner" role="alert" aria-live="assertive">
      <span className="outage-icon"><ShieldAlert size={22} /></span>
      <div className="outage-copy">
        <span className="outage-kicker">LIVE MODEL AVAILABILITY · CRITICAL</span>
        <strong>NO MODELS AVAILABLE</strong>
        <p>Every configured model is benched. Requests requiring a model are currently unable to complete.</p>
      </div>
      <div className="outage-count">
        <span>POLICY 503 RESPONSES</span>
        <b>{pretty(snapshot.requests?.no_model_available)}</b>
        <small>cumulative · gateway wide</small>
      </div>
    </section>
  );
}

export function Footer({ live }: { live: boolean }) {
  return (
    <footer className="footer">
      <div className="footer-brand">
        <BrandMark small /><span>TOLLGATE</span><span className="footer-separator">·</span><span>ADMIN METRICS CONSOLE</span>
      </div>
      <span className="footer-right">
        <i className={live ? "footer-indicator active" : "footer-indicator"} />
        {live ? "SESSION ACTIVE · STREAM HEALTHY" : "ADMIN SESSION"}
      </span>
    </footer>
  );
}
