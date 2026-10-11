from src.app.ports import LLMRepositoryInterface
from src.utils.types import LLMProvider, LLMInvocationResult, Message, GenerationParams
from ..connection import LLMConnection
from ..formatting import UserRequestFormat, FinishReasonFormat
from src.app.exceptions import (ModelProviderServerError, RateLimitedFromModelProvider, CreditExhaustion, PermissionDeniedForModel,
                                APIKeyInvalidOrExpired, BadRequestToModel, APIError)

from anthropic import BadRequestError, AuthenticationError, PermissionDeniedError, InternalServerError, RateLimitError, APIConnectionError

# Anthropic requires max_tokens; OpenAI clients usually leave it out
DEFAULT_MAX_TOKENS = 4096


class AnthropicRepository(LLMRepositoryInterface):
    def __init__(self):
        self.anthropic_client = LLMConnection.get_connection(LLMProvider.ANTHROPIC)

    async def invoke(self, messages: list[Message], model_name: str, params: GenerationParams) -> LLMInvocationResult:
        system_prompt, conversation = UserRequestFormat.to_anthropic_messages(messages)
        optional_params = {
            "system": system_prompt,
            "temperature": params.temperature,
            "top_p": params.top_p,
            "stop_sequences": params.stop,
        }
        try:
            response = await self.anthropic_client.messages.create(
                model=model_name,
                messages=conversation,
                max_tokens=params.max_tokens or DEFAULT_MAX_TOKENS,
                **{name: value for name, value in optional_params.items() if value is not None},
            )

            return LLMInvocationResult(
                # a refusal can come back with no content blocks at all
                content="".join(block.text for block in response.content if block.type == "text"),
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                finish_reason=FinishReasonFormat.from_anthropic(response.stop_reason),
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
