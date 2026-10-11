"""The token bucket's Lua script, run by fakeredis's Lua engine (real Redis semantics, faked clock)."""
import pytest
from fakeredis import FakeAsyncRedis

from src.cache.connection import CacheConnection
from src.cache.repository.redis_rate_limiter import RedisRateLimiter
from tests.conftest import FakeConfig


class Clock:
    """Stands in for Redis TIME so refills can be tested without sleeping."""
    def __init__(self, now=1_000_000.0):
        self.now = now


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def make_limiter(monkeypatch, clock):
    def _make(max_tokens=3, refill_rate=1, time_interval=1.0):
        redis = FakeAsyncRedis(decode_responses=True)
        monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: redis))
        limiter = RedisRateLimiter(FakeConfig({"rate_limiter": {
            "max_tokens": str(max_tokens), "refill_rate": str(refill_rate), "time_interval": str(time_interval),
        }}))
        # fakeredis follows the wall clock; pin TIME to our clock so the test controls refills
        script = limiter._take_token
        original = script.script

        def with_fixed_clock():
            seconds = int(clock.now)
            micros = int(round((clock.now - seconds) * 1_000_000))
            return original.replace("redis.call('TIME')", f"{{'{seconds}', '{micros}'}}")
        limiter._take_token = redis.register_script(with_fixed_clock())

        async def take(user_id="payments:alice"):
            limiter._take_token = redis.register_script(with_fixed_clock())
            return await limiter.acquire(user_id)
        return limiter, redis, take
    return _make


async def test_a_new_bucket_starts_full_and_runs_out(make_limiter):
    _, _, take = make_limiter(max_tokens=3)

    decisions = [await take() for _ in range(4)]

    assert [d.allowed for d in decisions] == [True, True, True, False]
    assert [d.remaining for d in decisions] == [2, 1, 0, 0]
    assert all(d.limit == 3 for d in decisions)


async def test_tokens_come_back_one_refill_per_interval(make_limiter, clock):
    _, _, take = make_limiter(max_tokens=3, refill_rate=1, time_interval=1.0)
    for _ in range(3):
        await take()

    clock.now += 0.5
    assert (await take()).allowed is False        # not a full interval yet

    clock.now += 0.6
    assert (await take()).allowed is True         # one refill after a full interval
    assert (await take()).allowed is False


async def test_refills_never_exceed_the_bucket_size(make_limiter, clock):
    _, _, take = make_limiter(max_tokens=3, refill_rate=2, time_interval=1.0)
    await take()

    clock.now += 60

    assert (await take()).remaining == 2          # back to 3, minus this request


async def test_reset_at_is_the_next_refill(make_limiter, clock):
    _, _, take = make_limiter(time_interval=1.0)

    decision = await take()

    assert decision.reset_at == pytest.approx(clock.now + 1.0)


async def test_each_user_has_their_own_bucket(make_limiter):
    _, _, take = make_limiter(max_tokens=1)

    assert (await take("payments:alice")).allowed is True
    assert (await take("payments:alice")).allowed is False
    assert (await take("search:bob")).allowed is True


async def test_an_idle_bucket_expires_once_it_would_be_full_again(make_limiter):
    _, redis, take = make_limiter(max_tokens=500, refill_rate=100, time_interval=1.0)

    await take()

    assert 0 < await redis.ttl("ratelimit:payments:alice") <= 5   # 500 / 100 per second = 5s


async def test_two_workers_share_one_bucket(monkeypatch):
    """The point of moving it to Redis: limiters in two processes draw from the same tokens.
    Both use Redis's real clock here, as they would in production."""
    redis = FakeAsyncRedis(decode_responses=True)
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: redis))
    config = FakeConfig({"rate_limiter": {"max_tokens": "2", "refill_rate": "1", "time_interval": "60"}})
    first_worker, second_worker = RedisRateLimiter(config), RedisRateLimiter(config)

    assert (await first_worker.acquire("payments:alice")).allowed is True
    assert (await second_worker.acquire("payments:alice")).allowed is True
    assert (await first_worker.acquire("payments:alice")).allowed is False
