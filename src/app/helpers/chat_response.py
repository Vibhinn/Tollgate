import uuid
import time
from src.utils.types import LLMInvocationResult

class TollgateResponseBuilder:
    @staticmethod
    def build_response(result: LLMInvocationResult):
        return {
            "id": f"chatcmpl-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": result.model,
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": result.content},
                "finish_reason": result.finish_reason,
            }],
            "usage": {
                "prompt_tokens": result.input_tokens,
                "completion_tokens": result.output_tokens,
                "total_tokens": result.input_tokens + result.output_tokens,
            },
        }
