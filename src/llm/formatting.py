from __future__ import annotations

from typing import TYPE_CHECKING

from google.genai import types

if TYPE_CHECKING:
    from src.utils.types import Message, FINISH_REASON

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


class FinishReasonFormat:
    """Maps each provider's stop reason onto OpenAI's finish_reason."""
    _ANTHROPIC = {"max_tokens": "length", "refusal": "content_filter"}
    _GEMINI = {"MAX_TOKENS": "length", "SAFETY": "content_filter", "RECITATION": "content_filter",
               "BLOCKLIST": "content_filter", "PROHIBITED_CONTENT": "content_filter", "SPII": "content_filter",
               "IMAGE_SAFETY": "content_filter"}
    _OPENAI = {"length", "content_filter"}

    @staticmethod
    def from_openai(finish_reason: str | None) -> FINISH_REASON:
        return finish_reason if finish_reason in FinishReasonFormat._OPENAI else "stop"

    @staticmethod
    def from_anthropic(stop_reason: str | None) -> FINISH_REASON:
        # end_turn and stop_sequence are a normal "stop"
        return FinishReasonFormat._ANTHROPIC.get(stop_reason, "stop")

    @staticmethod
    def from_gemini(finish_reason) -> FINISH_REASON:
        name = getattr(finish_reason, "name", finish_reason)
        return FinishReasonFormat._GEMINI.get(name, "stop")
