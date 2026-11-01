import { Activity, KeyRound, Network, type LucideIcon } from "lucide-react";
import type { EntityKind, EntityMetrics } from "../types";

type KindInfo = { tab: string; noun: string; title: string; idHeader: string; icon: LucideIcon };

export const ENTITY_KINDS: Record<EntityKind, KindInfo> = {
  tokens: { tab: "TOKENS", noun: "token", title: "Token", idHeader: "TOKEN ID", icon: KeyRound },
  users: { tab: "USERS", noun: "user", title: "User", idHeader: "TEAM : USER", icon: Activity },
  teams: { tab: "TEAMS", noun: "team", title: "Team", idHeader: "TEAM", icon: Network },
};

/** "team / name" for tokens (their id is opaque); the id itself for users and teams. */
export const entityLabel = (kind: EntityKind, id: string, stats: EntityMetrics) =>
  kind === "tokens" ? `${stats.team ?? ""}${stats.team ? " / " : ""}${stats.name ?? id}` : id;
