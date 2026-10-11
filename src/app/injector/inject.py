from src.utils.config import Config
from src.app.injector import container

from ..adapters import ChatAdapter, ModelsAdapter, MetricsAdapter


def get_chat_adapter() -> ChatAdapter:
    return container.resolve(ChatAdapter)

def get_models_adapter() -> ModelsAdapter:
    return container.resolve(ModelsAdapter)

def get_metrics_adapter() -> MetricsAdapter:
    return container.resolve(MetricsAdapter)

def get_config_object() -> Config:
    return container.resolve(Config)