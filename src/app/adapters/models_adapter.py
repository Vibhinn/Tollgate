from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.router import RouterRepository


class ModelsAdapter:
    def __init__(self, router_manager: RouterRepository):
        self.router_repo = router_manager
        self._MODEL_SELECTION_POLICIES = ("fast", "cheap", "smart")
        self._POLICY_OWNER = "tollgate"

    def list_models(self) -> dict[str, str]:
        return {
            **{policy: self._POLICY_OWNER for policy in self._MODEL_SELECTION_POLICIES},
            **self.router_repo.available_models(),
        }
