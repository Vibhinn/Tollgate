import asyncio
from functools import partial
from pathlib import Path
from llama_cpp import Llama, LlamaGrammar

class RoutingIntelligenceLayer:
    def __init__(self):
        model_path = Path(__file__).parent / "models" / "qwen0.5B.gguf"
        self.local_llm = Llama(
            model_path=str(model_path),
            n_ctx=512,
            n_threads=2,
            verbose=False
        )

        self.grammar = LlamaGrammar.from_string(r'root ::= "SIMPLE" | "CODE" | "REASONING" | "CREATIVE"')

    async def classify(self, user_message: str) -> str:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                self.local_llm.create_chat_completion,
                messages=[
                    {"role": "system",
                     "content": "Classify the user request. Reply with only one word: SIMPLE, CODE, REASONING, or CREATIVE."},
                    {"role": "user", "content": user_message}
                ],
                grammar=self.grammar,
                max_tokens=1
            )
        )
        return result


