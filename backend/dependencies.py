from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from auth import decode_access_token
from security import get_client_ip
from config import rate_limits

bearer_scheme = HTTPBearer(auto_error=False)


# ------------------------------------------------------------------------------------------
# Generic sliding-window limiter. Keyed by an arbitrary string (caller decides whether that's
# an IP, an account id, or both) so it backs all three tiers below instead of duplicating the
# window bookkeeping per tier.
# ------------------------------------------------------------------------------------------
_rate_limit_buckets: Dict[str, list[datetime]] = defaultdict(list)


def _check_sliding_window(key: str, max_requests: int, window_seconds: int) -> None:
    now = datetime.now(timezone.utc)
    attempts = [ts for ts in _rate_limit_buckets[key] if (now - ts).total_seconds() <= window_seconds]
    if len(attempts) >= max_requests:
        _rate_limit_buckets[key] = attempts
        raise HTTPException(status_code=429, detail='Too many requests. Please try again later.')
    attempts.append(now)
    _rate_limit_buckets[key] = attempts


def check_rate_limit(request: Request, bucket: str, max_requests: int, window_seconds: int) -> None:
    """Per-IP sliding window. Thresholds are passed in by the caller (see the tiered wrappers
    below for the recommended, configurable way to do that) rather than hardcoded here."""
    _check_sliding_window(f'{bucket}:ip:{get_client_ip(request)}', max_requests, window_seconds)


def check_public_rate_limit(request: Request, bucket: str) -> None:
    """Moderate, per-IP limit for unauthenticated but publicly-writable endpoints (contact
    form, reviews, cart sync). Thresholds come from the PUBLIC tier, overridable per-bucket -
    see config.rate_limits.get_bucket_limit()."""
    max_requests, window_seconds = rate_limits.get_bucket_limit(bucket, rate_limits.PUBLIC_MAX_REQUESTS, rate_limits.PUBLIC_WINDOW_SECONDS)
    check_rate_limit(request, bucket, max_requests, window_seconds)


def check_authenticated_rate_limit(request: Request, bucket: str, identity: str) -> None:
    """Loose, per-account limit for actions by an already-authenticated user (placing an
    order, updating a profile). Keyed by account id rather than IP - a valid bearer token is
    itself an abuse barrier, and shared IPs (offices, mobile carriers) shouldn't throttle each
    other's authenticated actions. Thresholds come from the AUTHENTICATED tier, overridable
    per-bucket."""
    max_requests, window_seconds = rate_limits.get_bucket_limit(bucket, rate_limits.AUTHENTICATED_MAX_REQUESTS, rate_limits.AUTHENTICATED_WINDOW_SECONDS)
    _check_sliding_window(f'{bucket}:account:{identity}', max_requests, window_seconds)


# ------------------------------------------------------------------------------------------
# AUTH tier: login, signup, password change. A flat per-IP ceiling (bounds raw flooding) plus
# exponential backoff triggered by failures, tracked independently per-IP *and* per-account, so
# both a distributed attack on one account and repeated attempts against many accounts from one
# IP are slowed down - without a hard lockout that a legitimate user could get stuck behind.
# ------------------------------------------------------------------------------------------
@dataclass
class _AttemptState:
    count: int = 0
    last_attempt: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


_auth_attempts: Dict[str, _AttemptState] = {}


def _auth_backoff_seconds(failure_count: int) -> float:
    if failure_count <= 0:
        return 0.0
    return min(rate_limits.AUTH_BACKOFF_MAX_SECONDS, rate_limits.AUTH_BACKOFF_BASE_SECONDS * (2 ** (failure_count - 1)))


def _check_auth_backoff(key: str) -> None:
    now = datetime.now(timezone.utc)
    state = _auth_attempts.get(key)
    if not state:
        return
    # A quiet key older than the reset window is forgotten entirely, so a stale failure from
    # long ago can't still be held against a rare/returning legitimate user.
    if (now - state.last_attempt).total_seconds() > rate_limits.AUTH_BACKOFF_RESET_SECONDS:
        _auth_attempts.pop(key, None)
        return
    wait = _auth_backoff_seconds(state.count)
    elapsed = (now - state.last_attempt).total_seconds()
    if elapsed < wait:
        retry_after = max(1, round(wait - elapsed))
        raise HTTPException(
            status_code=429,
            detail=f'Too many attempts. Please try again in {retry_after} seconds.',
            headers={'Retry-After': str(retry_after)},
        )


