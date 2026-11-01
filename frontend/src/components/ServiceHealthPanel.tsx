import { Cpu, Database, Gauge, Network } from "lucide-react";
import { pretty } from "../format";
import type { Snapshot } from "../types";
import { ChartPanel } from "./ui";

const DEPENDENCIES = [
  { key: "redis", title: "Redis", icon: Database },
  { key: "qdrant", title: "Qdrant", icon: Network },
  { key: "classifier", title: "Classifier", icon: Cpu },
] as const;

const healthClass = (state: string | undefined) => (state === "ok" ? "ok" : state ? "degraded" : "unknown");

export function ServiceHealthPanel({ snapshot }: { snapshot: Snapshot | null }) {
  const process = snapshot?.process;
  return (
    <ChartPanel title="Service health" subtitle="Gateway process and dependencies">
      <div className="process-health">
        <div className="process-health-item"><Cpu size={14} /><span>CPU</span><b>{process ? `${process.cpu_percent.toFixed(1)}%` : "—"}</b></div>
        <div className="process-health-item"><Gauge size={14} /><span>MEMORY</span><b>{process ? `${pretty(process.memory_mb)} MB` : "—"}</b></div>
      </div>
      <div className="dependency-list compact-dependencies">
        {DEPENDENCIES.map(({ key, title, icon: Icon }) => {
          const state = snapshot?.dependencies?.[key];
          return (
            <div className="dependency-row" key={key}>
              <span className="dependency-icon"><Icon size={14} /></span>
              <span className="dependency-name">{title}</span>
              <span className={`health ${healthClass(state)}`}><i />{state?.toUpperCase() ?? "WAITING"}</span>
            </div>
          );
        })}
      </div>
    </ChartPanel>
  );
}
