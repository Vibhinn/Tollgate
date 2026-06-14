from .dependency_container import DependencyContainer

container = DependencyContainer()

from .inject import get_chat_adapter, get_config_object, get_generate_token_adapter


__all__ = ["container", "get_chat_adapter", "get_config_object", "get_generate_token_adapter"]