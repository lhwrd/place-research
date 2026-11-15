"""Build the highways file for HIGHWAYS_PATH from Census TIGER/Line roads.

Downloads each state's primary and secondary roads (interstates, US, state and county
highways: MTFCC S1100 and S1200), keeps the columns the highway provider uses, and writes
one GeoParquet file.

    uv run python scripts/build_highways.py data/highways.parquet            # all states
    uv run python scripts/build_highways.py data/highways.parquet --states FL CO

Lines are simplified (--tolerance, default 10 m): plenty for distance-to-road, and it
shrinks the file and the server's memory several times over. Include neighboring states for
homes near a state line, since the nearest highway may be across it.
"""

import argparse
import sys
import tempfile
from pathlib import Path

import geopandas as gpd
import httpx
import pandas as pd

URL = "https://www2.census.gov/geo/tiger/TIGER{year}/PRISECROADS/tl_{year}_{fips}_prisecroads.zip"
COLUMNS = ["LINEARID", "FULLNAME", "MTFCC", "geometry"]

# Postal code -> state FIPS, for the states and territories TIGER publishes
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06", "CO": "08", "CT": "09",
    "DE": "10", "DC": "11", "FL": "12", "GA": "13", "HI": "15", "ID": "16", "IL": "17",
    "IN": "18", "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23", "MD": "24",
    "MA": "25", "MI": "26", "MN": "27", "MS": "28", "MO": "29", "MT": "30", "NE": "31",
    "NV": "32", "NH": "33", "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44", "SC": "45", "SD": "46",
    "TN": "47", "TX": "48", "UT": "49", "VT": "50", "VA": "51", "WA": "53", "WV": "54",
    "WI": "55", "WY": "56", "PR": "72",
}  # fmt: skip


def download(url: str, dest: Path) -> None:
    # census.gov refuses some default client User-Agents
    headers = {"User-Agent": "place-research/1.0"}
    with httpx.stream("GET", url, headers=headers, timeout=120, follow_redirects=True) as r:
        r.raise_for_status()
        with dest.open("wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)


def build(output: Path, states: list[str], year: int, tolerance_m: float) -> None:
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        for i, state in enumerate(states, 1):
            url = URL.format(year=year, fips=STATE_FIPS[state])
            print(f"[{i}/{len(states)}] {state} {url}", flush=True)
            zip_path = Path(tmp) / f"{state}.zip"
            download(url, zip_path)
            roads = gpd.read_file(zip_path, columns=COLUMNS[:-1])
            roads = roads[roads["MTFCC"].isin(["S1100", "S1200"])][COLUMNS]
            if tolerance_m > 0:
                # Simplify in meters (CONUS Albers), then store as plain lon/lat
                crs = roads.crs
                roads = roads.to_crs(epsg=5070)
                roads["geometry"] = roads.geometry.simplify(tolerance_m)
                roads = roads.to_crs(crs)
            frames.append(roads)
            zip_path.unlink()

    roads = gpd.GeoDataFrame(pd.concat(frames, ignore_index=True), crs=frames[0].crs)
    # Roads on a state line appear in both states' files
    roads = roads.drop_duplicates("LINEARID").reset_index(drop=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    roads.to_parquet(output)
    print(f"Wrote {len(roads):,} road segments to {output} ({output.stat().st_size / 1e6:.0f} MB)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("output", type=Path, help="GeoParquet file to write")
    parser.add_argument(
        "--states", nargs="+", metavar="XX", help="Postal codes to include (default: all)"
    )
    parser.add_argument("--year", type=int, default=2025, help="TIGER/Line release")
    parser.add_argument(
        "--tolerance",
        type=float,
        default=10.0,
        metavar="M",
        help="Simplify lines to within this many meters (0 to keep full detail)",
    )
    args = parser.parse_args()

    states = [s.upper() for s in args.states] if args.states else list(STATE_FIPS)
    unknown = [s for s in states if s not in STATE_FIPS]
    if unknown:
        parser.error(f"unknown state codes: {', '.join(unknown)}")
    build(args.output, states, args.year, args.tolerance)
    return 0


if __name__ == "__main__":
    sys.exit(main())
