import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Activity, ArrowUpRight, Cpu, Database, Gauge, KeyRound, LogOut, Network, RefreshCw, Search, Server, ShieldCheck, ShieldAlert, type LucideIcon } from "lucide-react";

type ModelMetrics = { requests: number; errors?: number; input_tokens: number; output_tokens: number; avg_latency_ms?: number | null; available?: boolean };
type EntityMetrics = { team?: string; name?: string; requests: number; "2xx": number; "4xx": number; "5xx": number; rate_limited: number; no_model_available: number; cache_exact_hits: number; cache_semantic_hits: number; cache_misses: number; input_tokens: number; output_tokens: number; models: Record<string, ModelMetrics> };
type Snapshot = {
  generated_at?: string; uptime_seconds: number;
  process?: { cpu_percent: number; memory_mb: number } | null;
  requests?: { total: number; "2xx": number; "4xx": number; "5xx": number; rate_limited: number; no_model_available: number; rejected_by_backpressure: number; shed: number; in_flight: number } | null;
  cache?: { exact_hits: number; semantic_hits: number; misses: number; hit_rate: number } | null; no_model_available?: boolean | null;
  models?: Record<string, ModelMetrics> | null; dependencies?: Record<string, string> | null;
  teams?: Record<string, EntityMetrics> | null; users?: Record<string, EntityMetrics> | null; tokens?: Record<string, EntityMetrics> | null;
};
type Point = { at: number; rps: number; success: number; clientError: number; serverError: number; backpressure: number; exact: number; semantic: number; misses: number; inflight: number; cpu: number; memory: number };
type EntityPoint = { at: number; requests: number; inputTokens: number; outputTokens: number; errors: number };
type Connection = "idle" | "connecting" | "live" | "error";
type EntityTab = "tokens" | "users" | "teams";
const MAX_POINTS = 36;
const pretty = (n: number | null | undefined) => n == null || !Number.isFinite(n) ? "—" : Intl.NumberFormat("en", { notation: n > 9999 ? "compact" : "standard", maximumFractionDigits: 1 }).format(n);
const duration = (seconds: number) => { const d = Math.floor(seconds / 86400), h = Math.floor(seconds % 86400 / 3600), m = Math.floor(seconds % 3600 / 60); return d ? `${d}d ${h}h` : h ? `${h}h ${m}m` : `${m}m`; };
const entityRequests = (stats: EntityMetrics) => stats.requests;

function Sparkline({ values, color = "#10b981", fill = false, label }: { values: number[]; color?: string; fill?: boolean; label: string }) {
  const width = 600, height = 150, pad = 8, max = Math.max(1, ...values), min = Math.min(0, ...values), range = max - min || 1;
  const coords = values.map((v, i) => `${pad + i * (width - pad * 2) / Math.max(values.length - 1, 1)},${height - pad - (v - min) / range * (height - pad * 2)}`);
  const line = coords.join(" "), area = `${pad},${height - pad} ${line} ${width - pad},${height - pad}`;
  return <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} preserveAspectRatio="none">
    {[0.25, 0.5, 0.75].map((v) => <line key={v} x1="0" x2={width} y1={height * v} y2={height * v} className="chart-grid" />)}
    {fill && <polygon points={area} fill={color} opacity=".12" />}
    <polyline points={line} fill="none" stroke={color} strokeWidth="2.5" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
    {coords.length > 0 && <circle cx={Number(coords.at(-1)?.split(",")[0])} cy={Number(coords.at(-1)?.split(",")[1])} r="4" fill={color} />}
  </svg>;
}

function MetricCard({ title, value, suffix, icon: Icon, detail, children }: { title: string; value: string; suffix?: string; icon: LucideIcon; detail: string; children?: ReactNode }) {
  return <section className="panel metric-card"><div className="metric-top"><span className="eyebrow">{title}</span><Icon size={16} /></div><div className="metric-value">{value}<small>{suffix}</small></div><div className="metric-detail">{detail}</div>{children}</section>;
}

function ChartPanel({ title, subtitle, children, tag }: { title: string; subtitle: string; children: ReactNode; tag?: string }) {
  return <section className="panel chart-panel"><header className="panel-heading"><div><h2>{title}</h2><p>{subtitle}</p></div>{tag && <span className="chart-tag">{tag}</span>}</header>{children}</section>;
}

