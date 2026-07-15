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


_CSV_FORMULA_LEAD_CHARS = ('=', '+', '-', '@', '\t', '\r')


def csv_safe(value: Any) -> Any:
    """Neutralizes CSV/formula injection: a cell starting with =, +, -, @ (or a tab/CR that can
    push a formula char to the start once opened) is interpreted as a formula by Excel/Sheets,
    not literal text - e.g. a customer entering "=HYPERLINK(...)" as their name could run
    arbitrary formulas in whoever's spreadsheet later opens an admin CSV export. Prefixing with
    a single quote forces it to display as literal text instead."""
    if isinstance(value, str) and value.startswith(_CSV_FORMULA_LEAD_CHARS):
        return "'" + value
    return value


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
        # Harmless to send over plain HTTP (browsers only honor it on responses actually
        # received over HTTPS), so no need to gate on request scheme.
        response.headers['Strict-Transport-Security'] = 'max-age=63072000; includeSubDomains'
        return response
