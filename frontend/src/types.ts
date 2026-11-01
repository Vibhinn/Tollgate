// Shapes of the snapshots sent by GET /api/v1/metrics (admin view).

export type ModelMetrics = {
  requests: number;
  errors?: number;
  input_tokens: number;
  output_tokens: number;
  avg_latency_ms?: number | null;
  available?: boolean;
};

export type EntityMetrics = {
  team?: string;
  name?: string;
  requests: number;
  "2xx": number;
  "4xx": number;
  "5xx": number;
  rate_limited: number;
  no_model_available: number;
  cache_exact_hits: number;
  cache_semantic_hits: number;
  cache_misses: number;
  input_tokens: number;
  output_tokens: number;
  models: Record<string, ModelMetrics>;
};

export type RequestCounters = {
  total: number;
  "2xx": number;
  "4xx": number;
  "5xx": number;
  rate_limited: number;
  no_model_available: number;
  rejected_by_backpressure: number;
  in_flight: number;
};

export type Snapshot = {
  generated_at?: string;
  uptime_seconds: number;
  process?: { cpu_percent: number; memory_mb: number } | null;
  requests?: RequestCounters | null;
  cache?: { exact_hits: number; semantic_hits: number; misses: number; hit_rate: number } | null;
  no_model_available?: boolean | null;
  models?: Record<string, ModelMetrics> | null;
  dependencies?: Record<string, string> | null;
  teams?: Record<string, EntityMetrics> | null;
  users?: Record<string, EntityMetrics> | null;
  tokens?: Record<string, EntityMetrics> | null;
};

export type EntityKind = "tokens" | "users" | "teams";

export type Connection = "idle" | "connecting" | "live" | "error";
