from src.llm import LLMConnection

class LLMCostCalculator:
    def __init__(self):
        self.connection_manager = LLMConnection()

    async def calculate_cost(self):