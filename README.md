# Tollgate

**A self-hosted LLM gateway that routes, caches, and ranks AI model calls in real time.**

Tollgate abstracts away the need to specify LLM model names inside the request.

Developers do not need to hardcode model names like `gpt-4o` or `claude-sonnet-4-6`. Simply ask Tollgate for `"fast"`, `"cheap"` or `"smart"` — and it figures out which model wins *right now*, across OpenAI, Anthropic, Google and your own self-hosted models, based on pricing, live latency data collected from your own traffic, and a local classifier that reads the prompt.

---

## What It Does

Most teams use one model, on one provider, forever — because switching takes effort. Tollgate makes the model an implementation detail.

```
POST /api/v1/chat/completions
{
  "model": "cheap",          ← not a model name. a policy.
  "messages": [...],
  "max_tokens": 256
}
```

Tollgate resolves `"cheap"` → the lowest-cost model that is configured and currently healthy, sends the request, returns the response, and silently updates its rankings for next time. If that model fails (rate limited, out of credits, provider outage), it's benched for a while and the request falls back to the next best one.

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
                         │  │   Token bucket (in-process memory)   │   │
                         │  └──────────────────┬───────────────────┘   │
                         └────────────────────┬────────────────────────┘
                                              │
                         ┌────────────────────▼────────────────────────┐
                         │               CHAT ADAPTER                  │
                         │                                             │
                         │  1. Exact cache lookup  (Redis)             │
                         │  2. Semantic cache lookup (Qdrant)          │
                         │  3. Route model selection                   │
                         │     ├── "fast"  → lowest latency EMA        │
                         │     ├── "cheap" → lowest price (pricing.py) │
                         │     ├── "smart" → local classifier ─┐       │
                         │     └── "gpt-4o" → direct route     │       │
                         └────────────────────┬────────────────┼───────┘
                                              │                │
                                              │   ┌────────────▼──────────────┐
                                              │   │  ROUTING INTELLIGENCE     │
                                              │   │  llama-server (subprocess)│
                                              │   │  Qwen2.5-1.5B Q4_K_M      │
                                              │   │  SIMPLE / CODE /          │
                                              │   │  REASONING / CREATIVE     │
                                              │   │  answers cached in Qdrant │
                                              │   └───────────────────────────┘
                                              │
     ┌───────────────────────┬────────────────┼───────────────────┬───────────────────────┐
     │                       │                │                   │                       │
┌────▼─────────────┐ ┌───────▼──────────┐ ┌───▼──────────────┐ ┌──▼────────────────────┐
│     OpenAI       │ │    Anthropic     │ │     Gemini       │ │     Self-hosted       │
│ GPT-4o, 4o-mini  │ │ Opus, Sonnet,    │ │ 3.5-flash,       │ │ Any OpenAI-compatible │
│ 4-turbo, o1, o3- │ │ Haiku            │ │ 3.5-flash-lite   │ │ endpoint (Ollama,     │
│ mini, 3.5-turbo  │ │                  │ │                  │ │ llama.cpp, vLLM ...)  │
└────┬─────────────┘ └───────┬──────────┘ └───┬──────────────┘ └──┬────────────────────┘
     └───────────────────────┴────────────────┼───────────────────┘
                                              │ response + usage metrics
                                              │
                         ┌────────────────────▼────────────────────────┐
                         │             REDIS STREAMS QUEUE             │
                         │     (consumed by an in-process asyncio      │
                         │      worker, consumer group + DLQ)          │
                         │                                             │
                         │   RESPONSE_CACHE stream                     │
                         │   └─ writes to Redis (exact) or Qdrant      │
                         │                                             │
                         │   ANALYTICS stream                          │
                         │   └─ updates latency EMA per model          │
                         └─────────────────────────────────────────────┘
