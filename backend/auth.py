import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv
import jwt
from passlib.context import CryptContext

logger = logging.getLogger(__name__)

package_dir = Path(__file__).resolve().parent
load_dotenv(package_dir / '.env')
load_dotenv(package_dir.parent / '.env')

JWT_SECRET = os.environ.get('JWT_SECRET', '')
if not JWT_SECRET:
    raise EnvironmentError('JWT_SECRET is not set in the environment or backend/.env')
JWT_ALGO = 'HS256'
JWT_EXPIRE_MINUTES = int(os.environ.get('JWT_EXPIRE_MINUTES', '120'))

_WEAK_JWT_SECRETS = {'devsecret', 'secret', 'changeme', 'password', 'test', 'default', 'admin', 'jwtsecret'}
if JWT_SECRET.lower() in _WEAK_JWT_SECRETS or len(JWT_SECRET) < 32:
    logger.warning(
        'JWT_SECRET looks weak/placeholder (%d chars). Anyone who guesses it can forge admin '
        'tokens. Set a long random value (e.g. `python -c "import secrets; print(secrets.token_urlsafe(48))"`) '
        'in production.',
        len(JWT_SECRET),
    )

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    try:
        return pwd_context.verify(password, hashed_password)
    except Exception:
        return False


def create_access_token(user_id: str, email: str, role: str = 'admin', token_version: int = 0, expires_delta: Optional[timedelta] = None) -> str:
    now = datetime.now(timezone.utc)
    if expires_delta is None:
        expires_delta = timedelta(minutes=JWT_EXPIRE_MINUTES)
    payload: Dict[str, Any] = {
        'sub': user_id,
        'email': email,
        'role': role,
        'token_version': token_version,
        'iat': now,
        'exp': now + expires_delta,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGO)


def decode_access_token(token: str) -> Dict[str, Any]:
    return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
