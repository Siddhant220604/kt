import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import dependencies
from config import rate_limits
from fastapi import HTTPException


class FakeClient:
    def __init__(self, host):
        self.host = host


class FakeRequest:
    """Minimal stand-in for fastapi.Request - just enough for security.get_client_ip()."""
    def __init__(self, ip='1.2.3.4'):
        self.headers = {}
        self.client = FakeClient(ip)


class FakeDatetime:
    """Lets tests advance time deterministically instead of sleeping for real."""
    _current = datetime.now(timezone.utc)

    @classmethod
    def now(cls, tz=None):
        return cls._current

    @classmethod
    def set(cls, dt):
        cls._current = dt

    @classmethod
    def advance(cls, seconds):
        cls._current += timedelta(seconds=seconds)


@pytest.fixture(autouse=True)
def _reset_rate_limit_state(monkeypatch):
    """Every test gets a clean slate: fresh in-memory buckets and a controllable clock."""
    from collections import defaultdict
    monkeypatch.setattr(dependencies, '_rate_limit_buckets', defaultdict(list))
    monkeypatch.setattr(dependencies, '_auth_attempts', {})
    FakeDatetime.set(datetime.now(timezone.utc))
    monkeypatch.setattr(dependencies, 'datetime', FakeDatetime)
    yield


def test_get_bucket_limit_falls_back_to_tier_default(monkeypatch):
    monkeypatch.delenv('RATE_LIMIT_SOME_BUCKET_MAX_REQUESTS', raising=False)
    monkeypatch.delenv('RATE_LIMIT_SOME_BUCKET_WINDOW_SECONDS', raising=False)
    assert rate_limits.get_bucket_limit('some_bucket', 20, 900) == (20, 900)


def test_get_bucket_limit_honors_per_bucket_env_override(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_CONTACT_SUBMIT_MAX_REQUESTS', '3')
    monkeypatch.setenv('RATE_LIMIT_CONTACT_SUBMIT_WINDOW_SECONDS', '60')
    assert rate_limits.get_bucket_limit('contact_submit', 5, 900) == (3, 60)


def test_sliding_window_allows_up_to_max_then_blocks():
    req = FakeRequest()
    for _ in range(3):
        dependencies.check_rate_limit(req, 'test_bucket', max_requests=3, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
        dependencies.check_rate_limit(req, 'test_bucket', max_requests=3, window_seconds=60)
    assert exc.value.status_code == 429


def test_sliding_window_resets_after_window_expires():
    req = FakeRequest()
    dependencies.check_rate_limit(req, 'test_bucket', max_requests=1, window_seconds=10)
    with pytest.raises(HTTPException):
        dependencies.check_rate_limit(req, 'test_bucket', max_requests=1, window_seconds=10)
    FakeDatetime.advance(11)
    # Window has fully rolled over - should be allowed again without raising.
    dependencies.check_rate_limit(req, 'test_bucket', max_requests=1, window_seconds=10)


def test_sliding_window_is_isolated_per_ip():
    req_a = FakeRequest('1.1.1.1')
    req_b = FakeRequest('2.2.2.2')
    dependencies.check_rate_limit(req_a, 'test_bucket', max_requests=1, window_seconds=60)
    with pytest.raises(HTTPException):
        dependencies.check_rate_limit(req_a, 'test_bucket', max_requests=1, window_seconds=60)
    # A different IP has its own independent bucket.
    dependencies.check_rate_limit(req_b, 'test_bucket', max_requests=1, window_seconds=60)


def test_auth_backoff_grows_exponentially(monkeypatch):
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_BASE_SECONDS', 2.0)
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_MAX_SECONDS', 900.0)
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_RESET_SECONDS', 3600)
    assert dependencies._auth_backoff_seconds(0) == 0
    assert dependencies._auth_backoff_seconds(1) == 2.0
    assert dependencies._auth_backoff_seconds(2) == 4.0
    assert dependencies._auth_backoff_seconds(3) == 8.0
    assert dependencies._auth_backoff_seconds(4) == 16.0


def test_auth_backoff_caps_at_max(monkeypatch):
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_BASE_SECONDS', 2.0)
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_MAX_SECONDS', 10.0)
    assert dependencies._auth_backoff_seconds(10) == 10.0


def test_check_auth_rate_limit_blocks_immediately_after_a_failure_then_allows_after_backoff(monkeypatch):
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_BASE_SECONDS', 5.0)
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_MAX_SECONDS', 900.0)
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_RESET_SECONDS', 3600)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_MAX_ATTEMPTS', 1000)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_WINDOW_SECONDS', 900)

    req = FakeRequest()
    # No prior failures - should pass silently.
    dependencies.check_auth_rate_limit(req, 'test_login', 'user@example.com')
    dependencies.record_auth_failure(req, 'test_login', 'user@example.com')

    # Immediately retrying (same IP, same account) should now be in backoff.
    with pytest.raises(HTTPException) as exc:
        dependencies.check_auth_rate_limit(req, 'test_login', 'user@example.com')
    assert exc.value.status_code == 429
    assert 'Retry-After' in exc.value.headers

    # After the backoff window elapses, it should be allowed again.
    FakeDatetime.advance(6)
    dependencies.check_auth_rate_limit(req, 'test_login', 'user@example.com')


def test_check_auth_rate_limit_is_independent_per_account(monkeypatch):
    # Failing for one account from one IP must not block a *different* account being tried
    # from a *different* IP - i.e. account-level backoff state doesn't leak across accounts.
    # (A failure also engages that IP's own backoff by design - see the flat-cap test below
    # for why that matters - so this test deliberately uses two different IPs to isolate the
    # per-account dimension from the per-IP dimension.)
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_BASE_SECONDS', 100.0)
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_MAX_SECONDS', 900.0)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_MAX_ATTEMPTS', 1000)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_WINDOW_SECONDS', 900)

    req_victim = FakeRequest('1.1.1.1')
    req_other = FakeRequest('2.2.2.2')
    dependencies.record_auth_failure(req_victim, 'test_login', 'victim@example.com')
    with pytest.raises(HTTPException):
        dependencies.check_auth_rate_limit(req_victim, 'test_login', 'victim@example.com')

    dependencies.check_auth_rate_limit(req_other, 'test_login', 'someone-else@example.com')


