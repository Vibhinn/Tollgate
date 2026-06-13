from src.utils.types import Message
from src.utils.config import ROUTING_TABLE
from src.llm import LLMRepositoryFactory

class RouterRepository:
    def __init__(self):
        self.routing_table = ROUTING_TABLE
        self.repo_factory = LLMRepositoryFactory()

    async def invoke_model(self, model_name: str, message: list[Message]) -> object:
        repository_name: str = self.routing_table.get(model_name).get("provider")
        repository = self.repo_factory.get_repo(repository_name)

        if not repository:
            return None

        model_response = await repository.invoke(message, model_name)
        return model_response

    async def get_best_model(self, requirement: str) -> str:
        pass
