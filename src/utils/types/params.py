from typing import Literal

from .enums import (
    LLMProvider,
    CacheType,
    ApplicationRepositoryType,
    RedisStreamName,
    VectorRepositoryCollection,
    ConfigurationSection,
    ConfigurationOption,
    ConfigurationSubSection,
    QueueType,
    AdapterType,
    RedisAtomicCounters
)

REDIS_STREAM_NAMES = Literal[RedisStreamName.RESPONSE_CACHE, RedisStreamName.ANALYTICS]
REPOSITORY_TYPE = Literal[
    ApplicationRepositoryType.EMBEDDING,
    ApplicationRepositoryType.VECTOR_CACHE,
    ApplicationRepositoryType.EXACT_CACHE,
    ApplicationRepositoryType.RANKING,
]
ADAPTER_TYPE = Literal[AdapterType.CHAT]

CONFIGURATION_SECTIONS = Literal[
    ConfigurationSection.MODELS,
    ConfigurationSection.EMBEDDING,
    ConfigurationSection.RATE_LIMITER,
    ConfigurationSection.GATEWAY,
]
CONFIGURATION_OPTIONS = Literal[
    ConfigurationOption.ENDPOINT,
    ConfigurationOption.API_KEY,
    ConfigurationOption.MODEL_NAME,
    ConfigurationOption.MAX_TOKENS,
    ConfigurationOption.REFILL_RATE,
    ConfigurationOption.TIME_INTERVAL,
    ConfigurationOption.DEFAULT_MODEL,
]
CONFIGURATION_SUB_SECTIONS = Literal[
    ConfigurationSubSection.OPENAI,
    ConfigurationSubSection.ANTHROPIC,
    ConfigurationSubSection.GEMINI,
    None,
]

LLM_PROVIDER = Literal[
    LLMProvider.OPENAI,
    LLMProvider.ANTHROPIC,
    LLMProvider.GEMINI,
    LLMProvider.EMBEDDING,
]
QUEUE_TYPE = Literal[QueueType.REDIS_STREAM]

CACHE_TYPE = Literal[CacheType.EXACT, CacheType.SEMANTIC]

VECTOR_REPOSITORY_COLLECTIONS = Literal[
    VectorRepositoryCollection.SEMANTIC_CACHE,
    VectorRepositoryCollection.INTELLIGENCE_CLASSIFIER_CACHE,
]

ATOMIC_COUNTERS = Literal[
    RedisAtomicCounters.FAILED,
    RedisAtomicCounters.SUCCESSFUL,
    RedisAtomicCounters.RATE_LIMITED
]