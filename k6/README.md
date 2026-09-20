# k6 load tests

Six scripts, each validated end-to-end against a mock of the two endpoints
they hit before being handed over (not against the real app - no live
Redis/Qdrant/API keys in this environment). Point `BASE_URL` at a real,
running instance to get real numbers.

## Prerequisites

1. `docker compose -f docker/docker-compose.yml up -d` (Redis + Qdrant)
2. At least one real provider API key configured in `config.yaml`
3. `python main.py` (or `uvicorn main:app`) running
4. `k6` installed (`brew install k6`)

All scripts default to `BASE_URL=http://localhost:13000`; override with
`k6 run --env BASE_URL=... k6/<script>.js`.

## Scripts

| Script | What it measures | Run it |
|---|---|---|
| `smoke.js` | 1 VU sanity check - auth, fast/cheap routing, validation, exact-cache round trip. Run this first, always. | `k6 run k6/smoke.js` |
| `load_chat_completions.js` | Throughput/latency under ramping concurrency (0→50 VUs) on `fast`/`cheap` | `k6 run k6/load_chat_completions.js` |
| `cache_effectiveness.js` | Cold (real LLM call) vs. warm (cache hit) latency for the same prompt - the actual "cache is worth it" number | `k6 run k6/cache_effectiveness.js` |
| `rate_limit_burst.js` | Bursts past the configured limit; checks 429 + headers, and is designed to be re-run after the rate limiter fix (see below) | `k6 run k6/rate_limit_burst.js` |
| `soak.js` | Sustained constant load (default 10m) - catches degradation over time, not peak throughput | `k6 run k6/soak.js` |
| `spike.js` | Sudden jump to 150 VUs and back - tests both handling the spike and recovering cleanly after | `k6 run k6/spike.js` |

`model: "smart"` is deliberately excluded from every script - it's currently
broken (the classifier's label gets used as a model name and never matches
`ROUTING_TABLE`), so hitting it would only measure error handling, not
routing.

## The before/after plan

Run `load_chat_completions.js` and `rate_limit_burst.js` now, save the
summary output (`k6 run --summary-export=results/before.json ...`). Once the
Redis-backed rate limiter (fixes the in-memory, per-process, drifting
`TokenBucket`) and the circuit breaker land, re-run the same scripts and
diff:

- `rate_limit_burst.js`: does the observed throttle rate now hold steady
  instead of drifting under sustained irregular-interval bursts, and does it
  stay correct if you point two instances at the same Redis?
- `load_chat_completions.js`: p95 latency and error rate under the same
  ramping-load profile, before vs. after.

That comparison is a stronger result than either run alone.

## A quirk worth knowing before you read the rate-limit numbers

`GenerateAccessTokenAdapter.generate_and_save_token` stores
`json.dumps({requirement, user_role})` as the value behind a token, and the
rate limiter's bucket key comes from that stored *value*, not the token
string itself. So every token minted with the same `(token_requirement,
role)` pair shares one bucket - minting more tokens under the same role
doesn't buy you more isolated "users" for a load test. `rate_limit_burst.js`
and `load_chat_completions.js` both mint a single token in `setup()` for this
reason; it's representative, not a shortcut.
