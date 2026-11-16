"""Strip credentials out of text before it is logged or stored.

Several APIs take their key as a query parameter (Walk Score's wsapikey, for one), and
httpx puts the full request URL in its exception messages, so any logged error can
otherwise leak the key.
"""

import re
from typing import Any

# Query parameters whose name contains key/token/secret/password, e.g. ?API_KEY=..., &wsapikey=...
_SENSITIVE_QUERY_PARAM = re.compile(
    r"([?&][^=&\s]*(?:key|token|secret|password)[^=&\s]*=)[^&#\s'\"]+",
    re.IGNORECASE,
)

# The same names as dict keys or header names, e.g. {"key": ...}, {"X-Goog-Api-Key": ...}
_SENSITIVE_NAME = re.compile(r"key|token|secret|password|authorization", re.IGNORECASE)

REDACTED = "REDACTED"


def redact_secrets(text: str) -> str:
    """Replace the values of credential-like query parameters with REDACTED."""
    return _SENSITIVE_QUERY_PARAM.sub(rf"\1{REDACTED}", text)


def redact_value(value: Any) -> Any:
    """
    A copy of a logged value with credentials removed: strings are scanned for query
    parameters, and dicts (request params, headers) lose the values of credential-like keys.
    Lists and nested dicts are followed; anything else is returned unchanged.
    """
    if isinstance(value, str):
        return redact_secrets(value)
    if isinstance(value, dict):
        return {
            k: (
                REDACTED
                if isinstance(k, str) and _SENSITIVE_NAME.search(k) and v is not None
                else redact_value(v)
            )
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return type(value)(redact_value(v) for v in value)
    return value
