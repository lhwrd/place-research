"""Tests for the server-rendered web UI."""

from unittest.mock import AsyncMock, Mock

import pytest

from app.db import PropertyStatus
from app.main import app
from app.services.property_service import (
    AMENITY_TYPES,
    PREFERRED_PLACES,
    PropertyService,
    get_property_service,
)
from app.web.routes import duration

WALK_SCORES = {"walk_score": 72, "bike_score": 55}
ENRICHMENT = {
    "distance_provider": {
        "distances": [
            {"location_name": "Mom", "status": "OK", "duration_minutes": 18, "distance_miles": 9.2}
        ]
    },
    "places_nearby_provider": {
        "places_nearby": [
            {
                "name": "King Soopers",
                "type": "Grocery store",
                "drive_minutes": 75,
                "drive_miles": 41.26,
            },
            {"name": "Mystery Spot"},
        ]
    },  # fmt: skip
    "census_provider": {
        "acs_year": 2024,
        "city": {"name": "Denver", "population": 715000},
        "tract": {"age_groups": {"Under 18": 21.5}},
    },
}


@pytest.fixture
def service(db):
    service = PropertyService(db=db, geocoder=Mock(), orchestrator=Mock())
    service.enrich = AsyncMock()
    return service


@pytest.fixture(autouse=True)
def walk_scores(monkeypatch):
    """Walk Score is asked on every property page view; answer for it here."""
    from app.web import routes

    lookup = AsyncMock(return_value=dict(WALK_SCORES))
    monkeypatch.setattr(routes, "live_walk_scores", lookup)
    return lookup


@pytest.fixture
def web(client, service):
    app.dependency_overrides[get_property_service] = lambda: service
    return client


@pytest.fixture
def enriched(db):
    return db.create_property(
        {
            "address": "42 Elm St, Denver, CO",
            "price": 615000,
            "beds": 3,
            "baths": 2.5,
            "status": PropertyStatus.ENRICHED,
            "latitude": 39.7,
            "longitude": -104.9,
            "enrichment": ENRICHMENT,
        }
    )


class TestPropertyList:
    def test_empty(self, web):
        response = web.get("/")

        assert response.status_code == 200
        assert "Nothing here yet" in response.text

    def test_lists_properties(self, web, enriched):
        html = web.get("/").text

        assert "42 Elm St, Denver, CO" in html
        assert "$615,000" in html
        assert "3 bd" in html and "2.5 ba" in html
        assert "Walk" not in html  # scores can't be stored, and the list doesn't fetch them
        assert f'href="/properties/{enriched}"' in html

    def test_sort(self, web, db):
        db.create_property({"address": "Cheap", "price": 100})
        db.create_property({"address": "Pricey", "price": 900})

        html = web.get("/?sort=price_desc").text

        assert html.index("Pricey") < html.index("Cheap")
        assert web.get("/?sort=bogus").status_code == 200

    def test_add_address_queues_enrichment(self, web, db, service):
        response = web.post("/properties", data={"query": "1 Main St, Boulder, CO"})

        assert response.status_code == 200  # followed the redirect to the detail page
        assert "1 Main St, Boulder, CO" in response.text
        [prop] = db.list_properties()
        service.enrich.assert_awaited_once_with(prop["id"], use_cached=True)

    def test_add_existing_address_does_not_re_enrich(self, web, db, service, enriched):
        response = web.post(
            "/properties", data={"query": "42 elm st, denver, co"}, follow_redirects=False
        )

        assert response.headers["location"] == f"/properties/{enriched}"
        service.enrich.assert_not_called()


