import pytest

from src.app.limiter.store import RateLimiterStore


@pytest.fixture
def store(monkeypatch, fake_config):
    monkeypatch.setattr("src.app.limiter.store.Config", lambda: fake_config)
    return RateLimiterStore()


def test_reads_bucket_parameters_from_config(store, fake_config):
    bucket = store.get_user_bucket("user-1")
    assert bucket.max_tokens == int(fake_config.get_config("rate_limiter", "max_tokens"))
    assert bucket.refill_rate == int(fake_config.get_config("rate_limiter", "refill_rate"))
    assert bucket.time_interval == float(fake_config.get_config("rate_limiter", "time_interval"))


def test_same_user_gets_same_bucket_instance(store):
    bucket_a = store.get_user_bucket("user-1")
    bucket_b = store.get_user_bucket("user-1")
    assert bucket_a is bucket_b


def test_different_users_get_independent_buckets(store):
    bucket_a = store.get_user_bucket("user-1")
    bucket_b = store.get_user_bucket("user-2")
    assert bucket_a is not bucket_b

    bucket_a.request_allowed(tokens=bucket_a.max_tokens)
    assert bucket_a.get_remaining() == 0
    assert bucket_b.get_remaining() == bucket_b.max_tokens
