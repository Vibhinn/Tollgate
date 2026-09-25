class ModelSemanticNotFound(Exception):
    pass

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

class SemanticCacheNotReachable(Exception):
    pass

class KVCacheNotReachable(Exception):
    pass