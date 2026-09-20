from unittest.mock import MagicMock

import numpy as np
import pytest

from src.llm.connection import LLMConnection
from src.llm.repository.model2vec_repository import Model2VecRepository


@pytest.fixture
def embedding_model(monkeypatch):
    model = MagicMock()
    model.encode.return_value = np.zeros((1, 256))
    monkeypatch.setattr(LLMConnection, "get_connection", classmethod(lambda cls, p: model))
    return model


def test_construction_does_not_require_a_running_event_loop(embedding_model):
    """Regression test: __init__ used to eagerly call asyncio.get_event_loop(),
    which raises RuntimeError with no loop running - exactly the situation
    during real app startup, where this is constructed synchronously via the
    DI container before uvicorn's event loop exists."""
    Model2VecRepository()


async def test_create_vector_embeddings_returns_the_actual_result_not_a_future(embedding_model):
    repo = Model2VecRepository()

    result = await repo.create_vector_embeddings("hello")

    embedding_model.encode.assert_called_once_with(["hello"])
    assert isinstance(result, np.ndarray)
    assert result.shape == (1, 256)
