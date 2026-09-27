"""Tests for compiling llama-server from source at `tollgate init` time.

Replaces downloading a prebuilt binary from tollgate-native: building and
running on the same machine means there's no shared-library packaging step,
and therefore no cross-machine mismatch class of bug to have at all.
"""
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from cli.steps import build_server


def test_verify_binary_runs_passes_when_the_binary_executes_successfully():
    with patch("cli.steps.build_server.subprocess.run") as mock_run:
        build_server._verify_binary_runs("/fake/path/llama-server")

    mock_run.assert_called_once()
    args, _ = mock_run.call_args
    assert args[0] == ["/fake/path/llama-server", "--help"]


def test_verify_binary_runs_raises_a_clear_error_when_the_binary_cant_execute():
    with patch(
        "cli.steps.build_server.subprocess.run",
        side_effect=OSError("error while loading shared libraries"),
    ):
        with pytest.raises(RuntimeError, match="could not run"):
            build_server._verify_binary_runs("/fake/path/llama-server")


def test_require_build_tools_passes_when_everything_is_on_path():
    with patch("cli.steps.build_server.shutil.which", return_value="/usr/bin/found"):
        build_server._require_build_tools()  # must not raise


def test_require_build_tools_raises_a_clear_error_naming_whats_missing():
    def fake_which(tool):
        return None if tool in ("git", "cmake") else "/usr/bin/found"

    with patch("cli.steps.build_server.shutil.which", side_effect=fake_which):
        with pytest.raises(RuntimeError, match="git.*cmake|cmake.*git"):
            build_server._require_build_tools()


def test_require_build_tools_raises_when_no_compiler_is_found():
    def fake_which(tool):
        return None if tool in ("gcc", "clang", "cc") else "/usr/bin/found"

    with patch("cli.steps.build_server.shutil.which", side_effect=fake_which):
        with pytest.raises(RuntimeError, match="compiler"):
            build_server._require_build_tools()


def test_run_verifies_an_already_present_binary_and_skips_building(tmp_path, monkeypatch):
    binary_path = tmp_path / build_server.BINARY_NAME
    binary_path.write_text("fake binary")
    monkeypatch.setattr(build_server, "_server_dir", lambda: tmp_path)

    verify_mock = MagicMock()
    monkeypatch.setattr(build_server, "_verify_binary_runs", verify_mock)

    with patch("cli.steps.build_server.subprocess.run") as mock_run:
        build_server.run({})

    verify_mock.assert_called_once_with(binary_path)
    mock_run.assert_not_called()


def test_run_clones_configures_builds_and_verifies_when_binary_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(build_server, "_server_dir", lambda: tmp_path)
    monkeypatch.setattr(build_server, "_require_build_tools", MagicMock())
    verify_mock = MagicMock()
    monkeypatch.setattr(build_server, "_verify_binary_runs", verify_mock)

    def fake_run(cmd, **kwargs):
        # Simulate cmake producing the binary at the expected build output path.
        if cmd[:2] == ["cmake", "--build"]:
            built = tmp_path / "_build" / "llama.cpp" / "build" / "bin"
            built.mkdir(parents=True, exist_ok=True)
            (built / build_server.BINARY_NAME).write_text("compiled binary")
        return MagicMock(returncode=0)

    with patch("cli.steps.build_server.subprocess.run", side_effect=fake_run) as mock_run:
        build_server.run({})

    binary_path = tmp_path / build_server.BINARY_NAME
    assert binary_path.exists()
    verify_mock.assert_called_once_with(binary_path)

    commands = [call.args[0] for call in mock_run.call_args_list]
    assert any(cmd[:2] == ["git", "clone"] for cmd in commands)
    assert any(cmd[:2] == ["git", "-C"] and "checkout" in cmd for cmd in commands)
    assert any(cmd[:2] == ["cmake", "-B"] for cmd in commands)
    assert any(cmd[:2] == ["cmake", "--build"] for cmd in commands)


def test_run_pins_llama_cpp_to_the_expected_commit(tmp_path, monkeypatch):
    monkeypatch.setattr(build_server, "_server_dir", lambda: tmp_path)
    monkeypatch.setattr(build_server, "_require_build_tools", MagicMock())
    monkeypatch.setattr(build_server, "_verify_binary_runs", MagicMock())

    def fake_run(cmd, **kwargs):
        if cmd[:2] == ["cmake", "--build"]:
            built = tmp_path / "_build" / "llama.cpp" / "build" / "bin"
            built.mkdir(parents=True, exist_ok=True)
            (built / build_server.BINARY_NAME).write_text("compiled binary")
        return MagicMock(returncode=0)

    with patch("cli.steps.build_server.subprocess.run", side_effect=fake_run) as mock_run:
        build_server.run({})

    commands = [call.args[0] for call in mock_run.call_args_list]
    checkout_cmd = next(cmd for cmd in commands if "checkout" in cmd)
    assert checkout_cmd[-1] == build_server.LLAMA_CPP_REF
