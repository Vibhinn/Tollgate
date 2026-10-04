from typing import override

from google.genai import types
from google.genai.errors import ClientError, ServerError

from src.app.ports import LLMRepositoryInterface
from src.app.exceptions import (ModelProviderServerError, RateLimitedFromModelProvider,
                                 PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel)
from src.utils.types import LLMProvider, LLMInvocationResult, Message

from ..connection import LLMConnection
from ..formatting import UserRequestFormat

class GeminiRepository(LLMRepositoryInterface):
    @override
    def __init__(self):
        self.gemini_client = LLMConnection.get_connection(LLMProvider.GEMINI)
        self._client_error_map= {
            401: APIKeyInvalidOrExpired,
            403: PermissionDeniedForModel,
            429: RateLimitedFromModelProvider,
        }

    @override
    async def invoke(self, messages: list[Message], model_name: str, max_tokens: int, temperature: float | None = None) -> LLMInvocationResult:
        system_instruction, contents = UserRequestFormat.to_gemini_messages(messages)
        try:
            response = await self.gemini_client.aio.models.generate_content(
                model=model_name,
                contents=contents,
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    temperature=temperature,
                    system_instruction=system_instruction,
                ),
            )
            return LLMInvocationResult(
                content=response.text,
                input_tokens=response.usage_metadata.prompt_token_count,
                output_tokens=response.usage_metadata.candidates_token_count,
            )

        except ServerError as e:
            raise ModelProviderServerError(str(e)) from e

        except ClientError as e:
            raise self._client_error_map.get(e.code, BadRequestToModel)(str(e)) from e