class TestPropertyDetail:
    def test_shows_enrichment(self, web, enriched, walk_scores):
        html = web.get(f"/properties/{enriched}").text

        assert "Walk score" in html and ">72<" in html
        walk_scores.assert_awaited_once_with(39.7, -104.9, "42 Elm St, Denver, CO")
        assert "Mom" in html and "18m" in html
        assert "Denver" in html and "715,000" in html
        assert "Under 18" in html
        assert "King Soopers" in html and "1h 15m" in html and "41.3 mi" in html
        assert "Mystery Spot" in html and "unavailable" in html
        assert "query=39.7,-104.9" in html

    def test_renting_section_uses_the_listing_rent(self, web, db, enriched):
        db.update_property(
            enriched,
            {
                "price": 2600,
                "beds": 2,
                "enrichment": {
                    **ENRICHMENT,
                    "census_provider": {
                        "acs_year": 2024,
                        "tract": {"median_gross_rent_by_bedrooms": {"2": 1789}},
                    },
                    "electric_utility_provider": {
                        "utilities": [{"name": "ORLANDO UTILITIES COMM", "type": "municipal"}]
                    },
                },
            },
        )

        html = web.get(f"/properties/{enriched}").text

        assert "<h2>Renting</h2>" in html
        assert "$2,600 asking · 45% above the tract&#39;s 2-bedroom median of $1,789" in html
        assert "Orlando Utilities Comm (municipal)" in html

    def test_no_renting_section_without_its_data(self, web, enriched):
        assert "<h2>Renting</h2>" not in web.get(f"/properties/{enriched}").text

    def test_unknown_property(self, web):
        assert web.get("/properties/999").status_code == 404

    def test_status(self, web, enriched):
        assert web.get(f"/properties/{enriched}/status").json() == {"status": "enriched"}

    def test_pending_property_polls(self, web, db):
        property_id = db.create_property({"address": "1 Main"})

        html = web.get(f"/properties/{property_id}").text

        assert f"/properties/{property_id}/status" in html

    def test_error_is_shown(self, web, db):
        property_id = db.create_property(
            {"address": "1 Main", "status": PropertyStatus.ERROR, "error": "Geocoding failed"}
        )

        assert "Geocoding failed" in web.get(f"/properties/{property_id}").text

    def test_save_notes(self, web, db, enriched):
        response = web.post(
            f"/properties/{enriched}/notes",
            data={"notes": " Big yard ", "rating": "4", "visited": "on"},
            follow_redirects=False,
        )

        assert response.status_code == 303
        prop = db.get_property(enriched)
        assert (prop["notes"], prop["rating"], prop["visited"]) == ("Big yard", 4, True)

        web.post(f"/properties/{enriched}/notes", data={"notes": "", "rating": "9"})
        prop = db.get_property(enriched)
        assert (prop["rating"], prop["visited"]) == (None, False)

    def test_save_facts(self, web, db, enriched):
        web.post(
            f"/properties/{enriched}/facts",
            data={"address": "42 Elm Street", "price": "$599,000", "beds": "4", "baths": "x",
                  "garage_spaces": "2"},
        )  # fmt: skip

        prop = db.get_property(enriched)
        assert prop["address"] == "42 Elm Street"
        assert (prop["price"], prop["beds"], prop["baths"]) == (599000, 4.0, None)
        assert prop["garage_spaces"] == 2
        assert "2-car garage" in web.get(f"/properties/{enriched}").text
        assert "2-car garage" in web.get("/").text

        web.post(
            f"/properties/{enriched}/facts", data={"address": "42 Elm Street", "garage_spaces": "0"}
        )
        assert db.get_property(enriched)["garage_spaces"] == 0
        assert "No garage" in web.get(f"/properties/{enriched}").text

    def test_walk_score_links_to_walkscore(self, web, enriched, walk_scores):
        html = web.get(f"/properties/{enriched}").text
        assert 'href="https://www.walkscore.com/how-it-works/"' in html

        for link, shown in [
            ("https://www.walkscore.com/score/42-elm-st", True),
            ("https://evil.example/walkscore", False),
        ]:
            walk_scores.return_value = {**WALK_SCORES, "link": link}
            assert (f'href="{link}"' in web.get(f"/properties/{enriched}").text) is shown

    def test_walk_scores_are_fetched_per_view_and_never_stored(
        self, web, db, enriched, walk_scores
    ):
        web.get(f"/properties/{enriched}")
        web.get(f"/properties/{enriched}")

        assert walk_scores.await_count == 2
        assert "walk_score" not in str(db.get_property(enriched)["enrichment"])

    def test_page_renders_without_walk_scores(self, web, db, enriched, walk_scores):
        walk_scores.return_value = {}

        html = web.get(f"/properties/{enriched}").text

        assert "Walk score" not in html and "walkscore.com" not in html
        assert "Mom" in html

    def test_no_lookup_before_the_property_is_located(self, web, db, walk_scores):
        property_id = db.create_property({"address": "1 New St"})

        assert web.get(f"/properties/{property_id}").status_code == 200
        walk_scores.assert_not_awaited()

    def test_reenrich_keeps_results_that_are_still_good(self, web, db, service, enriched):
        web.post(f"/properties/{enriched}/reenrich")

        assert db.get_property(enriched)["status"] == PropertyStatus.NEW
        service.enrich.assert_awaited_once_with(enriched, use_cached=True)

    def test_redo_all_runs_every_provider(self, web, service, enriched):
        web.post(f"/properties/{enriched}/reenrich", data={"everything": "1"})

        service.enrich.assert_awaited_once_with(enriched, use_cached=False)

    def test_new_address_forgets_the_old_location(self, web, db, enriched):
        db.update_property(enriched, {"enrichment_meta": {"walk_score_provider": {"ok": True}}})

        web.post(f"/properties/{enriched}/facts", data={"address": "9 Other Rd"})

        prop = db.get_property(enriched)
        assert (prop["latitude"], prop["longitude"]) == (None, None)
        assert prop["enrichment_meta"] == {}

    def test_same_address_keeps_the_location(self, web, db, enriched):
        before = db.get_property(enriched)

        web.post(f"/properties/{enriched}/facts", data={"address": before["address"]})

        assert db.get_property(enriched)["latitude"] == before["latitude"]

    def test_delete(self, web, db, enriched):
        response = web.post(f"/properties/{enriched}/delete", follow_redirects=False)

        assert response.headers["location"] == "/"
        assert db.get_property(enriched) is None


