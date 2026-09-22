class ModelSemanticNotFound(Exception):
    pass

class APIKeyExpired(Exception):
    pass

class PermissionDeniedForModel(Exception):
    pass

class CreditExhaustion(Exception):
    pass

class RateLimitedFromModelProvider(Exception):
    pass

class ModelProviderServerError(Exception):
    pass