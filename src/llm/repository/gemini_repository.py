from typing import override

from google.genai import types
from google.genai.errors import ClientError, ServerError

from src.app.ports import LLMRepositoryInterface
from src.app.exceptions import (ModelProviderServerError, RateLimitedFromModelProvider,
                                 PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel)
from src.utils.decorators import throws_exception
from src.utils.types import LLMProvider, LLMInvocationResult

from ..connection import LLMConnection

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
    @throws_exception(ModelProviderServerError, RateLimitedFromModelProvider,
                       PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel)
    async def invoke(self, message: str, model_name: str, max_tokens: int) -> LLMInvocationResult:
        print("We entered gemini repo!")
        try:
            response = await self.gemini_client.aio.models.generate_content(
                model=model_name,
                contents=message,
                config=types.GenerateContentConfig(max_output_tokens=max_tokens),
            )
            return LLMInvocationResult(
                content=response.text,
                input_tokens=response.usage_metadata.prompt_token_count,
                output_tokens=response.usage_metadata.candidates_token_count,
            )

        except ServerError as e:
            print(e)
            raise ModelProviderServerError(str(e)) from e

        except ClientError as e:
            print(e)
            raise self._client_error_map.get(e.code, BadRequestToModel)(str(e)) from e
