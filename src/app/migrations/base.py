import sys

from src.app.exceptions import CacheNotReachable


class BaseMigration:
    _registry: list[type["BaseMigration"]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseMigration._registry.append(cls)

    async def up(self) -> None:
        """Apply the migration"""
        raise NotImplementedError

    @classmethod
    async def run_all(cls):
        for migration_cls in cls._registry:
            migration = migration_cls()
            try:
                await migration.up()
            except CacheNotReachable as exc:
                print(
                    f"WARNING: migration {migration_cls.__name__} failed ({exc}). Continuing startup - "
                    "requests needing this will fail until it's fixed. Run `tollgate config --change` "
                    "to correct the host/port, then restart the gateway.",
                    file=sys.stderr,
                )