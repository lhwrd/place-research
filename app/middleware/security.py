"""Cross-site request blocking and security headers for the web UI.

The UI has no login (it's reached over the tailnet), so any web page the user visits could
otherwise make their browser POST to it: delete properties, change settings, upload files.
Browsers label every request with where it came from (Sec-Fetch-Site); state-changing
requests are only accepted from the app's own pages. Older browsers without that header
are checked by Origin/Referer instead. Requests with neither (curl, scripts) aren't
browser-driven, so they can't be forged this way and are let through.

The iOS Shortcut API (/api/) uses a bearer token, not ambient browser credentials, so it
isn't subject to this check.
"""

from typing import Optional
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import PlainTextResponse, Response

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})
# "none": typed into the address bar or opened from a bookmark
ALLOWED_FETCH_SITES = frozenset({"same-origin", "none"})
EXEMPT_PREFIXES = ("/api/",)

SECURITY_HEADERS = {
    # Nobody may frame the UI (clickjacking); it may still embed Google's Street View
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "strict-origin-when-cross-origin",
}
FRAME_ANCESTORS = "frame-ancestors 'none'"


class SecurityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if is_cross_site_write(request):
            return PlainTextResponse("Cross-site request blocked", status_code=403)

        response = await call_next(request)
        for name, value in SECURITY_HEADERS.items():
            response.headers.setdefault(name, value)
        # Keep a route's own CSP (photos have a stricter one); otherwise forbid framing
        response.headers.setdefault("Content-Security-Policy", FRAME_ANCESTORS)
        return response


def is_cross_site_write(request: Request) -> bool:
    """A state-changing browser request that didn't come from this app's own pages."""
    if request.method in SAFE_METHODS or request.url.path.startswith(EXEMPT_PREFIXES):
        return False

    fetch_site = request.headers.get("sec-fetch-site")
    if fetch_site is not None:
        return fetch_site not in ALLOWED_FETCH_SITES

    source = request.headers.get("origin") or request.headers.get("referer")
    if not source:
        return False
    return _host(source) not in _own_hosts(request)


def _host(url: str) -> Optional[str]:
    if url == "null":  # sandboxed frames and some redirects send Origin: null
        return None
    return urlparse(url).netloc.lower() or None


def _own_hosts(request: Request) -> set:
    hosts = {request.headers.get("host", "").lower()}
    forwarded = request.headers.get("x-forwarded-host")
    if forwarded:
        hosts.update(h.strip().lower() for h in forwarded.split(","))
    return hosts - {""}
