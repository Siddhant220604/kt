from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Optional

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
import jwt

from auth import decode_access_token
from security import get_client_ip

bearer_scheme = HTTPBearer(auto_error=False)

_failed_login_attempts: Dict[str, list[datetime]] = defaultdict(list)
MAX_FAILED_LOGIN_ATTEMPTS = 5
FAILED_LOGIN_WINDOW_SECONDS = 15 * 60


def _cleanup_attempts(ip: str) -> list[datetime]:
    now = datetime.now(timezone.utc)
    attempts = [ts for ts in _failed_login_attempts[ip] if (now - ts).total_seconds() <= FAILED_LOGIN_WINDOW_SECONDS]
    _failed_login_attempts[ip] = attempts
    return attempts


def check_login_rate_limit(request: Request) -> None:
    ip = get_client_ip(request)
    attempts = _cleanup_attempts(ip)
    if len(attempts) >= MAX_FAILED_LOGIN_ATTEMPTS:
        raise HTTPException(status_code=429, detail='Too many login attempts. Try again later.')


def record_failed_login(request: Request) -> None:
    ip = get_client_ip(request)
    attempts = _cleanup_attempts(ip)
    attempts.append(datetime.now(timezone.utc))
    _failed_login_attempts[ip] = attempts


def clear_failed_logins(request: Request) -> None:
    ip = get_client_ip(request)
    _failed_login_attempts.pop(ip, None)


# Generic per-IP sliding-window rate limiter for unauthenticated, publicly-writable
# endpoints (contact form, reviews, ...) that would otherwise have no abuse protection.
_rate_limit_buckets: Dict[str, list[datetime]] = defaultdict(list)


def check_rate_limit(request: Request, bucket: str, max_requests: int, window_seconds: int) -> None:
    key = f'{bucket}:{get_client_ip(request)}'
    now = datetime.now(timezone.utc)
    attempts = [ts for ts in _rate_limit_buckets[key] if (now - ts).total_seconds() <= window_seconds]
    if len(attempts) >= max_requests:
        _rate_limit_buckets[key] = attempts
        raise HTTPException(status_code=429, detail='Too many requests. Please try again later.')
    attempts.append(now)
    _rate_limit_buckets[key] = attempts


async def require_admin(creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme)) -> Dict:
    if creds is None or creds.scheme.lower() != 'bearer':
        raise HTTPException(status_code=401, detail='Missing or invalid authorization header')
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail='Token expired')
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail='Invalid token')
    if payload.get('role') != 'admin':
        raise HTTPException(status_code=403, detail='Admin access required')

    from server import db as server_db
    user = await server_db.users.find_one({'id': payload.get('sub')})
    if not user:
        raise HTTPException(status_code=401, detail='Invalid token')
    if payload.get('token_version', 0) != user.get('token_version', 0):
        raise HTTPException(status_code=401, detail='Token invalidated')
    return payload
