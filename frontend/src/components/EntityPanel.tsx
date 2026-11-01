import { Search } from "lucide-react";
import { percent, pretty } from "../format";
import { cacheHitRate, failures } from "../metrics/derive";
import type { EntityKind, EntityMetrics } from "../types";
import { ENTITY_KINDS, entityLabel } from "./entityKinds";
import { EmptyState, SectionKicker } from "./ui";

type Rows = [string, EntityMetrics][];

type Props = {
  kind: EntityKind;
  onKindChange: (kind: EntityKind) => void;
  rowsByKind: Record<EntityKind, Rows>;
  hasData: boolean;
  query: string;
  onQueryChange: (query: string) => void;
  selectedId: string;
  onSelect: (id: string) => void;
  totalRequests: number;
};

export function EntityPanel({ kind, onKindChange, rowsByKind, hasData, query, onQueryChange, selectedId, onSelect, totalRequests }: Props) {
  const rows = rowsByKind[kind];
  const needle = query.toLowerCase();
  const filtered = rows.filter(([id, stats]) => `${id} ${stats.team ?? ""} ${stats.name ?? ""}`.toLowerCase().includes(needle));

  return (
    <section className="panel entity-panel">
      <header className="panel-heading entity-heading">
        <div>
          <SectionKicker>USAGE BREAKDOWN</SectionKicker>
          <h2>Every client. One place.</h2>
          <p>Explore gateway usage by access token, user, or team.</p>
        </div>
        <span className="chart-tag">ADMIN ONLY</span>
      </header>

      <div className="entity-toolbar">
        <div className="entity-tabs" role="tablist" aria-label="Usage breakdown">
          {(Object.keys(ENTITY_KINDS) as EntityKind[]).map((k) => {
            const { tab, icon: Icon } = ENTITY_KINDS[k];
            return (
              <button key={k} className={k === kind ? "active" : ""} onClick={() => onKindChange(k)}>
                <Icon size={13} />{tab}<span>{rowsByKind[k].length}</span>
              </button>
            );
          })}
        </div>
        <label className="entity-search">
          <Search size={14} />
          <input placeholder={`Search ${kind}…`} value={query} onChange={(e) => onQueryChange(e.target.value)} />
          <span>{filtered.length} RESULTS</span>
        </label>
      </div>

      <div className="entity-table-wrap">
        <EntityTable kind={kind} rows={filtered} selectedId={selectedId} onSelect={onSelect} totalRequests={totalRequests} />
        {!filtered.length && <EmptyState>{hasData ? `No ${kind} match this search.` : `Waiting for ${kind} usage data…`}</EmptyState>}
      </div>

      <NoModelBreakdown kind={kind} rows={rows} />
    </section>
  );
}

type TableProps = { kind: EntityKind; rows: Rows; selectedId: string; onSelect: (id: string) => void; totalRequests: number };

function EntityTable({ kind, rows, selectedId, onSelect, totalRequests }: TableProps) {
  const isTokens = kind === "tokens";
  return (
    <table className="entity-table">
      <thead>
        <tr>
          <th>{ENTITY_KINDS[kind].idHeader}</th>
          {isTokens && <><th>TEAM</th><th>NAME</th></>}
          <th>REQUESTS</th><th>2XX</th><th>4XX + 5XX</th><th>INPUT TOKENS</th><th>OUTPUT TOKENS</th><th>CACHE HIT RATE</th><th>REQUEST SHARE</th>
        </tr>
      </thead>
      <tbody>
        {rows.map(([id, stats]) => {
          const share = totalRequests ? stats.requests / totalRequests : 0;
          return (
            <tr
              key={id}
              className={id === selectedId ? "selected" : ""}
              tabIndex={0}
              onClick={() => onSelect(id)}
              onKeyDown={(e) => e.key === "Enter" && onSelect(id)}
            >
              <td><span className="entity-id"><i className="model-dot" />{id}</span></td>
              {isTokens && <><td>{stats.team ?? "—"}</td><td>{stats.name ?? "—"}</td></>}
              <td>{pretty(stats.requests)}</td>
              <td>{pretty(stats["2xx"])}</td>
              <td>{pretty(failures(stats))}</td>
              <td>{pretty(stats.input_tokens)}</td>
              <td>{pretty(stats.output_tokens)}</td>
              <td><span className="entity-rate">{percent(cacheHitRate(stats))}</span></td>
              <td>
                <div className="share-cell">
                  <div className="share-track"><i style={{ width: `${share * 100}%` }} /></div>
                  <span>{percent(share)}</span>
                </div>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function NoModelBreakdown({ kind, rows }: { kind: EntityKind; rows: Rows }) {
  return (
    <div className="no-model-breakdown">
      <header>
        <strong>No model available responses by {ENTITY_KINDS[kind].noun}</strong>
        <span>POLICY 503 · BACKPRESSURE SHED EXCLUDED</span>
      </header>
      <div className="no-model-entities">
        {rows.length ? (
          rows.map(([id, stats]) => (
            <div className={stats.no_model_available ? "has-no-model" : ""} key={id}>
              <span>{entityLabel(kind, id, stats)}</span>
              <b>{pretty(stats.no_model_available)}</b>
              <small>rate limited {pretty(stats.rate_limited)}</small>
            </div>
          ))
        ) : (
          <span className="no-model-empty">Entity counters appear as requests are recorded.</span>
        )}
      </div>
    </div>
  );
}