class TestStreetView:
    @pytest.fixture(autouse=True)
    def keys(self, monkeypatch):
        from app.web import routes

        monkeypatch.setattr(routes.settings, "google_maps_api_key", "server-key")
        monkeypatch.setattr(routes.settings, "google_maps_embed_key", "browser-key")

    def test_embed_faces_the_house(self, web, db, enriched):
        db.update_property(
            enriched,
            {"enrichment": {**ENRICHMENT, "street_view_provider": {
                "available": True, "pano_id": "PANO1", "heading": 212, "date": "2024-03"}}},
        )  # fmt: skip

        html = web.get(f"/properties/{enriched}").text

        assert "maps/embed/v1/streetview?key=browser-key" in html
        assert "pano=PANO1" in html and "heading=212" in html
        assert "server-key" not in html
        assert "Imagery from 2024-03" in html

    def test_falls_back_to_location_without_a_panorama(self, web, enriched):
        html = web.get(f"/properties/{enriched}").text

        assert "key=browser-key" in html
        assert "location=39.7%2C-104.9" in html

    def test_server_key_is_never_sent_to_the_browser(self, web, enriched, monkeypatch):
        from app.web import routes

        monkeypatch.setattr(routes.settings, "google_maps_embed_key", None)

        html = web.get(f"/properties/{enriched}").text

        assert "server-key" not in html
        assert "maps/embed" not in html
        assert "GOOGLE_MAPS_EMBED_KEY" in html

    def test_no_coverage(self, web, db, enriched):
        db.update_property(
            enriched,
            {"enrichment": {**ENRICHMENT, "street_view_provider": {"available": False}}},
        )

        html = web.get(f"/properties/{enriched}").text

        assert "maps/embed" not in html
        assert "no Street View imagery" in html

    def test_no_key(self, web, enriched, monkeypatch):
        from app.web import routes

        monkeypatch.setattr(routes.settings, "google_maps_embed_key", None)
        monkeypatch.setattr(routes.settings, "google_maps_api_key", None)

        html = web.get(f"/properties/{enriched}").text

        assert "maps/embed" not in html
        assert "GOOGLE_MAPS_EMBED_KEY" in html

    def test_neighborhood_rating(self, web, db, enriched):
        response = web.post(
            f"/properties/{enriched}/neighborhood",
            data={"neighborhood_rating": "4"},
            follow_redirects=False,
        )

        assert response.headers["location"] == f"/properties/{enriched}#street-view"
        assert db.get_property(enriched)["neighborhood_rating"] == 4
        assert (
            'id="nr4" name="neighborhood_rating" value="4" checked'
            in web.get(f"/properties/{enriched}").text
        )
        assert "Area 4/5" in web.get("/").text

        web.post(f"/properties/{enriched}/neighborhood", data={})
        assert db.get_property(enriched)["neighborhood_rating"] is None


