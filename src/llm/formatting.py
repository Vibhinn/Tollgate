from __future__ import annotations

from typing import TYPE_CHECKING

from google.genai import types

if TYPE_CHECKING:
    from src.utils.types import Message

SYSTEM_ROLES = {"system", "developer"}


class UserRequestFormat:
    @staticmethod
    def to_openai_messages(messages: list[Message]) -> list[dict]:
        return [{"role": message.role, "content": message.content} for message in messages]

    @staticmethod
    def to_self_hosted_messages(messages: list[Message]) -> list[dict]:
        return [
            {"role": "system" if message.role == "developer" else message.role, "content": message.content}
            for message in messages
        ]

    @staticmethod
    def to_anthropic_messages(messages: list[Message]) -> tuple[str | None, list[dict]]:
        system_parts = [message.content for message in messages if message.role in SYSTEM_ROLES]
        conversation = [
            {"role": message.role, "content": message.content}
            for message in messages if message.role not in SYSTEM_ROLES
        ]
        return ("\n\n".join(system_parts) or None), conversation

    @staticmethod
    def to_gemini_messages(messages: list[Message]) -> tuple[str | None, list[types.Content]]:
        system_parts = [message.content for message in messages if message.role in SYSTEM_ROLES]
        contents = [
            types.Content(
                role="model" if message.role == "assistant" else "user",
                parts=[types.Part(text=message.content)],
            )
            for message in messages if message.role not in SYSTEM_ROLES
        ]
        return ("\n\n".join(system_parts) or None), contents
