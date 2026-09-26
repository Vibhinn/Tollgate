import asyncio
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from llama_cpp import Llama, LlamaGrammar

from src.utils.types import ApplicationRepositoryType, VectorRepositoryCollection

if TYPE_CHECKING:
    from src.app.factory import ApplicationRepositoryFactory

_CLASSIFICATION_PROMPT = (
    "Classify the user's request into exactly one category. Reply with only "
    "that one word: SIMPLE, CODE, REASONING, or CREATIVE.\n\n"
    "SIMPLE - factual lookups, definitions, basic how-to questions, simple "
    "programming syntax questions.\n"
    "  Example: \"Who is the president of France?\" -> SIMPLE\n"
    "  Example: \"What does the len() function do in Python?\" -> SIMPLE\n\n"
    "CODE - debugging a stack trace or error, or asking for code to solve a "
    "specific problem.\n"
    "  Example: \"Why am I getting a NullPointerException here?\" -> CODE\n"
    "  Example: \"Write a Python function to reverse a linked list.\" -> CODE\n\n"
    "REASONING - requires multi-step thinking, an in-depth explanation, or a "
    "philosophical/rhetorical question.\n"
    "  Example: \"Explain why the sky is blue in detail.\" -> REASONING\n"
    "  Example: \"Is it ethical to lie to protect someone's feelings?\" -> REASONING\n\n"
    "CREATIVE - asks you to generate, imagine, or write something new, or "
    "describes a hypothetical scenario.\n"
    "  Example: \"Write a short story about a dragon.\" -> CREATIVE\n"
    "  Example: \"Imagine if the internet had never been invented.\" -> CREATIVE"
)

MODEL_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"

class RoutingIntelligenceLayer:
    def __init__(self, repo_factory: ApplicationRepositoryFactory):
        model_path = Path(__file__).parent / "model" / MODEL_FILENAME
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
            # QdrantRepository.search() wraps a hit as {"response": <value>} -
            # return the category string itself, not the wrapper dict.
            return answer_from_vector_db["response"]

        else:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                partial(
                    self.local_llm.create_chat_completion,
                    messages=[
                        {"role": "system", "content": _CLASSIFICATION_PROMPT},
                        {"role": "user", "content": user_message},
                    ],
                    grammar=self.grammar,
                    max_tokens=10,
                ),
            )
            model_response = result["choices"][0]["message"]["content"].strip()
            print("The internal model gave - ", model_response)
            await self.vector_cache_repo.save(request_embedding, VectorRepositoryCollection.INTELLIGENCE_CLASSIFIER_CACHE,  user_message, model_response)

            return model_response