def test_check_auth_rate_limit_failure_also_engages_that_ips_own_backoff(monkeypatch):
    # By design, a failure records against *both* the account and the IP that made it - so
    # the same IP retrying against a *different* account right after is still slowed down
    # (this is what stops one IP from rapid-fire guessing across many accounts).
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_BASE_SECONDS', 100.0)
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_MAX_SECONDS', 900.0)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_MAX_ATTEMPTS', 1000)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_WINDOW_SECONDS', 900)

    req = FakeRequest('1.1.1.1')
    dependencies.record_auth_failure(req, 'test_login', 'victim@example.com')
    with pytest.raises(HTTPException):
        dependencies.check_auth_rate_limit(req, 'test_login', 'someone-else@example.com')


def test_check_auth_rate_limit_flat_ip_cap_blocks_even_without_failures(monkeypatch):
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_BASE_SECONDS', 0.0)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_MAX_ATTEMPTS', 2)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_WINDOW_SECONDS', 900)

    req = FakeRequest()
    dependencies.check_auth_rate_limit(req, 'test_login', 'a@example.com')
    dependencies.check_auth_rate_limit(req, 'test_login', 'b@example.com')
    with pytest.raises(HTTPException):
        # Third attempt in the window from the same IP, even against a third distinct
        # account with no prior failures, is stopped by the flat per-IP ceiling.
        dependencies.check_auth_rate_limit(req, 'test_login', 'c@example.com')


def test_clear_auth_attempts_resets_backoff(monkeypatch):
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_BASE_SECONDS', 100.0)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_MAX_ATTEMPTS', 1000)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_WINDOW_SECONDS', 900)

    req = FakeRequest()
    dependencies.record_auth_failure(req, 'test_login', 'user@example.com')
    with pytest.raises(HTTPException):
        dependencies.check_auth_rate_limit(req, 'test_login', 'user@example.com')

    dependencies.clear_auth_attempts(req, 'test_login', 'user@example.com')
    # Successful login clears both IP and account backoff, so the next attempt isn't blocked.
    dependencies.check_auth_rate_limit(req, 'test_login', 'user@example.com')


def test_auth_backoff_state_forgotten_after_reset_window(monkeypatch):
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_BASE_SECONDS', 2.0)
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_MAX_SECONDS', 900.0)
    monkeypatch.setattr(rate_limits, 'AUTH_BACKOFF_RESET_SECONDS', 100)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_MAX_ATTEMPTS', 1000)
    monkeypatch.setattr(rate_limits, 'AUTH_IP_WINDOW_SECONDS', 900)

    req = FakeRequest()
    dependencies.record_auth_failure(req, 'test_login', 'user@example.com')
    FakeDatetime.advance(101)
    # Old failure is old enough to be forgotten entirely, not just past its own backoff.
    dependencies.check_auth_rate_limit(req, 'test_login', 'user@example.com')
    assert 'test_login:account:user@example.com' not in dependencies._auth_attempts


def test_authenticated_rate_limit_keyed_by_account_not_ip(monkeypatch):
    monkeypatch.setenv('RATE_LIMIT_TEST_AUTHENTICATED_BUCKET_MAX_REQUESTS', '1')
    monkeypatch.setenv('RATE_LIMIT_TEST_AUTHENTICATED_BUCKET_WINDOW_SECONDS', '900')

    req = FakeRequest('9.9.9.9')
    dependencies.check_authenticated_rate_limit(req, 'test_authenticated_bucket', 'customer-1')
    with pytest.raises(HTTPException):
        dependencies.check_authenticated_rate_limit(req, 'test_authenticated_bucket', 'customer-1')
    # A different account, same IP, has its own independent bucket (a shared office IP
    # shouldn't throttle one customer's authenticated actions because of another's).
    dependencies.check_authenticated_rate_limit(req, 'test_authenticated_bucket', 'customer-2')
