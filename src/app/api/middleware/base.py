TOKEN_VALUE_STATE_KEY = "user_id"

# set by inner layers, read by RequestMetricsMiddleware once the response is sent
IDENTITY_STATE_KEY = "identity"          # TokenIdentity, set by auth
REJECTED_BY_STATE_KEY = "rejected_by"    # "rate_limit" / "backpressure"
COMPLETION_STATE_KEY = "completion"      # model, tokens and cache outcome, set by the chat endpoint


class BaseMiddleware:
    registry = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls not in BaseMiddleware.registry:
            BaseMiddleware.registry.append(cls)
