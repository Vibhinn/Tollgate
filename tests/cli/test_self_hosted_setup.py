"""Tests for the self-hosted model prompts added to `tollgate init` and
`tollgate config --change`. These call the prompt-driven functions directly
(not through the click commands) with Prompt/Confirm patched to return
canned answers, since that's the layer these functions actually own."""
from rich.prompt import Prompt, Confirm

from cli.helpers import change as change_helper
from cli.steps import providers as providers_step


def _queue(monkeypatch, cls, method_name, values):
    it = iter(values)
    monkeypatch.setattr(cls, method_name, lambda *a, **k: next(it))


# --- tollgate init: providers.py._collect_self_hosted_models ---

def test_collect_self_hosted_models_returns_empty_when_declined(monkeypatch):
    _queue(monkeypatch, Confirm, "ask", [False])

    result = providers_step._collect_self_hosted_models({"_fernet_key": b"unused"})

    assert result == {}


def test_collect_self_hosted_models_collects_multiple_distinct_aliases(monkeypatch):
    """Regression test: without per-alias storage, adding Ollama then
    llama.cpp then Apple FM would collide under one shared key."""
    _queue(monkeypatch, Confirm, "ask", [True, True, True, False])
    _queue(monkeypatch, Prompt, "ask", [
        "ollama-llama3", "http://localhost:11434/v1", "llama3", "",
        "llamacpp-mistral", "http://localhost:8080/v1", "mistral-7b-instruct", "",
        "mac-fm", "http://localhost:8081/v1", "apple-fm-3b", "",
    ])

    result = providers_step._collect_self_hosted_models({"_fernet_key": b"unused"})

    assert set(result.keys()) == {"ollama-llama3", "llamacpp-mistral", "mac-fm"}
    assert result["ollama-llama3"] == {
        "endpoint": "http://localhost:11434/v1", "model_name": "llama3", "api_key": "NOT_CONFIGURED",
    }
    assert result["mac-fm"] == {
        "endpoint": "http://localhost:8081/v1", "model_name": "apple-fm-3b", "api_key": "NOT_CONFIGURED",
    }


def test_collect_self_hosted_models_encrypts_a_real_api_key(monkeypatch):
    _queue(monkeypatch, Confirm, "ask", [True, False])
    _queue(monkeypatch, Prompt, "ask", ["hosted-vllm", "https://my-vllm.internal/v1", "llama3-70b", "sk-real-secret"])
    monkeypatch.setattr(providers_step, "encrypt_with_key", lambda value, key: f"encrypted:{value}")

    result = providers_step._collect_self_hosted_models({"_fernet_key": b"unused"})

    assert result["hosted-vllm"]["api_key"] == "encrypted:sk-real-secret"


def test_collect_self_hosted_models_rejects_a_duplicate_alias(monkeypatch):
    _queue(monkeypatch, Confirm, "ask", [True, True, False])
    _queue(monkeypatch, Prompt, "ask", [
        "dup", "http://localhost:11434/v1", "llama3", "",   # first: name "dup"
        "dup", "second-name",                                  # retry: "dup" again (rejected), then a real name
        "http://localhost:8080/v1", "mistral-7b", "",
    ])

    result = providers_step._collect_self_hosted_models({"_fernet_key": b"unused"})

    assert set(result.keys()) == {"dup", "second-name"}


# --- tollgate config --change: change.py._add_self_hosted_model / _remove_self_hosted_model ---

def test_add_self_hosted_model_saves_a_new_alias_without_touching_existing_ones(monkeypatch):
    _queue(monkeypatch, Prompt, "ask", ["llamacpp-mistral", "http://localhost:8080/v1", "mistral-7b", ""])
    data = {
        "models": {
            "self_hosted": {
                "ollama-llama3": {"endpoint": "http://localhost:11434/v1", "model_name": "llama3", "api_key": "NOT_CONFIGURED"},
            },
        },
    }

    result = change_helper._add_self_hosted_model(data)

    assert set(result["models"]["self_hosted"].keys()) == {"ollama-llama3", "llamacpp-mistral"}
    assert result["models"]["self_hosted"]["llamacpp-mistral"] == {
        "endpoint": "http://localhost:8080/v1", "model_name": "mistral-7b", "api_key": "NOT_CONFIGURED",
    }


def test_add_self_hosted_model_encrypts_a_real_api_key(monkeypatch):
    _queue(monkeypatch, Prompt, "ask", ["hosted-vllm", "https://my-vllm.internal/v1", "llama3-70b", "sk-real-secret"])
    monkeypatch.setattr(change_helper, "encrypt_value", lambda value: f"encrypted:{value}")
    data = {"models": {}}

    result = change_helper._add_self_hosted_model(data)

    assert result["models"]["self_hosted"]["hosted-vllm"]["api_key"] == "encrypted:sk-real-secret"


def test_add_self_hosted_model_reusing_an_existing_alias_updates_it_in_place(monkeypatch):
    _queue(monkeypatch, Prompt, "ask", ["ollama-llama3", "http://localhost:11434/v1", "llama3.1", ""])
    data = {
        "models": {
            "self_hosted": {
                "ollama-llama3": {"endpoint": "http://localhost:11434/v1", "model_name": "llama3", "api_key": "NOT_CONFIGURED"},
            },
        },
    }

    result = change_helper._add_self_hosted_model(data)

    assert len(result["models"]["self_hosted"]) == 1
    assert result["models"]["self_hosted"]["ollama-llama3"]["model_name"] == "llama3.1"


def test_remove_self_hosted_model_deletes_the_chosen_alias(monkeypatch):
    _queue(monkeypatch, Prompt, "ask", ["1"])
    data = {
        "models": {
            "self_hosted": {
                "ollama-llama3": {"endpoint": "http://localhost:11434/v1"},
                "llamacpp-mistral": {"endpoint": "http://localhost:8080/v1"},
            },
        },
    }

    result = change_helper._remove_self_hosted_model(data)

    assert "ollama-llama3" not in result["models"]["self_hosted"]
    assert "llamacpp-mistral" in result["models"]["self_hosted"]


def test_remove_self_hosted_model_errors_cleanly_when_none_exist():
    data = {"models": {}}

    result = change_helper._remove_self_hosted_model(data)

    assert result == data
