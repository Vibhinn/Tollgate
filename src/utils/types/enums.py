from enum import Enum, StrEnum


class ConfigurationEnums(Enum):
    API_KEY_NOT_CONFIGURED = "NOT_CONFIGURED"


class LLMProvider(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"
    EMBEDDING = "embedding"


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


class VectorRepositoryCollection(StrEnum):
    SEMANTIC_CACHE = "semantic_cache"
    INTELLIGENCE_CLASSIFIER_CACHE = "intelligence_classifier_cache"


class ConfigurationSection(StrEnum):
    MODELS = "models"
    EMBEDDING = "embedding"
    RATE_LIMITER = "rate_limiter"
    GATEWAY = "gateway"


class ConfigurationOption(StrEnum):
    ENDPOINT = "endpoint"
    API_KEY = "api_key"
    MODEL_NAME = "model_name"
    MAX_TOKENS = "max_tokens"
    REFILL_RATE = "refill_rate"
    TIME_INTERVAL = "time_interval"
    DEFAULT_MODEL = "default_model"


class ConfigurationSubSection(StrEnum):
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GEMINI = "gemini"


class QueueType(StrEnum):
    REDIS_STREAM = "redis_stream"


class AdapterType(StrEnum):
    CHAT = "chat"

class RedisAtomicCounters(StrEnum):
    SUCCESSFUL = "successful"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    REJECTED = "rejected"