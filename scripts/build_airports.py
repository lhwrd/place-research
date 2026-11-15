"""Build app/data/airports.csv, the airport list the airport provider ships with.

Downloads OurAirports (public domain, https://ourairports.com/data/), keeps large and
medium airports, and labels each for the noise model:

    large     large commercial airports
    military  air bases, naval air stations and other military fields
    regional  medium airports with scheduled airline service
    general   other medium airports (business and general aviation)

Small airports, heliports and seaplane bases are left out: there are tens of thousands,
mostly private strips with little traffic.

    uv run python scripts/build_airports.py
"""

import argparse
import io
import re
import sys
from pathlib import Path

import httpx
import pandas as pd

URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "app" / "data" / "airports.csv"

MILITARY = re.compile(
    r"\b(Air Force Base|AFB|Air Base|Naval Air|NAS|Naval Outlying|Air National Guard|"
    r"Army Air ?field|AAF|Marine Corps Air|MCAS|Space Force|Joint Base|Air Reserve)\b",
    re.IGNORECASE,
)


def categorize(row: pd.Series) -> str:
    if MILITARY.search(row["name"]):
        return "military"
    if row["type"] == "large_airport":
        return "large"
    return "regional" if row["scheduled_service"] == "yes" else "general"


def build(raw_csv: str) -> pd.DataFrame:
    airports = pd.read_csv(io.StringIO(raw_csv), keep_default_na=False)
    airports = airports[airports["type"].isin(["large_airport", "medium_airport"])].copy()
    airports["category"] = airports.apply(categorize, axis=1)
    out = airports.rename(
        columns={"latitude_deg": "latitude", "longitude_deg": "longitude", "iata_code": "iata"}
    )[["ident", "iata", "name", "municipality", "iso_region", "category", "latitude", "longitude"]]
    return out.sort_values("ident").reset_index(drop=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("output", type=Path, nargs="?", default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    # The CDN refuses some default client User-Agents
    response = httpx.get(
        URL, headers={"User-Agent": "place-research/1.0"}, timeout=120, follow_redirects=True
    )
    response.raise_for_status()
    airports = build(response.text)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    airports.to_csv(args.output, index=False)
    counts = airports["category"].value_counts().to_dict()
    print(f"Wrote {len(airports):,} airports to {args.output} {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
