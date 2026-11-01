import { pretty } from "../format";
import { cacheHits } from "../metrics/derive";
import type { EntityMetrics } from "../types";
import { ChartPanel } from "./ui";

export function SelectedClientPanel({ selected }: { selected: EntityMetrics | undefined }) {
  const show = (value: (s: EntityMetrics) => string) => (selected ? value(selected) : "—");
  const subtitle = selected
    ? `${selected.team ?? "Gateway client"}${selected.name ? ` · ${selected.name}` : ""}`
    : "Per-client counters and model selection";

  return (
    <ChartPanel title="Selected client" subtitle={subtitle}>
      <div className="selected-summary">
        <div><span>LIFETIME REQUESTS</span><b>{show((s) => pretty(s.requests))}</b></div>
        <div><span>RATE LIMITED</span><b>{show((s) => pretty(s.rate_limited))}</b></div>
        <div className={selected?.no_model_available ? "selected-warning" : ""}>
          <span>NO MODEL AVAILABLE</span><b>{show((s) => pretty(s.no_model_available))}</b>
        </div>
        <div><span>INPUT / OUTPUT</span><b>{show((s) => `${pretty(s.input_tokens)} / ${pretty(s.output_tokens)}`)}</b></div>
        <div><span>CACHE HITS</span><b>{show((s) => pretty(cacheHits(s)))}</b></div>
      </div>
    </ChartPanel>
  );
}
