// Sanity check: 1 VU, 1 iteration. Run this before any heavier script to
// confirm the gateway is actually up and the core paths respond as expected.
//
//   k6 run k6/smoke.js
//   BASE_URL=http://localhost:13000 k6 run k6/smoke.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, MAX_TOKENS } from './lib/config.js';
import { mintToken, authHeaders } from './lib/auth.js';

export const options = {
  vus: 1,
  iterations: 1,
  thresholds: {
    checks: ['rate==1'],
  },
};

export default function () {
  const token = mintToken();

  // fast routing resolves and returns a real answer
  let res = http.post(
    `${BASE_URL}/api/v1/chat/completions`,
    JSON.stringify({
      model: 'fast',
      messages: [{ role: 'user', content: 'Reply with exactly one word: hello.' }],
      max_tokens: MAX_TOKENS,
    }),
    authHeaders(token),
  );
  check(res, {
    'fast: status 200': (r) => r.status === 200,
    'fast: has message': (r) => !!r.json('message'),
  });

  // cheap routing resolves (PRICING_TABLE-based, no local pool needed)
  res = http.post(
    `${BASE_URL}/api/v1/chat/completions`,
    JSON.stringify({
      model: 'cheap',
      messages: [{ role: 'user', content: 'Reply with exactly one word: hello.' }],
      max_tokens: MAX_TOKENS,
    }),
    authHeaders(token),
  );
  check(res, { 'cheap: status 200': (r) => r.status === 200 });

  // no Authorization header -> 401
  res = http.post(
    `${BASE_URL}/api/v1/chat/completions`,
    JSON.stringify({ model: 'fast', messages: [{ role: 'user', content: 'hi' }], max_tokens: MAX_TOKENS }),
    { headers: { 'Content-Type': 'application/json' } },
  );
  check(res, { 'no auth: status 401': (r) => r.status === 401 });

  // unknown model name is rejected by validation, not routed
  res = http.post(
    `${BASE_URL}/api/v1/chat/completions`,
    JSON.stringify({ model: 'not-a-real-model', messages: [{ role: 'user', content: 'hi' }], max_tokens: MAX_TOKENS }),
    authHeaders(token),
  );
  check(res, { 'unknown model: status 422': (r) => r.status === 422 });

  // exact-cache round trip: write, then confirm a hit comes back as role "model"
  const cacheProbe = `smoke-cache-probe-${Date.now()}`;
  res = http.post(
    `${BASE_URL}/api/v1/chat/completions`,
    JSON.stringify({
      model: 'fast',
      messages: [{ role: 'user', content: cacheProbe }],
      cache_type: 'exact',
      max_tokens: MAX_TOKENS,
    }),
    authHeaders(token),
  );
  check(res, { 'cache write request: status 200': (r) => r.status === 200 });

  sleep(1.5); // let the async AddToCache job land

  res = http.post(
    `${BASE_URL}/api/v1/chat/completions`,
    JSON.stringify({
      model: 'fast',
      messages: [{ role: 'user', content: cacheProbe }],
      max_tokens: MAX_TOKENS,
    }),
    authHeaders(token),
  );
  check(res, {
    'cache hit: status 200': (r) => r.status === 200,
    'cache hit: served from cache (role=model)': (r) => r.json('role') === 'model',
  });
}
