import pytest
from pydantic import ValidationError

from src.app.api.validators import ChatModel
from src.utils.types import GenerationParams


def base_chat_payload(**overrides):
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "hi"}],
        "max_tokens": 4096,
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("model", ["gpt-4o", "claude-sonnet-4-6", "gemini-3.8-flash", "fast", "cheap", "smart"])
def test_chat_model_accepts_known_models_and_policies(model):
    chat = ChatModel(**base_chat_payload(model=model))
    assert chat.model == model


def test_max_tokens_is_optional_like_in_openai():
    payload = base_chat_payload()
    del payload["max_tokens"]

    assert ChatModel(**payload).generation_params().max_tokens is None


def test_max_completion_tokens_wins_over_the_deprecated_max_tokens():
    chat = ChatModel(**base_chat_payload(max_tokens=100, max_completion_tokens=50))

    assert chat.generation_params().max_tokens == 50


def test_generation_params_carry_every_sampling_option():
    chat = ChatModel(**base_chat_payload(temperature=0.3, top_p=0.9, stop="END"))

    assert chat.generation_params() == GenerationParams(max_tokens=4096, temperature=0.3, top_p=0.9, stop=["END"])


def test_text_content_parts_are_joined_into_one_string():
    chat = ChatModel(**base_chat_payload(messages=[
        {"role": "user", "content": [{"type": "text", "text": "first"}, {"type": "text", "text": "second"}]},
    ]))

    assert chat.messages[0].content == "first\nsecond"


def test_fields_tollgate_does_not_use_are_ignored():
    chat = ChatModel(**base_chat_payload(
        user="u-1", seed=7, metadata={"a": "b"}, stream_options=None, n=1, stream=False,
        response_format={"type": "text"}, messages=[{"role": "user", "content": "hi", "name": "alice"}],
    ))

    assert chat.messages[0].content == "hi"


@pytest.mark.parametrize("unsupported, reason", [
    ({"stream": True}, "stream"),
    ({"n": 2}, "n must be 1"),
    ({"tools": [{"type": "function", "function": {"name": "f"}}]}, "tools"),
    ({"tool_choice": "auto"}, "tools"),
    ({"functions": [{"name": "f"}]}, "tools"),
    ({"response_format": {"type": "json_object"}}, "response_format"),
    ({"messages": [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "x"}}]}]}, "image_url"),
    ({"messages": [{"role": "tool", "content": "42", "tool_call_id": "c1"}]}, "role"),
    ({"stop": ["a", "b", "c", "d", "e"]}, "at most 4"),
    ({"max_tokens": 0}, "max_tokens"),
])
def test_features_that_would_change_the_answer_are_rejected_not_ignored(unsupported, reason):
    with pytest.raises(ValidationError, match=reason):
        ChatModel(**base_chat_payload(**unsupported))


def test_chat_model_temperature_defaults_to_none_so_the_provider_default_applies():
    chat = ChatModel(**base_chat_payload())
    assert chat.temperature is None


def test_chat_model_rejects_empty_messages():
    with pytest.raises(ValidationError):
        ChatModel(**base_chat_payload(messages=[]))


def test_chat_model_rejects_a_conversation_without_a_user_message():
    with pytest.raises(ValidationError, match="at least one user message"):
        ChatModel(**base_chat_payload(messages=[{"role": "system", "content": "be nice"}]))


@pytest.mark.parametrize("temperature", [-0.1, 2.1])
def test_chat_model_rejects_out_of_range_temperature(temperature):
    with pytest.raises(ValidationError):
        ChatModel(**base_chat_payload(temperature=temperature))


@pytest.mark.parametrize("temperature", [0.0, 2.0, 1.0])
def test_chat_model_accepts_boundary_temperatures(temperature):
    chat = ChatModel(**base_chat_payload(temperature=temperature))
    assert chat.temperature == temperature


def test_chat_model_cache_type_defaults_to_none():
    chat = ChatModel(**base_chat_payload())
    assert chat.cache_type is None


@pytest.mark.parametrize("cache_type", ["exact", "semantic"])
def test_chat_model_accepts_valid_cache_types(cache_type):
    chat = ChatModel(**base_chat_payload(cache_type=cache_type))
    assert chat.cache_type == cache_type


def test_chat_model_rejects_invalid_cache_type():
    with pytest.raises(ValidationError):
        ChatModel(**base_chat_payload(cache_type="NOT_A_TYPE"))


def test_chat_model_rejects_invalid_message_role():
    with pytest.raises(ValidationError):
        ChatModel(**base_chat_payload(messages=[{"role": "not-a-role", "content": "hi"}]))


def test_chat_model_requires_at_least_the_model_and_messages_fields():
    with pytest.raises(ValidationError):
        ChatModel(model="gpt-4o")
