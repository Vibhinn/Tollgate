// Measures the actual payoff of the exact-match cache: latency on a cold
// (cache-miss, real LLM call) request vs. a warm (cache-hit) request for the
// same prompt. Produces two Trend metrics you can diff directly in the
// summary output - this is the number worth quoting ("cache hits are Nx
// faster than a cold call").
//
//   k6 run k6/cache_effectiveness.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend } from 'k6/metrics';
import { BASE_URL, MAX_TOKENS } from './lib/config.js';
import { mintToken, authHeaders } from './lib/auth.js';

const missLatency = new Trend('cache_miss_latency_ms', true);
const hitLatency = new Trend('cache_hit_latency_ms', true);

export const options = {
  vus: 5,
  iterations: 20,
  thresholds: {
    // the real claim this test exists to make - cache hits should be
    // dramatically faster than a real LLM round trip
    cache_hit_latency_ms: ['p(95)<500'],
  },
};

export function setup() {
  return { token: mintToken(), stamp: Date.now() };
}

export default function (data) {
  // Unique per (VU, iteration), not just per iteration - __ITER alone is
  // per-VU, so two VUs on the same iteration number would otherwise pick the
  // same prompt and race each other's miss/hit expectations.
  const prompt = `cache-effectiveness-probe-${data.stamp}-vu${__VU}-iter${__ITER}`;
  const headers = authHeaders(data.token);

  // cold: real LLM call, ask the gateway to cache the result
  let res = http.post(
    `${BASE_URL}/api/v1/chat/completions`,
    JSON.stringify({
      model: 'cheap',
      messages: [{ role: 'user', content: prompt }],
      cache_type: 'exact',
      max_tokens: MAX_TOKENS,
    }),
    headers,
  );
  check(res, {
    'miss: status 200': (r) => r.status === 200,
    'miss: not served from cache': (r) => r.status === 200 && r.json('role') === 'assistant',
  });
  missLatency.add(res.timings.duration);

  sleep(1.5); // let the async AddToCache job land before probing for a hit

  // warm: same prompt, should now be served straight from the exact cache
  res = http.post(
    `${BASE_URL}/api/v1/chat/completions`,
    JSON.stringify({
      model: 'cheap',
      messages: [{ role: 'user', content: prompt }],
      max_tokens: MAX_TOKENS,
    }),
    headers,
  );
  check(res, {
    'hit: status 200': (r) => r.status === 200,
    'hit: served from cache': (r) => r.status === 200 && r.json('role') === 'model',
  });
  hitLatency.add(res.timings.duration);
}