```

### Dual-Layer Cache

| Layer | Backend | Match Strategy | Threshold |
|---|---|---|---|
| Exact | Redis | Exact text of the last user message | Identical queries |
| Semantic | Qdrant + model2vec | Cosine similarity, 256-dim vectors | `cache_match_score` (default 0.9) |

Cache hits skip the LLM entirely. Semantic cache catches paraphrased duplicates that exact matching misses. Writes are opt-in per request via `cache_type` and happen asynchronously through Redis Streams, so they never add latency to the response.

### Model Selection

| Policy | How it picks |
|---|---|
| `"fast"` | Lowest latency EMA among models not currently benched |
| `"cheap"` | Lowest average input/output price from `src/router/core/pricing.py`, among configured, non-benched models |
| `"smart"` | A local Qwen2.5-1.5B model classifies the prompt into `SIMPLE` / `CODE` / `REASONING` / `CREATIVE`; each category has a preference list of models (`src/router/core/smart.py`) |

Every completed request feeds an Exponential Moving Average (EMA) of latency per model:

```
new_score = 0.1 × current_measurement + 0.9 × previous_score
```

Scores live in a Redis sorted set, so `"fast"` is a `ZRANGE` away. On startup, Tollgate sends a tiny probe to every configured model to seed the rankings before real traffic arrives.

When a provider call fails, the model is **benched** with a TTL — 600s for auth / credit / permission errors, 30s for rate limits and server errors — and policy requests fall back to the next best model.

---

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI + Uvicorn (async) |
| Exact cache | Redis 7 |
| Semantic cache | Qdrant (gRPC) |
| Embeddings | model2vec (`minishlab/potion-base-8M`) |
| Prompt classifier | llama.cpp `llama-server` + Qwen2.5-1.5B-Instruct (Q4_K_M GGUF) |
| Job queue | Redis Streams (consumer groups, dead-letter stream) |
| LLM SDKs | `openai`, `anthropic`, `google-genai` |
| Auth | Bearer tokens in Redis + token-bucket rate limiting |
| Config | `config.yaml`, secrets Fernet-encrypted, admin password hashed |
| CLI | `click` + `rich` |
| DI | Custom IoC container (no third-party framework) |
| Infra | Docker image on GHCR (`linux/amd64`, `linux/arm64`) |

---

## How to Use

### Prerequisites

- Python 3.14
- A reachable **Redis** and **Qdrant** — local, Docker, or managed (ElastiCache, Redis Cloud, Qdrant Cloud all work)
- At least one provider API key (OpenAI / Anthropic / Gemini) **or** a self-hosted OpenAI-compatible endpoint
- For a non-Docker install: `git`, `cmake` and a C/C++ compiler — `tollgate init` compiles `llama-server` from source
- ~1 GB of disk for the classifier model, plus RAM to hold it (see [Limitations](#limitations))

### Option A — Docker (recommended)

```bash
# 1. Start the container. It idles until it finds a config.yaml in /data.
docker compose -f docker/docker-compose.yml up -d

# 2. Run the setup wizard inside it
docker exec -it tollgate tollgate init

# 3. Restart, and the gateway comes up on :13000
docker restart tollgate
```

The image doesn't bundle Redis or Qdrant — point the wizard at instances that are reachable from inside the container.

### Option B — Local install

```bash
git clone https://github.com/Vibhinn/Tollgate    #clone locally
python3 -m venv venv    # create a virtual environment
cd Tollgate             # go inside the newly cloned project
pip3 install -e .       # installs the `tollgate` CLI
tollgate init           # interactive setup wizard
tollgate start          # serves on 0.0.0.0:13000
```

### The setup wizard (`tollgate init`)

| Step | What happens |
|---|---|
| 1. Routing intelligence model | Downloads `qwen2.5-1.5b-instruct-q4_k_m.gguf` (~1 GB, once) |
| 2. Routing intelligence server | Clones llama.cpp at a pinned commit and builds `llama-server` for your CPU |
| 3. Services | Redis + Qdrant host/port/password/TLS. On localhost it tries to start them for you |
| 4. Admin credentials | Username (encrypted) + password (hashed) — needed to mint admin tokens |
| 5. Providers | Pick providers, paste API keys (encrypted), add self-hosted endpoints, choose a default model |
| 6. Rate limiting | Sustained req/s and burst multiplier |
| 7. Finalize | Writes `config.yaml` and the `.tollgate.key` encryption key (mode `600`) atomically |

Re-running `tollgate init` on a configured machine asks for the admin credentials first. To tweak one setting instead:

```bash
tollgate config            # print the current configuration
tollgate config --change   # change a single setting (restart to apply)
```

> **Keep `.tollgate.key` safe.** It decrypts the API keys in `config.yaml`. Lose it and you'll need to re-run `tollgate init`.

### Making requests

**1. Mint an access token**

```bash
curl -X POST http://localhost:13000/api/v1/chat/generate \
  -H "Content-Type: application/json" \
  -d '{"token_requirement": "chat"}'
