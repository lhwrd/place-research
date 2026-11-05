"""Tests for Zillow URL and listing JSON parsing."""

import json

import pytest

from app.services.zillow_listing import (
    ListingFacts,
    address_from_url,
    parse_listing_json,
    parse_zpid,
)

URL = "https://www.zillow.com/homedetails/111-White-Pl-Port-Orange-FL-32127/46284123_zpid/"

ZILLOW_PROPERTY = {
    "zpid": 46284123,
    "price": 425000,
    "bedrooms": 3,
    "bathrooms": 2.5,
    "livingArea": 1850,
    "lotAreaValue": 0.25,
    "lotAreaUnits": "Acres",
    "yearBuilt": 1998,
    "homeType": "SINGLE_FAMILY",
    "latitude": 29.1234,
    "longitude": -81.0123,
    "address": {
        "streetAddress": "111 White Pl",
        "city": "Port Orange",
        "state": "FL",
        "zipcode": "32127",
    },
}

JSON_LD = {
    "@type": "SingleFamilyResidence",
    "address": {
        "streetAddress": "111 White Pl",
        "addressLocality": "Port Orange",
        "addressRegion": "FL",
        "postalCode": "32127",
    },
    "floorSize": {"@type": "QuantitativeValue", "value": "1,850"},
    "numberOfRooms": 3,
    "geo": {"latitude": 29.1234, "longitude": -81.0123},
}


class TestParseZpid:
    @pytest.mark.parametrize(
        "url,expected",
        [
            (URL, "46284123"),
            ("https://www.zillow.com/homedetails/46284123_zpid/", "46284123"),
            ("https://www.zillow.com/homes/for_sale/", None),
            ("", None),
        ],
    )
    def test_parse_zpid(self, url, expected):
        assert parse_zpid(url) == expected


class TestAddressFromUrl:
    def test_slug_with_state_and_zip(self):
        assert address_from_url(URL) == "111 White Pl Port Orange, FL 32127"

    def test_slug_without_state_zip(self):
        url = "https://www.zillow.com/homedetails/Some-Lot-Road/123_zpid/"
        assert address_from_url(url) == "Some Lot Road"

    def test_no_slug(self):
        assert address_from_url("https://www.zillow.com/homedetails/123_zpid/") is None


class TestParseListingJson:
    def test_zillow_property_object(self):
        facts = parse_listing_json({"props": {"pageProps": {"property": ZILLOW_PROPERTY}}})

        assert facts.full_address == "111 White Pl, Port Orange, FL 32127"
        assert facts.price == 425000
        assert facts.beds == 3
        assert facts.baths == 2.5
        assert facts.sqft == 1850
        assert facts.lot_acres == 0.25
        assert facts.year_built == 1998
        assert facts.property_type == "Single family"
        assert (facts.latitude, facts.longitude) == (29.1234, -81.0123)

    def test_property_nested_as_json_string(self):
        """Zillow embeds its property cache as a JSON string inside __NEXT_DATA__."""
        cache = json.dumps({"ForSaleDoubleScrollFullRenderQuery": {"property": ZILLOW_PROPERTY}})
        payload = {"props": {"pageProps": {"componentProps": {"gdpClientCache": cache}}}}

        facts = parse_listing_json(json.dumps(payload))

        assert facts.price == 425000
        assert facts.street == "111 White Pl"

    def test_json_ld_only(self):
        facts = parse_listing_json([JSON_LD])

        assert facts.full_address == "111 White Pl, Port Orange, FL 32127"
        assert facts.sqft == 1850
        assert facts.beds == 3
        assert facts.latitude == 29.1234
        assert facts.price is None

    def test_zillow_property_wins_over_json_ld(self):
        ld = {**JSON_LD, "floorSize": {"value": "9,999"}}
        facts = parse_listing_json({"ld": [ld], "property": ZILLOW_PROPERTY})

        assert facts.sqft == 1850

    def test_lot_size_in_sqft(self):
        prop = {**ZILLOW_PROPERTY, "lotAreaValue": 10890, "lotAreaUnits": "sqft"}
        assert parse_listing_json({"property": prop}).lot_acres == 0.25

    def test_lot_size_fallback_field(self):
        prop = {k: v for k, v in ZILLOW_PROPERTY.items() if not k.startswith("lotArea")}
        prop["lotSize"] = 21780
        assert parse_listing_json({"property": prop}).lot_acres == 0.5

    @pytest.mark.parametrize("raw", [None, "", "not json", 42, {"unrelated": True}])
    def test_unusable_input_returns_empty_facts(self, raw):
        assert parse_listing_json(raw) == ListingFacts()

    def test_full_address_requires_street(self):
        assert ListingFacts(city="Port Orange", state="FL").full_address is None
