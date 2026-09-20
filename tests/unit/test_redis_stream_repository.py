"""Behavioral tests for RedisStreamRepository.

These drive the class only through its public surface (register_helper,
create_job, start) against fakeredis - a real Redis Streams implementation,
not a mock - so they exercise the actual delivery/retry/crash-recovery
guarantees instead of asserting which internal methods got called with
which arguments. In particular, test_message_written_while_previous_entry_is_processing_is_not_lost
reproduces the exact concurrency scenario that silently dropped messages
under the old XREAD + "$" implementation; a mock-based test cannot catch
a regression back to that bug, this one can.
"""
import asyncio
import contextlib
import json

import pytest
from fakeredis import FakeAsyncRedis

from src.cache.connection import CacheConnection
from src.jobs.repository import redis_stream_repository as stream_module
from src.jobs.repository.redis_stream_repository import RedisStreamRepository


async def wait_until(condition, timeout=5.0, interval=0.01):
    loop = asyncio.get_event_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if condition():
            return
        await asyncio.sleep(interval)
    raise AssertionError(f"condition not met within {timeout}s")


def _yielding(fn):
    """fakeredis resolves its async methods without ever truly suspending,
    so a tight `while True: await ...` loop with no new data never hands
    control back to the event loop - it livelocks the whole process instead
    of cooperatively waiting, unlike a real network-backed Redis client.
    This forces a genuine scheduler checkpoint on every stream call so the
    background consumer task behaves the way it would against real Redis."""
    async def wrapper(*args, **kwargs):
        await asyncio.sleep(0)
        return await fn(*args, **kwargs)
    return wrapper


@pytest.fixture
def fake_redis():
    redis = FakeAsyncRedis(decode_responses=True)
    for method_name in ("xreadgroup", "xautoclaim", "xgroup_create", "xack", "xadd", "xpending_range"):
        setattr(redis, method_name, _yielding(getattr(redis, method_name)))
    return redis


@pytest.fixture
async def spawned(monkeypatch, fake_redis):
    """Every RedisStreamRepository() created via the returned factory shares
    one fake Redis instance, so tests can simulate a process restart by
    spawning a second repository against the same backing store. Any
    consumer task left running at teardown is cancelled and awaited."""
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: fake_redis))
    repos = []

    def make_repo():
        repo = RedisStreamRepository()
        repos.append(repo)
        return repo

    yield make_repo

    for repo in repos:
        task = repo._task
        if task and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


async def test_job_written_before_start_is_delivered_to_registered_helper(spawned):
    repo = spawned()
    delivered = []

    class Helper:
        async def execute(self, data):
            delivered.append(json.loads(data["payload"]))

    repo.register_helper("response_cache", Helper())
    await repo.create_job("response_cache", {"cache_type": "exact", "user_message": "hi"})

    repo.start()

    await wait_until(lambda: delivered == [{"cache_type": "exact", "user_message": "hi"}])


async def test_message_written_while_previous_entry_is_processing_is_not_lost(spawned):
    """Regression test for the original message-loss bug: a second job
    written while the first is still mid-processing must still be delivered."""
    repo = spawned()
    delivered = []
    started_processing_a = asyncio.Event()
    release_a = asyncio.Event()

    class Helper:
        async def execute(self, data):
            payload = json.loads(data["payload"])
            if payload["id"] == "A":
                started_processing_a.set()
                await release_a.wait()
            delivered.append(payload["id"])

    repo.register_helper("response_cache", Helper())
    await repo.create_job("response_cache", {"id": "A"})

    repo.start()
    await asyncio.wait_for(started_processing_a.wait(), timeout=2.0)

    # A second request arrives and writes its job while A is still being processed.
    await repo.create_job("response_cache", {"id": "B"})

    release_a.set()

    await wait_until(lambda: set(delivered) == {"A", "B"})


async def test_helper_that_fails_then_succeeds_eventually_completes(spawned, monkeypatch):
    monkeypatch.setattr(stream_module, "CLAIM_IDLE_MS", 10)
    repo = spawned()
    attempts = []

    class Helper:
        async def execute(self, data):
            attempts.append(1)
            if len(attempts) < 3:
                raise RuntimeError("transient failure")

    repo.register_helper("response_cache", Helper())
    await repo.create_job("response_cache", {"id": "A"})

    repo.start()

    await wait_until(lambda: len(attempts) >= 3, timeout=10.0)
    await asyncio.sleep(0.3)  # let any further (unwanted) redelivery attempt land
    assert len(attempts) == 3


async def test_helper_that_always_fails_ends_up_dead_lettered_after_max_retries(spawned, monkeypatch, fake_redis):
    monkeypatch.setattr(stream_module, "CLAIM_IDLE_MS", 10)
    repo = spawned()
    attempts = []

    class Helper:
        async def execute(self, data):
            attempts.append(1)
            raise RuntimeError("permanent failure")

    repo.register_helper("response_cache", Helper())
    await repo.create_job("response_cache", {"id": "A"})

    repo.start()

    await wait_until(lambda: len(attempts) >= stream_module.MAX_DELIVERIES, timeout=15.0)
    await asyncio.sleep(0.3)
    assert len(attempts) == stream_module.MAX_DELIVERIES  # gave up, stopped retrying

    dead_entries = await fake_redis.xrange("response_cache:dead")
    assert len(dead_entries) == 1
    _, dead_payload = dead_entries[0]
    assert json.loads(dead_payload["payload"]) == {"id": "A"}


async def test_consumer_crash_before_ack_does_not_lose_the_job(spawned, monkeypatch):
    monkeypatch.setattr(stream_module, "CLAIM_IDLE_MS", 10)
    repo1 = spawned()
    started = asyncio.Event()

    class HangingHelper:
        async def execute(self, data):
            started.set()
            await asyncio.sleep(30)  # never returns - simulates a worker that dies mid-task

    repo1.register_helper("response_cache", HangingHelper())
    await repo1.create_job("response_cache", {"id": "A"})

    repo1.start()
    await asyncio.wait_for(started.wait(), timeout=2.0)

    # Simulate the process dying before the entry is acked, by killing the
    # task directly - there's no public "crash" API, this is fault injection
    # from outside, not a call into RedisStreamRepository's internals.
    repo1._task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await repo1._task

    # A fresh consumer wired to the same Redis should still recover the job.
    repo2 = spawned()
    delivered = []

    class WorkingHelper:
        async def execute(self, data):
            delivered.append(json.loads(data["payload"]))

    repo2.register_helper("response_cache", WorkingHelper())
    repo2.start()

    await wait_until(lambda: delivered == [{"id": "A"}])


async def test_consumer_recovers_automatically_from_an_unexpected_error(spawned, fake_redis):
    repo = spawned()
    delivered = []

    class Helper:
        async def execute(self, data):
            delivered.append(json.loads(data["payload"]))

    repo.register_helper("response_cache", Helper())
    await repo.create_job("response_cache", {"id": "A"})

    real_xreadgroup = fake_redis.xreadgroup
    call_count = {"n": 0}

    async def flaky_xreadgroup(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise ConnectionError("simulated redis blip")
        return await real_xreadgroup(*args, **kwargs)

    fake_redis.xreadgroup = flaky_xreadgroup

    repo.start()

    await wait_until(lambda: delivered == [{"id": "A"}])
