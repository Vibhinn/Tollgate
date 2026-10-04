from src.app.ports import LLMRepositoryInterface
from src.utils.types import LLMProvider, LLMInvocationResult, Message
from ..connection import LLMConnection
from ..formatting import UserRequestFormat
from src.app.exceptions import (ModelProviderServerError, RateLimitedFromModelProvider, CreditExhaustion, PermissionDeniedForModel,
                                APIKeyInvalidOrExpired, BadRequestToModel, APIError)

from anthropic import BadRequestError, AuthenticationError, PermissionDeniedError, InternalServerError, RateLimitError, APIConnectionError

class AnthropicRepository(LLMRepositoryInterface):
    def __init__(self):
        self.anthropic_client = LLMConnection.get_connection(LLMProvider.ANTHROPIC)

    async def invoke(self, messages: list[Message], model_name: str, max_tokens: int, temperature: float | None = None) -> LLMInvocationResult:
        system_prompt, conversation = UserRequestFormat.to_anthropic_messages(messages)
        optional_params = {}
        if system_prompt is not None:
            optional_params["system"] = system_prompt
        if temperature is not None:
            optional_params["temperature"] = temperature
        try:
            response = await self.anthropic_client.messages.create(
                model=model_name,
                messages=conversation,
                max_tokens=max_tokens,
                **optional_params,
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