# → {"token": "tg_..."}
```

| Field | Required | Default | Notes |
|---|---|---|---|
| `token_requirement` | yes | — | `"chat"`, `"image"` or `"audio"` |
| `role` | no | `"user"` | `"user"` or `"admin"` |
| `password` | for `admin` | — | The admin password set during `tollgate init` |
| `lifetime` | no | `1296000` (15 days) | Token TTL in seconds |

**2. Call the gateway with a policy...**

```bash
curl -X POST http://localhost:13000/api/v1/chat/completions \
  -H "Authorization: Bearer tg_<your_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "cheap",
    "messages": [{"role": "user", "content": "Summarize this contract"}],
    "max_tokens": 512,
    "cache_type": "SEMANTIC"
  }'
```

**...or pin a model directly**

```bash
  -d '{"model": "claude-sonnet-4-6", "messages": [...], "max_tokens": 512}'
```

| Field | Required | Default | Notes |
|---|---|---|---|
| `model` | yes | — | `"cheap"`, `"fast"`, `"smart"`, any model in `src/utils/config/providers.py`, or a self-hosted alias from `config.yaml` |
| `messages` | yes | — | `[{"role": ..., "content": ...}]` — see [Limitations](#functional-gaps) |
| `max_tokens` | yes | — | Passed through to the provider |
| `cache_type` | no | none | `"EXACT"` or `"SEMANTIC"` — stores the response for future hits |
| `cache_match_score` | no | `0.9` | Semantic similarity needed to count as a hit (0–1) |
| `temperature` | no | `0.7` | Accepted but not yet forwarded to providers |

**Response**

```json
{ "role": "assistant", "message": "..." }
```

Cache hits come back with `"role": "model"`.

**Optional headers**
- `X-Cache-TTL: 3600` — exact-cache TTL in seconds (default 3600)

**Status codes**

| Code | Meaning |
|---|---|
| `401` | Missing / invalid token, or wrong admin password |
| `403` | Provider denied access to that model |
| `404` | Unknown model, provider not configured, or **no healthy model left for the policy** |
| `422` | Request validation failed (e.g. missing `max_tokens`, unknown model name) |
| `429` | Tollgate's rate limit (`Retry-After` and `X-RateLimit-*` headers included) or the provider's |
| `500` | Provider outage / API error |
| `503` | Gateway overloaded: more requests in flight than `backpressure.max_in_flight`. Has `Retry-After`. Change it with `tollgate config --change` |

Swagger docs at `http://localhost:13000/docs`.

### Environment variables

| Variable | Default | Purpose |
|---|---|---|
| `TOLLGATE_DATA_DIR` | `src/app/intelligence/` | Where the classifier model and `llama-server` live (`/data/intelligence` in Docker) |
| `TOLLGATE_APP_DIR` | `.` | Where `main.py` is found by `tollgate start` |
| `TOLLGATE_CLASSIFIER_CONCURRENCY` | `1` | Max concurrent classifier calls. Raise only on boxes with spare cores |

### Running tests

```bash
pip3 install -e ".[test]"
pytest tests/
```

---

## Limitations

Tollgate is a single-node gateway today. The limits below come from the code and from k6 load runs (scripts in `k6/`, local only).

### Measured

| Run | Where | Load | Result |
|---|---|---|---|
| Soak | Local | 20 VUs constant, 5 min | 2,645 requests, **0% errors**, p50 1.2s / p95 1.6s / p99 2.6s — latency is almost entirely the provider |
| Cache stress | Local | ramp to 100 VUs | Cache hits served at **p50 6.5ms / p95 15ms**. `"cheap"` started returning `404` once every configured model got benched by provider errors |
| Chaos | AWS, 2 vCPU | erratic, peaks at 1,000 VUs, random policy / model / cache mix | ~6k requests in ~2 min, **~55% error rate**, 93 requests hit the 60s client timeout. `"smart"` failed **86–99%** of the time, p95 up to 60s |

The chaos run was taken *before* the classifier concurrency cap (`TOLLGATE_CLASSIFIER_CONCURRENCY`) was added. It should do better now, but hasn't been re-measured.

### Load limits

