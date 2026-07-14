"""Rate-limit configuration, all overridable via environment variables (never hardcoded in
call sites). Three tiers, matching how abuse-prone each kind of endpoint is:

- AUTH (strict): login, signup, password change. Combines a flat per-IP request ceiling with
  exponential backoff on failures, checked both per-IP and per-account.
- PUBLIC (moderate): unauthenticated but publicly writable endpoints (contact form, reviews,
  cart sync) - a flat per-IP sliding window.
- AUTHENTICATED (loose): actions by an already-authenticated user (placing an order, updating
  a profile) - a flat per-account sliding window. A valid bearer token is itself an abuse
  barrier, so these limits are deliberately generous.

Every individual bucket (e.g. "admin_login", "contact_submit") can also be overridden
independently - see get_bucket_limit() - by setting RATE_LIMIT_<BUCKET>_MAX_REQUESTS /
RATE_LIMIT_<BUCKET>_WINDOW_SECONDS, without needing a code change.
"""
import os
from typing import Tuple


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def _float_env(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


# ------------------ AUTH tier ------------------
AUTH_IP_MAX_ATTEMPTS = _int_env('RATE_LIMIT_AUTH_IP_MAX_ATTEMPTS', 20)
AUTH_IP_WINDOW_SECONDS = _int_env('RATE_LIMIT_AUTH_IP_WINDOW_SECONDS', 15 * 60)
# Backoff grows as: min(cap, base * 2^(failures - 1)) seconds between attempts for the same
# IP/account, e.g. with the defaults below: 2s, 4s, 8s, 16s, ... capped at 15 minutes - so
# a mistyped password once or twice barely slows anyone down, but sustained guessing gets
# throttled hard without ever fully locking the account out.
AUTH_BACKOFF_BASE_SECONDS = _float_env('RATE_LIMIT_AUTH_BACKOFF_BASE_SECONDS', 2)
AUTH_BACKOFF_MAX_SECONDS = _float_env('RATE_LIMIT_AUTH_BACKOFF_MAX_SECONDS', 15 * 60)
# A backoff record is forgotten after this many quiet seconds, so an old failure from days ago
# can't still be counted against a rare/returning legitimate user.
AUTH_BACKOFF_RESET_SECONDS = _int_env('RATE_LIMIT_AUTH_BACKOFF_RESET_SECONDS', 60 * 60)

# ------------------ PUBLIC tier ------------------
PUBLIC_MAX_REQUESTS = _int_env('RATE_LIMIT_PUBLIC_MAX_REQUESTS', 20)
PUBLIC_WINDOW_SECONDS = _int_env('RATE_LIMIT_PUBLIC_WINDOW_SECONDS', 15 * 60)

# ------------------ AUTHENTICATED tier ------------------
AUTHENTICATED_MAX_REQUESTS = _int_env('RATE_LIMIT_AUTHENTICATED_MAX_REQUESTS', 120)
AUTHENTICATED_WINDOW_SECONDS = _int_env('RATE_LIMIT_AUTHENTICATED_WINDOW_SECONDS', 15 * 60)


def get_bucket_limit(bucket: str, tier_max_requests: int, tier_window_seconds: int) -> Tuple[int, int]:
    """Per-bucket override, falling back to the tier default. E.g. for bucket="contact_submit"
    this checks RATE_LIMIT_CONTACT_SUBMIT_MAX_REQUESTS / _WINDOW_SECONDS before falling back to
    the PUBLIC tier's defaults, so any single endpoint's threshold can be tuned in production
    without touching code."""
    prefix = f'RATE_LIMIT_{bucket.upper()}'
    max_requests = _int_env(f'{prefix}_MAX_REQUESTS', tier_max_requests)
    window_seconds = _int_env(f'{prefix}_WINDOW_SECONDS', tier_window_seconds)
    return max_requests, window_seconds
