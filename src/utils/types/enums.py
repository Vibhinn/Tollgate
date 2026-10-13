from enum import Enum, StrEnum


class ConfigurationEnums(Enum):
    API_KEY_NOT_CONFIGURED = "NOT_CONFIGURED"


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    EMBEDDING = "embedding"
    SELF_HOSTED = "self_hosted"


class CacheType(StrEnum):
    EXACT = "exact"
    SEMANTIC = "semantic"


class ApplicationRepositoryType(StrEnum):
    EMBEDDING = "embedding"
    VECTOR_CACHE = "vector_cache"
    EXACT_CACHE = "exact_cache"
    RANKING = "ranking"


class RedisStreamName(StrEnum):
    RESPONSE_CACHE = "response_cache"
    ANALYTICS = "analytics"
    LOGGING = "logging"


class VectorRepositoryCollection(StrEnum):
    SEMANTIC_CACHE = "semantic_cache"
    INTELLIGENCE_CLASSIFIER_CACHE = "intelligence_classifier_cache"


class ConfigurationSection(StrEnum):
    MODELS = "models"
    EMBEDDING = "embedding"
    RATE_LIMITER = "rate_limiter"
    BACKPRESSURE = "backpressure"
    GATEWAY = "gateway"
    REDIS = "redis"
    QDRANT = "qdrant"
    ADMIN = "admin"


class ConfigurationOption(StrEnum):
    USERNAME = "username"
    PASSWORD_HASH = "password_hash"
    ENDPOINT = "endpoint"
    API_KEY = "api_key"
    MODEL_NAME = "model_name"
    MAX_TOKENS = "max_tokens"
    REFILL_RATE = "refill_rate"
    TIME_INTERVAL = "time_interval"
    MAX_IN_FLIGHT = "max_in_flight"
    DEFAULT_MODEL = "default_model"
    HOST = "host"
    PORT = "port"
    PASSWORD = "password"
    TLS = "tls"
    HTTPS = "https"


class ConfigurationSubSection(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"

class ConfigurationValue(StrEnum):
    SELF_HOSTED_NO_AUTH_PLACEHOLDER = "not-required"

class QueueType(StrEnum):
    REDIS_STREAM = "redis_stream"


class AdapterType(StrEnum):
    CHAT = "chat"

class RedisAtomicCounters(StrEnum):
    RESPONSES_2XX = "responses_2xx"
    RESPONSES_4XX = "responses_4xx"
    RESPONSES_5XX = "responses_5xx"
    RATE_LIMITED = "rate_limited"
    IN_FLIGHT = "in_flight"
    SHED = "shed"
    CACHE_EXACT_HITS = "cache_exact_hits"
    CACHE_SEMANTIC_HITS = "cache_semantic_hits"
    CACHE_MISSES = "cache_misses"
    NO_MODEL_AVAILABLE = "no_model_available"
