class BaseMiddleware:
    registry = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseMiddleware.registry.append(cls)