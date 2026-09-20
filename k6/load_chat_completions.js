// Ramping-load throughput/latency test against the two routing strategies
// that are actually correct today (fast, cheap). "smart" is deliberately
// excluded - it's known broken (the classifier's label gets used as a model
// name and never matches ROUTING_TABLE), so including it would just measure
// error handling, not routing performance.
//
//   k6 run k6/load_chat_completions.js
//   k6 run --env BASE_URL=http://localhost:13000 k6/load_chat_completions.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Trend, Rate } from 'k6/metrics';
import { BASE_URL, MAX_TOKENS } from './lib/config.js';
import { mintToken, authHeaders } from './lib/auth.js';

const fastLatency = new Trend('fast_latency_ms', true);
const cheapLatency = new Trend('cheap_latency_ms', true);
const errorRate = new Rate('error_rate');

export const options = {
  scenarios: {
    ramping_load: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 10 },
        { duration: '1m', target: 50 },
        { duration: '2m', target: 50 },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '15s',
    },
  },
  thresholds: {
    error_rate: ['rate<0.01'],
    http_req_failed: ['rate<0.01'],
    fast_latency_ms: ['p(95)<5000'],
    cheap_latency_ms: ['p(95)<5000'],
  },
};

const PROMPTS = [
  'Summarize the plot of Romeo and Juliet in one sentence.',
  'What is the capital of France?',
  'Write a haiku about autumn.',
  'Explain recursion to a five year old.',
  'What year did the Berlin Wall fall?',
  'Name three primary colors.',
  'What is the boiling point of water in Celsius?',
];

export function setup() {
  // All VUs share one token deliberately - see lib/auth.js for why minting
  // more tokens under the same role wouldn't create more rate-limit buckets
  // anyway, so there's no isolation benefit to giving each VU its own.
  return { token: mintToken() };
}

export default function (data) {
  const model = Math.random() < 0.5 ? 'fast' : 'cheap';
  const prompt = PROMPTS[Math.floor(Math.random() * PROMPTS.length)];

  const res = http.post(
    `${BASE_URL}/api/v1/chat/completions`,
    JSON.stringify({
      model,
      messages: [{ role: 'user', content: prompt }],
      max_tokens: MAX_TOKENS,
    }),
    authHeaders(data.token),
  );

  const ok = check(res, {
    'status is 200': (r) => r.status === 200,
    'response has message': (r) => r.status === 200 && !!r.json('message'),
  });
  errorRate.add(!ok);

  if (model === 'fast') {
    fastLatency.add(res.timings.duration);
  } else {
    cheapLatency.add(res.timings.duration);
  }

  sleep(0.5 + Math.random()); // 0.5-1.5s think time between requests
}
