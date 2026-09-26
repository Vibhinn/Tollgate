# Tollgate

**A self-hosted LLM gateway that routes, caches, and ranks AI model calls in real time.**

Tollgate abstracts away the need to specify LLM model names inside the request. 

We expose and OpenAI API like interface, and the developers do not need to manually add model names like `gpt-4o` or `claude-sonnet-4-6`. 

Simply ask Tollgate you want `"fast"` or `"cheap"` or `"smart"` — and it figures out which model wins *right now*, across OpenAI, Anthropic, and Google, based on live cost and latency data it collects from your own traffic.

---

## What It Does

Most teams use one model, on one provider, forever — because switching takes effort. Tollgate makes the model an implementation detail.

```
POST /api/v1/chat/completions
{
  "model": "cheap",          ← not a model name. a policy.
  "messages": [...]
}
```

Tollgate resolves `"cheap"` → the lowest-cost model it has observed recently, sends the request, streams back the response, and silently updates its rankings for next time. You get automatic cost savings without touching your application code.

---

## Architecture

```
                         ┌─────────────────────────────────────────────┐
                         │                   CLIENT                    │
                         │          POST /api/v1/chat/completions      │
                         └────────────────────┬────────────────────────┘
                                              │
                         ┌────────────────────▼────────────────────────┐
                         │              MIDDLEWARE STACK               │
                         │  ┌──────────────────────────────────────┐   │
                         │  │   AuthenticationMiddleware           │   │
                         │  │   Bearer token → Redis lookup        │   │
                         │  └──────────────────┬───────────────────┘   │
                         │  ┌──────────────────▼───────────────────┐   │
                         │  │   RateLimitingMiddleware             │   │
                         │  │   Token bucket  (10 tok / user)      │   │
                         │  └──────────────────┬───────────────────┘   │
                         └────────────────────┬────────────────────────┘
                                              │
                         ┌────────────────────▼────────────────────────┐
                         │               CHAT ADAPTER                  │
                         │                                             │
                         │  1. Exact cache lookup  (Redis)             │
                         │  2. Semantic cache lookup (Qdrant + EMA)    │
                         │  3. Route model selection                   │
                         │     ├── "fast"  → lowest latency model      │
                         │     ├── "cheap" → lowest cost model         │
                         │     ├── "smart" → highest quality model     │
                         │     └── "gpt-4o" → direct provider route    │
                         └────────────────────┬────────────────────────┘
                                              │
               ┌──────────────────────────────┼──────────────────────────────┐
               │                              │                              │
   ┌───────────▼──────────┐      ┌────────────▼────────────┐    ┌───────────▼──────────┐
   │     OpenAI           │      │     Anthropic           │    │      Gemini          │
   │  GPT-4o, o3-mini     │      │  Opus, Sonnet, Haiku    │    │  2.0-flash, 1.5-pro  │
   │  GPT-4-turbo, mini   │      │                         │    │  flash-lite          │
   └───────────┬──────────┘      └────────────┬────────────┘    └───────────┬──────────┘
               └──────────────────────────────┼──────────────────────────────┘
                                              │ response + usage metrics
                                              │
                         ┌────────────────────▼────────────────────────┐
                         │             REDIS STREAMS QUEUE             │
                         │                                             │
                         │   RESPONSE_CACHE stream                     │
                         │   └─ writes to Redis (exact) + Qdrant       │
                         │                                             │
                         │   ANALYTICS stream                          │
                         │   └─ updates EMA rankings per model         │
                         └─────────────────────────────────────────────┘
```

### Dual-Layer Cache

| Layer | Backend | Match Strategy | Threshold |
|---|---|---|---|
| Exact | Redis | Hash of messages + model | Identical queries |
| Semantic | Qdrant + model2vec | Cosine similarity, 256-dim vectors | 0.9 similarity |

Cache hits skip the LLM entirely. Semantic cache catches paraphrased duplicates that exact matching misses.

### Live Model Ranking

Every completed request feeds an Exponential Moving Average (EMA) per model, per metric:

```
new_score = 0.1 × current_measurement + 0.9 × previous_score
```

Stored in Redis sorted sets. `"cheap"` and `"fast"` queries are O(1) lookups (`ZRANGE ... 0 0`). Rankings automatically adapt to provider outages, pricing changes, and load spikes — no config changes needed.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + Uvicorn (async) |
| Exact cache | Redis 7 |
| Semantic cache | Qdrant |
| Embeddings | model2vec (`minishlab/potion-base-8M`) |
| Job queue | Redis Streams |
| LLM SDKs | `openai`, `anthropic`, `google-genai` |
| Auth | Token-bucket rate limiting + Bearer tokens |
| DI | Custom IoC container (no third-party framework) |
| Infra | Docker Compose |

---

## API

