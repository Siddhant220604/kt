import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import jwt
from passlib.context import CryptContext

JWT_SECRET = os.environ['JWT_SECRET']
JWT_ALGO = 'HS256'
JWT_EXPIRE_MINUTES = int(os.environ.get('JWT_EXPIRE_MINUTES', '120'))

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
