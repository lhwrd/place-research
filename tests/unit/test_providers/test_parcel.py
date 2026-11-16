"""Tests for the Florida parcel provider (ArcGIS calls mocked)."""

from unittest.mock import AsyncMock

import httpx
import pytest
from shapely.geometry import box

from app.services.enrichment.providers.parcel import (
    COUNTIES,
    ParcelProvider,
    choose_parcel,
    normalize,
    parcel_details,
    recent_sales,
    same_house,
    use_description,
)

LAT, LON = 28.564, -81.364
# ~1 m of latitude, in degrees
M = 1 / 110_950


def lot(north_m: float, size_m: float = 20, **attributes):
    """A square parcel whose south edge is north_m meters north of the point."""
    south = LAT + north_m * M
    return {
        "geometry": box(LON - size_m * M, south, LON + size_m * M, south + size_m * M),
        **attributes,
    }


# A record as the layer serves it: blank NAL fields come back as 0 or " "
ROLL = {
    "CO_NO": 58,
    "PARCEL_ID": "242229582203011",
    "ASMNT_YR": 2026,
    "DOR_UC": "001",
    "PHY_ADDR1": "1216 VIRGINIA DR",
    "PHY_CITY": "ORLANDO",
    "ACT_YR_BLT": 1955,
    "EFF_YR_BLT": 1980,
    "TOT_LVG_AR": 2376,
    "LND_SQFOOT": 12333,
    "NO_BULDNG": 1,
    "NO_RES_UNT": 1,
    "IMP_QUAL": "3",
    "JV": 636740,
    "LND_VAL": 374400,
    "TV_SD": 586740,
    "TV_NSD": 561740,
    "JV_HMSTD": 636740,
    "SALE_PRC1": 0, "SALE_YR1": 0, "SALE_MO1": " ", "QUAL_CD1": " ", "VI_CD1": " ",
    "SALE_PRC2": 0, "SALE_YR2": 0, "SALE_MO2": " ", "QUAL_CD2": " ", "VI_CD2": " ",
}  # fmt: skip


class TestCounties:
    def test_department_numbering(self):
        assert len(COUNTIES) == 67
        assert COUNTIES[11] == "Alachua"
        assert COUNTIES[23] == "Miami-Dade"  # filed under Dade
        assert COUNTIES[58] == "Orange"
        assert COUNTIES[65] == "St. Johns"
        assert COUNTIES[77] == "Washington"


class TestUse:
    @pytest.mark.parametrize(
        "code,expected",
        [("001", "Single family"), ("004", "Condominium"), ("003", "Multi-family, 10+ units"),
         ("011", "Commercial"), ("048", "Industrial"), ("066", "Agricultural"),
         ("082", "Government"), ("099", "Non-agricultural acreage"), (None, None), ("", None)],
    )  # fmt: skip
    def test_descriptions(self, code, expected):
        assert use_description(code) == expected


class TestAddressMatching:
    def test_normalize(self):
        assert normalize("304 S MacDill Ave, #3") == "304 S MACDILL AVE 3"
        assert normalize("304 S MACDILL AVE UNIT 3") == "304 S MACDILL AVE 3"
        assert normalize(None) == ""

    @pytest.mark.parametrize(
        "situs,wanted,expected",
        [("1216 VIRGINIA DR", "1216 VIRGINIA DRIVE", True),
         ("304 S MACDILL AVE 3", "304 MACDILL AVE", True),
         ("1216 VIRGINIA DR", "1218 VIRGINIA DR", False),
         ("1216 VIRGINIA DR", "1216 PORTLAND AVE", False),
         ("", "1216 VIRGINIA DR", False),
         ("VIRGINIA DR", "VIRGINIA DR", False)],
    )  # fmt: skip
    def test_same_house(self, situs, wanted, expected):
        assert same_house(situs, wanted) is expected

    def test_address_match_beats_location(self):
        containing = lot(-10, PHY_ADDR1="1221 VIRGINIA DR")
        neighbor = lot(15, PHY_ADDR1="1216 VIRGINIA DR")
        parcel, match = choose_parcel(
            LAT, LON, "1216 Virginia Drive, Orlando, FL 32803", [containing, neighbor]
        )
        assert parcel is neighbor and match == "address"

    def test_exact_unit_beats_other_units(self):
        unit_1 = lot(-10, PHY_ADDR1="304 S MACDILL AVE UNIT 1")
        unit_3 = lot(-10, PHY_ADDR1="304 S MACDILL AVE UNIT 3")
        parcel, match = choose_parcel(LAT, LON, "304 S MacDill Ave #3, Tampa", [unit_1, unit_3])
        assert parcel is unit_3 and match == "address"

    def test_falls_back_to_containing_parcel(self):
        containing = lot(-10, PHY_ADDR1="1221 VIRGINIA DR")
        neighbor = lot(15, PHY_ADDR1="1215 VIRGINIA DR")
        parcel, match = choose_parcel(LAT, LON, "Somewhere, Orlando", [neighbor, containing])
        assert parcel is containing and match == "location"

    def test_containing_unit_beats_common_area(self):
        common = lot(-10, DOR_UC="009", PHY_ADDR1="")
        unit = lot(-10, DOR_UC="004", PHY_ADDR1="")
        parcel, _ = choose_parcel(LAT, LON, "Somewhere", [common, unit])
        assert parcel is unit

    def test_point_on_the_street_takes_nearest(self):
        near = lot(5, PHY_ADDR1="1 A ST")
        far = lot(25, PHY_ADDR1="2 A ST")
        parcel, match = choose_parcel(LAT, LON, "Somewhere", [far, near])
        assert parcel is near and match == "nearest"

    def test_no_parcels(self):
        assert choose_parcel(LAT, LON, "1 A St", []) is None


