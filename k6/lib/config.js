export const BASE_URL = __ENV.BASE_URL || 'http://localhost:13000';

// ChatModel.max_tokens has no default - every /chat/completions body must
// include it or the request is rejected with 422 before it reaches routing.
export const MAX_TOKENS = Number(__ENV.MAX_TOKENS) || 4096;
