import asyncio
from unittest.mock import AsyncMock

import pytest

from src.cache.connection import CacheConnection
from src.jobs.repository.redis_stream_repository import (
    RedisStreamRepository,
    GROUP_NAME,
    MAX_DELIVERIES,
)


@pytest.fixture
def redis_conn(monkeypatch):
    conn = AsyncMock()
    monkeypatch.setattr(CacheConnection, "get_connection", classmethod(lambda cls, t: conn))
    return conn


@pytest.fixture
def repo(redis_conn):
    return RedisStreamRepository()


@pytest.fixture
def helper():
    h = AsyncMock()
    h.execute = AsyncMock()
    return h


async def test_create_groups_creates_one_group_per_registered_stream(repo, redis_conn, helper):
    repo.register_helper("response_cache", helper)
    repo.register_helper("analytics", helper)

    await repo._create_groups()

    assert redis_conn.xgroup_create.await_count == 2
    redis_conn.xgroup_create.assert_any_await(name="response_cache", groupname=GROUP_NAME, id="0", mkstream=True)
    redis_conn.xgroup_create.assert_any_await(name="analytics", groupname=GROUP_NAME, id="0", mkstream=True)


async def test_create_groups_tolerates_busygroup(repo, redis_conn, helper):
    repo.register_helper("response_cache", helper)
    redis_conn.xgroup_create.side_effect = Exception("BUSYGROUP Consumer Group name already exists")

    await repo._create_groups()  # should not raise


async def test_create_groups_reraises_other_errors(repo, redis_conn, helper):
    repo.register_helper("response_cache", helper)
    redis_conn.xgroup_create.side_effect = Exception("WRONGTYPE some other redis error")

    with pytest.raises(Exception, match="WRONGTYPE"):
        await repo._create_groups()


async def test_process_acks_on_success(repo, redis_conn, helper):
    repo.register_helper("response_cache", helper)

    await repo._process("response_cache", "1-0", {"payload": "{}"})

    helper.execute.assert_awaited_once_with({"payload": "{}"})
    redis_conn.xack.assert_awaited_once_with("response_cache", GROUP_NAME, "1-0")


async def test_process_does_not_ack_on_helper_failure(repo, redis_conn, helper):
    repo.register_helper("response_cache", helper)
    helper.execute.side_effect = ValueError("boom")
    redis_conn.xpending_range.return_value = [{"times_delivered": 1}]

    await repo._process("response_cache", "1-0", {"payload": "{}"})

    redis_conn.xack.assert_not_awaited()


async def test_process_handles_missing_helper_as_failure(repo, redis_conn):
    redis_conn.xpending_range.return_value = [{"times_delivered": 1}]

    await repo._process("unregistered_stream", "1-0", {"payload": "{}"})

    redis_conn.xack.assert_not_awaited()
    redis_conn.xadd.assert_not_awaited()


async def test_handle_failure_dead_letters_after_max_deliveries(repo, redis_conn):
    redis_conn.xpending_range.return_value = [{"times_delivered": MAX_DELIVERIES}]

    await repo._handle_failure("response_cache", "1-0", {"payload": "{}"})

    redis_conn.xadd.assert_awaited_once_with(
        "response_cache:dead", {"payload": "{}"}, maxlen=1000, approximate=True
    )
    redis_conn.xack.assert_awaited_once_with("response_cache", GROUP_NAME, "1-0")


async def test_handle_failure_leaves_entry_pending_below_max_deliveries(repo, redis_conn):
    redis_conn.xpending_range.return_value = [{"times_delivered": MAX_DELIVERIES - 1}]

    await repo._handle_failure("response_cache", "1-0", {"payload": "{}"})

    redis_conn.xadd.assert_not_awaited()
    redis_conn.xack.assert_not_awaited()


async def test_read_new_entries_processes_actual_xreadgroup_result(repo, redis_conn, helper):
    repo.register_helper("response_cache", helper)
    redis_conn.xreadgroup.return_value = [
        ("response_cache", [("1-0", {"payload": "a"}), ("2-0", {"payload": "b"})]),
    ]

    await repo._read_new_entries()

    assert helper.execute.await_count == 2
    helper.execute.assert_any_await({"payload": "a"})
    helper.execute.assert_any_await({"payload": "b"})
    assert redis_conn.xack.await_count == 2


async def test_reclaim_stale_entries_awaits_xautoclaim_and_processes_claimed(repo, redis_conn, helper):
    repo.register_helper("response_cache", helper)
    redis_conn.xautoclaim.return_value = ("0-0", [("1-0", {"payload": "a"})], [])

    await repo._reclaim_stale_entries()

    redis_conn.xautoclaim.assert_awaited_once()
    helper.execute.assert_awaited_once_with({"payload": "a"})
    redis_conn.xack.assert_awaited_once_with("response_cache", GROUP_NAME, "1-0")


async def test_on_task_done_restarts_after_exception(repo, monkeypatch):
    restarted = AsyncMock()
    monkeypatch.setattr(repo, "start", restarted)

    async def _boom():
        raise RuntimeError("consumer crashed")

    task = asyncio.create_task(_boom())
    with pytest.raises(RuntimeError):
        await task

    repo._on_task_done(task)

    restarted.assert_called_once()


async def test_on_task_done_does_nothing_when_cancelled(repo, monkeypatch):
    restarted = AsyncMock()
    monkeypatch.setattr(repo, "start", restarted)

    async def _wait_forever():
        await asyncio.sleep(10)

    task = asyncio.create_task(_wait_forever())
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    repo._on_task_done(task)

    restarted.assert_not_called()


async def test_create_job_writes_to_stream_with_approximate_trim(repo, redis_conn):
    await repo.create_job("response_cache", {"cache_type": "exact"})

    await_args = redis_conn.xadd.await_args
    assert await_args.args[0] == "response_cache"
    assert await_args.kwargs["maxlen"] == 1000
    assert await_args.kwargs["approximate"] is True
