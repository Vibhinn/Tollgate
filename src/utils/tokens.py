import hashlib
import re

TOKEN_PREFIX = "tg_"
TOKEN_KEY_PREFIX = "token:"
TOKEN_INDEX_KEY = "tokens:index"

# team and name end up inside Redis keys and reports, so no ":" or spaces
IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")


def hash_token(token: str) -> str:
    """Only the hash is stored, so a Redis dump does not hand out working tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


def token_key(token_hash: str) -> str:
    return f"{TOKEN_KEY_PREFIX}{token_hash}"