1. **One process, one event loop.** `tollgate start` runs a single uvicorn worker. Request handling, the Redis Streams worker and embedding calls all share it. You can't simply add workers (see 2 and 3).
2. **The rate limiter is in-memory and per-process.** Buckets live in a Python dict, reset on restart, and aren't shared across processes or instances. Running two instances behind a load balancer doubles the effective limit.
3. **Rate-limit buckets are per role, not per user.** The bucket key is what's stored behind the token (`{"requirement", "user_role"}`), so every `chat`/`user` token shares **one bucket**. In practice the configured limit is a gateway-wide limit for all regular users together.
4. **`"smart"` routing is CPU-bound and serialized.** On a classifier cache miss, the prompt goes to a 1.5B model on CPU, one at a time by default. On a small box, concurrent `"smart"` traffic queues behind it. That's what drove the 60s timeouts in the chaos run. Classifier answers are cached in Qdrant (similarity ≥ 0.7), so repeat-ish prompts skip it.
5. **Each process spawns its own `llama-server` on fixed port 8091.** A second instance on the same host can't start its classifier and drops to "degraded" mode, where every `"smart"` request routes as `SIMPLE`.
6. **Every request pays for an embedding.** When the exact cache misses, the semantic lookup runs, even if the request didn't set `cache_type`. model2vec runs on the default thread pool, so it competes for CPU with everything else. `"smart"` computes a second embedding for the classifier cache.
7. **Provider throttling reduces your choices.** A provider `429` benches that model for 30s. Under sustained load, models get benched faster than they come back. Once none are left, policy requests return `404` instead of waiting or returning `503`. That was most of the failures in the chaos and cache-stress runs.
8. **Fallback goes one level deep.** If the fallback model also fails, the error goes straight back to the client.
9. **Background jobs can be dropped.** Each stream is capped at ~1,000 entries (`MAXLEN ~1000`) and one consumer works through them in batches of 10. Under heavy write load, unprocessed cache and analytics jobs can be trimmed before they're handled. Jobs that fail 5 times move to `<stream>:dead`.
10. **No streaming.** Responses are fully buffered before they're returned, so long generations hold a connection and memory for their whole duration.
11. **The semantic cache grows forever.** Qdrant points have no TTL (`X-Cache-TTL` only applies to the exact cache), and nothing evicts them.
12. **Connection pools are capped.** Redis allows 1,000 connections with 3s socket timeouts. Qdrant's gRPC pool also allows 1,000. A Redis stall longer than 3s fails auth for every request in flight.
13. **Startup isn't free.** Boot waits up to 30s for `llama-server`, then sends a real 1-token request to every configured model (small, but real, provider spend on every restart).
14. **No observability yet.** `/api/v1/metrics` is a stub and isn't mounted. Logging is `print`.

### Functional gaps

- **Only the last message is sent to the provider.** Earlier turns in `messages` are ignored, so there's no multi-turn context yet.
- **The cache key is just the last user message.** It doesn't include the model or the user, so two different models, or two different users, asking the same thing share a cached answer.
- **`temperature` isn't forwarded** to providers.
- **The response shape isn't OpenAI-compatible yet** (`{"role", "message"}` instead of `choices[]`), so OpenAI SDKs can't use Tollgate as a drop-in `base_url`.
- **`"cheap"` uses static list prices** from `pricing.py`, not observed spend. Self-hosted models aren't in the pricing table, so `"cheap"` never picks them.

---

## Roadmap

