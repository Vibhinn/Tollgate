// Sustained, moderate constant load over a longer duration. The point isn't
// peak throughput - it's catching degradation over time: growing latency,
// memory leaks, the background stream consumer falling behind or dying and
// silently stopping (which is exactly the class of bug fixed earlier in this
// branch - a soak test is how you'd actually notice a regression back to
// that, since a short load test wouldn't run long enough to show it).
//
//   k6 run k6/soak.js
//   k6 run --env DURATION=30m k6/soak.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { BASE_URL, MAX_TOKENS } from './lib/config.js';
import { mintToken, authHeaders } from './lib/auth.js';

export const options = {
  scenarios: {
    soak: {
      executor: 'constant-vus',
      vus: 20,
      duration: __ENV.DURATION || '10m',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    http_req_duration: ['p(95)<5000'],
  },
};

export function setup() {
  return { token: mintToken() };
}

export default function (data) {
  const res = http.post(
    `${BASE_URL}/api/v1/chat/completions`,
    JSON.stringify({
      model: 'fast',
      messages: [{ role: 'user', content: 'What is 2 + 2?' }],
      max_tokens: MAX_TOKENS,
    }),
    authHeaders(data.token),
  );
  check(res, { 'status 200': (r) => r.status === 200 });
  sleep(1);
}
