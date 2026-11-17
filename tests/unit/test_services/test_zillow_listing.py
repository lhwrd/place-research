"""Tests for Zillow URL and listing JSON parsing."""

import json

import pytest

from app.services.zillow_listing import (
    ListingDetails,
    ListingFacts,
    address_from_url,
    find_zillow_property,
    parse_listing_details,
    parse_listing_json,
    parse_zpid,
    photo_urls,
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

    @pytest.mark.parametrize(
        "prop,expected",
        [
            ({"resoFacts": {"garageParkingCapacity": 2, "hasGarage": True}}, 2),
            ({"resoFacts": {"garageParkingCapacity": "3"}}, 3),
            ({"garageParkingCapacity": 1}, 1),
            ({"resoFacts": {"hasGarage": False}}, 0),  # says there's none
            ({"resoFacts": {"hasGarage": True}}, None),  # has one, size unknown
            ({}, None),
        ],
    )
    def test_garage_spaces(self, prop, expected):
        facts = parse_listing_json({"zpid": 1, "price": 100, **prop})
        assert facts.garage_spaces == expected

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


RENTAL = {
    "zpid": 58336203,
    "price": 2050,
    "homeStatus": "FOR_RENT",
    "description": "  Screened porch.\n\nRenter pays utilities.  ",
    "daysOnZillow": 2,
    "rentZestimate": 2123,
    "zestimate": 335300,
    "brokerageName": "Vista Realty",
    "postingContact": {"name": "Pat Lee", "photo": None},
    "attributionInfo": {"agentName": "Pat Lee", "agentPhoneNumber": "321-555-0100"},
    "homeInsights": [
        {"insights": [{"phrases": ["Large screened-in porch", "One-level living"]}]},
        {"insights": [{"phrases": ["Repeated"]}]},
    ],
    "resoFacts": {
        "atAGlanceFacts": [
            {"factLabel": "Date available", "factValue": "Available Now"},
            {"factLabel": "Heating", "factValue": None},
            {"factLabel": "Pets", "factValue": "Cats, Small Dogs"},
        ],
        "feesAndDues": [
            {"type": "Deposit", "fee": "$2,050"},
            {"type": "Application", "fee": "$50"},
            {"type": "Pet", "fee": None},
        ],
        "leaseTerm": "1 Year",
        "appliances": ["Dishwasher", "Washer"],
        "flooring": ["Hardwood"],
    },
    "originalPhotos": [
        {
            "mixedSources": {
                "jpeg": [
                    {"url": "https://photos.zillowstatic.com/a-small.jpg", "width": 800},
                    {"url": "https://photos.zillowstatic.com/a-big.jpg", "width": 1536},
                ]
            }
        },
        {"url": "https://photos.zillowstatic.com/b.jpg"},
        "not a photo",
        {"mixedSources": {"jpeg": [{"url": "https://photos.zillowstatic.com/b.jpg"}]}},
    ],
}


class TestParseListingDetails:
    def test_rental(self):
        details = parse_listing_details({"props": {"property": RENTAL}})

        assert details == ListingDetails(
            status="For rent",
            description="Screened porch.\n\nRenter pays utilities.",
            at_a_glance=[("Date available", "Available Now"), ("Pets", "Cats, Small Dogs")],
            highlights=["Large screened-in porch", "One-level living"],
            fees=[("Deposit", "$2,050"), ("Application", "$50")],
            lease_term="1 Year",
            appliances=["Dishwasher", "Washer"],
            flooring=["Hardwood"],
            days_on_zillow=2,
            rent_zestimate=2123,
            zestimate=335300,
            listed_by="Pat Lee · Vista Realty",
            contact_phone="321-555-0100",
            photo_urls=[
                "https://photos.zillowstatic.com/a-big.jpg",
                "https://photos.zillowstatic.com/b.jpg",
            ],
        )

    def test_from_json_string(self):
        assert parse_listing_details(json.dumps(RENTAL)).lease_term == "1 Year"

    @pytest.mark.parametrize("raw", [None, "", "not json", {"@type": "House"}, []])
    def test_nothing_to_find(self, raw):
        details = parse_listing_details(raw)

        assert details == ListingDetails()
        assert not details

    def test_odd_shapes_are_ignored(self):
        details = parse_listing_details(
            {"zpid": 1, "price": 1, "resoFacts": "oops", "homeInsights": {}, "description": 5}
        )

        assert details.description is None
        assert details.at_a_glance == [] and details.highlights == []

    def test_photo_urls_empty(self):
        assert photo_urls({}) == []


class TestFindZillowProperty:
    def test_prefers_matching_zpid(self):
        data = {"a": {"zpid": 1, "price": 5}, "b": {"zpid": 2, "price": 6}}

        assert find_zillow_property(data, "2")["zpid"] == 2

    def test_falls_back_to_first(self):
        data = {"a": {"zpid": 1, "price": 5}}

        assert find_zillow_property(data, "9")["zpid"] == 1
        assert find_zillow_property(data)["zpid"] == 1


def test_half_baths_count_as_half():
    prop = {
        "zpid": 1,
        "price": 1,
        "bathrooms": 3,
        "resoFacts": {"bathroomsFull": 2, "bathroomsHalf": 1},
    }

    assert parse_listing_json(prop).baths == 2.5


def test_placeholder_brokerage_is_dropped():
    prop = {"zpid": 1, "price": 1, "brokerageName": "Enter a company name"}

    assert parse_listing_details(prop).listed_by is None
