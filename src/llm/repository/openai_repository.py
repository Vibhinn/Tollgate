from typing import override

from openai import BadRequestError, AuthenticationError, PermissionDeniedError, InternalServerError, RateLimitError, APIConnectionError

from src.app.ports import LLMRepositoryInterface
from src.app.exceptions import (ModelProviderServerError, RateLimitedFromModelProvider,
                                 PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel, APIError)
from src.utils.types import LLMProvider, LLMInvocationResult, Message, GenerationParams

from ..connection import LLMConnection
from ..formatting import UserRequestFormat, FinishReasonFormat


class OpenAIRepository(LLMRepositoryInterface):
    @override
    def __init__(self):
        self.openai_client = LLMConnection.get_connection(LLMProvider.OPENAI)

    @override
    async def invoke(self, messages: list[Message], model_name: str, params: GenerationParams) -> LLMInvocationResult:
        optional_params = {
            # o-series and newer models reject max_tokens
            "max_completion_tokens": params.max_tokens,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "stop": params.stop,
        }
        try:
            response = await self.openai_client.chat.completions.create( #type: ignore
                model=model_name,
                messages=UserRequestFormat.to_openai_messages(messages),
                **{name: value for name, value in optional_params.items() if value is not None},
            )
            choice = response.choices[0] #type: ignore
            return LLMInvocationResult(
                content=choice.message.content or "",
                input_tokens=response.usage.prompt_tokens, #type: ignore
                output_tokens=response.usage.completion_tokens, #type: ignore
                finish_reason=FinishReasonFormat.from_openai(choice.finish_reason),
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
