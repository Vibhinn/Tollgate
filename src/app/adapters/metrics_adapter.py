from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.utils.tokens import ROLE_ADMIN

if TYPE_CHECKING:
    from src.jobs import MetricsAggregator
    from src.utils.types import TokenIdentity


class MetricsAdapter:
    def __init__(self, aggregator: MetricsAggregator):
        self.aggregator = aggregator

    def snapshot_for(self, identity: TokenIdentity | None) -> dict[str, Any] | None:
        """Admins see the breakdown per team, user and token; everyone else the gateway-wide numbers."""
        if identity is not None and identity.role == ROLE_ADMIN:
            return self.aggregator.admin_snapshot
        return self.aggregator.snapshot
