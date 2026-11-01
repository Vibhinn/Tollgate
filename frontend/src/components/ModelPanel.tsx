import { pretty } from "../format";
import { byRequestsDesc } from "../metrics/derive";
import type { EntityMetrics, ModelMetrics } from "../types";
import { EmptyState } from "./ui";

type Props = { gatewayModels: Record<string, ModelMetrics> | null | undefined; selected: EntityMetrics | undefined };

/** Gateway-wide model table, or the selected client's per-model usage when a client is selected. */
export function ModelPanel({ gatewayModels, selected }: Props) {
  const rows = selected ? byRequestsDesc(selected.models) : Object.entries(gatewayModels ?? {});
  const gateway = !selected;

  return (
    <section className="panel model-panel">
      <header className="panel-heading model-heading">
        <div>
          <h2>{gateway ? "Gateway model performance" : "Model usage for selected client"}</h2>
          <p>{gateway ? "Lifetime gateway model counters and current availability" : "Per-token request and token counts by model"}</p>
        </div>
        <span className="model-count">{rows.length.toString().padStart(2, "0")} MODELS</span>
      </header>
      <div className="model-table-wrap">
        <table className="model-table">
          <thead>
            <tr>
              <th>MODEL</th>
              {gateway && <th>STATUS</th>}
              <th>REQUESTS</th><th>INPUT TOKENS</th><th>OUTPUT TOKENS</th>
              {gateway && <th>AVG LATENCY</th>}
            </tr>
          </thead>
          <tbody>
            {rows.map(([name, model]) => (
              <tr key={name}>
                <td><span className="model-name"><i className={gateway && !model.available ? "model-dot offline" : "model-dot"} />{name}</span></td>
                {gateway && (
                  <td>
                    <span className={`model-status ${model.available ? "available" : "unavailable"}`}>{model.available ? "AVAILABLE" : "BENCHED"}</span>
                  </td>
                )}
                <td>{pretty(model.requests)}</td>
                <td>{pretty(model.input_tokens)}</td>
                <td>{pretty(model.output_tokens)}</td>
                {gateway && <td>{model.avg_latency_ms == null ? "—" : `${pretty(model.avg_latency_ms)} ms`}</td>}
              </tr>
            ))}
          </tbody>
        </table>
        {gateway && !gatewayModels && <EmptyState>Waiting for model telemetry.</EmptyState>}
        {!gateway && !rows.length && <EmptyState>No model usage recorded for this client yet.</EmptyState>}
      </div>
    </section>
  );
}
