"""Build app/data/heliports.csv, the Florida heliports the sirens provider ships with.

Downloads OurAirports (public domain, https://ourairports.com/data/) and keeps Florida's
open heliports, labeled by who flies from them:

    hospital  medical helicopters, flying day and night at short notice
    public    police, sheriff and fire rescue
    tours     helicopter tour and charter operators, flying all day near attractions
    other     private, corporate, TV stations and the rest; most see little traffic

    uv run python scripts/build_heliports.py
"""

import argparse
import io
import re
import sys
from pathlib import Path

import httpx
import pandas as pd

URL = "https://davidmegginson.github.io/ourairports-data/airports.csv"
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "app" / "data" / "heliports.csv"

HOSPITAL = re.compile(
    r"\b(hospital|medical|health|healthplex|regional|clinic|trauma|healthcare|emergency|ER|"
    r"OSED|FSED|AH|HCA|baptist|adventhealth|mayo|memorial|shands|tampa general|halifax)\b",
    re.IGNORECASE,
)
PUBLIC = re.compile(
    r"\b(police|sheriff|sheriff's|pbso|fire|rescue|ems|fhp|highway patrol|law enforcement|"
    r"district station|fwc)\b",
    re.IGNORECASE,
)
TOURS = re.compile(
    r"helicopters?|helicenter|heli-?tours?|heli-?partners|\btours?\b|air orlando", re.IGNORECASE
)


def categorize(name: str) -> str:
    if HOSPITAL.search(name):
        return "hospital"
    if PUBLIC.search(name):
        return "public"
    return "tours" if TOURS.search(name) else "other"


def build(raw_csv: str) -> pd.DataFrame:
    rows = pd.read_csv(io.StringIO(raw_csv), keep_default_na=False)
    heliports = rows[(rows["type"] == "heliport") & (rows["iso_region"] == "US-FL")].copy()
    heliports["category"] = heliports["name"].map(categorize)
    out = heliports.rename(columns={"latitude_deg": "latitude", "longitude_deg": "longitude"})[
        ["ident", "name", "municipality", "category", "latitude", "longitude"]
    ]
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
    heliports = build(response.text)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    heliports.to_csv(args.output, index=False)
    counts = heliports["category"].value_counts().to_dict()
    print(f"Wrote {len(heliports):,} heliports to {args.output} {counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