function LoginPage({ onLogin, notice }: { onLogin: (username: string, password: string) => Promise<void>; notice?: string }) {
  const [username, setUsername] = useState(""); const [password, setPassword] = useState(""); const [pending, setPending] = useState(false); const [error, setError] = useState("");
  const submit = async (event: FormEvent) => { event.preventDefault(); setPending(true); setError(""); try { await onLogin(username, password); } catch (caught) { setError(caught instanceof Error ? caught.message : "Unable to sign in."); } finally { setPending(false); } };
  return <main className="login-shell"><div className="login-glow" /><section className="login-card panel"><div className="login-brand"><span className="brand-mark"><span /><span /><i /></span><span>TOLLGATE</span><span className="login-brand-divider">/</span><span>ADMIN</span></div><div className="login-emblem"><ShieldCheck size={24} /></div><div className="section-kicker"><span>ADMINISTRATOR ACCESS</span><span className="kicker-rule" /></div><h1>Welcome <em>back.</em></h1><p className="login-copy">Sign in to view gateway and per-token activity.</p>{notice && <div className="login-error"><ShieldAlert size={15} />{notice}</div>}<form className="login-form" onSubmit={(event) => { void submit(event); }}><label>USERNAME<input autoComplete="username" value={username} onChange={(event) => setUsername(event.target.value)} placeholder="Admin username" required /></label><label>PASSWORD<input type="password" autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="Admin password" required /></label>{error && <div className="login-error"><ShieldAlert size={15} />{error}</div>}<button className="login-submit" disabled={pending || !username || !password}>{pending ? <RefreshCw size={15} className="spin" /> : <KeyRound size={15} />}{pending ? "SIGNING IN" : "SIGN IN TO DASHBOARD"}<ArrowUpRight size={14} /></button></form><div className="login-foot"><i />CREDENTIALS ARE SENT SECURELY TO THE ADMIN LOGIN API</div></section><div className="login-caption">TOLLGATE <span>·</span> LIVE GATEWAY OBSERVABILITY</div></main>;
}

