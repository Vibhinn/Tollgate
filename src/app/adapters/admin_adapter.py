from __future__ import annotations

import asyncio
import hmac
from typing import Any, TYPE_CHECKING

from src.app.exceptions import InvalidAdminCredentials
from src.utils.crypto import verify_password
from src.utils.tokens import ROLE_ADMIN
from src.utils.types import ConfigurationSection, ConfigurationOption

if TYPE_CHECKING:
    from src.utils.config import Config
    from ..ports import CacheRepositoryInterface


class AdminAdapter:
    def __init__(self, config: Config, token_repo: CacheRepositoryInterface):
        self.config = config
        self.token_repo = token_repo
        self._SESSION_TTL_SECONDS = 12 * 60 * 60
        # sessions are listed by `tollgate token list` under this team and name
        self._SESSION_TEAM = "admin"
        self._SESSION_NAME = "dashboard-session"

    async def login(self, username: str, password: str) -> dict[str, Any]:
        """The admin credentials from `tollgate init` in exchange for a short-lived admin token."""
        if not await self._credentials_match(username, password):
            raise InvalidAdminCredentials("Invalid admin username or password.")

        session_token = await self.token_repo.create_token(self._SESSION_TEAM, self._SESSION_NAME, ROLE_ADMIN,
                                                           self._SESSION_TTL_SECONDS)
        return {"session_token": session_token, "token_type": "bearer", "expires_in": self._SESSION_TTL_SECONDS}

    async def _credentials_match(self, username: str, password: str) -> bool:
        stored_username = self.config.get_config(ConfigurationSection.ADMIN, ConfigurationOption.USERNAME)
        stored_hash = self.config.get_config(ConfigurationSection.ADMIN, ConfigurationOption.PASSWORD_HASH)
        username_matches = hmac.compare_digest(username.encode(), stored_username.encode())
        # the hash is deliberately slow (~0.1-0.2s of CPU), so it runs off the event loop
        password_matches = await asyncio.to_thread(verify_password, password, stored_hash)
        return username_matches and password_matches
