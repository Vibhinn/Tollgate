from unittest.mock import MagicMock

import pytest

from src.app.adapters import MetricsAdapter
from src.utils.types import TokenIdentity


def identity(role):
    return TokenIdentity(user_id="ops:dashboard", team="ops", name="dashboard", token_id="abc123", role=role)


@pytest.fixture
def adapter():
    aggregator = MagicMock(snapshot={"view": "gateway"}, admin_snapshot={"view": "admin"})
    return MetricsAdapter(aggregator)


def test_an_admin_token_gets_the_full_breakdown(adapter):
    assert adapter.snapshot_for(identity("admin")) == {"view": "admin"}


@pytest.mark.parametrize("who", [identity("user"), None])
def test_everyone_else_gets_the_gateway_wide_view(adapter, who):
    assert adapter.snapshot_for(who) == {"view": "gateway"}
