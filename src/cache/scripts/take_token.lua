local max_tokens = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local interval = tonumber(ARGV[3])
local ttl = tonumber(ARGV[4])

local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000

local state = redis.call('HMGET', KEYS[1], 'tokens', 'last_refill')
local tokens = tonumber(state[1])
local last_refill = tonumber(state[2])
if tokens == nil or last_refill == nil then
    tokens = max_tokens
    last_refill = now
end

local refills = math.floor((now - last_refill) / interval)
if refills > 0 then
    tokens = math.min(max_tokens, tokens + refills * refill_rate)
    last_refill = last_refill + refills * interval
end

local allowed = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
end

redis.call('HSET', KEYS[1], 'tokens', tokens, 'last_refill', tostring(last_refill))
redis.call('EXPIRE', KEYS[1], ttl)
return {allowed, tokens, tostring(last_refill + interval)}
