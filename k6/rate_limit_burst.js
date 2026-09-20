// Deliberately bursts well past the configured rate limit to characterize
// current behavior: does it 429 correctly, are Retry-After/X-RateLimit-*
// headers present and sane, and - the more interesting question - does the
// *actual* observed refill rate match the configured refill_rate?
//
// This is a "before" script on purpose: TokenBucket.refill() has a known
// drift bug (it snaps last_refill_time to `now` instead of advancing it by
// exactly num_refills * time_interval, losing leftover fractional progress
// toward the next refill every cycle) and the whole limiter is in-process
// memory, not Redis-backed. Re-run this same script after that's fixed to
// get a real before/after comparison instead of guessing at the effect.
//
//   k6 run k6/rate_limit_burst.js
import http from 'k6/http';
import { check } from 'k6';
import { Counter, Trend } from 'k6/metrics';
import { BASE_URL, MAX_TOKENS } from './lib/config.js';
import { mintToken, authHeaders, getHeader } from './lib/auth.js';

const rateLimited = new Counter('rate_limited_responses');
const allowed = new Counter('allowed_responses');
const remainingAtRejection = new Trend('remaining_at_rejection', false);

export const options = {
  scenarios: {
    burst: {
      executor: 'constant-arrival-rate',
      // config.yaml's rate_limiter is (max_tokens=500, refill_rate=100,
      // time_interval=1.0) - i.e. ~100/s sustained with a 500 burst
      // allowance today, not the "100 requests/minute" the spec describes.
      // 200/s is comfortably past that so we can actually observe 429s.
      rate: 200,
      timeUnit: '1s',
      duration: '30s',
      preAllocatedVUs: 50,
      maxVUs: 250,
    },
  },
};

export function setup() {
  // See lib/auth.js: every "user"-role token shares one rate-limit bucket
  // today, so one token is sufficient (and representative) for this test.
  return { token: mintToken('user') };
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

  if (res.status === 429) {
    rateLimited.add(1);
    check(res, {
      '429 has Retry-After': (r) => getHeader(r, 'Retry-After') !== undefined,
      '429 has X-RateLimit-Limit': (r) => getHeader(r, 'X-RateLimit-Limit') !== undefined,
      '429 has X-RateLimit-Remaining': (r) => getHeader(r, 'X-RateLimit-Remaining') !== undefined,
    });
    const remaining = getHeader(res, 'X-RateLimit-Remaining');
    if (remaining !== undefined) remainingAtRejection.add(Number(remaining));
  } else {
    allowed.add(1);
    check(res, { 'non-429 is 200': (r) => r.status === 200 });
  }
}

export function teardown() {
  // Nothing to clean up - the point of this script is the summary counts,
  // not per-request assertions. Compare rate_limited_responses vs
  // allowed_responses across runs to see if throttling is consistent.
}
