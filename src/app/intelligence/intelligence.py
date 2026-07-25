import asyncio
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from llama_cpp import Llama, LlamaGrammar

from src.utils.types import ApplicationRepositoryType, VectorRepositoryCollection

if TYPE_CHECKING:
    from src.app.factory import ApplicationRepositoryFactory

class RoutingIntelligenceLayer:
    def __init__(self, repo_factory: ApplicationRepositoryFactory):
        model_path = Path(__file__).parent / "model" / "qwen2.5-0.5b-instruct-q4_k_m.gguf"
        self.local_llm = Llama(
            model_path=str(model_path),
            n_ctx=512,
            n_threads=2,
            verbose=False,
            chat_format="chatml",
        )
        self.grammar = LlamaGrammar.from_string(
            r'root ::= "SIMPLE" | "CODE" | "REASONING" | "CREATIVE"'
        )

        self.embedding_model_repo = repo_factory.get_repo(ApplicationRepositoryType.EMBEDDING)
        self.vector_cache_repo = repo_factory.get_repo(ApplicationRepositoryType.VECTOR_CACHE)

    async def classify(self, user_message: str) -> str:
        request_embedding = await self.embedding_model_repo.create_vector_embeddings(user_message)
        answer_from_vector_db = await self.vector_cache_repo.search(collection=VectorRepositoryCollection.INTELLIGENCE_CLASSIFIER_CACHE,
                                                                    embedding=request_embedding,
                                                                    score_threshold=0.7)

        if answer_from_vector_db:
            return answer_from_vector_db

        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                partial(
                    self.local_llm.create_chat_completion,
                    messages=[
                        {
                            "role": "system",
                            "content": "Classify the user request. Reply with only one word: SIMPLE, CODE, REASONING, or CREATIVE.",
                        },
                        {"role": "user", "content": user_message},
                    ],
                    grammar=self.grammar,
                    max_tokens=1,
                ),
            )
            model_response = result["choices"][0]["message"]["content"].strip()
            await self.vector_cache_repo.save(request_embedding, VectorRepositoryCollection.INTELLIGENCE_CLASSIFIER_CACHE,  user_message, model_response)

            return model_response
