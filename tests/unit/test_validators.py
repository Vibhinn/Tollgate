import pytest
from pydantic import ValidationError

from app.api.validators import ChatModel
from app.api.validators.generate import GenerateTokenRequest


def base_chat_payload(**overrides):
    payload = {
        "model": "gpt-4o",
        "messages": [{"role": "user", "content": "hi"}],
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("model", ["gpt-4o", "claude-sonnet-4-6", "gemini-2.0-flash", "fast", "cheap", "smart"])
def test_chat_model_accepts_known_models_and_policies(model):
    chat = ChatModel(**base_chat_payload(model=model))
    assert chat.model == model


def test_chat_model_rejects_unknown_model():
    with pytest.raises(ValidationError, match="Unknown model"):
        ChatModel(**base_chat_payload(model="not-a-real-model"))


def test_chat_model_default_temperature_is_0_7():
    chat = ChatModel(**base_chat_payload())
    assert chat.temperature == 0.7


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


def test_generate_token_request_accepts_valid_values():
    req = GenerateTokenRequest(token_requirement="chat", role="user")
    assert req.token_requirement == "chat"
    assert req.role == "user"
    assert req.lifetime == 1296000


def test_generate_token_request_accepts_custom_lifetime():
    req = GenerateTokenRequest(token_requirement="image", role="admin", lifetime=60)
    assert req.lifetime == 60


@pytest.mark.parametrize("requirement", ["video", "", "CHAT"])
def test_generate_token_request_rejects_invalid_requirement(requirement):
    with pytest.raises(ValidationError):
        GenerateTokenRequest(token_requirement=requirement, role="user")


def test_generate_token_request_rejects_invalid_role():
    with pytest.raises(ValidationError):
        GenerateTokenRequest(token_requirement="chat", role="superadmin")
