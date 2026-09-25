from src.utils.config.configuration import Config


def make_config(data: dict) -> Config:
    config = Config.__new__(Config)
    config._data = data
    return config


def test_get_config_returns_a_plain_value():
    config = make_config({"gateway": {"default_model": "gpt-4o"}})

    assert config.get_config("gateway", "default_model") == "gpt-4o"


def test_get_config_with_single_string_sub_section():
    config = make_config({"models": {"openai": {"api_key": "sk-real-key"}}})

    assert config.get_config("models", "api_key", "openai") == "sk-real-key"


def test_get_config_with_nested_path_list():
    """Self-hosted models need a third level of nesting - models.self_hosted.<alias>.*
    - which a single sub_section string can't express since the alias is
    user-chosen, not a fixed enum."""
    config = make_config({
        "models": {
            "self_hosted": {
                "ollama-llama3": {"endpoint": "http://localhost:11434/v1"},
            },
        },
    })

    result = config.get_config("models", "endpoint", ["self_hosted", "ollama-llama3"])

    assert result == "http://localhost:11434/v1"


def test_get_config_decrypts_fernet_looking_values(monkeypatch):
    monkeypatch.setattr("src.utils.crypto.decrypt_value", lambda v: f"decrypted:{v}")
    config = make_config({"admin": {"username": "gAAAAAfake-encrypted-value"}})

    assert config.get_config("admin", "username") == "decrypted:gAAAAAfake-encrypted-value"


def test_get_config_does_not_decrypt_plain_values():
    config = make_config({"models": {"self_hosted": {"my-model": {"api_key": "NOT_CONFIGURED"}}}})

    result = config.get_config("models", "api_key", ["self_hosted", "my-model"])

    assert result == "NOT_CONFIGURED"


def test_get_entire_config_section_returns_the_raw_dict():
    config = make_config({"models": {"self_hosted": {"a": {}, "b": {}}}})

    assert config.get_entire_config_section("models") == {"self_hosted": {"a": {}, "b": {}}}


def test_get_entire_config_section_returns_empty_dict_for_missing_section():
    config = make_config({})

    assert config.get_entire_config_section("nonexistent") == {}
