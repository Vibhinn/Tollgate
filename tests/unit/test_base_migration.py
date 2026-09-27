"""Tests for BaseMigration.run_all()'s per-migration resilience.

An unreachable Redis/Qdrant at startup used to crash the whole app (see
main.py's lifespan) - which also makes `docker exec` unusable exactly when
you need it to fix the bad host/port via `tollgate config --change`. Catching
CacheNotReachable per-migration (not around the whole loop) also means one
migration being unreachable doesn't stop every migration after it from even
being attempted.
"""
import pytest

from src.app.exceptions import KVCacheNotReachable, SemanticCacheNotReachable
from src.app.migrations.base import BaseMigration


@pytest.fixture(autouse=True)
def clean_registry():
    original = list(BaseMigration._registry)
    BaseMigration._registry.clear()
    yield
    BaseMigration._registry.clear()
    BaseMigration._registry.extend(original)


def _register(up_side_effect):
    calls = []

    class _FakeMigration(BaseMigration):
        async def up(self):
            calls.append(self)
            if up_side_effect is not None:
                raise up_side_effect

    return calls


async def test_run_all_runs_every_registered_migration_when_nothing_fails():
    first_calls = _register(None)
    second_calls = _register(None)

    await BaseMigration.run_all()

    assert len(first_calls) == 1
    assert len(second_calls) == 1


async def test_run_all_continues_past_a_cache_not_reachable_migration(capsys):
    _register(SemanticCacheNotReachable("qdrant is down"))
    second_calls = _register(None)

    await BaseMigration.run_all()  # must not raise

    assert len(second_calls) == 1
    assert "qdrant is down" in capsys.readouterr().err


async def test_run_all_continues_past_a_kv_cache_not_reachable_migration():
    _register(KVCacheNotReachable("redis is down"))
    second_calls = _register(None)

    await BaseMigration.run_all()  # must not raise

    assert len(second_calls) == 1


async def test_run_all_does_not_swallow_a_genuine_bug():
    _register(TypeError("this is a real bug in the migration, not a reachability issue"))

    with pytest.raises(TypeError):
        await BaseMigration.run_all()