def _record_auth_attempt(key: str) -> None:
    now = datetime.now(timezone.utc)
    state = _auth_attempts.get(key)
    if not state:
        state = _AttemptState(count=0, last_attempt=now)
        _auth_attempts[key] = state
    state.count += 1
    state.last_attempt = now


def _clear_auth_attempts(key: str) -> None:
    _auth_attempts.pop(key, None)


def check_auth_rate_limit(request: Request, bucket: str, account_key: str) -> None:
    """Call before attempting an authentication action (verifying a password, creating an
    account). Raises 429 if the flat per-IP ceiling for `bucket` is exceeded, or if either the
    caller's IP or `account_key` is still within its exponential-backoff cooldown from a
    recent failure."""
    ip = get_client_ip(request)
    max_requests, window_seconds = rate_limits.get_bucket_limit(bucket, rate_limits.AUTH_IP_MAX_ATTEMPTS, rate_limits.AUTH_IP_WINDOW_SECONDS)
    check_rate_limit(request, bucket, max_requests, window_seconds)
    _check_auth_backoff(f'{bucket}:ip:{ip}')
    _check_auth_backoff(f'{bucket}:account:{account_key}')


def record_auth_failure(request: Request, bucket: str, account_key: str) -> None:
    """Call after an authentication action fails (wrong password, duplicate signup) to advance
    the exponential backoff for both the caller's IP and the targeted account."""
    ip = get_client_ip(request)
    _record_auth_attempt(f'{bucket}:ip:{ip}')
    _record_auth_attempt(f'{bucket}:account:{account_key}')


def clear_auth_attempts(request: Request, bucket: str, account_key: str) -> None:
    """Call after an authentication action succeeds to reset the backoff for both keys."""
    ip = get_client_ip(request)
    _clear_auth_attempts(f'{bucket}:ip:{ip}')
    _clear_auth_attempts(f'{bucket}:account:{account_key}')


async def _require_admin_role(creds: Optional[HTTPAuthorizationCredentials], allowed_roles: set) -> Dict:
    if creds is None or creds.scheme.lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Missing or invalid authorization header')
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expired')
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail='Invalid token')
    if payload.get('role') not in allowed_roles:
        raise HTTPException(status_code=403, detail='Admin access required')

    from server import db as server_db
    user = await server_db.users.find_one({'id': payload.get('sub')})
    if not user:
        raise HTTPException(status_code=401, detail='Invalid token')
    if payload.get('token_version', 0) != user.get('token_version', 0):
        raise HTTPException(status_code=401, detail='Token invalidated')
    return payload


async def require_admin(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Dict:
    """Full admin only. Used on everything sensitive - settings, catalog/coupon/banner
    management, financial exports, user management, moderation, audit log - anything outside
    the restricted 'staff' role's order-fulfillment scope (see require_staff)."""
    return await _require_admin_role(creds, {'admin'})


async def require_staff(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Dict:
    """Full admin OR the restricted 'staff' role. Only wired up on the endpoints a staff
    account should reach: their own profile, and order fulfillment (view/update status/
    refund/return/bulk actions, and looking up customers for order context). Everything else
    stays behind require_admin."""
    return await _require_admin_role(creds, {'admin', 'staff'})


async def require_customer(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Dict:
    """Auth for customer accounts (email/password signup+login). Mirrors require_admin's
    token_version check so changing password invalidates any other still-logged-in session."""
    if creds is None or creds.scheme.lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Missing or invalid authorization header')
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expired')
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail='Invalid token')
    if payload.get('role') != 'customer':
        raise HTTPException(status_code=403, detail='Customer access required')

    from server import db as server_db
    customer = await server_db.customers.find_one({'id': payload.get('sub')})
    if not customer:
        raise HTTPException(status_code=401, detail='Invalid token')
    if payload.get('token_version', 0) != customer.get('token_version', 0):
        raise HTTPException(status_code=401, detail='Token invalidated')
    return payload


async def optional_admin(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Optional[Dict]:
    """Like require_admin, but returns None instead of raising when there's no/invalid token.

    For endpoints that are usable by both an unauthenticated customer (via some other
    proof of ownership, e.g. a matching mobile number) and an authenticated admin.
    """
    if creds is None or creds.scheme.lower() != 'bearer':
        return None
    try:
        return await require_admin(creds)
    except HTTPException:
        return None
