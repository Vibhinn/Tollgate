"""Ships log records to the `logging` Redis stream without slowing down requests.

Code logs the normal way, `logging.getLogger(__name__).warning("... %r", value)`, and that call
only puts the record on an in-memory queue (about 2.6 µs). Everything slow happens on one
background thread: formatting the message and traceback, JSON encoding, and writing to Redis in
batches. LoggingHelper then reads the stream and appends to the log file.

Log only what's unusual (warnings, errors). A normal request should make no log calls; its numbers
already reach the metrics as a request event.
"""
from __future__ import annotations

import json
import logging
import queue
import sys
import threading
from datetime import datetime, timezone
from logging.handlers import QueueHandler
from typing import TYPE_CHECKING

from src.utils.types import RedisStreamName

if TYPE_CHECKING:
    import redis

_QUEUE_SIZE = 10_000            # records waiting for the thread; beyond this, new ones are dropped
_BATCH_SIZE = 100               # records per Redis round trip
_STREAM_MAX_LENGTH = 100_000
_STOP = object()


def tune_logging_for_speed() -> None:
    """Stops `logging` from collecting the caller's file, line, thread and process for every record
    (the documented optimisations in the logging HOWTO). Tollgate's log lines don't use them."""
    logging._srcfile = None
    logging.logThreads = False
    logging.logProcesses = False
    logging.logMultiprocessing = False
    if hasattr(logging, "logAsyncioTasks"):
        logging.logAsyncioTasks = False


class _DeferredQueueHandler(QueueHandler):
    """Queues the record untouched: the shipper thread formats it, so the caller doesn't pay for it.
    Never blocks: when the queue is full, the record is dropped and counted."""

    def __init__(self, log_queue: queue.Queue, on_drop):
        super().__init__(log_queue)
        self._on_drop = on_drop

    def prepare(self, record: logging.LogRecord) -> logging.LogRecord:
        return record

    def enqueue(self, record: logging.LogRecord) -> None:
        try:
            self.queue.put_nowait(record)
        except queue.Full:
            self._on_drop()


class LogShipper:
    def __init__(self, redis_client: redis.Redis, stream: str = RedisStreamName.LOGGING):
        self._redis = redis_client
        self._stream = stream
        self._queue: queue.Queue = queue.Queue(maxsize=_QUEUE_SIZE)
        self._formatter = logging.Formatter("%(message)s")   # also renders tracebacks from logger.exception
        self._thread = threading.Thread(target=self._run, name="log-shipper", daemon=True)
        self.dropped = 0

    def install(self, logger_name: str = "src", level: int = logging.INFO) -> None:
        """Sends everything logged under `logger_name` (all of Tollgate's getLogger(__name__) loggers) here."""
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)
        logger.addHandler(_DeferredQueueHandler(self._queue, self._count_drop))
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Ships what's still queued, then ends the thread. Called at shutdown."""
        if not self._thread.is_alive():
            return
        try:
            self._queue.put(_STOP, timeout=timeout)
        except queue.Full:
            return
        self._thread.join(timeout)

    def _count_drop(self) -> None:
        self.dropped += 1

    def _run(self) -> None:
        while True:
            batch, stopping = self._next_batch()
            if batch:
                self._ship(batch)
            if stopping:
                return

    def _next_batch(self) -> tuple[list[logging.LogRecord], bool]:
        first = self._queue.get()           # waits on this thread only, never on the event loop
        if first is _STOP:
            return [], True
        batch = [first]
        while len(batch) < _BATCH_SIZE:
            try:
                record = self._queue.get_nowait()
            except queue.Empty:
                break
            if record is _STOP:
                return batch, True
            batch.append(record)
        return batch, False

    def _ship(self, records: list[logging.LogRecord]) -> None:
        entries = [self._entry(record) for record in records]
        try:
            pipe = self._redis.pipeline(transaction=False)
            for entry in entries:
                pipe.xadd(self._stream, {"payload": json.dumps(entry)}, maxlen=_STREAM_MAX_LENGTH, approximate=True)
            pipe.execute()
        except Exception:
            # Redis unreachable: these lines (often about Redis itself) still have to reach someone
            for entry in entries:
                print(f'{entry["timestamp"]} {entry["level"]} [{entry["logger"]}] {entry["message"]}', file=sys.stderr)

    def _entry(self, record: logging.LogRecord) -> dict[str, str]:
        return {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": self._formatter.format(record),
        }