class TestPhotos:
    def test_upload_view_delete(self, web, db, enriched):
        web.post(
            f"/properties/{enriched}/photos",
            files=[
                ("file", ("a.jpg", b"jpeg-1", "image/jpeg")),
                ("file", ("b.png", b"png-2", "image/png")),
            ],
        )
        first, second = db.photo_ids(enriched)

        photo = web.get(f"/photos/{first}")
        assert photo.content == b"jpeg-1"
        assert photo.headers["content-type"] == "image/jpeg"
        assert f'src="/photos/{first}"' in web.get("/").text  # cover photo

        web.post(f"/photos/{first}/delete")
        assert db.photo_ids(enriched) == [second]

    def test_rejects_non_images(self, web, enriched):
        response = web.post(
            f"/properties/{enriched}/photos", files=[("file", ("a.txt", b"hi", "text/plain"))]
        )
        assert response.status_code == 415

    def test_unknown_photo(self, web):
        assert web.get("/photos/999").status_code == 404


class TestLocations:
    def test_add_edit_delete(self, web, db):
        web.post(
            "/locations",
            data={"name": "Mom", "address": "2 Home St", "type": "Family", "priority": "5"},
        )
        [loc] = db.list_locations()
        assert (loc["name"], loc["type"], loc["priority"], loc["active"]) == (
            "Mom", "Family", 5, True,
        )  # fmt: skip
        assert "2 Home St" in web.get("/locations").text

        # Unchecked "active" checkbox is absent from the form
        web.post(
            f"/locations/{loc['id']}",
            data={"name": "Mom & Dad", "address": "2 Home St", "type": "bogus", "priority": ""},
        )
        [loc] = db.list_locations()
        assert (loc["name"], loc["type"], loc["priority"], loc["active"]) == (
            "Mom & Dad", None, 0, False,
        )  # fmt: skip

        web.post(f"/locations/{loc['id']}/delete")
        assert db.list_locations() == []


class TestSettings:
    def test_save(self, web, db):
        response = web.post(
            "/settings", data={"amenity_types": "park\ngym\n", "preferred_places": "Costco"}
        )

        assert "Saved." in response.text
        assert db.get_setting(AMENITY_TYPES) == "park\ngym"
        assert db.get_setting(PREFERRED_PLACES) == "Costco"
        assert "Costco" in response.text


@pytest.mark.parametrize(
    "minutes,text",
    [(None, "—"), (0, "0m"), (45, "45m"), (59.6, "1h"), (60, "1h"), (90, "1h 30m"),
     (125.4, "2h 5m")],
)  # fmt: skip
def test_duration(minutes, text):
    assert duration(minutes) == text


def test_health(client):
    assert client.get("/health").json()["status"] == "healthy"
