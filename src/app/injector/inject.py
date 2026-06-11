from ..adapters import ChatAdapter
from src.app.injector import container

def get_chat_adapter() -> ChatAdapter:
    return container.resolve(ChatAdapter)
