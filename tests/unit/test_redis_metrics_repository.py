"""Against fakeredis, so the real INCR / HINCRBY / MULTI / pipeline behaviour is exercised."""
import pytest
from fakeredis import FakeAsyncRedis

from src.cache.connection import CacheConnection
from src.cache.repository.redis_metrics_repository import RedisMetricsRepository
from src.utils.types import RedisAtomicCounters as Counter


def request_event(status=200, team="payments", name="alice", token_id="e72bb248c316", cache_outcome="miss",
                  model="gpt-4o", input_tokens=100, output_tokens=20, rejected_by=None):
    return {"kind": "request", "status": status, "rejected_by": rejected_by, "cache_outcome": cache_outcome,
            "model": model, "input_tokens": input_tokens, "output_tokens": output_tokens,
            "team": team, "name": name, "token_id": token_id, "timestamp": "2026-10-11T00:00:00+00:00"}


@pytest.fixture
def repo(monkeypatch):
    redis = FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: redis))
    return RedisMetricsRepository()


async def test_requests_add_up_in_the_gateway_counters(repo):
    await repo.record_request(request_event(status=200, cache_outcome="exact_hit", model=None))
    await repo.record_request(request_event(status=200, cache_outcome="miss"))
    await repo.record_request(request_event(status=429, rejected_by="rate_limit", cache_outcome=None, model=None))
    await repo.record_request(request_event(status=503, rejected_by="backpressure", team=None, name=None,
                                            token_id=None, cache_outcome=None, model=None))

    counters = await repo.read_counters()

    assert (counters[Counter.RESPONSES_2XX], counters[Counter.RESPONSES_4XX], counters[Counter.RESPONSES_5XX]) == (2, 1, 1)
    assert (counters[Counter.CACHE_EXACT_HITS], counters[Counter.CACHE_MISSES]) == (1, 1)
    assert (counters[Counter.RATE_LIMITED], counters[Counter.SHED]) == (1, 1)
    assert set(counters) == {counter.value for counter in Counter}


async def test_each_request_is_counted_for_its_team_user_and_token(repo):
    await repo.record_request(request_event(token_id="tok-alice-1", input_tokens=100, output_tokens=20))
    await repo.record_request(request_event(token_id="tok-alice-2", status=429, rejected_by="rate_limit",
                                            cache_outcome=None, model=None))
    await repo.record_request(request_event(name="invoice-bot", token_id="tok-bot", cache_outcome="semantic_hit",
                                            model=None))

    teams = await repo.read_entity_stats("team")
    users = await repo.read_entity_stats("user")
    tokens = await repo.read_entity_stats("token")

    assert teams["payments"]["requests"] == 3
    assert teams["payments"]["cache_semantic_hits"] == 1
    assert users["payments:alice"]["requests"] == 2
    assert users["payments:alice"]["rate_limited"] == 1
    assert users["payments:invoice-bot"]["requests"] == 1
    assert tokens["tok-alice-1"] == {
        "team": "payments", "name": "alice", "requests": 1, "2xx": 1, "4xx": 0, "5xx": 0, "rate_limited": 0,
        "cache_exact_hits": 0, "cache_semantic_hits": 0, "cache_misses": 1, "input_tokens": 100, "output_tokens": 20,
        "models": {"gpt-4o": {"requests": 1, "input_tokens": 100, "output_tokens": 20}},
    }


async def test_usage_is_broken_down_per_model(repo):
    await repo.record_request(request_event(model="gpt-4o", input_tokens=100, output_tokens=20))
    await repo.record_request(request_event(model="gpt-4o", input_tokens=50, output_tokens=10))
    await repo.record_request(request_event(model="claude-haiku-4-5", input_tokens=7, output_tokens=3))

    team = (await repo.read_entity_stats("team"))["payments"]

    assert team["models"] == {
        "gpt-4o": {"requests": 2, "input_tokens": 150, "output_tokens": 30},
        "claude-haiku-4-5": {"requests": 1, "input_tokens": 7, "output_tokens": 3},
    }
    assert (team["input_tokens"], team["output_tokens"]) == (157, 33)


async def test_a_request_rejected_before_auth_only_counts_gateway_wide(repo):
    await repo.record_request(request_event(status=401, team=None, name=None, token_id=None, cache_outcome=None,
                                            model=None))

    assert (await repo.read_counters())[Counter.RESPONSES_4XX] == 1
    assert await repo.read_entity_stats("team") == {}


async def test_model_stats_add_up_calls_tokens_and_errors(repo):
    await repo.record_model_call("gpt-4o", input_tokens=100, output_tokens=20)
    await repo.record_model_call("gpt-4o", input_tokens=50, output_tokens=10)
    await repo.record_model_error("gpt-4o")

    stats = await repo.read_model_stats(["gpt-4o", "never-used"])

    assert stats["gpt-4o"] == {"requests": 2, "errors": 1, "input_tokens": 150, "output_tokens": 30}
    assert stats["never-used"] == {"requests": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0}


async def test_reading_stats_for_no_models_returns_nothing(repo):
    assert await repo.read_model_stats([]) == {}


async def test_ping_reports_whether_redis_answers(repo, monkeypatch):
    assert await repo.ping() is True

    async def down():
        raise ConnectionError("redis down")
    monkeypatch.setattr(repo.cache_conn, "ping", down)

    assert await repo.ping() is False
