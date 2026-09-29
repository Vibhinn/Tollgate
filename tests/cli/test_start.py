"""Tests for `tollgate start` - the entrypoint's exec target once config.yaml
exists, replacing a raw `uvicorn main:app ...` shell invocation so config
gets validated with a clear error instead of a raw traceback on failure.
"""
from unittest.mock import MagicMock, patch

import pytest

from cli.init import start


def test_start_exits_with_a_clear_error_when_config_is_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit):
        start.callback()


def test_start_exits_with_a_clear_error_when_config_fails_to_load(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text(": not valid yaml :::")

    with pytest.raises(SystemExit):
        start.callback()


def test_start_runs_uvicorn_when_config_is_valid(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "config.yaml").write_text("admin:\n  username: gAAAA\n  password_hash: x\n")

    with patch("cli.init.Config", MagicMock()):
        with patch("uvicorn.run") as mock_run:
            start.callback()

    mock_run.assert_called_once_with("main:app", host="0.0.0.0", port=13000, app_dir=".")
