from typing import Literal, overload

from src.app.ports import VectorEmbeddingRepositoryInterface, VectorDBRepositoryInterface
from src.cache import RedisRepository, QdrantRepository
from src.llm import Model2VecRepository
from src.router import RouterRepository

from src.utils.types import REPOSITORY_TYPE
from src.utils import singleton

@singleton
class RepositoryManagementFactory:
    def __init__(self):
        self.__embedding_repo = Model2VecRepository()
        self.__redis_repo = RedisRepository()
        self.__vector_db_repo = QdrantRepository()
        self.__router_repo = RouterRepository()

        self.__repo_map = {
            "EMBEDDING": self.__embedding_repo,
            "VECTOR_CACHE": self.__vector_db_repo,
            "EXACT_CACHE": self.__redis_repo,
            "ROUTER": self.__router_repo
        }

    @overload
    def get_repo(self, repo_type: Literal["EMBEDDING"]) -> VectorEmbeddingRepositoryInterface: ...
    @overload
    def get_repo(self, repo_type: Literal["VECTOR_CACHE"]) -> VectorDBRepositoryInterface: ...
    @overload
    def get_repo(self, repo_type: Literal["EXACT_CACHE"]) -> RedisRepository: ...
    @overload
    def get_repo(self, repo_type: Literal["ROUTER"]) -> RouterRepository: ...

    def get_repo(self, repo_type: REPOSITORY_TYPE) -> object:
        return self.__repo_map[repo_type]