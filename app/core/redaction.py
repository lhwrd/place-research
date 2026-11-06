"""Strip credentials out of text before it is logged or stored.

Several APIs take their key as a query parameter (Walk Score's wsapikey, for one), and
httpx puts the full request URL in its exception messages, so any logged error can
otherwise leak the key.
"""

import re

# Query parameters whose name contains key/token/secret/password, e.g. ?API_KEY=..., &wsapikey=...
_SENSITIVE_QUERY_PARAM = re.compile(
    r"([?&][^=&\s]*(?:key|token|secret|password)[^=&\s]*=)[^&#\s'\"]+",
    re.IGNORECASE,
)

REDACTED = "REDACTED"


def redact_secrets(text: str) -> str:
    """Replace the values of credential-like query parameters with REDACTED."""
    return _SENSITIVE_QUERY_PARAM.sub(rf"\1{REDACTED}", text)
