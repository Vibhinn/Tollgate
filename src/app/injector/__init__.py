from .dependency_container import DependencyContainer

container = DependencyContainer()

from .inject import get_chat_adapter, get_models_adapter, get_metrics_adapter, get_admin_adapter, get_config_object


__all__ = ["container", "get_chat_adapter", "get_models_adapter", "get_metrics_adapter", "get_admin_adapter", "get_config_object"]