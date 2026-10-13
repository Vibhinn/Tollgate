from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import IO, override, TYPE_CHECKING

from .base import BaseHelper

if TYPE_CHECKING:
    from src.utils.types import StreamPayload

DEFAULT_LOG_PATH = Path("logs/tollgate.log")


class LoggingHelper(BaseHelper):
    """Appends the entries LogShipper puts on the `logging` stream to the log file."""

    def __init__(self, log_path: Path = DEFAULT_LOG_PATH):
        self._log_path = log_path
        self._file: IO[str] | None = None

    @override
    async def execute(self, data: StreamPayload):
        entry = json.loads(data["payload"])
        line = f'{entry["timestamp"]} {entry["level"]:<8} [{entry["logger"]}] {entry["message"]}\n'
        # file writes block; this keeps them off the event loop that serves requests
        await asyncio.to_thread(self._write, line)

    def _write(self, line: str) -> None:
        if self._file is None:
            # opened on first use, so building the app never creates an empty log file
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self._log_path.open("a", encoding="utf-8", buffering=1)   # line-buffered
        self._file.write(line)