class TestDetails:
    def test_fields(self):
        details = parcel_details(ROLL)
        assert details == {
            "county": "Orange",
            "parcel_id": "242229582203011",
            "assessment_year": 2026,
            "situs_address": "1216 VIRGINIA DR, Orlando",
            "use_code": "001",
            "use": "Single family",
            "year_built": 1955,
            "effective_year_built": 1980,
            "living_area_sqft": 2376,
            "lot_sqft": 12333,
            "lot_acres": 0.28,
            "buildings": 1,
            "residential_units": 1,
            "quality": "Average",
            "just_value": 636740,
            "land_value": 374400,
            "taxable_value": 561740,
            "school_taxable_value": 586740,
            "homestead": True,
            "recent_sales": [],
        }

    def test_blank_fields_are_none(self):
        vacant = {**ROLL, "DOR_UC": "000", "ACT_YR_BLT": 0, "EFF_YR_BLT": 0, "TOT_LVG_AR": 0,
                  "NO_BULDNG": 0, "NO_RES_UNT": 0, "IMP_QUAL": " ", "JV_HMSTD": 0, "TV_NSD": 0}  # fmt: skip
        details = parcel_details(vacant)
        assert details["year_built"] is None
        assert details["living_area_sqft"] is None
        assert details["buildings"] is None
        assert details["quality"] is None
        assert details["taxable_value"] is None
        assert details["homestead"] is False

    def test_recent_sales_newest_first(self):
        roll = {**ROLL,
                "SALE_PRC1": 410000, "SALE_YR1": 2025, "SALE_MO1": "03", "QUAL_CD1": "01", "VI_CD1": "I",
                "SALE_PRC2": 100, "SALE_YR2": 2025, "SALE_MO2": "11", "QUAL_CD2": "30", "VI_CD2": "I"}  # fmt: skip
        assert recent_sales(roll) == [
            {"year": 2025, "month": 11, "price": 100, "qualification_code": "30",
             "arms_length": False, "vacant_land": False},
            {"year": 2025, "month": 3, "price": 410000, "qualification_code": "01",
             "arms_length": True, "vacant_land": False},
        ]  # fmt: skip


class TestProvider:
    @pytest.mark.asyncio
    async def test_enrich(self):
        provider = ParcelProvider()
        provider.api_client.query_box = AsyncMock(return_value=[lot(-10, **ROLL)])

        result = await provider.enrich(LAT, LON, "1216 Virginia Dr, Orlando, FL 32803")

        assert result.success
        assert result.data["found"] is True
        assert result.data["match"] == "address"
        assert result.data["year_built"] == 1955
        assert result.data["county"] == "Orange"

    @pytest.mark.asyncio
    async def test_outside_florida(self):
        provider = ParcelProvider()
        provider.api_client.query_box = AsyncMock(return_value=[])

        result = await provider.enrich(33.749, -84.388, "Atlanta, GA")

        assert result.success and result.data == {"found": False}

    @pytest.mark.asyncio
    async def test_service_error(self):
        provider = ParcelProvider()
        provider.api_client.query_box = AsyncMock(side_effect=httpx.ConnectError("down"))

        result = await provider.enrich(LAT, LON, "1216 Virginia Dr")

        assert not result.success and result.error_message == "down"