export default function Dashboard() {
  const [sessionToken, setSessionToken] = useState(() => sessionStorage.getItem("tollgate-admin-session") ?? "");
  const [connection, setConnection] = useState<Connection>("idle"); const [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [points, setPoints] = useState<Point[]>([]); const [entityPoints, setEntityPoints] = useState<EntityPoint[]>([]);
  const [lastSeen, setLastSeen] = useState<Date | null>(null); const [error, setError] = useState("");
  const [loginNotice, setLoginNotice] = useState("");
  const [tab, setTab] = useState<EntityTab>("tokens"); const [query, setQuery] = useState(""); const [selectedId, setSelectedId] = useState("");
  const abortRef = useRef<AbortController | null>(null); const previousRef = useRef<Snapshot | null>(null); const previousAtRef = useRef<number | null>(null);
  const entityHistoryRef = useRef<Record<string, EntityPoint[]>>({}); const selectionRef = useRef({ tab, selectedId });
  selectionRef.current = { tab, selectedId };

  const signOut = useCallback(() => { abortRef.current?.abort(); abortRef.current = null; sessionStorage.removeItem("tollgate-admin-session"); setSessionToken(""); setConnection("idle"); setSnapshot(null); setPoints([]); setEntityPoints([]); setError(""); setSelectedId(""); previousRef.current = null; previousAtRef.current = null; entityHistoryRef.current = {}; }, []);
  const login = useCallback(async (username: string, password: string) => {
    const response = await fetch("/api/v1/admin/login", { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" }, body: JSON.stringify({ username, password }) });
    const body = await response.json().catch(() => ({})) as { session_token?: string; error?: { message?: string } };
    if (!response.ok || !body.session_token) throw new Error(body.error?.message ?? `Login failed (${response.status}). Check your credentials and try again.`);
    sessionStorage.setItem("tollgate-admin-session", body.session_token); setLoginNotice(""); setSessionToken(body.session_token);
  }, []);

  useEffect(() => {
    if (!sessionToken) return;
    const controller = new AbortController(); abortRef.current?.abort(); abortRef.current = controller;
    previousRef.current = null; previousAtRef.current = null; entityHistoryRef.current = {}; setPoints([]); setEntityPoints([]); setSnapshot(null); setError(""); setConnection("connecting");
    const stream = async () => {
      try {
        const response = await fetch("/api/v1/metrics?interval=2", { headers: { Authorization: `Bearer ${sessionToken}`, Accept: "text/event-stream" }, signal: controller.signal });
        if (!response.ok) {
          if (response.status === 401) { signOut(); setLoginNotice("Your admin session is invalid or expired. Sign in again."); return; }
          throw new Error(`Metrics endpoint returned ${response.status}.`);
        }
        if (!response.body) throw new Error("This browser does not support streaming responses.");
        setConnection("live"); const reader = response.body.getReader(), decoder = new TextDecoder(); let buffer = "";
        while (!controller.signal.aborted) {
          const { value, done } = await reader.read(); if (done) break;
          buffer += decoder.decode(value, { stream: true }); let boundary = buffer.indexOf("\n\n");
          while (boundary !== -1) {
            const frame = buffer.slice(0, boundary); buffer = buffer.slice(boundary + 2);
            if (frame.split("\n").some((line) => line === "event: metrics")) {
              const data = frame.split("\n").filter((line) => line.startsWith("data:")).map((line) => line.slice(5).trim()).join("\n");
              if (data) {
                const now = Date.now(), next = JSON.parse(data) as Snapshot, prev = previousRef.current, interval = prev && previousAtRef.current ? Math.max((now - previousAtRef.current) / 1000, 0.25) : 2;
                const delta = (a: number | undefined, b: number | undefined) => prev && a !== undefined && b !== undefined ? Math.max(0, a - b) / interval : 0;
                const point: Point = { at: now, rps: delta(next.requests?.total, prev?.requests?.total), success: delta(next.requests?.["2xx"], prev?.requests?.["2xx"]), clientError: delta(next.requests?.["4xx"], prev?.requests?.["4xx"]), serverError: delta(next.requests?.["5xx"], prev?.requests?.["5xx"]), backpressure: delta(next.requests?.rejected_by_backpressure, prev?.requests?.rejected_by_backpressure), exact: delta(next.cache?.exact_hits, prev?.cache?.exact_hits), semantic: delta(next.cache?.semantic_hits, prev?.cache?.semantic_hits), misses: delta(next.cache?.misses, prev?.cache?.misses), inflight: next.requests?.in_flight ?? 0, cpu: next.process?.cpu_percent ?? 0, memory: next.process?.memory_mb ?? 0 };
                for (const kind of ["tokens", "users", "teams"] as const) {
                  const currentEntities = next[kind] ?? {}, beforeEntities = prev?.[kind] ?? {};
                  for (const id of new Set([...Object.keys(currentEntities), ...Object.keys(beforeEntities)])) {
                    const current = currentEntities[id], before = beforeEntities[id], historyKey = `${kind}:${id}`, prior = entityHistoryRef.current[historyKey] ?? [];
                    entityHistoryRef.current[historyKey] = [...prior, { at: now, requests: current ? (before ? Math.max(0, current.requests - before.requests) / interval : 0) : 0, inputTokens: current && before ? Math.max(0, current.input_tokens - before.input_tokens) / interval : 0, outputTokens: current && before ? Math.max(0, current.output_tokens - before.output_tokens) / interval : 0, errors: current && before ? Math.max(0, current["4xx"] + current["5xx"] - before["4xx"] - before["5xx"]) / interval : 0 }].slice(-MAX_POINTS);
                  }
                }
                previousRef.current = next; previousAtRef.current = now; setPoints((old) => [...old, point].slice(-MAX_POINTS)); setSnapshot(next); setLastSeen(new Date(now)); setConnection("live");
                const { tab: selectedTab, selectedId: currentSelected } = selectionRef.current;
                setEntityPoints(entityHistoryRef.current[`${selectedTab}:${currentSelected}`] ?? []);
              }
            }
            boundary = buffer.indexOf("\n\n");
          }
        }
        if (!controller.signal.aborted) { setConnection("error"); setError("The metrics stream ended. Reconnect by signing in again."); }
      } catch (caught) { if (!controller.signal.aborted) { setConnection("error"); setError(caught instanceof Error ? caught.message : "Could not connect to admin metrics."); } }
    };
    void stream(); return () => controller.abort();
  }, [sessionToken, signOut]);

  const tokens = useMemo(() => Object.entries(snapshot?.tokens ?? {}).sort((a, b) => b[1].requests - a[1].requests), [snapshot]);
  const users = useMemo(() => Object.entries(snapshot?.users ?? {}).sort((a, b) => b[1].requests - a[1].requests), [snapshot]);
  const teams = useMemo(() => Object.entries(snapshot?.teams ?? {}).sort((a, b) => b[1].requests - a[1].requests), [snapshot]);
  const items = tab === "tokens" ? tokens : tab === "users" ? users : teams;
  const filtered = useMemo(() => items.filter(([id, stats]) => `${id} ${stats.team ?? ""} ${stats.name ?? ""}`.toLowerCase().includes(query.toLowerCase())), [items, query]);
  const selectedEntities = tab === "tokens" ? snapshot?.tokens : tab === "users" ? snapshot?.users : snapshot?.teams;
  const selected = selectedEntities?.[selectedId];
  const selectedSeries = entityHistoryRef.current[`${tab}:${selectedId}`] ?? [];
  const selectedRate = selectedSeries.at(-1)?.requests ?? 0;
  const totalRequests = snapshot?.requests?.total ?? 0, cacheRate = snapshot?.cache?.hit_rate;
  const requestSeries = points.map((p) => p.rps);
  const modelRows = Object.entries(selected?.models ?? {}).sort((a, b) => b[1].requests - a[1].requests);
  const totalTokens = (snapshot?.tokens ? Object.values(snapshot.tokens) : []).reduce((sum, item) => sum + item.input_tokens + item.output_tokens, 0);

  if (!sessionToken) return <LoginPage onLogin={login} notice={loginNotice || undefined} />;

  return <main className="app-shell"><div className="ambient ambient-one" /><div className="ambient ambient-two" />
    <nav className="topbar"><div className="brand"><span className="brand-mark"><span /><span /><i /></span><span>TOLLGATE</span><span className="brand-divider">/</span><span className="brand-context">ADMIN OBSERVABILITY</span></div><div className="topbar-right"><span className="admin-badge"><ShieldCheck size={13} />ADMIN SESSION</span><span className={`connection ${connection}`}><i />{connection === "live" ? "LIVE STREAM" : connection === "connecting" ? "CONNECTING" : connection === "error" ? "STREAM ERROR" : "STREAM PAUSED"}</span><span className="api-route">API / V1 / METRICS</span><button className="logout-button" onClick={signOut}><LogOut size={13} />LOG OUT</button></div></nav>
    <div className="content"><header className="hero"><div><div className="section-kicker"><span>ADMINISTRATOR OVERVIEW</span><span className="kicker-rule" /></div><h1>Gateway <em>control.</em></h1><p className="hero-copy">One live view across every team, user, and access token.</p></div><div className="hero-side"><div className="live-pulse"><span className={connection === "live" ? "pulse-dot active" : "pulse-dot"} /><span>{connection === "live" ? "ADMIN METRICS STREAMING" : "CONNECTING TO METRICS"}</span></div><div className="updated">{lastSeen ? `UPDATED ${lastSeen.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}` : "REFRESHING EVERY 2 SECONDS"}</div></div></header>
      {error && <div className="error-banner"><ShieldAlert size={16} /><span>{error}</span>{connection === "error" && <button onClick={() => { setConnection("connecting"); setSessionToken(""); sessionStorage.removeItem("tollgate-admin-session"); }}>Sign in again</button>}</div>}
      {snapshot?.no_model_available === true && <section className="model-outage-banner" role="alert" aria-live="assertive"><span className="outage-icon"><ShieldAlert size={22} /></span><div className="outage-copy"><span className="outage-kicker">LIVE MODEL AVAILABILITY · CRITICAL</span><strong>NO MODELS AVAILABLE</strong><p>Every configured model is benched. Requests requiring a model are currently unable to complete.</p></div><div className="outage-count"><span>POLICY 503 RESPONSES</span><b>{pretty(snapshot.requests?.no_model_available)}</b><small>cumulative · gateway wide</small></div></section>}
      <div className="metrics-grid">
        <MetricCard title="GATEWAY REQUESTS" value={pretty(totalRequests)} icon={Activity} detail="All clients · cumulative count"><div className="mini-chart"><Sparkline values={requestSeries} label="Recent gateway request rate" /></div><div className="metric-foot"><span>LIVE RATE</span><b>{points.length > 1 ? `${requestSeries.at(-1)?.toFixed(2)} req/s` : "— req/s"}</b></div></MetricCard>
        <MetricCard title="NO MODEL RESPONSES" value={pretty(snapshot?.requests?.no_model_available)} icon={ShieldAlert} detail="Policy requests answered with 503"><div className="metric-foot"><span>TEAMS / USERS / TOKENS</span><b>{teams.length} <small>teams · {users.length} users · {tokens.length} tokens</small></b></div></MetricCard>
        <MetricCard title="BACKPRESSURE REJECTIONS" value={pretty(snapshot?.requests?.rejected_by_backpressure)} icon={Activity} detail="Gateway-wide · 503 overloaded"><div className="metric-foot"><span>RECENT · LAST INTERVAL</span><b>{points.length > 1 ? pretty(points.at(-1)?.backpressure) : "—"}</b></div></MetricCard>
        <MetricCard title="CACHE HIT RATE" value={cacheRate == null ? "—" : `${(cacheRate * 100).toFixed(1)}`} suffix={cacheRate == null ? "" : "%"} icon={Database} detail="Gateway-wide exact and semantic hits"><div className="rate-track"><span style={{ width: `${Math.max(0, Math.min(100, (cacheRate ?? 0) * 100))}%` }} /></div><div className="metric-foot"><span>TOTAL TOKENS USED</span><b>{pretty(totalTokens)}</b></div></MetricCard>
        <MetricCard title="GATEWAY UPTIME" value={snapshot ? duration(snapshot.uptime_seconds) : "—"} icon={Server} detail="Time since gateway process start"><div className="uptime-decoration"><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /><span /></div><div className="metric-foot"><span>LAST SNAPSHOT</span><b>{lastSeen ? lastSeen.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "WAITING"}</b></div></MetricCard>
      </div>

      <div className="wide-grid"><ChartPanel title="Gateway request throughput" subtitle="Requests per second · derived from cumulative counter deltas" tag="LIVE · 72 SEC"><div className="chart-legend"><span><i className="legend-dot emerald" />ALL TOKENS / SEC</span><span className="legend-current">{points.length > 1 ? `${requestSeries.at(-1)?.toFixed(2)} / SEC` : "AWAITING DATA"}</span></div><div className="large-chart"><Sparkline values={requestSeries} label="Gateway requests per second" fill /></div><div className="chart-axis"><span>OLDEST SAMPLE</span><span>UPDATES EVERY 2 SEC</span><span>NOW</span></div></ChartPanel>
        <ChartPanel title="Service health" subtitle="Gateway process and dependencies"><div className="process-health"><div className="process-health-item"><Cpu size={14} /><span>CPU</span><b>{snapshot?.process ? `${snapshot.process.cpu_percent.toFixed(1)}%` : "—"}</b></div><div className="process-health-item"><Gauge size={14} /><span>MEMORY</span><b>{snapshot?.process ? `${pretty(snapshot.process.memory_mb)} MB` : "—"}</b></div></div><div className="dependency-list compact-dependencies">{([{ key: "redis", title: "Redis", icon: Database }, { key: "qdrant", title: "Qdrant", icon: Network }, { key: "classifier", title: "Classifier", icon: Cpu }] as const).map(({ key, title, icon: Icon }) => { const state = snapshot?.dependencies?.[key]; return <div className="dependency-row" key={key}><span className="dependency-icon"><Icon size={14} /></span><span className="dependency-name">{title}</span><span className={`health ${state === "ok" ? "ok" : state ? "degraded" : "unknown"}`}><i />{state?.toUpperCase() ?? "WAITING"}</span></div>; })}</div></ChartPanel></div>

      <section className="panel entity-panel"><header className="panel-heading entity-heading"><div><div className="section-kicker"><span>USAGE BREAKDOWN</span></div><h2>Every client. One place.</h2><p>Explore gateway usage by access token, user, or team.</p></div><span className="chart-tag">ADMIN ONLY</span></header>
        <div className="entity-toolbar"><div className="entity-tabs" role="tablist" aria-label="Usage breakdown"><button className={tab === "tokens" ? "active" : ""} onClick={() => { setTab("tokens"); setSelectedId(""); }}><KeyRound size={13} />TOKENS<span>{tokens.length}</span></button><button className={tab === "users" ? "active" : ""} onClick={() => { setTab("users"); setSelectedId(""); }}><Activity size={13} />USERS<span>{users.length}</span></button><button className={tab === "teams" ? "active" : ""} onClick={() => { setTab("teams"); setSelectedId(""); }}><Network size={13} />TEAMS<span>{teams.length}</span></button></div><label className="entity-search"><Search size={14} /><input placeholder={`Search ${tab}…`} value={query} onChange={(event) => setQuery(event.target.value)} /><span>{filtered.length} RESULTS</span></label></div>
        <div className="entity-table-wrap"><table className="entity-table"><thead><tr>{tab === "tokens" ? <><th>TOKEN ID</th><th>TEAM</th><th>NAME</th></> : <><th>{tab === "users" ? "TEAM : USER" : "TEAM"}</th></> }<th>REQUESTS</th><th>2XX</th><th>4XX + 5XX</th><th>INPUT TOKENS</th><th>OUTPUT TOKENS</th><th>CACHE HIT RATE</th><th>REQUEST SHARE</th></tr></thead><tbody>{filtered.map(([id, stats]) => { const active = id === selectedId, failures = stats["4xx"] + stats["5xx"], lookups = stats.cache_exact_hits + stats.cache_semantic_hits + stats.cache_misses, hitRate = lookups ? (stats.cache_exact_hits + stats.cache_semantic_hits) / lookups * 100 : 0, share = totalRequests ? stats.requests / totalRequests * 100 : 0; return <tr key={id} className={active ? "selected" : ""} onClick={() => { setSelectedId(id); setEntityPoints(entityHistoryRef.current[`${tab}:${id}`] ?? []); }} tabIndex={0} onKeyDown={(event) => { if (event.key === "Enter") { setSelectedId(id); setEntityPoints(entityHistoryRef.current[`${tab}:${id}`] ?? []); } }}><td><span className="entity-id"><i className="model-dot" />{id}</span></td>{tab === "tokens" && <><td>{stats.team ?? "—"}</td><td>{stats.name ?? "—"}</td></>}<td>{pretty(stats.requests)}</td><td>{pretty(stats["2xx"])}</td><td>{pretty(failures)}</td><td>{pretty(stats.input_tokens)}</td><td>{pretty(stats.output_tokens)}</td><td><span className="entity-rate">{hitRate.toFixed(1)}%</span></td><td><div className="share-cell"><div className="share-track"><i style={{ width: `${share}%` }} /></div><span>{share.toFixed(1)}%</span></div></td></tr>; })}</tbody></table>
          {!filtered.length && <div className="empty-models"><Activity size={19} /><span>{snapshot?.[tab] ? `No ${tab} match this search.` : `Waiting for ${tab} usage data…`}</span></div>}
        </div>
        <div className="no-model-breakdown"><header><strong>No model available responses by {tab === "tokens" ? "token" : tab === "users" ? "user" : "team"}</strong><span>POLICY 503 · BACKPRESSURE SHED EXCLUDED</span></header><div className="no-model-entities">{items.length ? items.map(([id, stats]) => <div className={stats.no_model_available ? "has-no-model" : ""} key={id}><span>{tab === "tokens" ? `${stats.team ?? ""}${stats.team ? " / " : ""}${stats.name ?? id}` : id}</span><b>{pretty(stats.no_model_available)}</b><small>rate limited {pretty(stats.rate_limited)}</small></div>) : <span className="no-model-empty">Entity counters appear as requests are recorded.</span>}</div></div>
      </section>

      <div className="wide-grid detail-grid"><ChartPanel title={selected ? `${tab === "tokens" ? "Token" : tab === "users" ? "User" : "Team"} activity · ${selectedId}` : "Select a client to inspect"} subtitle={selected ? "Recent request rate calculated from admin metric snapshots" : "Choose a row above to see recent activity and model usage"} tag={selected ? "LIVE · 72 SEC" : undefined}><div className="chart-legend"><span><i className="legend-dot emerald" />REQUESTS / SEC</span><span className="legend-current">{selected ? `${selectedRate.toFixed(2)} / SEC` : "NO CLIENT SELECTED"}</span></div><div className="large-chart"><Sparkline values={entityPoints.map((item) => item.requests)} label="Selected client requests per second" fill /></div><div className="chart-axis"><span>OLDEST SAMPLE</span><span>UPDATES EVERY 2 SEC</span><span>NOW</span></div></ChartPanel>
        <ChartPanel title="Selected client" subtitle={selected ? `${selected.team ?? "Gateway client"}${selected.name ? ` · ${selected.name}` : ""}` : "Per-client counters and model selection"}><div className="selected-summary"><div><span>LIFETIME REQUESTS</span><b>{selected ? pretty(entityRequests(selected)) : "—"}</b></div><div><span>RATE LIMITED</span><b>{selected ? pretty(selected.rate_limited) : "—"}</b></div><div className={selected?.no_model_available ? "selected-warning" : ""}><span>NO MODEL AVAILABLE</span><b>{selected ? pretty(selected.no_model_available) : "—"}</b></div><div><span>INPUT / OUTPUT</span><b>{selected ? `${pretty(selected.input_tokens)} / ${pretty(selected.output_tokens)}` : "—"}</b></div><div><span>CACHE HITS</span><b>{selected ? pretty(selected.cache_exact_hits + selected.cache_semantic_hits) : "—"}</b></div></div></ChartPanel></div>

      <section className="panel model-panel"><header className="panel-heading model-heading"><div><h2>{selected ? "Model usage for selected client" : "Gateway model performance"}</h2><p>{selected ? "Per-token request and token counts by model" : "Lifetime gateway model counters and current availability"}</p></div><span className="model-count">{(selected ? modelRows : Object.entries(snapshot?.models ?? {})).length.toString().padStart(2, "0")} MODELS</span></header><div className="model-table-wrap"><table className="model-table"><thead><tr><th>MODEL</th>{!selected && <th>STATUS</th>}<th>REQUESTS</th><th>INPUT TOKENS</th><th>OUTPUT TOKENS</th>{!selected && <th>AVG LATENCY</th>}</tr></thead><tbody>{selected ? modelRows.map(([name, model]) => <tr key={name}><td><span className="model-name"><i className="model-dot" />{name}</span></td><td>{pretty(model.requests)}</td><td>{pretty(model.input_tokens)}</td><td>{pretty(model.output_tokens)}</td></tr>) : Object.entries(snapshot?.models ?? {}).map(([name, model]) => <tr key={name}><td><span className="model-name"><i className={model.available ? "model-dot" : "model-dot offline"} />{name}</span></td><td><span className={`model-status ${model.available ? "available" : "unavailable"}`}>{model.available ? "AVAILABLE" : "BENCHED"}</span></td><td>{pretty(model.requests)}</td><td>{pretty(model.input_tokens)}</td><td>{pretty(model.output_tokens)}</td><td>{model.avg_latency_ms == null ? "—" : `${pretty(model.avg_latency_ms)} ms`}</td></tr>)}</tbody></table>{!selected && !snapshot?.models && <div className="empty-models"><Activity size={19} /><span>Waiting for model telemetry.</span></div>}{selected && !modelRows.length && <div className="empty-models"><Activity size={19} /><span>No model usage recorded for this client yet.</span></div>}</div></section>

      <footer className="footer"><div className="footer-brand"><span className="brand-mark small"><span /><span /><i /></span><span>TOLLGATE</span><span className="footer-separator">·</span><span>ADMIN METRICS CONSOLE</span></div><span className="footer-right"><i className={connection === "live" ? "footer-indicator active" : "footer-indicator"} />{connection === "live" ? "SESSION ACTIVE · STREAM HEALTHY" : "ADMIN SESSION"}</span></footer>
    </div>
  </main>;
}
