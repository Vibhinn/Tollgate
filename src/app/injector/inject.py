from src.utils.config import Config
from src.app.injector import container

from ..adapters import ChatAdapter

def get_chat_adapter() -> ChatAdapter:
    return container.resolve(ChatAdapter)

def get_config_object() -> Config:
    return container.resolve(Config)

