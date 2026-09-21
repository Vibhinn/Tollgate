import threading
from typing import Callable, Type, TypeVar

T = TypeVar("T")

class DependencyContainer:
    def __init__(self):
        self._singleton: dict[type, Callable] = {}
        self._registry: dict[type, tuple[Callable, bool]] = {}
        self._lock = threading.RLock()

    def register(self, abstraction: Type[T], factory: Callable, singleton: bool = True) -> None:
        self._registry[abstraction] = (factory, singleton)

    def resolve(self, abstraction: Type[T]) -> T:
        if abstraction in self._singleton:
            return self._singleton[abstraction]

        if abstraction not in self._registry:
            raise ValueError(f"No registration found for {abstraction.__name__}")

        with self._lock:
            if abstraction in self._singleton:
                return self._singleton[abstraction]

            factory, is_singleton = self._registry[abstraction]
            instance = factory()

            if is_singleton:
                self._singleton[abstraction] = instance

            return instance
