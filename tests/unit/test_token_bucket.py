import pytest

from app.api.limiter import TokenBucket


class FakeClock:
    def __init__(self, start: float = 1_000.0):
        self.now = start

    def time(self):
        return self.now

    def advance(self, seconds: float):
        self.now += seconds


@pytest.fixture
def clock(monkeypatch):
    fake_clock = FakeClock()
    monkeypatch.setattr("src.app.limiter.bucket.time.time", fake_clock.time)
    return fake_clock


def test_starts_full(clock):
    bucket = TokenBucket(max_tokens=5, refill_rate=1, time_interval=1.0)
    assert bucket.get_remaining() == 5


def test_request_allowed_consumes_tokens(clock):
    bucket = TokenBucket(max_tokens=3, refill_rate=1, time_interval=1.0)

    assert bucket.request_allowed() is True
    assert bucket.get_remaining() == 2
    assert bucket.request_allowed() is True
    assert bucket.get_remaining() == 1


def test_request_denied_when_exhausted(clock):
    bucket = TokenBucket(max_tokens=1, refill_rate=1, time_interval=1.0)

    assert bucket.request_allowed() is True
    assert bucket.request_allowed() is False
    assert bucket.get_remaining() == 0


def test_request_allowed_supports_multi_token_cost(clock):
    bucket = TokenBucket(max_tokens=5, refill_rate=1, time_interval=1.0)

    assert bucket.request_allowed(tokens=3) is True
    assert bucket.get_remaining() == 2
    assert bucket.request_allowed(tokens=3) is False
    assert bucket.get_remaining() == 2


def test_refill_after_interval_elapses(clock):
    bucket = TokenBucket(max_tokens=5, refill_rate=2, time_interval=1.0)
    bucket.request_allowed(tokens=5)
    assert bucket.get_remaining() == 0

    clock.advance(1.0)
    assert bucket.get_remaining() == 2


def test_refill_caps_at_max_tokens(clock):
    bucket = TokenBucket(max_tokens=5, refill_rate=10, time_interval=1.0)
    bucket.request_allowed(tokens=5)

    clock.advance(1.0)
    assert bucket.get_remaining() == 5


def test_no_refill_before_interval_elapses(clock):
    bucket = TokenBucket(max_tokens=5, refill_rate=1, time_interval=10.0)
    bucket.request_allowed(tokens=5)

    clock.advance(5.0)
    assert bucket.get_remaining() == 0


def test_refill_accounts_for_multiple_elapsed_intervals(clock):
    bucket = TokenBucket(max_tokens=10, refill_rate=1, time_interval=1.0)
    bucket.request_allowed(tokens=10)

    clock.advance(3.5)
    assert bucket.get_remaining() == 3


def test_get_reset_time_tracks_last_refill(clock):
    bucket = TokenBucket(max_tokens=5, refill_rate=1, time_interval=2.0)
    assert bucket.get_reset_time() == pytest.approx(1_000.0 + 2.0)

    clock.advance(2.0)
    bucket.get_remaining()  # triggers refill, updates last_refill_time
    assert bucket.get_reset_time() == pytest.approx(1_002.0 + 2.0)
