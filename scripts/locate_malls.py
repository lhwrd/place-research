"""Fill in coordinates for app/data/malls.csv, the mall list the mall provider ships with.

The list itself is kept by hand: which Florida malls and shopping centers are on it and
whether each is thriving, healthy, struggling, dead or redeveloping (a judgment call, with
the reason in the note column). This script only looks up a location for rows that have
none, with Google Places Text Search, and prints what it matched so a wrong match is easy
to spot. Pass --all to look every row up again.

    uv run python scripts/locate_malls.py
"""

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402

MALLS_CSV = Path(__file__).resolve().parents[1] / "app" / "data" / "malls.csv"
URL = "https://places.googleapis.com/v1/places:searchText"
FIELDS = "places.displayName,places.formattedAddress,places.location,places.types"
FLORIDA = {
    "low": {"latitude": 24.3, "longitude": -87.7},
    "high": {"latitude": 31.1, "longitude": -79.8},
}
MALL_TYPES = {"shopping_mall", "outlet_mall"}


def locate(client: httpx.Client, name: str, city: str) -> Optional[Dict[str, Any]]:
    """The best Places match for a mall: a shopping mall if any result is one."""
    response = client.post(
        URL,
        json={
            "textQuery": f"{name}, {city}, FL",
            "pageSize": 5,
            "locationRestriction": {"rectangle": FLORIDA},
        },
        headers={"X-Goog-Api-Key": settings.google_maps_api_key, "X-Goog-FieldMask": FIELDS},
        timeout=30,
    )
    response.raise_for_status()
    places = response.json().get("places") or []
    malls = [p for p in places if MALL_TYPES & set(p.get("types") or [])]
    return (malls or places or [None])[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--all", action="store_true", help="look up rows that have coordinates too")
    parser.add_argument("--file", type=Path, default=MALLS_CSV)
    args = parser.parse_args()
    if not settings.google_maps_api_key:
        sys.exit("GOOGLE_MAPS_API_KEY is not set")

    malls = pd.read_csv(args.file, keep_default_na=False, dtype=str)
    missing = []
    with httpx.Client() as client:
        for i, row in malls.iterrows():
            if row["latitude"] and row["longitude"] and not args.all:
                continue
            place = locate(client, row["name"], row["city"])
            if not place:
                missing.append(row["name"])
                print(f"  ??  {row['name']}, {row['city']}: no match")
                continue
            location = place["location"]
            malls.at[i, "latitude"] = f"{location['latitude']:.6f}"
            malls.at[i, "longitude"] = f"{location['longitude']:.6f}"
            flag = "  " if MALL_TYPES & set(place.get("types") or []) else "!!"
            print(
                f"  {flag}  {row['name']}, {row['city']} -> "
                f"{place['displayName']['text']}, {place.get('formattedAddress')}"
            )
    malls.to_csv(args.file, index=False)
    print(f"Wrote {args.file} ({len(malls)} malls)")
    if missing:
        sys.exit(f"No location for: {', '.join(missing)}")


if __name__ == "__main__":
    main()
