"""Build the broadband file for BROADBAND_PATH from FCC National Broadband Map data.

The FCC publishes, per state and technology, every provider's advertised service at every
location (Broadband Data Collection "Fixed Broadband" availability). Download them from
https://broadbandmap.fcc.gov/data-download/nationwide-data: choose the latest filing,
Florida, Fixed Broadband, and download the CSVs for the technologies you care about
(Cable, Fiber to the Premises, Copper, Licensed/Unlicensed Fixed Wireless). Satellite is
available everywhere, so it adds nothing and is skipped by default.

    uv run python scripts/build_broadband.py data/broadband.parquet ~/Downloads/bdc_12_*.zip

This rolls locations up to census blocks: for each block, provider and technology, the
fastest advertised speeds and how many of the block's residential locations get them.
The output is a few tens of MB for Florida.
"""

import argparse
import sys
import zipfile
from pathlib import Path
from typing import Iterator, List

import pandas as pd

COLUMNS = [
    "location_id",
    "brand_name",
    "technology",
    "max_advertised_download_speed",
    "max_advertised_upload_speed",
    "low_latency",
    "business_residential_code",
    "block_geoid",
]

# FCC technology codes
SATELLITE = {60, 61}  # GSO (HughesNet, Viasat) and NGSO (Starlink)
BUSINESS_ONLY = "B"

CHUNK_ROWS = 2_000_000


def read_chunks(path: Path) -> Iterator[pd.DataFrame]:
    """The CSV, or each CSV inside a zip, in chunks of the columns we use."""
    dtypes = {
        "block_geoid": "string",
        "brand_name": "string",
        "business_residential_code": "string",
    }

    def from_handle(handle) -> Iterator[pd.DataFrame]:
        yield from pd.read_csv(handle, usecols=COLUMNS, dtype=dtypes, chunksize=CHUNK_ROWS)

    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            for name in archive.namelist():
                if name.lower().endswith(".csv"):
                    with archive.open(name) as handle:
                        yield from from_handle(handle)
    else:
        with path.open("rb") as handle:
            yield from from_handle(handle)


def build(output: Path, inputs: List[Path], include_satellite: bool) -> None:
    service_parts, location_parts = [], []
    for i, path in enumerate(inputs, 1):
        print(f"[{i}/{len(inputs)}] {path}", flush=True)
        for chunk in read_chunks(path):
            chunk = chunk[chunk["business_residential_code"] != BUSINESS_ONLY]
            if not include_satellite:
                chunk = chunk[~chunk["technology"].isin(SATELLITE)]
            if chunk.empty:
                continue
            service_parts.append(
                chunk.groupby(["block_geoid", "brand_name", "technology"], observed=True).agg(
                    max_down=("max_advertised_download_speed", "max"),
                    max_up=("max_advertised_upload_speed", "max"),
                    low_latency=("low_latency", "max"),
                    locations=("location_id", "count"),
                )
            )
            location_parts.append(chunk[["block_geoid", "location_id"]].drop_duplicates())

    if not service_parts:
        sys.exit("No residential service rows found in the input files")

    # A provider's locations in one block can span chunks and files: combine them
    service = (
        pd.concat(service_parts)
        .groupby(level=[0, 1, 2])
        .agg({"max_down": "max", "max_up": "max", "low_latency": "max", "locations": "sum"})
        .reset_index()
    )
    block_locations = (
        pd.concat(location_parts)
        .drop_duplicates()
        .groupby("block_geoid")
        .size()
        .rename("block_locations")
        .reset_index()
    )
    service = service.merge(block_locations, on="block_geoid")
    service["low_latency"] = service["low_latency"].astype(bool)

    output.parent.mkdir(parents=True, exist_ok=True)
    service.to_parquet(output, index=False)
    print(
        f"Wrote {len(service):,} block/provider rows for {service['block_geoid'].nunique():,} "
        f"blocks to {output} ({output.stat().st_size / 1e6:.0f} MB)"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("output", type=Path, help="Parquet file to write")
    parser.add_argument("inputs", type=Path, nargs="+", help="FCC availability CSV or zip files")
    parser.add_argument("--include-satellite", action="store_true", help="Keep satellite providers")
    args = parser.parse_args()
    missing = [p for p in args.inputs if not p.exists()]
    if missing:
        parser.error(f"Not found: {', '.join(map(str, missing))}")
    build(args.output, args.inputs, args.include_satellite)
    return 0


if __name__ == "__main__":
    sys.exit(main())
