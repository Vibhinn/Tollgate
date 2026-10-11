# Tollgate

**A self-hosted LLM gateway that routes, caches, and ranks AI model calls in real time.**

Tollgate abstracts away the need to specify LLM model names inside the request.

Developers do not need to hardcode model names like `gpt-4o` or `claude-sonnet-4-6`. Simply ask Tollgate for `"fast"`, `"cheap"` or `"smart"` — and it figures out which model wins *right now*, across OpenAI, Anthropic, Google and your own self-hosted models, based on pricing, live latency data collected from your own traffic, and a local classifier that reads the prompt.

---

## What It Does

Most teams use one model, on one provider, forever — because switching takes effort. Tollgate makes the model an implementation detail.

```
POST /v1/chat/completions
{
  "model": "cheap",          ← not a model name. a policy.
  "messages": [...]
}
```

It speaks OpenAI's Chat Completions API, so the OpenAI SDKs and the frameworks built on them work by changing only `base_url` and `api_key`.

Tollgate resolves `"cheap"` → the lowest-cost model that is configured and currently healthy, sends the request, returns the response, and silently updates its rankings for next time. If that model fails (rate limited, out of credits, provider outage), it's benched for a while and the request falls back to the next best one.

---

## Architecture

```
                         ┌─────────────────────────────────────────────┐
                         │                   CLIENT                    │
                         │          POST /v1/chat/completions          │
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
| Exact | Redis | Hash of the whole request: every message, model, temperature, user | Identical requests |
| Semantic | Qdrant + model2vec | Cosine similarity on the last user message, only among entries with the same system prompt, history, model, temperature and user | `cache_match_score` (default 0.9) |

Cache hits skip the LLM entirely. Semantic cache catches paraphrased duplicates that exact matching misses. Entries are per user, so one user's cached answers are never served to another. Writes are opt-in per request via `cache_type` and happen asynchronously through Redis Streams, so they never add latency to the response.

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
| 4. Admin credentials | Username (encrypted) + password (hashed) — needed to create or revoke tokens and change config |
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

**1. Create an access token**

Tokens are created by whoever runs the gateway, with the `tollgate` CLI on the gateway host. Every token belongs to a **team** and a **name** (a person or an app). Creating or revoking a token asks for the admin credentials set during `tollgate init`.

```bash
tollgate token create --team payments --name alice
tollgate token create --team payments --name invoice-bot --ttl never
tollgate token create --team ops --name dashboard --admin   # sees the full metrics breakdown
# → tg_...   (shown once; Tollgate stores only its hash)

tollgate token list                         # ID, team, name, created, expires
tollgate token list --team payments
tollgate token revoke e72bb248c316          # by the ID from `list`, or the full token
tollgate token revoke --team payments --name alice   # every token of alice
```

In Docker, prefix each command with `docker exec -it tollgate`.

| Option | Default | Notes |
|---|---|---|
| `--team`, `--name` | required | Lowercase letters, digits and `-` |
| `--ttl` | `90d` | e.g. `30d`, `12h`, or `never` |
| `--admin` | off | An admin token also sees the metrics per team, person and token. It works for chat requests like any other token |

Tokens with the same team and name share one rate limit and one cache. Give each app or environment its own name (`invoice-bot`, `invoice-bot-staging`) to keep them separate. Two tokens for the same name are how you rotate a key: create the new one, switch your app over, revoke the old one.

**2. Point the OpenAI SDK at Tollgate**

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:13000/v1", api_key="tg_<your_token>")

completion = client.chat.completions.create(
    model="cheap",                              # a policy, or pin a model: "claude-sonnet-4-6"
    messages=[{"role": "user", "content": "Summarize this contract"}],
    extra_body={"cache_type": "semantic"},      # Tollgate's own options go in extra_body
)
print(completion.model)                         # the model that actually answered
print(completion.choices[0].message.content)
```

