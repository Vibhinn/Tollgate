import { useCallback, useMemo, useState } from "react";
import { clearSession, loadSession, requestSessionToken, saveSession } from "./api/session";
import { ENTITY_KINDS } from "./components/entityKinds";
import { EntityPanel } from "./components/EntityPanel";
import { ErrorBanner, Footer, Hero, OutageBanner, TopBar } from "./components/layout";
import { LoginPage } from "./components/LoginPage";
import { ModelPanel } from "./components/ModelPanel";
import { SelectedClientPanel } from "./components/SelectedClientPanel";
import { ServiceHealthPanel } from "./components/ServiceHealthPanel";
import { SummaryCards } from "./components/SummaryCards";
import { ChartPanel, LIVE_TAG, RateChart } from "./components/ui";
import { useMetricsStream } from "./hooks/useMetricsStream";
import { byRequestsDesc } from "./metrics/derive";
import { entityKey } from "./metrics/history";
import type { EntityKind } from "./types";

export default function Dashboard() {
  const [sessionToken, setSessionToken] = useState(loadSession);
  const [loginNotice, setLoginNotice] = useState("");
  const [kind, setKind] = useState<EntityKind>("tokens");
  const [query, setQuery] = useState("");
  const [selectedId, setSelectedId] = useState("");

  const signOut = useCallback(() => {
    clearSession();
    setSessionToken("");
    setSelectedId("");
  }, []);

  const expireSession = useCallback(() => {
    signOut();
    setLoginNotice("Your admin session is invalid or expired. Sign in again.");
  }, [signOut]);

  const login = useCallback(async (username: string, password: string) => {
    const token = await requestSessionToken(username, password);
    saveSession(token);
    setLoginNotice("");
    setSessionToken(token);
  }, []);

  const { connection, error, snapshot, points, entityHistory, lastSeen } = useMetricsStream(sessionToken, expireSession);

  const rowsByKind = useMemo(
    () => ({ tokens: byRequestsDesc(snapshot?.tokens), users: byRequestsDesc(snapshot?.users), teams: byRequestsDesc(snapshot?.teams) }),
    [snapshot],
  );

  if (!sessionToken) return <LoginPage onLogin={login} notice={loginNotice || undefined} />;

  const live = connection === "live";
  const selected = snapshot?.[kind]?.[selectedId];
  const selectedSeries = entityHistory[entityKey(kind, selectedId)] ?? [];
  const requestSeries = points.map((p) => p.rps);

  const changeKind = (next: EntityKind) => {
    setKind(next);
    setSelectedId("");
  };

  return (
    <main className="app-shell">
      <div className="ambient ambient-one" />
      <div className="ambient ambient-two" />
      <TopBar connection={connection} onSignOut={signOut} />

      <div className="content">
        <Hero live={live} lastSeen={lastSeen} />
        {error && <ErrorBanner message={error} onSignInAgain={connection === "error" ? signOut : undefined} />}
        {snapshot?.no_model_available === true && <OutageBanner snapshot={snapshot} />}

        <SummaryCards
          snapshot={snapshot}
          points={points}
          lastSeen={lastSeen}
          counts={{ teams: rowsByKind.teams.length, users: rowsByKind.users.length, tokens: rowsByKind.tokens.length }}
        />

        <div className="wide-grid">
          <ChartPanel title="Gateway request throughput" subtitle="Requests per second · derived from cumulative counter deltas" tag={LIVE_TAG}>
            <RateChart
              legend="ALL TOKENS / SEC"
              current={points.length > 1 ? `${requestSeries.at(-1)?.toFixed(2)} / SEC` : "AWAITING DATA"}
              values={requestSeries}
              label="Gateway requests per second"
            />
          </ChartPanel>
          <ServiceHealthPanel snapshot={snapshot} />
        </div>

        <EntityPanel
          kind={kind}
          onKindChange={changeKind}
          rowsByKind={rowsByKind}
          hasData={Boolean(snapshot?.[kind])}
          query={query}
          onQueryChange={setQuery}
          selectedId={selectedId}
          onSelect={setSelectedId}
          totalRequests={snapshot?.requests?.total ?? 0}
        />

        <div className="wide-grid detail-grid">
          <ChartPanel
            title={selected ? `${ENTITY_KINDS[kind].title} activity · ${selectedId}` : "Select a client to inspect"}
            subtitle={selected ? "Recent request rate calculated from admin metric snapshots" : "Choose a row above to see recent activity and model usage"}
            tag={selected ? LIVE_TAG : undefined}
          >
            <RateChart
              legend="REQUESTS / SEC"
              current={selected ? `${(selectedSeries.at(-1) ?? 0).toFixed(2)} / SEC` : "NO CLIENT SELECTED"}
              values={selectedSeries}
              label="Selected client requests per second"
            />
          </ChartPanel>
          <SelectedClientPanel selected={selected} />
        </div>

        <ModelPanel gatewayModels={snapshot?.models} selected={selected} />

        <Footer live={live} />
      </div>
    </main>
  );
}
