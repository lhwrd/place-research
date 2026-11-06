"""Tests for credential redaction in logs and error messages."""

import io
import json
import logging

import httpx
import pytest

from app.core.logging_config import CustomJsonFormatter, RedactingFilter
from app.core.redaction import redact_secrets
from app.integrations.base_client import USER_AGENT, BaseAPIClient

URL = "https://www.airnowapi.org/aq/forecast/latLong/?API_KEY=FBD89C42-SECRET&latitude=29.1"


@pytest.mark.parametrize(
    "text,expected",
    [
        (URL, "https://www.airnowapi.org/aq/forecast/latLong/?API_KEY=REDACTED&latitude=29.1"),
        ("score?lat=1&wsapikey=abc123&format=json", "score?lat=1&wsapikey=REDACTED&format=json"),
        ("x?access_token=t0k&other=1", "x?access_token=REDACTED&other=1"),
        ("for url 'https://h/p?key=k1'", "for url 'https://h/p?key=REDACTED'"),
        ("https://h/p?lat=1&lon=2", "https://h/p?lat=1&lon=2"),
        ("no urls here", "no urls here"),
    ],
)
def test_redact_secrets(text, expected):
    assert redact_secrets(text) == expected


def _emit(record_kwargs, formatter):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(RedactingFilter())
    handler.setFormatter(formatter)
    logger = logging.getLogger("test_redaction")
    logger.handlers = [handler]
    logger.propagate = False
    try:
        logger.error(*record_kwargs.pop("args"), **record_kwargs)
    finally:
        logger.handlers = []
    return stream.getvalue()


def test_filter_redacts_message_extras_and_traceback_in_json():
    try:
        raise RuntimeError(f"Client error for url '{URL}'")
    except RuntimeError:
        output = _emit(
            {"args": ("failed: %s", URL), "extra": {"error": URL}, "exc_info": True},
            CustomJsonFormatter("%(message)s"),
        )

    assert "FBD89C42" not in output
    data = json.loads(output)
    assert "API_KEY=REDACTED" in data["message"]
    assert "API_KEY=REDACTED" in data["error"]
    assert "RuntimeError" in data["exc_info"]


def test_filter_redacts_traceback_in_text_format():
    try:
        raise RuntimeError(URL)
    except RuntimeError:
        output = _emit({"args": ("boom",), "exc_info": True}, logging.Formatter("%(message)s"))

    assert "FBD89C42" not in output
    assert "Traceback" in output and "API_KEY=REDACTED" in output


class _Client(BaseAPIClient):
    def _get_service_name(self):
        return "test"

    async def validate_api_key(self):
        return True


@pytest.mark.asyncio
async def test_http_error_message_is_redacted_and_ua_is_set():
    seen = {}

    def handler(request):
        seen["ua"] = request.headers["user-agent"]
        return httpx.Response(410, text="")

    client = _Client(base_url="https://api.test")
    client._client = None
    real = client.client  # built with the default headers
    client._client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), headers=dict(real.headers)
    )

    with pytest.raises(Exception) as exc_info:
        await client._make_request("GET", "aq", params={"API_KEY": "SECRET123", "lat": 1})

    assert seen["ua"] == USER_AGENT
    message = exc_info.value.message
    assert "SECRET123" not in message
    assert "HTTP 410 from https://api.test/aq?API_KEY=REDACTED&lat=1" == message
