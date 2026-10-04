from google.genai import types

from src.llm.formatting import UserRequestFormat
from src.utils.types import Message

USER_ONLY = [Message(role="user", content="hi")]


def test_openai_keeps_every_role_as_is():
    messages = [Message(role="developer", content="be brief"), Message(role="user", content="hi")]

    assert UserRequestFormat.to_openai_messages(messages) == [
        {"role": "developer", "content": "be brief"},
        {"role": "user", "content": "hi"},
    ]


def test_self_hosted_leaves_system_messages_alone():
    messages = [Message(role="system", content="be brief"), Message(role="user", content="hi")]

    assert UserRequestFormat.to_self_hosted_messages(messages)[0] == {"role": "system", "content": "be brief"}


def test_anthropic_without_system_messages_has_no_system_prompt():
    system_prompt, conversation = UserRequestFormat.to_anthropic_messages(USER_ONLY)

    assert system_prompt is None
    assert conversation == [{"role": "user", "content": "hi"}]


def test_gemini_without_system_messages_has_no_system_instruction():
    system_instruction, contents = UserRequestFormat.to_gemini_messages(USER_ONLY)

    assert system_instruction is None
    assert contents == [types.Content(role="user", parts=[types.Part(text="hi")])]


def test_system_messages_anywhere_in_the_conversation_are_collected_in_order():
    messages = [
        Message(role="system", content="first"),
        Message(role="user", content="hi"),
        Message(role="developer", content="second"),
    ]

    assert UserRequestFormat.to_anthropic_messages(messages)[0] == "first\n\nsecond"
    assert UserRequestFormat.to_gemini_messages(messages)[0] == "first\n\nsecond"
