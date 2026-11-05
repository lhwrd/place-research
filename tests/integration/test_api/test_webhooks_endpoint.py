"""Tests for the Baserow webhook endpoint."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.core.config import settings
from app.main import app
from app.services.baserow_enrichment import get_baserow_service

HEADERS = {"X-Webhook-Secret": "test-webhook-secret"}
PROPS = settings.baserow_properties_table_id


def _payload(items, event_type="rows.created", table_id=PROPS):
    return {"table_id": table_id, "event_type": event_type, "items": items}


@pytest.fixture
def service():
    service = Mock()
    service.enrich_row = AsyncMock(return_value=True)
    return service


@pytest.fixture
def api(client, service):
    app.dependency_overrides[get_baserow_service] = lambda: service
    return client


@pytest.mark.parametrize("headers", [{}, {"X-Webhook-Secret": "wrong"}])
def test_rejects_bad_secret(api, service, headers):
    response = api.post("/api/v1/webhooks/baserow", json=_payload([{"id": 1}]), headers=headers)

    assert response.status_code == 401
    service.enrich_row.assert_not_called()


def test_queues_actionable_rows(api, service):
    items = [
        {"id": 1, "Status": {"id": 100, "value": "New"}},
        {"id": 2, "Status": {"id": 102, "value": "Enriched"}},
        {"id": 3, "Status": None},
        {"id": 4, "Status": {"id": 104, "value": "Re-enrich"}},
        {"id": 5, "Status": {"id": 101, "value": "Enriching"}},
    ]

    response = api.post(
        "/api/v1/webhooks/baserow", json=_payload(items, "rows.updated"), headers=HEADERS
    )

    assert response.status_code == 200
    assert response.json() == {"queued": [1, 3, 4]}
    assert [c.args[0] for c in service.enrich_row.await_args_list] == [1, 3, 4]


@pytest.mark.parametrize(
    "payload",
    [
        _payload([{"id": 1}], event_type="rows.deleted"),
        _payload([{"id": 1}], table_id=12345),
    ],
)
def test_ignores_other_events_and_tables(api, service, payload):
    response = api.post("/api/v1/webhooks/baserow", json=payload, headers=HEADERS)

    assert response.json() == {"queued": []}
    service.enrich_row.assert_not_called()


def test_background_failure_does_not_fail_request(api, service):
    service.enrich_row.side_effect = RuntimeError("boom")

    response = api.post("/api/v1/webhooks/baserow", json=_payload([{"id": 1}]), headers=HEADERS)

    assert response.status_code == 200
