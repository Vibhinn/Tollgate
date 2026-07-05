from typing import Literal, overload, TYPE_CHECKING

if TYPE_CHECKING:
    from ..ports import (VectorEmbeddingRepositoryInterface,
                           VectorDBRepositoryInterface,
                           CacheRepositoryInterface,
                            RankingRepositoryInterface)
    from src.utils.types import REPOSITORY_TYPE


from src.cache import RedisRepository, QdrantRepository, RedisRankingRepository
from src.llm import Model2VecRepository
from src.utils import singleton

@singleton
class ApplicationRepositoryFactory:
    def __init__(self):
        self.__embedding_repo = Model2VecRepository()
        self.__redis_repo = RedisRepository()
        self.__vector_db_repo = QdrantRepository()
        self.__ranking_repo = RedisRankingRepository()

        self.__repo_map = {
            "EMBEDDING": self.__embedding_repo,
            "VECTOR_CACHE": self.__vector_db_repo,
            "EXACT_CACHE": self.__redis_repo,
            "RANKING": self.__ranking_repo
        }

    @overload
    def get_repo(self, repo_type: Literal["EMBEDDING"]) -> VectorEmbeddingRepositoryInterface: ...
    @overload
    def get_repo(self, repo_type: Literal["VECTOR_CACHE"]) -> VectorDBRepositoryInterface: ...
    @overload
    def get_repo(self, repo_type: Literal["EXACT_CACHE"]) -> CacheRepositoryInterface: ...
    @overload
    def get_repo(self, repo_type: Literal["RANKING"]) -> RankingRepositoryInterface: ...

    def get_repo(self, repo_type: REPOSITORY_TYPE) -> object:
        return self.__repo_map[repo_type]