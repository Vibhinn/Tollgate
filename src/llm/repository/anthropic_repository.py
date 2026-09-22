from src.app.ports import LLMRepositoryInterface
from src.utils.types import LLMProvider, LLMInvocationResult
from src.utils.decorators import throws_exception
from ..connection import LLMConnection
from src.app.exceptions import (ModelProviderServerError, RateLimitedFromModelProvider, CreditExhaustion, PermissionDeniedForModel,
                                APIKeyInvalidOrExpired, BadRequestToModel, APIError)

from anthropic import BadRequestError, AuthenticationError, PermissionDeniedError, InternalServerError, RateLimitError, APIConnectionError

class AnthropicRepository(LLMRepositoryInterface):
    def __init__(self):
        self.anthropic_client = LLMConnection.get_connection(LLMProvider.ANTHROPIC)

    @throws_exception(ModelProviderServerError, RateLimitedFromModelProvider, CreditExhaustion,
                      PermissionDeniedForModel, APIKeyInvalidOrExpired, BadRequestToModel, APIError)
    async def invoke(self, message: str, model_name: str, max_tokens: int) -> LLMInvocationResult:
        try:
            response = await self.anthropic_client.messages.create(
                model=model_name,
                messages=[
                    {
                        "role": "user",
                        "content": message,
                    }
                ],
                max_tokens=max_tokens
            )

            return LLMInvocationResult(
                content=response.content[0].text,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
            )

        except InternalServerError as e:
            raise ModelProviderServerError(str(e)) from e

        except BadRequestError as e:
            if "credit balance is too low" in str(e):
                raise CreditExhaustion(str(e)) from e
            raise BadRequestToModel(str(e)) from e

        except PermissionDeniedError as e:
            raise PermissionDeniedForModel(str(e)) from e

        except AuthenticationError as e:
            raise APIKeyInvalidOrExpired(str(e)) from e

        except APIConnectionError as e:
            raise APIError(str(e)) from e

        except RateLimitError as e:
            raise RateLimitedFromModelProvider(str(e)) from e
