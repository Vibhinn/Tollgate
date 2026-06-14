from src.utils.types import Message
from src.utils.config import ROUTING_TABLE
from src.llm import LLMRepositoryFactory

class RouterRepository:
    def __init__(self, llm_repo_factory: LLMRepositoryFactory):
        self.routing_table = ROUTING_TABLE
        self.llm_repo_factory = llm_repo_factory

    async def invoke_model(self, model_name: str, message: list[Message]) -> object:
        repository_name: str = self.routing_table.get(model_name).get("provider")
        repository = self.llm_repo_factory.get_repo(repository_name)

        if not repository:
            return None

        model_response = await repository.invoke(message[-1].content, model_name)
        return model_response

    async def get_best_model(self, requirement: str) -> str:
        pass
