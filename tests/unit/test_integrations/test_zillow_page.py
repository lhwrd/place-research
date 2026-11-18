"""Tests for fetching Zillow listing pages."""

import json

import httpx
import pytest

from app.integrations.zillow_page import (
    ZillowFetchError,
    ZillowPageClient,
    property_from_html,
    trim_property,
)

URL = "https://www.zillow.com/homedetails/4645-Willamette-Cir-Orlando-FL-32826/58336203_zpid/"
PHOTO = "https://photos.zillowstatic.com/fp/abc-uncropped_scaled_within_1536_1152.jpg"

PROPERTY = {
    "zpid": 58336203,
    "price": 2050,
    "bedrooms": 3,
    "homeStatus": "FOR_RENT",
    "description": "Single-story home with a screened porch.",
    "resoFacts": {"leaseTerm": "1 Year", "heating": None, "appliances": [], "hasGarage": False},
    "nearbyHomes": [{"zpid": 1, "price": 900000}],
    "adTargets": {"listtp": "rent_general"},
    "originalPhotos": [
        {
            "caption": "Front",
            "mixedSources": {
                "jpeg": [
                    {"url": "https://photos.zillowstatic.com/fp/abc-d_d.jpg", "width": 800},
                    {"url": PHOTO, "width": 1536},
                    {"url": "https://photos.zillowstatic.com/fp/abc-huge.jpg", "width": 4000},
                ]
            },
        }
    ],
    "responsivePhotos": [{"url": "https://photos.zillowstatic.com/fp/abc-p_d.jpg"}],
}


def page(prop=PROPERTY, neighbor_first=False):
    """A listing page shaped like Zillow's: the property cache is a JSON string."""
    cache = {"ForRentQuery": {"property": prop}}
    if neighbor_first:
        cache = {"SimilarHomes": {"property": {"zpid": 999, "price": 1}}, **cache}
    next_data = {"props": {"pageProps": {"componentProps": {"gdpClientCache": json.dumps(cache)}}}}
    return (
        '<html><head><script id="__NEXT_DATA__" type="application/json">'
        f"{json.dumps(next_data)}</script></head></html>"
    )


def client_for(handler):
    return ZillowPageClient(httpx.AsyncClient(transport=httpx.MockTransport(handler)))


class TestPropertyFromHtml:
    def test_extracts_and_trims(self):
        prop = property_from_html(page())

        assert prop["zpid"] == 58336203
        assert prop["description"] == "Single-story home with a screened porch."
        assert "nearbyHomes" not in prop and "adTargets" not in prop
        assert "responsivePhotos" not in prop
        # Empty RESO facts are dropped, but False is a fact (no garage)
        assert prop["resoFacts"] == {"leaseTerm": "1 Year", "hasGarage": False}

    def test_keeps_one_photo_size_within_the_limit(self):
        prop = property_from_html(page())

        assert prop["originalPhotos"] == [
            {"caption": "Front", "mixedSources": {"jpeg": [{"url": PHOTO, "width": 1536}]}}
        ]

    def test_prefers_the_listing_zpid(self):
        prop = property_from_html(page(neighbor_first=True), zpid="58336203")

        assert prop["zpid"] == 58336203

    @pytest.mark.parametrize(
        "html",
        ["", "<html>captcha</html>", '<script id="__NEXT_DATA__">not json</script>'],
    )
    def test_no_property(self, html):
        assert property_from_html(html) is None

    def test_responsive_photos_when_no_originals(self):
        prop = {
            "zpid": 1,
            "price": 1,
            "responsivePhotos": [
                {"mixedSources": {"jpeg": [{"url": PHOTO, "width": 1536}]}},
            ],
        }

        assert trim_property(prop)["originalPhotos"][0]["mixedSources"]["jpeg"][0]["url"] == PHOTO


class TestFetchProperty:
    @pytest.mark.asyncio
    async def test_success_sends_browser_headers(self):
        seen = {}

        def handler(request):
            seen["ua"] = request.headers.get("user-agent")
            return httpx.Response(200, text=page())

        client = ZillowPageClient()
        client._client = httpx.AsyncClient(
            transport=httpx.MockTransport(handler), headers=client.client.headers
        )

        prop = await client.fetch_property(URL)

        assert prop["price"] == 2050
        assert seen["ua"].startswith("Mozilla/5.0")

    @pytest.mark.asyncio
    async def test_captcha(self):
        client = client_for(lambda r: httpx.Response(403, text='<div id="px-captcha"></div>'))

        with pytest.raises(ZillowFetchError, match="captcha"):
            await client.fetch_property(URL)

    @pytest.mark.asyncio
    async def test_http_error_status(self):
        client = client_for(lambda r: httpx.Response(404, text="gone"))

        with pytest.raises(ZillowFetchError, match="HTTP 404"):
            await client.fetch_property(URL)

    @pytest.mark.asyncio
    async def test_page_without_data(self):
        client = client_for(lambda r: httpx.Response(200, text="<html></html>"))

        with pytest.raises(ZillowFetchError, match="No property data"):
            await client.fetch_property(URL)

    @pytest.mark.asyncio
    async def test_transport_error(self):
        def handler(request):
            raise httpx.ConnectTimeout("slow")

        with pytest.raises(ZillowFetchError, match="ConnectTimeout"):
            await client_for(handler).fetch_property(URL)

    @pytest.mark.asyncio
    async def test_redirect_off_zillow(self):
        def handler(request):
            if request.url.host == "www.zillow.com":
                return httpx.Response(302, headers={"location": "https://example.com/"})
            return httpx.Response(200, text=page())

        client = ZillowPageClient(
            httpx.AsyncClient(transport=httpx.MockTransport(handler), follow_redirects=True)
        )

        with pytest.raises(ZillowFetchError, match="off Zillow"):
            await client.fetch_property(URL)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "url", ["https://example.com/homedetails/1_zpid/", "file:///etc/passwd", ""]
    )
    async def test_rejects_other_urls(self, url):
        client = client_for(lambda r: pytest.fail("should not send"))

        with pytest.raises(ZillowFetchError, match="Not a Zillow"):
            await client.fetch_property(url)


class TestFetchPhoto:
    @pytest.mark.asyncio
    async def test_downloads_zillow_photo(self):
        client = client_for(lambda r: httpx.Response(200, content=b"jpeg"))

        response = await client.fetch_photo(PHOTO)

        assert response.content == b"jpeg"

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "url", ["http://photos.zillowstatic.com/a.jpg", "https://169.254.169.254/latest"]
    )
    async def test_rejects_other_hosts(self, url):
        client = client_for(lambda r: pytest.fail("should not send"))

        with pytest.raises(ZillowFetchError):
            await client.fetch_photo(url)