```bash
# 1. Generate an access token
curl -X POST http://localhost:13000/api/v1/chat/generate \
  -H "Content-Type: application/json" \
  -d '{"requirement": "chat"}'

# 2. Call the gateway — use a policy, not a model name
curl -X POST http://localhost:13000/api/v1/chat/completions \
  -H "Authorization: Bearer tg_<your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "cheap",
    "messages": [{"role": "user", "content": "Summarize this contract"}],
    "cache_type": "SEMANTIC"
  }'

# Or pin a specific model directly
  -d '{"model": "claude-sonnet-4-6", ...}'
```

**Model values:** `"cheap"` `"fast"` `"smart"` or any literal model name (`"gpt-4o"`, `"claude-haiku-4-5"`, `"gemini-2.0-flash"`, ...)

**Optional headers:**
- `X-Cache-TTL: 3600` — override cache TTL in seconds

---

## Running Locally

```bash
# Start Redis and Qdrant
docker compose -f docker/docker-compose.yml up -d

# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp config.ini.example config.ini
# Edit config.ini with your OpenAI / Anthropic / Gemini keys

# Start the gateway
uvicorn main:app --port 13000 --reload
```

Swagger docs at `http://localhost:13000/docs`.

---

## Roadmap

```
DONE ──────────────────────────────────────────────────────────── IN PROGRESS ──── PLANNED
  │                                                                      │               │
  ▼                                                                      ▼               ▼
```

| #  | Feature | Status |
|----|---|---|
| 1  | Multi-provider routing (OpenAI, Anthropic, Gemini) | ✅ Done |
| 2  | Bearer token auth + BYOK token generation | ✅ Done |
| 3  | Token bucket rate limiting with `Retry-After` | ✅ Done |
| 4  | Exact cache (Redis) with configurable TTL | ✅ Done |
| 5  | Semantic cache (Qdrant + model2vec embeddings) | ✅ Done |
| 6  | Redis Streams async job queue for cache + analytics | ✅ Done |
| 7  | Live EMA-based cost and latency ranking per model | ✅ Done |
| 8  | `"cheap"` / `"fast"` / `"smart"` policy routing | ✅ Done |
| 9  | Ports & adapters architecture with custom DI container | ✅ Done |
| 10 | Add a dedicated CLI to setup the proxy on end user | ✅ Done |
| 11 | Analytics dashboard endpoint (data collected, API stub) | 🔧 In Progress |
| 12 | Gemini provider fully wired (config exists, adapter pending) | ✅ Done |
| 13 | `"smart"` routing via quality ranking (currently pinned to Opus) | ✅ Done |
| 14 | Production-grade stream listener stability (cross-event-loop) | 🔧 In Progress |
| 15 | Streaming responses (SSE / chunked transfer) | 🔧 In Progress |
| 16 | Per-token budget enforcement and cost caps | 📋 Planned |
| 17 | Fallback chains (primary → fallback on error/timeout) | ✅ Done |
| 18 | Multi-tenant routing with isolated rate limits | 📋 Planned |
| 19 | OpenAI-compatible `/v1/chat/completions` drop-in API | ✅ Done |

---

## Project Structure (for the nerds)

```
Tollgate/
├── main.py                    # FastAPI app, lifespan, route registration
├── config.ini                 # API keys, rate limiter config
├── docker/
│   └── docker-compose.yml     # Redis + Qdrant
└── src/
    ├── app/
    │   ├── adapters/           # ChatAdapter, RouterAdapter, TokenAdapter
    │   ├── endpoints/          # HTTP route handlers
    │   ├── factory/            # LLM repository factory
    │   ├── injector/           # IoC container
    │   ├── limiter/            # Token bucket implementation
    │   ├── middleware/          # Auth + rate limiting middleware
    │   ├── migrations/          # Qdrant collection setup
    │   ├── ports/              # Abstract interfaces (Repository protocols)
    │   ├── state/              # App-level state (connections, registrations)
    │   └── validators/          # Pydantic request/response models
    ├── cache/
    │   ├── redis/              # Exact cache + stream publisher
    │   └── qdrant/             # Semantic cache + vector search
    ├── jobs/
    │   ├── worker.py           # Background stream consumer
    │   └── helpers/            # CacheJobHelper, AnalyticsJobHelper
    ├── llm/
    │   ├── openai/             # AsyncOpenAI wrapper
    │   ├── anthropic/          # AsyncAnthropic wrapper
    │   └── model2vec/          # Embedding repository
    ├── router/
    │   ├── core/
    │   │   └── pricing.py      # Token pricing table (all providers)
    │   └── repository.py       # Model selection + EMA ranking
    └── utils/                  # Config loader, shared types, decorators
```

---

*Built with Python 3.14 · FastAPI · Redis · Qdrant · OpenAI SDK · Anthropic SDK · Google GenAI SDK*
