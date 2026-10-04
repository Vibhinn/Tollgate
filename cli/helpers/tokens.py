from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import redis

from src.utils.config import Config
from src.utils.tokens import TOKEN_PREFIX, TOKEN_INDEX_KEY, IDENTIFIER_PATTERN, hash_token, token_key
from src.utils.types import ConfigurationEnums, ConfigurationSection, ConfigurationOption

TOKEN_ID_LENGTH = 12
_TTL_PATTERN = re.compile(r"^(\d+)([dh])$")
_TTL_UNIT_SECONDS = {"d": 86_400, "h": 3_600}


@dataclass(frozen=True)
class TokenRecord:
    id: str
    team: str
    name: str
    created_at: str
    expires_at: str | None


def parse_ttl(value: str) -> int | None:
    """"30d" / "12h" -> seconds; "never" -> None."""
    if value == "never":
        return None
    match = _TTL_PATTERN.match(value)
    if not match or int(match.group(1)) == 0:
        raise ValueError(f"Invalid TTL '{value}'. Use e.g. 30d, 12h or never.")
    return int(match.group(1)) * _TTL_UNIT_SECONDS[match.group(2)]


def validate_identifier(kind: str, value: str) -> None:
    if not IDENTIFIER_PATTERN.match(value):
        raise ValueError(f"Invalid {kind} '{value}'. Use lowercase letters, digits and '-', up to 63 characters.")


def redis_from_config(config: Config) -> redis.Redis:
    password = config.get_config(ConfigurationSection.REDIS, ConfigurationOption.PASSWORD)
    return redis.Redis(
        host=config.get_config(ConfigurationSection.REDIS, ConfigurationOption.HOST),
        port=int(config.get_config(ConfigurationSection.REDIS, ConfigurationOption.PORT)),
        password=None if password == ConfigurationEnums.API_KEY_NOT_CONFIGURED.value else password,
        ssl=config.get_config(ConfigurationSection.REDIS, ConfigurationOption.TLS) == "true",
        decode_responses=True,
        socket_connect_timeout=3.0,
    )


class TokenStore:
    """Tokens live in Redis as token:<sha256> -> record, plus an index set of hashes for list/revoke."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    def create(self, team: str, name: str, ttl_seconds: int | None) -> tuple[str, TokenRecord]:
        validate_identifier("team", team)
        validate_identifier("name", name)

        token = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
        token_hash = hash_token(token)
        now = datetime.now(timezone.utc)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds") if ttl_seconds else None

        record = {
            "user_id": f"{team}:{name}",
            "team": team,
            "name": name,
            "created_at": now.isoformat(timespec="seconds"),
            "expires_at": expires_at,
        }
        pipe = self.redis.pipeline()
        pipe.set(token_key(token_hash), json.dumps(record), ex=ttl_seconds)
        pipe.sadd(TOKEN_INDEX_KEY, token_hash)
        pipe.execute()

        return token, self._to_record(token_hash, record)

    def list(self, team: str | None = None) -> list[TokenRecord]:
        records = [self._to_record(token_hash, stored) for token_hash, stored in self._load_live()]
        return sorted(
            (record for record in records if team is None or record.team == team),
            key=lambda record: (record.team, record.name, record.created_at),
        )

    def revoke(self, token_or_id: str) -> bool:
        """Accepts the full token or the ID shown by `list`."""
        if token_or_id.startswith(TOKEN_PREFIX):
            return self._delete([hash_token(token_or_id)]) == 1

        matches = [h for h in self.redis.smembers(TOKEN_INDEX_KEY) if h.startswith(token_or_id)]
        if len(matches) > 1:
            raise ValueError(f"ID '{token_or_id}' matches more than one token. Use the full ID from `tollgate token list`.")
        return self._delete(matches) == 1

    def revoke_identity(self, team: str, name: str) -> int:
        return self._delete([
            token_hash for token_hash, stored in self._load_live()
            if stored["team"] == team and stored["name"] == name
        ])

    def _load_live(self) -> list[tuple[str, dict]]:
        """Records of unexpired tokens. Hashes whose token expired are dropped from the index."""
        hashes = list(self.redis.smembers(TOKEN_INDEX_KEY))
        if not hashes:
            return []

        live, expired = [], []
        for token_hash, stored in zip(hashes, self.redis.mget([token_key(h) for h in hashes])):
            if stored is None:
                expired.append(token_hash)
            else:
                live.append((token_hash, json.loads(stored)))

        if expired:
            self.redis.srem(TOKEN_INDEX_KEY, *expired)
        return live

    def _delete(self, hashes: list[str]) -> int:
        if not hashes:
            return 0
        deleted = self.redis.delete(*[token_key(h) for h in hashes])
        self.redis.srem(TOKEN_INDEX_KEY, *hashes)
        return deleted

    @staticmethod
    def _to_record(token_hash: str, stored: dict) -> TokenRecord:
        return TokenRecord(
            id=token_hash[:TOKEN_ID_LENGTH],
            team=stored["team"],
            name=stored["name"],
            created_at=stored["created_at"],
            expires_at=stored.get("expires_at"),
        )
