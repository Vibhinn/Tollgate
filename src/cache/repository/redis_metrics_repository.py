from __future__ import annotations

from typing import Any, override, TYPE_CHECKING

from src.app.ports import MetricsRepositoryInterface
from src.utils.types import CacheType, RedisAtomicCounters as Counter

from ..connection import CacheConnection

if TYPE_CHECKING:
    from src.app.ports.metrics import ENTITY_KIND
    from src.utils.types import RequestEventData

_MODEL_STATS_KEY_PREFIX = "model:stats:"
_MODEL_STAT_FIELDS = ("requests", "errors", "input_tokens", "output_tokens")

# metrics:<kind>:<id> hashes, plus metrics:<kind>s sets to list them
_ENTITY_KEY_PREFIX = "metrics:"
ENTITY_FIELDS = ("requests", "2xx", "4xx", "5xx", "rate_limited", "cache_exact_hits", "cache_semantic_hits",
                 "cache_misses", "input_tokens", "output_tokens")
_MODEL_FIELD_PREFIX = "model:"          # per-model usage inside an entity hash: model:<name>:<stat>
_TOKEN_DETAIL_FIELDS = ("team", "name")

_STATUS_COUNTERS = {2: Counter.RESPONSES_2XX, 4: Counter.RESPONSES_4XX, 5: Counter.RESPONSES_5XX}
_CACHE_COUNTERS = {"exact_hit": Counter.CACHE_EXACT_HITS, "semantic_hit": Counter.CACHE_SEMANTIC_HITS,
                   "miss": Counter.CACHE_MISSES}
_CACHE_FIELDS = {"exact_hit": "cache_exact_hits", "semantic_hit": "cache_semantic_hits", "miss": "cache_misses"}
_REJECTION_COUNTERS = {"rate_limit": Counter.RATE_LIMITED, "backpressure": Counter.SHED}


def _entity_key(kind: str, entity_id: str) -> str:
    return f"{_ENTITY_KEY_PREFIX}{kind}:{entity_id}"


def _index_key(kind: str) -> str:
    return f"{_ENTITY_KEY_PREFIX}{kind}s"


class RedisMetricsRepository(MetricsRepositoryInterface):
    def __init__(self):
        self.cache_conn = CacheConnection.get_connection(CacheType.EXACT)

    @override
    async def record_request(self, event: RequestEventData) -> None:
        # one transaction: a job that is retried after a failure is never half-counted
        pipe = self.cache_conn.pipeline(transaction=True)
        status_class = event["status"] // 100

        if counter := _STATUS_COUNTERS.get(status_class):
            pipe.incr(counter)
        if counter := _CACHE_COUNTERS.get(event["cache_outcome"]):
            pipe.incr(counter)
        if counter := _REJECTION_COUNTERS.get(event["rejected_by"]):
            pipe.incr(counter)

        if event["team"] is not None:
            entities = (("team", event["team"]),
                        ("user", f'{event["team"]}:{event["name"]}'),
                        ("token", event["token_id"]))
            for kind, entity_id in entities:
                self._add_to_entity(pipe, kind, entity_id, event, status_class)
            pipe.hset(_entity_key("token", event["token_id"]), mapping={"team": event["team"], "name": event["name"]})

        await pipe.execute()

    @staticmethod
    def _add_to_entity(pipe, kind: str, entity_id: str, event: RequestEventData, status_class: int) -> None:
        key = _entity_key(kind, entity_id)
        pipe.sadd(_index_key(kind), entity_id)
        pipe.hincrby(key, "requests", 1)
        if status_class in (2, 4, 5):
            pipe.hincrby(key, f"{status_class}xx", 1)
        if event["rejected_by"] == "rate_limit":
            pipe.hincrby(key, "rate_limited", 1)
        if field := _CACHE_FIELDS.get(event["cache_outcome"]):
            pipe.hincrby(key, field, 1)
        if event["model"]:
            pipe.hincrby(key, "input_tokens", event["input_tokens"])
            pipe.hincrby(key, "output_tokens", event["output_tokens"])
            model_field = f'{_MODEL_FIELD_PREFIX}{event["model"]}:'
            pipe.hincrby(key, f"{model_field}requests", 1)
            pipe.hincrby(key, f"{model_field}input_tokens", event["input_tokens"])
            pipe.hincrby(key, f"{model_field}output_tokens", event["output_tokens"])

    @override
    async def record_model_call(self, model_name: str, input_tokens: int, output_tokens: int) -> None:
        key = f"{_MODEL_STATS_KEY_PREFIX}{model_name}"
        pipe = self.cache_conn.pipeline(transaction=True)
        pipe.hincrby(key, "requests", 1)
        pipe.hincrby(key, "input_tokens", input_tokens)
        pipe.hincrby(key, "output_tokens", output_tokens)
        await pipe.execute()

    @override
    async def record_model_error(self, model_name: str) -> None:
        await self.cache_conn.hincrby(f"{_MODEL_STATS_KEY_PREFIX}{model_name}", "errors", 1)

    @override
    async def read_counters(self) -> dict[str, int]:
        names = [counter.value for counter in Counter]
        values = await self.cache_conn.mget(names)
        return {name: int(value or 0) for name, value in zip(names, values)}

    @override
    async def read_model_stats(self, model_names: list[str]) -> dict[str, dict[str, int]]:
        if not model_names:
            return {}
        pipe = self.cache_conn.pipeline(transaction=False)
        for model_name in model_names:
            pipe.hgetall(f"{_MODEL_STATS_KEY_PREFIX}{model_name}")
        rows = await pipe.execute()
        return {
            model_name: {field: int(row.get(field, 0)) for field in _MODEL_STAT_FIELDS}
            for model_name, row in zip(model_names, rows)
        }

    @override
    async def read_entity_stats(self, kind: ENTITY_KIND) -> dict[str, dict[str, Any]]:
        entity_ids = sorted(await self.cache_conn.smembers(_index_key(kind)))
        if not entity_ids:
            return {}
        pipe = self.cache_conn.pipeline(transaction=False)
        for entity_id in entity_ids:
            pipe.hgetall(_entity_key(kind, entity_id))
        rows = await pipe.execute()
        return {entity_id: self._parse_entity(row) for entity_id, row in zip(entity_ids, rows)}

    @staticmethod
    def _parse_entity(row: dict[str, str]) -> dict[str, Any]:
        stats: dict[str, Any] = {field: row[field] for field in _TOKEN_DETAIL_FIELDS if field in row}
        stats.update({field: int(row.get(field, 0)) for field in ENTITY_FIELDS})
        models: dict[str, dict[str, int]] = {}
        for field, value in row.items():
            if field.startswith(_MODEL_FIELD_PREFIX):
                model_name, stat = field.removeprefix(_MODEL_FIELD_PREFIX).rsplit(":", 1)
                models.setdefault(model_name, {})[stat] = int(value)
        stats["models"] = models
        return stats

    @override
    async def ping(self) -> bool:
        try:
            return bool(await self.cache_conn.ping())
        except Exception:
            return False
