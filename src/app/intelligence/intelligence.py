import subprocess
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
from openai import AsyncOpenAI

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

_GRAMMAR = r'root ::= "SIMPLE" | "CODE" | "REASONING" | "CREATIVE"'

MODEL_FILENAME = "qwen2.5-1.5b-instruct-q4_k_m.gguf"
SERVER_BINARY_NAME = "llama-server"
SERVER_HOST = "127.0.0.1"
SERVER_PORT = 8091
_READINESS_TIMEOUT_SECONDS = 30


class RoutingIntelligenceLayer:
    def __init__(self, repo_factory: ApplicationRepositoryFactory):
        model_path = Path(__file__).parent / "model" / MODEL_FILENAME
        server_binary = Path(__file__).parent / "server" / SERVER_BINARY_NAME

        self._server_process = subprocess.Popen([
            str(server_binary),
            "-m", str(model_path),
            "-c", "2048",
            "--host", SERVER_HOST,
            "--port", str(SERVER_PORT),
            "-ngl", "99",
        ])
        self._wait_until_ready()

        self.client = AsyncOpenAI(base_url=f"http://{SERVER_HOST}:{SERVER_PORT}/v1", api_key="not-required")

        self.embedding_model_repo = repo_factory.get_repo(ApplicationRepositoryType.EMBEDDING)
        self.vector_cache_repo = repo_factory.get_repo(ApplicationRepositoryType.VECTOR_CACHE)

    def _wait_until_ready(self) -> None:
        deadline = time.monotonic() + _READINESS_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if self._server_process.poll() is not None:
                raise RuntimeError(
                    f"{SERVER_BINARY_NAME} exited (code {self._server_process.returncode}) before becoming ready"
                )
            try:
                if httpx.get(f"http://{SERVER_HOST}:{SERVER_PORT}/health", timeout=1).status_code == 200:
                    return
            except httpx.TransportError:
                pass
            time.sleep(0.2)
        raise TimeoutError(f"{SERVER_BINARY_NAME} did not become ready within {_READINESS_TIMEOUT_SECONDS}s")

    def shutdown(self) -> None:
        self._server_process.terminate()
        try:
            self._server_process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._server_process.kill()

    async def classify(self, user_message: str) -> str:
        request_embedding = await self.embedding_model_repo.create_vector_embeddings(user_message)
        answer_from_vector_db = await self.vector_cache_repo.search(collection=VectorRepositoryCollection.INTELLIGENCE_CLASSIFIER_CACHE,
                                                                    embedding=request_embedding,
                                                                    score_threshold=0.7)

        if answer_from_vector_db:
            # QdrantRepository.search() wraps a hit as {"response": <value>} -
            # return the category string itself, not the wrapper dict.
            return answer_from_vector_db["response"]

        result = await self.client.chat.completions.create(
            model="qwen",  # llama-server serves whatever single model it was started with - this is ignored
            messages=[
                {"role": "system", "content": _CLASSIFICATION_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=10,
            extra_body={"grammar": _GRAMMAR},
        )
        model_response = result.choices[0].message.content.strip()
        await self.vector_cache_repo.save(request_embedding, VectorRepositoryCollection.INTELLIGENCE_CLASSIFIER_CACHE, user_message, model_response)

        return model_response
