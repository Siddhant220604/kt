"""The rate limiter's own memory bookkeeping.

Keys are per-IP and per-account, so their number is bounded only by how many distinct callers
turn up. The sweep that reclaims dead ones must not reclaim live ones: dropping a key early
resets its owner's counter, which is exactly what the limiter exists to prevent.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import dependencies  # noqa: E402


@pytest.fixture(autouse=True)
def clean_state():
    dependencies._rate_limit_buckets.clear()
    dependencies._bucket_windows.clear()
    dependencies._auth_attempts.clear()
    yield
    dependencies._rate_limit_buckets.clear()
    dependencies._bucket_windows.clear()
    dependencies._auth_attempts.clear()


def _force_sweep_next_call():
    dependencies._LAST_SWEEP = datetime.now(timezone.utc) - timedelta(seconds=dependencies._SWEEP_INTERVAL_SECONDS + 1)


def test_expired_keys_are_reclaimed():
    dependencies._check_sliding_window('old:ip:1.1.1.1', max_requests=5, window_seconds=60)
    dependencies._rate_limit_buckets['old:ip:1.1.1.1'] = [datetime.now(timezone.utc) - timedelta(seconds=120)]
    _force_sweep_next_call()

    dependencies._check_sliding_window('other:ip:2.2.2.2', max_requests=5, window_seconds=60)

    assert 'old:ip:1.1.1.1' not in dependencies._rate_limit_buckets
    assert 'old:ip:1.1.1.1' not in dependencies._bucket_windows


def test_a_slow_buckets_key_survives_a_sweep_triggered_by_a_fast_one():
    # The regression this guards: sweeping by the *calling* endpoint's window dropped keys from
    # buckets with longer windows, resetting a counter that was still supposed to be counting.
    slow_key = 'contact_submit:ip:3.3.3.3'
    dependencies._check_sliding_window(slow_key, max_requests=5, window_seconds=15 * 60)
    dependencies._rate_limit_buckets[slow_key] = [datetime.now(timezone.utc) - timedelta(seconds=120)]
    _force_sweep_next_call()

    dependencies._check_sliding_window('pincode_verify:ip:4.4.4.4', max_requests=30, window_seconds=60)

    assert slow_key in dependencies._rate_limit_buckets, 'key from a 15-minute bucket dropped after 2 minutes'


def test_quiet_auth_backoff_records_are_reclaimed():
    dependencies._record_auth_attempt('admin_login:ip:5.5.5.5')
    state = dependencies._auth_attempts['admin_login:ip:5.5.5.5']
    state.last_attempt = datetime.now(timezone.utc) - timedelta(seconds=dependencies.rate_limits.AUTH_BACKOFF_RESET_SECONDS + 60)
    _force_sweep_next_call()

    dependencies._check_sliding_window('anything:ip:6.6.6.6', max_requests=5, window_seconds=60)

    assert 'admin_login:ip:5.5.5.5' not in dependencies._auth_attempts
