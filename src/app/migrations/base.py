class BaseMigration:
    _registry: list[type["BaseMigration"]] = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseMigration._registry.append(cls)

    def up(self) -> None:
        """Apply the migration"""
        raise NotImplementedError

    @classmethod
    def run_all(cls):
        for migration_cls in cls._registry:
            migration = migration_cls()
            migration.up()