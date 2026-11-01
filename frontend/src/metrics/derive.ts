import type { EntityMetrics } from "../types";

export const byRequestsDesc = <T extends { requests: number }>(record: Record<string, T> | null | undefined) =>
  Object.entries(record ?? {}).sort((a, b) => b[1].requests - a[1].requests);

export const cacheHits = (stats: EntityMetrics) => stats.cache_exact_hits + stats.cache_semantic_hits;

export const cacheHitRate = (stats: EntityMetrics) => {
  const lookups = cacheHits(stats) + stats.cache_misses;
  return lookups ? cacheHits(stats) / lookups : 0;
};

export const failures = (stats: EntityMetrics) => stats["4xx"] + stats["5xx"];
