from dataclasses import dataclass

class InvalidAdminCredentials(Exception):
    pass

class ModelSemanticNotFound(Exception):
    pass

class NoHealthyModelAvailable(Exception):
    """Every model a policy could pick is benched right now. Temporary: a 503 the client retries."""
    def __init__(self, message: str, retry_after_seconds: int):
        super().__init__(message)
        self.headers = {"Retry-After": str(max(1, retry_after_seconds))}

class APIKeyInvalidOrExpired(Exception):
    pass

class PermissionDeniedForModel(Exception):
    pass

class CreditExhaustion(Exception):
    pass

class RateLimitedFromModelProvider(Exception):
    pass

class ModelProviderServerError(Exception):
    pass

class BadRequestToModel(Exception):
    pass

class APIError(Exception):
    pass

class CacheNotReachable(Exception):
    pass

class SemanticCacheNotReachable(CacheNotReachable):
    pass

class KVCacheNotReachable(CacheNotReachable):
    pass

@dataclass(frozen=True)
class ErrorSpec:
    status_code: int
    type: str
    code: str | None = None
