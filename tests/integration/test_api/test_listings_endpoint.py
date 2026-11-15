"""Tests for the iOS Shortcut listing endpoints."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.core.config import settings
from app.main import app
from app.services.property_service import PropertyService, get_property_service

AUTH = {"Authorization": "Bearer test-ingest-token"}
URL = "https://www.zillow.com/homedetails/111-White-Pl-Port-Orange-FL-32127/46284123_zpid/"


@pytest.fixture
def service(db):
    service = PropertyService(db=db, geocoder=Mock(), orchestrator=Mock())
    service.enrich = AsyncMock()
    return service


@pytest.fixture
def api(client, service):
    app.dependency_overrides[get_property_service] = lambda: service
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
    def test_creates_then_dedupes(self, api, db, service):
        listing_json = {"property": {"zpid": 46284123, "price": 425000}}

        first = api.post(
            "/api/v1/listings", json={"url": URL, "listing_json": listing_json}, headers=AUTH
        )
        second = api.post("/api/v1/listings", json={"url": URL}, headers=AUTH)

        assert first.status_code == 200
        assert first.json()["created"] is True
        assert second.json() == {"row_id": first.json()["row_id"], "created": False}
        assert db.get_property(first.json()["row_id"])["price"] == 425000
        # Enrichment is queued once, for the new listing only
        service.enrich.assert_awaited_once_with(first.json()["row_id"], use_cached=True)

    def test_accepts_listing_json_as_string(self, api, db):
        response = api.post(
            "/api/v1/listings",
            json={"url": URL, "listing_json": '{"property": {"zpid": 1, "bedrooms": 4}}'},
            headers=AUTH,
        )

        assert db.get_property(response.json()["row_id"])["beds"] == 4

    def test_requires_url(self, api):
        assert api.post("/api/v1/listings", json={}, headers=AUTH).status_code == 422


class TestUploadImages:
    @pytest.fixture
    def row_id(self, db):
        return db.create_property({"address": "1 Main"})

    def test_multipart_multiple_files(self, api, db, row_id):
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
        photos = [db.get_photo(i) for i in db.photo_ids(row_id)]
        assert [(p.filename, p.data) for p in photos] == [
            ("a.jpg", b"jpeg-bytes"),
            ("b.png", b"png-bytes"),
        ]

    def test_raw_body_upload(self, api, db, row_id):
        response = api.post(
            f"/api/v1/listings/{row_id}/images?filename=front",
            content=b"jpeg-bytes",
            headers={**AUTH, "Content-Type": "image/jpeg"},
        )

        assert response.status_code == 200
        assert response.json()["photo_count"] == 1
        assert db.get_photo(db.photo_ids(row_id)[0]).filename == "front.jpeg"

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
