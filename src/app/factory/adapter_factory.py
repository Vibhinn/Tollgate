from typing import overload, Literal

from ..adapters import ChatAdapter
from .repository_factory import RepositoryManagementFactory

from src.utils import singleton

from src.utils.types import ADAPTER_TYPE

@singleton
class AdapterManagementFactory:
    def __init__(self, repo_factory: RepositoryManagementFactory):
        self.__chat_adapter = ChatAdapter(repo_factory)

        self.__adapter_map = {
            "CHAT": self.__chat_adapter
        }

    @overload
    def get_adapter(self, adapter_name: Literal["CHAT"]) -> ChatAdapter: ...
    @overload
    def get_adapter(self, adapter_name: Literal["IMAGE"]) -> ChatAdapter: ...

    def get_adapter(self, adapter_name: ADAPTER_TYPE):
        return self.__adapter_map.get(adapter_name)
