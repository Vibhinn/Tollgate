import json
from unittest.mock import patch

import fakeredis
import pytest
from click.testing import CliRunner

from cli.helpers.tokens import TokenStore, parse_ttl, TOKEN_ID_LENGTH
from cli.init import cli
from src.utils.tokens import TOKEN_INDEX_KEY, hash_token, token_key


@pytest.fixture
def redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def store(redis_client):
    return TokenStore(redis_client)


# --- TokenStore -------------------------------------------------------------

def test_create_stores_only_the_hash_with_team_name_and_user_id(store, redis_client):
    token, record = store.create("payments", "alice", ttl_seconds=3600)

    assert token.startswith("tg_")
    assert redis_client.get(f"token:{token}") is None
    stored = json.loads(redis_client.get(token_key(hash_token(token))))
    assert stored["user_id"] == "payments:alice"
    assert (stored["team"], stored["name"]) == ("payments", "alice")
    assert 3590 < redis_client.ttl(token_key(hash_token(token))) <= 3600
    assert record.id == hash_token(token)[:TOKEN_ID_LENGTH]


def test_never_expiring_token_has_no_ttl(store, redis_client):
    token, record = store.create("payments", "invoice-bot", ttl_seconds=None)

    assert redis_client.ttl(token_key(hash_token(token))) == -1
    assert record.expires_at is None


def test_same_team_and_name_share_a_user_id_but_get_different_tokens(store, redis_client):
    first, _ = store.create("payments", "alice", 3600)
    second, _ = store.create("payments", "alice", 3600)

    assert first != second
    user_ids = {json.loads(redis_client.get(token_key(hash_token(t))))["user_id"] for t in (first, second)}
    assert user_ids == {"payments:alice"}


@pytest.mark.parametrize("team, name", [
    ("Payments", "alice"), ("payments", "alice smith"), ("pay:ments", "alice"), ("", "alice"), ("-pay", "alice"),
])
def test_create_rejects_identifiers_that_would_break_keys(store, team, name):
    with pytest.raises(ValueError):
        store.create(team, name, 3600)


def test_list_filters_by_team_and_drops_expired_tokens_from_the_index(store, redis_client):
    expired, _ = store.create("payments", "alice", 3600)
    store.create("payments", "invoice-bot", 3600)
    store.create("search", "bob", 3600)
    redis_client.delete(token_key(hash_token(expired)))  # what Redis does when the TTL runs out

    assert [(r.team, r.name) for r in store.list()] == [("payments", "invoice-bot"), ("search", "bob")]
    assert [r.name for r in store.list("payments")] == ["invoice-bot"]
    assert hash_token(expired) not in redis_client.smembers(TOKEN_INDEX_KEY)


def test_revoke_by_full_token_or_by_id(store, redis_client):
    by_token, _ = store.create("payments", "alice", 3600)
    by_id, record = store.create("payments", "bob", 3600)

    assert store.revoke(by_token) is True
    assert store.revoke(record.id) is True
    assert redis_client.get(token_key(hash_token(by_token))) is None
    assert redis_client.get(token_key(hash_token(by_id))) is None
    assert store.list() == []


def test_revoke_unknown_token_returns_false(store):
    assert store.revoke("tg_not-a-real-token") is False
    assert store.revoke("abc123") is False


def test_revoke_identity_removes_every_token_of_that_team_and_name_only(store):
    store.create("payments", "alice", 3600)
    store.create("payments", "alice", 3600)
    store.create("payments", "invoice-bot", 3600)

    assert store.revoke_identity("payments", "alice") == 2
    assert [r.name for r in store.list()] == ["invoice-bot"]


@pytest.mark.parametrize("value, expected", [("30d", 30 * 86_400), ("12h", 12 * 3_600), ("never", None)])
def test_parse_ttl(value, expected):
    assert parse_ttl(value) == expected


@pytest.mark.parametrize("value", ["0d", "30", "30m", "-1d", "forever"])
def test_parse_ttl_rejects_bad_values(value):
    with pytest.raises(ValueError):
        parse_ttl(value)


# --- CLI ---------------------------------------------------------------------

@pytest.fixture
def run(store):
    def _run(*args):
        with patch("cli.init._token_store", return_value=store), \
             patch("cli.init.require_config", return_value={}), \
             patch("cli.init.verify_admin") as verify_admin:
            result = CliRunner().invoke(cli, ["token", *args])
        return result, verify_admin
    return _run


def test_cli_create_requires_admin_and_prints_the_token_once(run, store):
    result, verify_admin = run("create", "--team", "payments", "--name", "alice", "--ttl", "30d")

    assert result.exit_code == 0, result.output
    verify_admin.assert_called_once()
    assert "tg_" in result.output
    assert [(r.team, r.name) for r in store.list()] == [("payments", "alice")]


def test_cli_create_rejects_bad_input_before_asking_for_admin_credentials(run, store):
    result, verify_admin = run("create", "--team", "Payments", "--name", "alice")

    assert result.exit_code == 1
    verify_admin.assert_not_called()
    assert store.list() == []


def test_cli_list_shows_ids_but_never_tokens(run, store):
    token, record = store.create("payments", "alice", 3600)

    result, verify_admin = run("list")

    assert result.exit_code == 0
    assert record.id in result.output
    assert token not in result.output
    verify_admin.assert_not_called()


def test_cli_revoke_by_id(run, store):
    _, record = store.create("payments", "alice", 3600)

    result, verify_admin = run("revoke", record.id)

    assert result.exit_code == 0, result.output
    verify_admin.assert_called_once()
    assert store.list() == []


def test_cli_revoke_by_team_and_name(run, store):
    store.create("payments", "alice", 3600)
    store.create("payments", "alice", 3600)

    result, _ = run("revoke", "--team", "payments", "--name", "alice")

    assert result.exit_code == 0, result.output
    assert store.list() == []


@pytest.mark.parametrize("args", [[], ["--team", "payments"], ["abc123", "--team", "payments", "--name", "alice"]])
def test_cli_revoke_needs_exactly_one_way_to_pick_tokens(run, args):
    result, verify_admin = run("revoke", *args)

    assert result.exit_code == 1
    verify_admin.assert_not_called()


def test_cli_revoke_unknown_id_fails(run):
    result, _ = run("revoke", "doesnotexist")

    assert result.exit_code == 1