Anything built on the OpenAI SDK (LangChain's `ChatOpenAI`, LlamaIndex, chat UIs) works the same way with `base_url` set. `client.models.list()` returns the policies and every model you have a provider key for.

With curl:

```bash
curl -X POST http://localhost:13000/v1/chat/completions \
  -H "Authorization: Bearer tg_<your_token>" \
  -H "Content-Type: application/json" \
  -d '{"model": "cheap", "messages": [{"role": "user", "content": "Summarize this contract"}], "cache_type": "semantic"}'
```

**Request fields**

| Field | Default | Notes |
|---|---|---|
| `model` | required | `"cheap"`, `"fast"`, `"smart"`, any model in `src/utils/config/providers.py`, or a self-hosted alias from `config.yaml` |
| `messages` | required | Roles `system`, `developer`, `user`, `assistant`. `content` is a string or a list of `{"type": "text"}` parts |
| `max_completion_tokens` / `max_tokens` | provider default | Anthropic requires a value, so Tollgate sends 4096 when neither is set |
| `temperature` | provider default | 0–2. Omit it for reasoning models, which reject non-default values |
| `top_p`, `stop` | provider default | `stop` takes a string or up to 4 strings |
| `cache_type` | none | Tollgate only. `"exact"` or `"semantic"`: stores the response for future hits |
| `cache_match_score` | `0.9` | Tollgate only. Semantic similarity needed to count as a hit (0–1) |

Other OpenAI fields (`user`, `seed`, `metadata`, a message's `name`, ...) are accepted and ignored. Fields Tollgate can't honour yet are **rejected with a 400** instead of being silently dropped: `stream: true`, `n` > 1, `tools` / `functions`, `response_format` other than `text`, image or audio content, and the `tool` role.

**Response**

A standard `chat.completion` object: `id`, `created`, `model`, `choices[0].message`, `choices[0].finish_reason` (`stop`, `length` or `content_filter`, mapped from every provider) and `usage`. `model` is the model that answered, so you can see what `"cheap"` picked. Responses cut off at the token limit (`length`) or filtered by the provider (`content_filter`) are never cached.

**Headers**
- `X-Tollgate-Cache: hit | miss` on every response. A hit has `usage` at zero, and its `model` is the one you asked for.
- `X-Cache-TTL: 3600` (request) — exact-cache TTL in seconds (default 3600). Must be a positive integer, otherwise the request gets a 400. With the OpenAI SDK, send it via `extra_headers`

**Errors**

Errors use OpenAI's body, `{"error": {"message", "type", "param", "code"}}`, so the SDKs raise the right exception and retry the right ones (`429` and `5xx`).

| Code | `code` | Meaning |
|---|---|---|
| `400` | — | Invalid request (`param` names the field), an unsupported feature, or the provider rejected it (e.g. context too long) |
| `401` | `invalid_api_key` | Missing, invalid, expired or revoked Tollgate token |
| `404` | `model_not_found` | Unknown model, provider not configured, or a policy has no configured model to pick from |
| `429` | `rate_limit_exceeded` / `upstream_rate_limited` | Tollgate's rate limit (`Retry-After` and `X-RateLimit-*` headers included) or the provider's |
| `502` | `upstream_auth_failed`, `upstream_permission_denied`, `upstream_credit_exhausted` | Tollgate's provider key is invalid, lacks access to the model, or is out of credit. Not a 401: the client's token is fine. Fix it with `tollgate config --change` |
| `502` | `upstream_server_error`, `upstream_connection_error` | Provider outage or unreachable |
| `503` | `overloaded` | More requests in flight than `backpressure.max_in_flight`. Has `Retry-After`. Change it with `tollgate config --change` |
| `503` | `no_model_available` | Every model the policy could use is benched after provider errors. `Retry-After` says when the first one is back; the OpenAI SDKs wait and retry on their own |

Swagger docs at `http://localhost:13000/docs`.

### Metrics

`GET /api/v1/metrics` is a [server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) stream. It sends one `metrics` event with a full snapshot every `interval` seconds (`?interval=1` to `60`, default `2`). Any token sees the gateway-wide numbers; an **admin token** (`tollgate token create ... --admin`) also sees the breakdown per team, person and token.

```bash
curl -N -H "Authorization: Bearer tg_<your_token>" "http://localhost:13000/api/v1/metrics?interval=2"
```

```
event: metrics
data: {"uptime_seconds": 8123, "process": {...}, "requests": {...}, "cache": {...}, "models": {...}, "dependencies": {...}}
```

| Section | Fields |
|---|---|
| `uptime_seconds`, `process` | Gateway uptime, `cpu_percent` since the previous snapshot, `memory_mb` |
| `requests` | `total`, `2xx`, `4xx`, `5xx`, `rate_limited`, `no_model_available` (policy requests answered `503` because every model they could use was benched), `rejected_by_backpressure` (turned away with `503 overloaded`; gateway-wide only, since backpressure runs before the token is checked), `in_flight` (right now) |
| `no_model_available` | `true` while every configured model is benched, i.e. no request can be answered right now; `null` if the models can't be read |
| `cache` | `exact_hits`, `semantic_hits`, `misses`, `hit_rate` |
| `models` | For every configured model: `requests`, `errors`, `input_tokens`, `output_tokens`, `avg_latency_ms`, and `available` (`false` while benched) |
| `dependencies` | `redis` and `qdrant` (`ok` / `down`), `classifier` (`ok` / `degraded`) |
| `teams`, `users`, `tokens` | **Admin tokens only.** One entry per team, per person or app (`team:name`), and per token ID from `tollgate token list`. Each has `requests`, `2xx`, `4xx`, `5xx`, `rate_limited`, `no_model_available`, `cache_exact_hits`, `cache_semantic_hits`, `cache_misses`, `input_tokens`, `output_tokens`, and `models` (requests and tokens per model). Token entries also have `team` and `name` |

- **How the numbers are made:** every request pushes one event to the `analytics` Redis stream after its response is sent (status, cache outcome, model, tokens, and who sent it). A background worker adds the events up, and an aggregator builds the snapshot once per second. The endpoint only reads that snapshot, so the numbers lag by about a second and any number of dashboards costs the same as one.
- **Counters are running totals** kept in Redis, so they survive restarts. A dashboard gets rates (requests per second, etc.) from the difference between two snapshots. `in_flight` is the only current value.
- **A part that can't be read is `null`**, e.g. `requests`, `cache` and `models` when Redis is down, and the stream keeps going.
- **The stream isn't counted** in `requests` and doesn't use a backpressure slot, so a dashboard left open has no effect on the gateway.
**Admin login (for dashboards).** Instead of storing an admin token, a dashboard can log in with the admin username and password set during `tollgate init`:

```bash
curl -X POST http://localhost:13000/api/v1/admin/login \
  -H "Content-Type: application/json" -d '{"username": "<admin username>", "password": "<admin password>"}'
# → {"session_token": "tg_...", "token_type": "bearer", "expires_in": 43200}
```

The session token is an admin token valid for 12 hours: use it as the bearer token for `/api/v1/metrics` to get the full breakdown. Wrong credentials get `401` with code `invalid_credentials`. Sessions show up in `tollgate token list` as `admin:dashboard-session`, and `tollgate token revoke <ID>` ends one early. The endpoint has no attempt limit, so the strength of the admin password and the protection of `.tollgate.key` matter; use HTTPS when it's reachable over a network. A password changed with `tollgate config --change` applies after a restart.

- **From a browser,** the built-in `EventSource` can't send an `Authorization` header. Read the stream with `fetch()` and a stream reader instead, or have your dashboard's server read it and pass it on. A page served from another origin also needs Tollgate to send CORS headers, which it doesn't yet.

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

1. **One process, one event loop.** `tollgate start` runs a single uvicorn worker. Request handling, the Redis Streams worker and embedding calls all share it. Rate limits are now shared through Redis, but two things still stop you from simply adding workers on one host: the classifier's fixed port (see 4), and each worker resetting the shared `in_flight` counter to 0 when it starts.
2. **Rate-limit buckets live in Redis.** One token bucket per team:name, taken atomically by a Lua script using Redis's clock, so every worker and instance shares the same limit and buckets survive restarts. If Redis can't be reached for the limit check, the request is let through rather than failed.
3. **`"smart"` routing is CPU-bound and serialized.** On a classifier cache miss, the prompt goes to a 1.5B model on CPU, one at a time by default. On a small box, concurrent `"smart"` traffic queues behind it. That's what drove the 60s timeouts in the chaos run. Classifier answers are cached in Qdrant (similarity ≥ 0.7), so repeat-ish prompts skip it.
4. **Each process spawns its own `llama-server` on fixed port 8091.** A second instance on the same host can't start its classifier and drops to "degraded" mode, where every `"smart"` request routes as `SIMPLE`.
5. **Every request pays for an embedding.** When the exact cache misses, the semantic lookup runs, even if the request didn't set `cache_type`. model2vec runs on the default thread pool, so it competes for CPU with everything else. `"smart"` computes a second embedding for the classifier cache.
6. **Provider throttling reduces your choices.** A provider `429` benches that model for 30s. Under sustained load, models get benched faster than they come back. Once none are left, policy requests get `503 no_model_available` with a `Retry-After` until the first model is back (they used to get a `404`, which was most of the failures in the chaos and cache-stress runs). Requests still fail during that window; Tollgate doesn't queue them.
7. **Fallback goes one level deep.** If the fallback model also fails, the error goes straight back to the client.
8. **Background jobs can be dropped.** Each stream is capped at ~1,000 entries (`MAXLEN ~1000`) and one consumer works through them in batches of 10. Under heavy write load, unprocessed cache and analytics jobs can be trimmed before they're handled. Jobs that fail 5 times move to `<stream>:dead`.
9. **No streaming.** `stream: true` is rejected with a 400. Responses are fully buffered before they're returned, so long generations hold a connection and memory for their whole duration.
10. **The semantic cache grows forever.** Qdrant points have no TTL (`X-Cache-TTL` only applies to the exact cache), and nothing evicts them.
11. **Connection pools are capped.** Redis allows 1,000 connections with 3s socket timeouts. Qdrant's gRPC pool also allows 1,000. A Redis stall longer than 3s fails auth for every request in flight.
12. **Startup isn't free.** Boot waits up to 30s for `llama-server`, then sends a real 1-token request to every configured model (small, but real, provider spend on every restart).
13. **Basic observability only.** `/api/v1/metrics` streams live counters (see [Metrics](#metrics)), but there's no Prometheus export or request tracing, and logging is `print`.

### Functional gaps

- **OpenAI compatibility covers Chat Completions without streaming or tools.** Streaming, tool / function calling, JSON mode, image inputs and `/v1/embeddings` aren't supported yet; requests that use them get a 400. The Responses and Assistants APIs aren't planned.
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
| 17 | Live metrics stream (`/api/v1/metrics`, server-sent events) | ✅ Done |
| 18 | Streaming responses (SSE / chunked transfer) | 🔧 In Progress |
| 19 | OpenAI-compatible Chat Completions (`/v1/chat/completions`, `/v1/models`, OpenAI errors) | ✅ Done |
| 19b | Tool calling, JSON mode, image inputs, `/v1/embeddings` | 📋 Planned |
| 20 | Redis-backed, per-user rate limiter (multi-instance safe) | ✅ Done |
| 21 | Multi-worker / horizontally scalable deployment | 📋 Planned |
| 22 | Full conversation history + `temperature` passthrough | ✅ Done |
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
│   │   ├── api/                 # /v1 routes (chat completions, models), metrics stream (SSE)
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
