from .dependency_container import DependencyContainer
from .inject import get_chat_adapter

container = DependencyContainer()

__all__ = ["container", "get_chat_adapter"]