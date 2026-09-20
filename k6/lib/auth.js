import http from 'k6/http';
import { check } from 'k6';
import { BASE_URL } from './config.js';

// NOTE on identity: GenerateAccessTokenAdapter.generate_and_save_token stores
// json.dumps({requirement, user_role}) as the value behind the token key, and
// the rate limiter derives its bucket key from that *value*, not the token
// string itself (RedisRepository.get_user_id just returns the stored value).
// So every token minted with the same (token_requirement, role) pair shares
// one rate-limit bucket, regardless of how many distinct tokens you mint.
// Minting "more users" with the same role does not create more buckets -
// worth knowing before you design a test around "N independent API keys".
export function mintToken(role = 'user', tokenRequirement = 'chat', lifetime = 1296000) {
  const res = http.post(
    `${BASE_URL}/api/v1/chat/generate`,
    JSON.stringify({ token_requirement: tokenRequirement, role, lifetime }),
    { headers: { 'Content-Type': 'application/json' } },
  );

  const ok = check(res, {
    'token generated (200)': (r) => r.status === 200,
    'token present in response': (r) => !!r.json('token'),
  });
  if (!ok) {
    throw new Error(`Failed to mint token: ${res.status} ${res.body}`);
  }
  return res.json('token');
}

export function authHeaders(token) {
  return {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  };
}

// Response header names get canonicalized by Go's net/http on the way into
// k6 (e.g. "X-RateLimit-Limit" -> "X-Ratelimit-Limit", since Go only
// capitalizes the letter after a hyphen, not after an internal capital).
// Look headers up case-insensitively instead of hardcoding the casing.
export function getHeader(res, name) {
  const target = name.toLowerCase();
  for (const key in res.headers) {
    if (key.toLowerCase() === target) return res.headers[key];
  }
  return undefined;
}
