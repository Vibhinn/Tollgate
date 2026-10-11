import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone

TOKEN_PREFIX = "tg_"
TOKEN_KEY_PREFIX = "token:"
TOKEN_INDEX_KEY = "tokens:index"
# the short ID shown by `tollgate token list` and used in metrics
TOKEN_ID_LENGTH = 12

ROLE_USER = "user"
ROLE_ADMIN = "admin"     # sees the full metrics breakdown per team, name and token

# team and name end up inside Redis keys and reports, so no ":" or spaces
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def hash_token(token: str) -> str:
    """Only the hash is stored, so a Redis dump does not hand out working tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def token_key(token_hash: str) -> str:
    return f"{TOKEN_KEY_PREFIX}{token_hash}"


def token_id(token_hash: str) -> str:
    return token_hash[:TOKEN_ID_LENGTH]


def new_token() -> tuple[str, str]:
    """A fresh token and its hash. Only the hash is ever stored."""
    token = f"{TOKEN_PREFIX}{secrets.token_urlsafe(32)}"
    return token, hash_token(token)


def token_record(team: str, name: str, role: str, ttl_seconds: int | None) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "user_id": f"{team}:{name}",
        "team": team,
        "name": name,
        "created_at": now.isoformat(timespec="seconds"),
        "expires_at": (now + timedelta(seconds=ttl_seconds)).isoformat(timespec="seconds") if ttl_seconds else None,
        "role": role,
    }
