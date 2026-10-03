TOKEN_VALUE_STATE_KEY = "user_id"


class BaseMiddleware:
    registry = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls not in BaseMiddleware.registry:
            BaseMiddleware.registry.append(cls)
