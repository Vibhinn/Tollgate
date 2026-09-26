from typing import override

from openai import (BadRequestError, AuthenticationError, PermissionDeniedError, InternalServerError,
                    RateLimitError, APIConnectionError)

from src.app.ports import LLMRepositoryInterface
from src.app.exceptions import (ModelProviderServerError, RateLimitedFromModelProvider,
                                 PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel,
                                APIError)
from src.utils.decorators import throws_exception
from src.utils.types import LLMInvocationResult

from ..connection import LLMConnection


class SelfHostedModelRepository(LLMRepositoryInterface):
    @override
    def __init__(self, alias: str):
        self.self_hosted_model_client = LLMConnection.get_connection(alias)

    @override
    @throws_exception(ModelProviderServerError, RateLimitedFromModelProvider,
                       PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel, APIError)
    async def invoke(self, message: str, model_name: str, max_tokens: int) -> LLMInvocationResult:
        try:
            stream = await self.self_hosted_model_client.chat.completions.create( #type: ignore
                model=model_name,
                messages=[{"role": "user", "content": message}],
                max_tokens=max_tokens,
                stream=True,
                stream_options={"include_usage": True},
            )

            content_parts: list[str] = []
            input_tokens = 0
            output_tokens = 0

            async for chunk in stream: #type: ignore
                if chunk.choices and chunk.choices[0].delta.content:
                    content_parts.append(chunk.choices[0].delta.content)
                if chunk.usage:
                    input_tokens = chunk.usage.prompt_tokens
                    output_tokens = chunk.usage.completion_tokens

            return LLMInvocationResult(
                content="".join(content_parts),
                input_tokens=input_tokens,
                output_tokens=output_tokens,
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
