// Sudden spike then sudden drop, rather than a gradual ramp. Tests how the
// gateway behaves when concurrency jumps far faster than it would under
// organic growth - and, just as importantly, whether it recovers cleanly
// once the spike passes rather than staying degraded.
//
//   k6 run k6/spike.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';
import { BASE_URL, MAX_TOKENS } from './lib/config.js';
import { mintToken, authHeaders } from './lib/auth.js';

const errorRate = new Rate('error_rate');

export const options = {
  scenarios: {
    spike: {
      executor: 'ramping-vus',
      startVUs: 2,
      stages: [
        { duration: '30s', target: 2 },    // baseline
        { duration: '10s', target: 150 },  // sudden spike
        { duration: '1m', target: 150 },   // hold at peak
        { duration: '10s', target: 2 },    // sudden drop
        { duration: '30s', target: 2 },    // confirm recovery
      ],
      gracefulRampDown: '10s',
    },
  },
  thresholds: {
    error_rate: ['rate<0.05'],
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
      messages: [{ role: 'user', content: 'ping' }],
      max_tokens: MAX_TOKENS,
    }),
    authHeaders(data.token),
  );

  const ok = check(res, {
    'status is 200 or 429': (r) => r.status === 200 || r.status === 429,
  });
  errorRate.add(!ok);

  sleep(0.3);
}
