# Logging

Configured once at startup by `setup_logging()` in `app/core/logging_config.py`.

## Settings

| Variable        | Default | Meaning                                                    |
| --------------- | ------- | ---------------------------------------------------------- |
| `LOG_LEVEL`     | `INFO`  | Root log level                                             |
| `LOG_FORMAT`    | `json`  | `json` (one object per line), `text`, or `color` (dev)     |
| `LOG_REQUESTS`  | `true`  | Log each incoming request (`RequestLoggingMiddleware`)     |
| `LOG_RESPONSES` | `true`  | Log each response with status and duration                 |

`httpx`, `httpcore` and `urllib3` are capped at `WARNING`.

Credential-like query parameters (`?API_KEY=`, `&wsapikey=`, anything with key, token,
secret or password in the name) are replaced with `REDACTED` in every message, string
field and traceback before it's written (`RedactingFilter`, `app/core/redaction.py`).

## Request IDs

`RequestLoggingMiddleware` gives every request a UUID. The UUID appears on every log
line written while the request is handled and is returned in the `X-Request-ID`
response header. Background enrichment that a webhook queues runs in the same context,
so its log lines carry the webhook request's ID, which makes it easy to find everything
one Baserow event caused. Rows enriched by the periodic sweep have no request ID.

```python
from app.core.logging_config import get_request_id

get_request_id()  # None outside a request
```

## Context

Extra fields to attach to every subsequent log line in the current context:

```python
from app.core.logging_config import clear_log_context, set_log_context

set_log_context(row_id=12)
logger.info("Enriching")  # includes row_id=12
clear_log_context()
```

## Timing

```python
from app.core.logging_config import LogTimer

with LogTimer(logger, "geocode", address=address):
    ...
# Logs "Starting geocode", then "Completed geocode in 123.45ms"
# (or "Failed geocode after ...ms: <error>" if it raises)
```

## Style

Use lazy `%` formatting so messages aren't built when the level is disabled, and put
structured values in `extra`:

```python
logger.info("Enriched row %s", row_id, extra={"row_id": row_id})
```
