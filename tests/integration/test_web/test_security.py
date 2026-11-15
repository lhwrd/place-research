"""Security tests: cross-site request blocking, headers, uploads and escaping."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.main import app
from app.services.property_service import PropertyService, get_property_service

AUTH = {"Authorization": "Bearer test-ingest-token"}
SVG = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(document.domain)</script></svg>'


@pytest.fixture
def service(db):
    service = PropertyService(db=db, geocoder=Mock(), orchestrator=Mock())
    service.enrich = AsyncMock()
    return service


@pytest.fixture
def web(client, service):
    app.dependency_overrides[get_property_service] = lambda: service
    return client


@pytest.fixture
def prop(db):
    return db.create_property({"address": "1 Main St"})


class TestCrossSiteRequests:
    """Another web page must not be able to drive the login-free UI."""

    @pytest.mark.parametrize(
        "headers",
        [
            {"Sec-Fetch-Site": "cross-site"},
            {"Sec-Fetch-Site": "same-site"},  # another *.ts.net machine
            {"Origin": "https://evil.example"},
            {"Origin": "null"},
            {"Referer": "https://evil.example/page"},
        ],
    )
    def test_blocked(self, web, db, prop, headers):
        response = web.post(f"/properties/{prop}/delete", headers=headers)

        assert response.status_code == 403
        assert db.get_property(prop) is not None

    @pytest.mark.parametrize(
        "headers",
        [
            {"Sec-Fetch-Site": "same-origin"},
            {"Origin": "http://testserver"},
            {"Referer": "http://testserver/properties/1"},
            {"Origin": "https://place.example.ts.net", "X-Forwarded-Host": "place.example.ts.net"},
            {},  # curl, scripts: not a browser, can't be forged cross-site
        ],
    )
    def test_allowed(self, web, db, prop, headers):
        response = web.post(f"/properties/{prop}/delete", headers=headers, follow_redirects=False)

        assert response.status_code == 303
        assert db.get_property(prop) is None

    def test_reads_are_not_blocked(self, web, prop):
        assert (
            web.get(f"/properties/{prop}", headers={"Sec-Fetch-Site": "cross-site"}).status_code
            == 200
        )

    def test_token_api_is_exempt(self, web):
        response = web.post(
            "/api/v1/listings",
            json={"url": "https://www.zillow.com/homedetails/x/1_zpid/"},
            headers={**AUTH, "Sec-Fetch-Site": "cross-site"},
        )
        assert response.status_code == 200


class TestHeaders:
    def test_pages_cannot_be_framed(self, web):
        response = web.get("/")

        assert response.headers["X-Frame-Options"] == "DENY"
        assert response.headers["Content-Security-Policy"] == "frame-ancestors 'none'"
        assert response.headers["X-Content-Type-Options"] == "nosniff"

    def test_photos_are_served_inert(self, web, db, prop):
        photo = db.add_photo(prop, "a.png", "image/png", b"png")

        response = web.get(f"/photos/{photo}")

        assert "sandbox" in response.headers["Content-Security-Policy"]
        assert "default-src 'none'" in response.headers["Content-Security-Policy"]
        assert response.headers["X-Content-Type-Options"] == "nosniff"


class TestUploads:
    def test_svg_rejected_from_ui(self, web, db, prop):
        response = web.post(
            f"/properties/{prop}/photos", files=[("file", ("x.svg", SVG, "image/svg+xml"))]
        )

        assert response.status_code == 415
        assert db.photo_ids(prop) == []

    def test_svg_rejected_from_api(self, web, db, prop):
        response = web.post(
            f"/api/v1/listings/{prop}/images",
            content=SVG,
            headers={**AUTH, "Content-Type": "image/svg+xml"},
        )

        assert response.status_code == 415
        assert db.photo_ids(prop) == []

    def test_common_photo_types_accepted(self, web, db, prop):
        for content_type in ("image/jpeg", "image/JPG", "image/heic", "image/webp"):
            response = web.post(
                f"/api/v1/listings/{prop}/images",
                content=b"bytes",
                headers={**AUTH, "Content-Type": content_type},
            )
            assert response.status_code == 200, content_type

        types = {db.get_photo(i).content_type for i in db.photo_ids(prop)}
        assert types == {"image/jpeg", "image/heic", "image/webp"}


class TestEscaping:
    def test_location_name_cannot_break_out_of_confirm(self, web, db):
        db.create_location({"name": "x');alert(1);('", "address": "1 Main"})

        html = web.get("/locations").text

        # The name only ever appears HTML-escaped in a data attribute, never inside JS
        assert "confirm('Delete" not in html
        assert 'data-confirm="Delete x&#39;);alert(1);(&#39;?"' in html

    @pytest.mark.parametrize(
        "url",
        [
            "javascript:alert(document.domain)//x",
            "data:text/html,<script>x</script>",
            "zillow.com/x/1_zpid",
        ],
    )
    def test_ingest_rejects_non_http_urls(self, web, db, url):
        response = web.post("/api/v1/listings", json={"url": url}, headers=AUTH)

        assert response.status_code == 422
        assert db.list_properties() == []

    def test_stored_non_http_url_is_not_linked(self, web, db):
        prop = db.create_property({"address": "1 Main", "zillow_url": "javascript:alert(1)"})

        html = web.get(f"/properties/{prop}").text

        assert "javascript:" not in html
