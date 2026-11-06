"""Tests for the listing ingest endpoints."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.core.config import settings
from app.integrations.baserow_schema import PropertyFields
from app.main import app
from app.services.baserow_enrichment import BaserowEnrichmentService, get_baserow_service
from tests.fakes import FakeBaserowAPI

AUTH = {"Authorization": "Bearer test-ingest-token"}
PROPS = settings.baserow_properties_table_id
URL = "https://www.zillow.com/homedetails/111-White-Pl-Port-Orange-FL-32127/46284123_zpid/"


@pytest.fixture
def baserow():
    return FakeBaserowAPI()


@pytest.fixture
def api(client, baserow):
    service = BaserowEnrichmentService(client=baserow, geocoder=Mock(), orchestrator=Mock())
    service.enrich_row = AsyncMock()
    app.dependency_overrides[get_baserow_service] = lambda: service
    return client


class TestAuth:
    @pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer wrong"}])
    def test_rejects_bad_token(self, api, headers):
        response = api.post("/api/v1/listings", json={"url": URL}, headers=headers)
        assert response.status_code == 401

    def test_unconfigured_ingest(self, api, monkeypatch):
        monkeypatch.setattr(settings, "ingest_api_token", None)
        response = api.post("/api/v1/listings", json={"url": URL}, headers=AUTH)
        assert response.status_code == 503


class TestCreateListing:
    def test_creates_then_dedupes(self, api, baserow):
        listing_json = {"property": {"zpid": 46284123, "price": 425000}}

        first = api.post(
            "/api/v1/listings", json={"url": URL, "listing_json": listing_json}, headers=AUTH
        )
        second = api.post("/api/v1/listings", json={"url": URL}, headers=AUTH)

        assert first.status_code == 200
        assert first.json()["created"] is True
        assert second.json() == {"row_id": first.json()["row_id"], "created": False}
        assert baserow.row(PROPS, first.json()["row_id"])[PropertyFields.PRICE] == 425000

    def test_accepts_listing_json_as_string(self, api, baserow):
        response = api.post(
            "/api/v1/listings",
            json={"url": URL, "listing_json": '{"property": {"zpid": 1, "bedrooms": 4}}'},
            headers=AUTH,
        )

        assert baserow.row(PROPS, response.json()["row_id"])[PropertyFields.BEDS] == 4

    def test_requires_url(self, api):
        assert api.post("/api/v1/listings", json={}, headers=AUTH).status_code == 422


class TestUploadImages:
    @pytest.fixture
    def row_id(self, baserow):
        return baserow.add_row(PROPS, {PropertyFields.ADDRESS: "1 Main"})["id"]

    def test_multipart_multiple_files(self, api, baserow, row_id):
        response = api.post(
            f"/api/v1/listings/{row_id}/images",
            files=[
                ("file", ("a.jpg", b"jpeg-bytes", "image/jpeg")),
                ("file", ("b.png", b"png-bytes", "image/png")),
            ],
            headers=AUTH,
        )

        assert response.status_code == 200
        assert response.json() == {"row_id": row_id, "uploaded": 2, "photo_count": 2}
        assert [u["name"] for u in baserow.uploads] == ["stored_0_a.jpg", "stored_1_b.png"]

    def test_raw_body_upload(self, api, baserow, row_id):
        response = api.post(
            f"/api/v1/listings/{row_id}/images?filename=front",
            content=b"jpeg-bytes",
            headers={**AUTH, "Content-Type": "image/jpeg"},
        )

        assert response.status_code == 200
        assert response.json()["photo_count"] == 1
        assert baserow.uploads[0]["name"] == "stored_0_front.jpeg"

    def test_rejects_non_images(self, api, row_id):
        response = api.post(
            f"/api/v1/listings/{row_id}/images",
            content=b"hello",
            headers={**AUTH, "Content-Type": "text/plain"},
        )
        assert response.status_code == 415

    def test_rejects_empty_form(self, api, row_id):
        response = api.post(
            f"/api/v1/listings/{row_id}/images",
            files=[("other", ("a.jpg", b"x", "image/jpeg"))],
            headers=AUTH,
        )
        assert response.status_code == 400

    def test_unknown_row(self, api):
        response = api.post(
            "/api/v1/listings/999/images",
            content=b"jpeg-bytes",
            headers={**AUTH, "Content-Type": "image/jpeg"},
        )
        assert response.status_code == 404
