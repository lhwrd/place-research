"""Build app/data/beach_parking.csv, the beach parking list the beach provider ships with.

Downloads FDEP's Coastal Access Sites (the Florida Beach Access Guide: about 2,200 public
access points on the Gulf and Atlantic) and keeps the ones with regular parking. Walkovers
and street ends with nowhere to leave a car are left out.

    uv run python scripts/build_beach_parking.py
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, List

import httpx
import pandas as pd

URL = (
    "https://services1.arcgis.com/nRHtyn3uE1kyzoYc/arcgis/rest/services/"
    "BEACH_ACCESS_SITES/FeatureServer/0/query"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "app" / "data" / "beach_parking.csv"
PAGE_SIZE = 1000
FIELDS = (
    "SITE_ID,ACCESS_NAM,BEACH_OR_C,COUNTY,Address,GULF_COAST,REGULAR_PA,NUMBER_OF_,"
    "PARKING_FE,PARKING__1"
)


def download() -> List[Dict[str, Any]]:
    features: List[Dict[str, Any]] = []
    while True:
        response = httpx.get(
            URL,
            params={
                "where": "1=1",
                "outFields": FIELDS,
                "outSR": 4326,
                "orderByFields": "FID",
                "resultOffset": len(features),
                "resultRecordCount": PAGE_SIZE,
                "f": "json",
            },
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["error"].get("message"))
        features.extend(data["features"])
        if not data.get("exceededTransferLimit"):
            return features


def build(features: List[Dict[str, Any]]) -> pd.DataFrame:
    def text(value: Any) -> str:
        return " ".join(str(value or "").split())

    rows = []
    for feature in features:
        a, point = feature["attributes"], feature.get("geometry")
        if text(a.get("REGULAR_PA")).lower() != "yes" or not point:
            continue
        spaces = text(a.get("NUMBER_OF_"))
        rows.append(
            {
                "site_id": text(a.get("SITE_ID")),
                "name": text(a.get("ACCESS_NAM")),
                "beach": text(a.get("BEACH_OR_C")),
                "county": text(a.get("COUNTY")),
                # Sites without a street address come as ", ,"
                "address": text(a.get("Address")).strip(" ,"),
                "coast": "Gulf" if text(a.get("GULF_COAST")).lower() == "yes" else "Atlantic",
                "spaces": int(spaces) if spaces.isdigit() else "",
                "fee": text(a.get("PARKING__1"))
                or ("yes" if text(a.get("PARKING_FE")).lower().startswith("yes") else ""),
                "latitude": round(point["y"], 6),
                "longitude": round(point["x"], 6),
            }
        )
    return pd.DataFrame(rows).sort_values(["county", "beach", "name"]).reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("output", type=Path, nargs="?", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    sites = build(download())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    sites.to_csv(args.output, index=False)
    print(f"Wrote {len(sites):,} beach parking sites to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
