"""Tests for the backpressure prompt in `tollgate init` and `tollgate config --change`.
Prompt is patched to return canned answers, same as the self-hosted setup tests."""
from rich.prompt import Prompt

from cli.helpers import change as change_helper
from cli.steps import backpressure as backpressure_step


def _queue(monkeypatch, cls, method_name, values):
    it = iter(values)
    monkeypatch.setattr(cls, method_name, lambda *a, **k: next(it))


def test_init_step_stores_max_in_flight(monkeypatch):
    _queue(monkeypatch, Prompt, "ask", ["80"])

    result = backpressure_step.run({})

    assert result["backpressure"] == {"max_in_flight": "80"}


def test_init_step_reprompts_until_positive_integer(monkeypatch):
    _queue(monkeypatch, Prompt, "ask", ["0", "-3", "abc", "25"])

    result = backpressure_step.run({})

    assert result["backpressure"] == {"max_in_flight": "25"}


def test_change_updates_existing_value(monkeypatch):
    _queue(monkeypatch, Prompt, "ask", ["120"])

    result = change_helper._change_backpressure({"backpressure": {"max_in_flight": "50"}})

    assert result["backpressure"] == {"max_in_flight": "120"}


def test_change_works_on_config_without_backpressure_section(monkeypatch):
    _queue(monkeypatch, Prompt, "ask", ["30"])

    result = change_helper._change_backpressure({"rate_limiter": {"max_tokens": "5"}})

    assert result["backpressure"] == {"max_in_flight": "30"}
    assert result["rate_limiter"] == {"max_tokens": "5"}


def test_backpressure_is_a_change_option():
    labels = [label for label, _ in change_helper._CHANGE_OPTIONS.values()]

    assert "Backpressure (max requests in flight)" in labels
