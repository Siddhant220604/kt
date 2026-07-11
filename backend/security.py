import re
from html import escape
from typing import Any, Dict
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

CONTROL_CHAR_RE = re.compile(r'[\x00-\x1f\x7f]+')


def sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        text = CONTROL_CHAR_RE.sub('', value).strip()
        return escape(text)
    if isinstance(value, dict):
        return sanitize_dict(value)
    if isinstance(value, list):
        return [sanitize_value(item) for item in value]
    return value


def sanitize_dict(value: Dict[str, Any]) -> Dict[str, Any]:
    return {k: sanitize_value(v) for k, v in value.items()}


def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip()
    client_host = request.client.host if request.client else 'unknown'
    return client_host


class SecureHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response
