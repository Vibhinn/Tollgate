import json
import logging
import uuid

import fakeredis
import pytest

from src.jobs import log_shipper as log_shipper_module
from src.jobs.log_shipper import LogShipper


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def make_logger():
    """A fresh logger per test, so handlers never leak between tests."""
    created = []

    def _make(shipper: LogShipper) -> logging.Logger:
        name = f"src.test_{uuid.uuid4().hex[:8]}"
        shipper.install(name)
        created.append(name)
        return logging.getLogger(name)

    yield _make
    for name in created:
        logging.getLogger(name).handlers.clear()


def shipped(redis_client) -> list[dict]:
    return [json.loads(fields["payload"]) for _, fields in redis_client.xrange("logging")]


def test_a_warning_reaches_the_logging_stream(redis_client, make_logger):
    shipper = LogShipper(redis_client)
    logger = make_logger(shipper)

    logger.warning("rate limiter unavailable (%r)", ConnectionError("redis down"))
    shipper.stop()

    [entry] = shipped(redis_client)
    assert entry["level"] == "WARNING"
    assert entry["logger"] == logger.name
    assert entry["message"] == "rate limiter unavailable (ConnectionError('redis down'))"
    assert entry["timestamp"].endswith("+00:00")


def test_an_exception_is_shipped_with_its_traceback(redis_client, make_logger):
    shipper = LogShipper(redis_client)
    logger = make_logger(shipper)

    try:
        raise KeyError("missing")
    except KeyError:
        logger.exception("lookup failed")
    shipper.stop()

    [entry] = shipped(redis_client)
    assert entry["message"].startswith("lookup failed\nTraceback")
    assert "KeyError: 'missing'" in entry["message"]


def test_records_below_the_level_never_reach_the_queue(redis_client, make_logger):
    shipper = LogShipper(redis_client)
    logger = make_logger(shipper)

    logger.debug("not shipped")
    logger.info("shipped")
    shipper.stop()

    assert [entry["message"] for entry in shipped(redis_client)] == ["shipped"]


def test_a_full_queue_drops_and_counts_instead_of_blocking_the_caller(redis_client, monkeypatch):
    monkeypatch.setattr(log_shipper_module, "_QUEUE_SIZE", 2)
    shipper = LogShipper(redis_client)
    logger = logging.getLogger(f"src.test_{uuid.uuid4().hex[:8]}")
    logger.setLevel(logging.INFO)
    # the handler without the thread, so nothing drains the queue
    logger.addHandler(log_shipper_module._DeferredQueueHandler(shipper._queue, shipper._count_drop))
    try:
        for i in range(5):
            logger.warning("line %d", i)
    finally:
        logger.handlers.clear()

    assert shipper.dropped == 3


def test_when_redis_is_down_the_lines_go_to_stderr(make_logger, capsys):
    class DownRedis:
        def pipeline(self, transaction=False):
            raise ConnectionError("redis down")

    shipper = LogShipper(DownRedis())
    logger = make_logger(shipper)

    logger.error("redis is down")
    shipper.stop()

    err = capsys.readouterr().err
    assert "ERROR" in err and "redis is down" in err


def test_many_records_are_shipped_in_batches_of_at_most_100(redis_client, make_logger, monkeypatch):
    shipper = LogShipper(redis_client)
    batches = []
    original_ship = shipper._ship
    monkeypatch.setattr(shipper, "_ship", lambda records: (batches.append(len(records)), original_ship(records)))
    logger = logging.getLogger(f"src.test_{uuid.uuid4().hex[:8]}")
    logger.setLevel(logging.INFO)
    logger.addHandler(log_shipper_module._DeferredQueueHandler(shipper._queue, shipper._count_drop))
    try:
        for i in range(250):                   # queued before the thread starts, so it finds a backlog
            logger.warning("line %d", i)
        shipper._thread.start()
        shipper.stop()
    finally:
        logger.handlers.clear()

    assert len(shipped(redis_client)) == 250
    assert batches == [100, 100, 50]
