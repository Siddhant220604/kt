import ipaddress
import os
import re
from html import escape
from typing import Any, Dict, List, Optional
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


_trusted_proxy_networks_cache: Optional[List] = None


def _trusted_proxy_networks() -> List:
    global _trusted_proxy_networks_cache
    if _trusted_proxy_networks_cache is None:
        raw = os.environ.get('TRUSTED_PROXY_IPS', '127.0.0.1,::1')
        networks = []
        for part in raw.split(','):
            part = part.strip()
            if not part:
                continue
            try:
                networks.append(ipaddress.ip_network(part, strict=False))
            except ValueError:
                pass
        _trusted_proxy_networks_cache = networks
    return _trusted_proxy_networks_cache


def get_client_ip(request: Request) -> str:
    """Returns the caller's real IP, used to key rate limiting and audit logs - so this must not
    be spoofable. Only trusts the X-Forwarded-For header when the immediate TCP peer
    (request.client.host) is itself a configured reverse proxy (TRUSTED_PROXY_IPS env var,
    comma-separated IPs/CIDRs, defaults to loopback only). Without this check, a client that can
    reach the app directly (e.g. a port left open behind a reverse proxy setup) could set
    X-Forwarded-For to any value and bypass IP-based rate limiting entirely."""
    client_host = request.client.host if request.client else None
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded and client_host:
        try:
            peer = ipaddress.ip_address(client_host)
            if any(peer in net for net in _trusted_proxy_networks()):
                return forwarded.split(',')[0].strip()
        except ValueError:
            pass
    return client_host or 'unknown'


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
