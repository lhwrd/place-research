"""Client for public ArcGIS REST services (FDEP, USFWS, FDEM, ...). No API key.

Many state and federal datasets are published as ArcGIS MapServer/FeatureServer layers or
ImageServer rasters. This client answers the two questions the providers ask of them:
"which features are within N meters of this point?" and "what is the raster value here?".
"""

import logging
import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from .base_client import BaseAPIClient, send_with_retry

logger = logging.getLogger(__name__)


class ArcGISClient(BaseAPIClient):
    """Point queries against one ArcGIS server."""

    def __init__(self, base_url: str, service: str, timeout: float = 30.0):
        """
        Args:
            base_url: The server's services root, e.g. https://host/arcgis/rest/services
            service: Short name for logs and retry messages
        """
        super().__init__(
            base_url=base_url, api_key=None, timeout=timeout, rate_limit_per_second=10.0
        )
        self.service = service

    def _get_service_name(self) -> str:
        return self.service

    async def validate_api_key(self) -> bool:
        """No key is needed."""
        return True

    async def query_near(
        self,
        layer: str,
        latitude: float,
        longitude: float,
        distance_m: float = 0,
        out_fields: Sequence[str] = ("*",),
        geometry: bool = False,
        where: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Features of a layer within distance_m of a point (0: features containing the point).

        Args:
            layer: Layer path under the services root, e.g. "OpenData/FGS_SUBSIDENCE/MapServer/0"
            geometry: Also return each feature's geometry, in WGS84
            where: SQL filter on the layer's fields, e.g. "STATUS = 'ACTIVE'"

        Returns:
            One dict per feature: its attributes, plus "geometry" (a shapely geometry) when
            asked for. Results stop at the layer's record limit (usually 1000-2000).

        Raises:
            httpx.HTTPError: If the server can't be reached or returns an HTTP error
            ValueError: If the server returns an ArcGIS error body
        """
        params: Dict[str, Any] = {
            "geometry": f"{longitude},{latitude}",
            "geometryType": "esriGeometryPoint",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": ",".join(out_fields),
            "returnGeometry": "true" if geometry else "false",
            # GeoJSON gives geometries shapely reads directly; plain JSON is lighter
            "f": "geojson" if geometry else "json",
        }
        if distance_m:
            params.update(distance=distance_m, units="esriSRUnit_Meter")
        if geometry:
            params.update(outSR=4326, geometryPrecision=6)
        if where:
            params["where"] = where

        data = await self._get(f"{layer}/query", params)
        if geometry:
            return [
                {**(f.get("properties") or {}), "geometry": _shape(f.get("geometry"))}
                for f in data.get("features", [])
            ]
        return [f.get("attributes") or {} for f in data.get("features", [])]

    async def query_box(
        self,
        layer: str,
        latitude: float,
        longitude: float,
        half_size_m: float,
        out_fields: Sequence[str] = ("*",),
    ) -> List[Dict[str, Any]]:
        """
        Features intersecting a square of 2 * half_size_m around a point, with geometries.

        Use this rather than query_near(distance_m=...) for layers stored in a projection
        the server can't buffer in (it answers distance queries with an SRID error). The
        Florida statewide parcels, in Florida GDL Albers, are one.

        Returns:
            One dict per feature: its attributes plus "geometry" (a shapely geometry in WGS84)
        """
        dlat = half_size_m / 110_950.0
        dlon = half_size_m / (111_320.0 * math.cos(math.radians(latitude)))
        params: Dict[str, Any] = {
            "geometry": f"{longitude - dlon},{latitude - dlat},{longitude + dlon},{latitude + dlat}",
            "geometryType": "esriGeometryEnvelope",
            "inSR": 4326,
            "spatialRel": "esriSpatialRelIntersects",
            "outFields": ",".join(out_fields),
            "returnGeometry": "true",
            "outSR": 4326,
            "geometryPrecision": 6,
            "f": "geojson",
        }
        data = await self._get(f"{layer}/query", params)
        return [
            {**(f.get("properties") or {}), "geometry": _shape(f.get("geometry"))}
            for f in data.get("features", [])
        ]

    async def sample(
        self, image_service: str, latitude: float, longitude: float
    ) -> Optional[float]:
        """
        The raster value at a point, or None where the raster has no data.

        Args:
            image_service: ImageServer path, e.g. "OpenData/FGS_FAV_SINK_FORMATION/ImageServer"
        """
        return (await self.sample_many(image_service, [(latitude, longitude)]))[0]

    async def sample_many(
        self, image_service: str, points: Sequence[Tuple[float, float]]
    ) -> List[Optional[float]]:
        """Raster values at several (latitude, longitude) points in one request, in order."""
        coordinates = ",".join(f"[{lon},{lat}]" for lat, lon in points)
        params = {
            "geometry": f'{{"points":[{coordinates}],"spatialReference":{{"wkid":4326}}}}',
            "geometryType": "esriGeometryMultipoint",
            "returnFirstValueOnly": "true",
            "f": "json",
        }
        data = await self._get(f"{image_service}/getSamples", params)
        values: List[Optional[float]] = [None] * len(points)
        for sample in data.get("samples") or []:
            index = sample.get("locationId")
            if isinstance(index, int) and 0 <= index < len(points):
                values[index] = _number(sample.get("value"))
        return values

    async def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/{path}"
        await self._rate_limit()
        response = await send_with_retry(
            lambda: self.client.get(url, params=params), service=self.service
        )
        response.raise_for_status()
        data = response.json()
        # ArcGIS reports query errors with HTTP 200 and an "error" body
        if isinstance(data, dict) and "error" in data:
            raise ValueError(f"{self.service} query failed: {data['error'].get('message')}")
        return data


def _number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):  # "NoData" or missing
        return None


def _shape(geojson: Optional[Dict[str, Any]]) -> Optional[BaseGeometry]:
    return shape(geojson) if geojson else None


# Servers used by the providers
FDEP_OPEN_DATA = "https://ca.dep.state.fl.us/arcgis/rest/services"
USFWS_WETLANDS = "https://fwspublicservices.wim.usgs.gov/wetlandsmapservice/rest/services"
USGS_ELEVATION = "https://elevation.nationalmap.gov/arcgis/rest/services"
FL_EVACUATION_ZONES = "https://services1.arcgis.com/CY1LXxl9zlJeBuRZ/ArcGIS/rest/services"
# Florida GIO's ArcGIS Online org: the Department of Revenue's statewide parcels
FL_GIO = "https://services9.arcgis.com/Gh9awoU677aKree0/arcgis/rest/services"
# Esri's Living Atlas copy of the electric retail service territories, with EIA-861 rates
ESRI_POLICY_MAPS = "https://services8.arcgis.com/peDZJliSvYims39Q/arcgis/rest/services"
# FDOT Transportation Data and Analytics
FDOT_TDA = "https://services1.arcgis.com/O1JpcwDW8sjYuddV/arcgis/rest/services"