| #  | Feature | Status |
|----|---|---|
| 1  | Multi-provider routing (OpenAI, Anthropic, Gemini) | ✅ Done |
| 2  | Bearer token auth + BYOK token generation | ✅ Done |
| 3  | Token bucket rate limiting with `Retry-After` | ✅ Done |
| 4  | Exact cache (Redis) with configurable TTL | ✅ Done |
| 5  | Semantic cache (Qdrant + model2vec embeddings) | ✅ Done |
| 6  | Redis Streams async job queue for cache + analytics | ✅ Done |
| 7  | Live EMA-based latency ranking per model | ✅ Done |
| 8  | `"cheap"` / `"fast"` / `"smart"` policy routing | ✅ Done |
| 9  | Ports & adapters architecture with custom DI container | ✅ Done |
| 10 | `tollgate` CLI: `init`, `start`, `config --change` | ✅ Done |
| 11 | Gemini provider | ✅ Done |
| 12 | `"smart"` routing via local prompt classifier (llama.cpp + Qwen2.5-1.5B) | ✅ Done |
| 13 | Fallback on provider failure + TTL-based model benching | ✅ Done |
| 14 | Self-hosted models (any OpenAI-compatible endpoint) | ✅ Done |
| 15 | Managed Redis / Qdrant support (ElastiCache, Redis Cloud, Qdrant Cloud) | ✅ Done |
| 16 | Docker image on GHCR (amd64 + arm64) | ✅ Done |
| 17 | Analytics / metrics endpoint (data collected, API stub) | 🔧 In Progress |
| 18 | Streaming responses (SSE / chunked transfer) | 🔧 In Progress |
| 19 | OpenAI-compatible request **and response** shape (true drop-in) | 🔧 In Progress |
| 20 | Redis-backed, per-user rate limiter (multi-instance safe) | 📋 Planned |
| 21 | Multi-worker / horizontally scalable deployment | 📋 Planned |
| 22 | Full conversation history + `temperature` passthrough | 📋 Planned |
| 23 | Per-token budget enforcement and cost caps | 📋 Planned |
| 24 | Multi-tenant routing with isolated rate limits | 📋 Planned |

---

## Project Structure (for the nerds)

```
Tollgate/
├── main.py                      # FastAPI app + lifespan (migrations, stream worker, warm-up)
├── config.yaml                  # Written by `tollgate init` - encrypted keys, services, limits
├── pyproject.toml               # Package + `tollgate` entry point, test config
├── build/
│   ├── build.py                 # Builder: connections, middleware, routers, DI, job helpers
│   └── installation.py          # Middleware + router registration
├── cli/
│   ├── init.py                  # `tollgate init | start | config`
│   ├── helpers/                 # Wizard orchestration, config print/change
│   ├── steps/                   # One file per wizard step (model, llama-server build, services, ...)
│   ├── inputs/                  # Accepted providers / models for the wizard
│   └── ui/                      # rich console helpers
├── docker/
│   ├── Dockerfile               # Image published to ghcr.io/vibhinn/tollgate
│   ├── docker-compose.yml       # Runs the published image (no bundled Redis/Qdrant)
│   └── entrypoint.sh            # Starts the gateway, or idles until `tollgate init` has run
├── src/
│   ├── app/
│   │   ├── adapters/            # ChatAdapter, RouterAdapter, GenerateAccessTokenAdapter
│   │   ├── api/                 # Route handlers (chat, generate, metrics stub)
│   │   │   ├── limiter/         # Token bucket + per-key bucket store
│   │   │   ├── middleware/      # Auth + rate limiting, exempt paths
│   │   │   └── validators/      # Pydantic request models
│   │   ├── exceptions/          # Gateway exception types
│   │   ├── factory/             # Application repository factory
│   │   ├── injector/            # IoC container
│   │   ├── intelligence/        # llama-server lifecycle + prompt classifier
│   │   ├── migrations/          # Qdrant collection setup
│   │   └── ports/               # Abstract interfaces (cache, vector DB, LLM, jobs, ranking)
│   ├── cache/
│   │   ├── connection.py        # Redis + Qdrant clients
│   │   └── repository/          # Redis KV, Redis ranking (sorted sets), Qdrant
│   ├── jobs/
│   │   ├── repository/          # Redis Streams producer + in-process consumer
│   │   └── helpers/             # AddToCache, AnalyticsJobHelper (latency EMA)
│   ├── llm/
│   │   ├── connection.py        # Provider clients from config
│   │   ├── factory/             # LLM repository factory
│   │   └── repository/          # OpenAI, Anthropic, Gemini, self-hosted, model2vec
│   ├── router/
│   │   ├── router.py            # Invocation, benching, fallback, warm-up probes
│   │   └── core/
│   │       ├── pricing.py       # Token pricing table
│   │       ├── cost.py          # "cheap" selection
│   │       └── smart.py         # Category → model preference lists
│   └── utils/                   # Config loader, routing table, crypto, types, decorators
├── tests/
│   ├── unit/
│   ├── integration/
│   └── cli/
└── .github/workflows/           # Tests on push/PR, image publish on develop + tags
```

---

*Built with Python 3.14 · FastAPI · Redis · Qdrant · llama.cpp · OpenAI SDK · Anthropic SDK · Google GenAI SDK*
