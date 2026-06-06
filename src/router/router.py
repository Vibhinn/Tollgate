from .providers import ROUTING_TABLE
from src.llm import LLMRepositoryFactory

class RouterRepository:
    def __init__(self):
        self.routing_table = ROUTING_TABLE
        self.repo_factory = LLMRepositoryFactory()

    async def invoke_model(self, model_name: str, message: str) -> object:
        repository_name: str = self.routing_table.get(model_name).get("provider")
        repository = self.repo_factory.get_repo(repository_name)

        if not repository:
            return None

        model_response = await repository.invoke(message)
        return model_response
