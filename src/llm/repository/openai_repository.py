from typing import override

from openai import BadRequestError, AuthenticationError, PermissionDeniedError, InternalServerError, RateLimitError, APIConnectionError

from src.app.ports import LLMRepositoryInterface
from src.app.exceptions import (ModelProviderServerError, RateLimitedFromModelProvider,
                                 PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel, APIError)
from src.utils.types import LLMProvider, LLMInvocationResult, Message

from ..connection import LLMConnection
from ..formatting import UserRequestFormat


class OpenAIRepository(LLMRepositoryInterface):
    @override
    def __init__(self):
        self.openai_client = LLMConnection.get_connection(LLMProvider.OPENAI)

    @override
    async def invoke(self, messages: list[Message], model_name: str, max_tokens: int, temperature: float | None = None) -> LLMInvocationResult:
        optional_params = {"temperature": temperature} if temperature is not None else {}
        try:
            response = await self.openai_client.chat.completions.create(
                model=model_name,
                messages=UserRequestFormat.to_openai_messages(messages),
                max_tokens=max_tokens,
                **optional_params,
            )
            return LLMInvocationResult(
                content=response.choices[0].message.content,
                input_tokens=response.usage.prompt_tokens,
                output_tokens=response.usage.completion_tokens,
            )

        except InternalServerError as e:
            raise ModelProviderServerError(str(e)) from e

        except BadRequestError as e:
            raise BadRequestToModel(str(e)) from e

        except PermissionDeniedError as e:
            raise PermissionDeniedForModel(str(e)) from e

        except AuthenticationError as e:
            raise APIKeyInvalidOrExpired(str(e)) from e

        except APIConnectionError as e:
            raise APIError(str(e)) from e

        except RateLimitError as e:
            raise RateLimitedFromModelProvider(str(e)) from e
