from typing import override

from openai import (BadRequestError, AuthenticationError, PermissionDeniedError, InternalServerError,
                    RateLimitError, APIConnectionError)

from src.app.ports import LLMRepositoryInterface
from src.app.exceptions import (ModelProviderServerError, RateLimitedFromModelProvider,
                                 PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel,
                                APIError)
from src.utils.types import LLMInvocationResult, Message, GenerationParams

from ..connection import LLMConnection
from ..formatting import UserRequestFormat, FinishReasonFormat


class SelfHostedModelRepository(LLMRepositoryInterface):
    @override
    def __init__(self, alias: str):
        self.self_hosted_model_client = LLMConnection.get_self_hosted_connection(alias)

    @override
    async def invoke(self, messages: list[Message], model_name: str, params: GenerationParams) -> LLMInvocationResult:
        optional_params = {
            "max_tokens": params.max_tokens,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "stop": params.stop,
        }
        try:
            stream = await self.self_hosted_model_client.chat.completions.create( #type: ignore
                model=model_name,
                messages=UserRequestFormat.to_self_hosted_messages(messages),
                stream=True,
                stream_options={"include_usage": True},
                **{name: value for name, value in optional_params.items() if value is not None},
            )

            content_parts: list[str] = []
            input_tokens = 0
            output_tokens = 0
            finish_reason = None

            async for chunk in stream: #type: ignore
                if chunk.choices and chunk.choices[0].delta.content:
                    content_parts.append(chunk.choices[0].delta.content)
                if chunk.choices and chunk.choices[0].finish_reason:
                    finish_reason = chunk.choices[0].finish_reason
                if chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens
                    output_tokens = chunk.usage.completion_tokens

            return LLMInvocationResult(
                content="".join(content_parts),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                finish_reason=FinishReasonFormat.from_openai(finish_reason),
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
