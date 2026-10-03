from __future__ import annotations

from typing import Literal, overload, TYPE_CHECKING

if TYPE_CHECKING:
    from ..ports import (VectorEmbeddingRepositoryInterface,
                           VectorDBRepositoryInterface,
                           CacheRepositoryInterface,
                            RankingRepositoryInterface)
    from src.utils.types import REPOSITORY_TYPE

from src.utils.types import ApplicationRepositoryType

class ApplicationRepositoryFactory:
    def __init__(self,
                 embedding_repo: VectorEmbeddingRepositoryInterface,
                 redis_repo: CacheRepositoryInterface,
                 vector_db_repo: VectorDBRepositoryInterface,
                 ranking_repo: RankingRepositoryInterface):
        self.__embedding_repo = embedding_repo
        self.__redis_repo = redis_repo
        self.__vector_db_repo = vector_db_repo
        self.__ranking_repo = ranking_repo

        self.__repo_map = {
            ApplicationRepositoryType.EMBEDDING: self.__embedding_repo,
            ApplicationRepositoryType.VECTOR_CACHE: self.__vector_db_repo,
            ApplicationRepositoryType.EXACT_CACHE: self.__redis_repo,
            ApplicationRepositoryType.RANKING: self.__ranking_repo
        }

    @overload
    def get_repo(self, repo_type: Literal[ApplicationRepositoryType.EMBEDDING]) -> VectorEmbeddingRepositoryInterface: ...
    @overload
    def get_repo(self, repo_type: Literal[ApplicationRepositoryType.VECTOR_CACHE]) -> VectorDBRepositoryInterface: ...
    @overload
    def get_repo(self, repo_type: Literal[ApplicationRepositoryType.EXACT_CACHE]) -> CacheRepositoryInterface: ...
    @overload
    def get_repo(self, repo_type: Literal[ApplicationRepositoryType.RANKING]) -> RankingRepositoryInterface: ...

    def get_repo(self, repo_type: REPOSITORY_TYPE) -> object:
        return self.__repo_map[repo_type]