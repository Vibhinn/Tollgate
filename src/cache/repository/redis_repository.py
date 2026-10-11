import json
from typing import override, Any

from src.app.ports import CacheRepositoryInterface
from src.utils.types import CacheType, ATOMIC_COUNTERS, TokenIdentity
from src.utils.tokens import hash_token, token_key, token_id, new_token, token_record, ROLE_USER, TOKEN_INDEX_KEY
from ..connection import CacheConnection

class RedisRepository(CacheRepositoryInterface):
    def __init__(self):
        self.cache_conn = CacheConnection.get_connection(CacheType.EXACT)

    @override
    async def get_user_id(self, token: str) -> str | None:
        stored = await self.cache_conn.get(token_key(hash_token(token)))
        if not stored:
            return None
        try:
            return json.loads(stored).get("user_id")
        except (ValueError, AttributeError):
            return None

    @override
    async def get_identity(self, token: str) -> TokenIdentity | None:
        token_hash = hash_token(token)
        stored = await self.cache_conn.get(token_key(token_hash))
        if not stored:
            return None
        try:
            record = json.loads(stored)
            return TokenIdentity(
                user_id=record["user_id"],
                team=record["team"],
                name=record["name"],
                token_id=token_id(token_hash),
                # tokens created before roles existed are user tokens
                role=record.get("role", ROLE_USER),
            )
        except (ValueError, KeyError, TypeError, AttributeError):
            return None

    @override
    async def create_token(self, team: str, name: str, role: str, ttl_seconds: int) -> str:
        token, token_hash = new_token()
        pipe = self.cache_conn.pipeline(transaction=True)
        pipe.set(token_key(token_hash), json.dumps(token_record(team, name, role, ttl_seconds)), ex=ttl_seconds)
        # indexed like CLI tokens, so `tollgate token list` shows it and `tollgate token revoke` can end it
        pipe.sadd(TOKEN_INDEX_KEY, token_hash)
        await pipe.execute()
        return token

    @override
    async def save(self, key: Any, value: Any, timeout: int | None = None) -> None:
        await self.cache_conn.set(key, value, ex=timeout)

    @override
    async def search(self, key: Any) -> Any:
        return await self.cache_conn.get(key)

    @override
    async def increment(self, key: ATOMIC_COUNTERS) -> int:
        return await self.cache_conn.incr(key)

    @override
    async def decrement(self, key: ATOMIC_COUNTERS) -> int:
        return await self.cache_conn.decr(key)

