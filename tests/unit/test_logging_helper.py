import json

from src.jobs.helpers import LoggingHelper


def stream_entry(**fields):
    entry = {"timestamp": "2026-10-13T09:41:07.312+00:00", "level": "WARNING",
             "logger": "src.app.api.middleware.rate_limiting", "message": "rate limiter unavailable"}
    entry.update(fields)
    return {"payload": json.dumps(entry)}


async def test_each_entry_is_appended_to_the_log_file_as_one_line(tmp_path):
    log_file = tmp_path / "logs" / "tollgate.log"
    helper = LoggingHelper(log_file)

    await helper.execute(stream_entry())
    await helper.execute(stream_entry(level="ERROR", message="second"))

    assert log_file.read_text().splitlines() == [
        "2026-10-13T09:41:07.312+00:00 WARNING  [src.app.api.middleware.rate_limiting] rate limiter unavailable",
        "2026-10-13T09:41:07.312+00:00 ERROR    [src.app.api.middleware.rate_limiting] second",
    ]


def test_the_file_is_only_created_once_something_is_logged(tmp_path):
    LoggingHelper(tmp_path / "logs" / "tollgate.log")

    assert not (tmp_path / "logs").exists()
