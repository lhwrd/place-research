# Place Research

Collect homes you're considering and see what living there would be like. Add a property
by typing an address or pasting a Zillow URL, or share a listing from your iPhone. The
app then enriches it with flood zone, distance to the nearest highway,
railroad and airport, an estimate of noise pollution from all three, air quality, nearby places, drive times to the people and places you
care about, and Census data (city and county population; age, race/ethnicity and education
for the census tract). In Florida it also covers sinkhole geology and reported sinkholes,
open contamination cleanups, impaired lakes, hurricane evacuation zone, the property appraiser's record (year built, living area, value, recent sales), theme park
fireworks and Cape launches; anywhere, nearby wetlands, whether the house sits below
the ground around it, and FCC home internet providers. Look around in Street View, rate the home and how the neighborhood looks, mark it
visited, keep notes and photos.

```
Web UI / iOS Shortcut ──▶ FastAPI ──▶ SQLite
                             └─(background)─▶ geocode ─▶ providers ─▶ SQLite
```

One FastAPI app serves the web UI (server-rendered HTML, no build step) and the Shortcut
API. Everything lives in one SQLite file (`DATABASE_PATH`), photos included, so a backup
is one file. CI publishes the image as `ghcr.io/<repo>/backend`; the VM, environment
config and deployment live in howard-home.

There is no login: reach the UI over the tailnet only.

## Pages

| Page              | What it's for                                                                        |
| ----------------- | ------------------------------------------------------------------------------------ |
| `/`               | All properties, sortable. Add one by address or Zillow URL.                          |
| `/properties/{id}`| Facts, photos, enrichment, your rating / visited / notes. Re-enrich, edit, delete.   |
| `/locations`      | Drive-time destinations (name, address, type, priority, active).                     |
| `/settings`       | Amenity types (Google Places types) and preferred places to search for near each home. |

Enrichment starts as soon as a property is added; the detail page refreshes itself when
it finishes. Each provider's stored result is kept until it is too old (its
`cache_duration_days`), it failed, or the locations or settings it used have changed.
**Re-enrich** fetches only those, so the billed Google lookups aren't repeated for
nothing; **Redo all** fetches everything again. A provider that fails keeps its previous data and is listed under the
property; if the whole run fails (e.g. the address can't be geocoded) the property shows
the error. Properties left mid-enrichment by a restart are picked up on startup.

## iOS Shortcut API

Both endpoints need `Authorization: Bearer <INGEST_API_TOKEN>`. The phone must be on the
tailnet.

### Add a listing

```
POST /api/v1/listings
Content-Type: application/json

{"url": "https://www.zillow.com/homedetails/.../46284123_zpid/",
 "listing_json": { ...anything extracted from the page... }}
```

Response: `{"row_id": 12, "created": true}` (`row_id` is the property id). Sharing the
same listing again (same zpid) returns the existing property with `"created": false`.

`listing_json` is optional, as an object or a JSON string. The parser looks for Zillow's
embedded property object (from `__NEXT_DATA__`, including the `gdpClientCache` JSON
string) and schema.org JSON-LD blocks, and takes address, price, beds, baths, sqft, lot,
year built, type and coordinates from them. Without it, the address comes from the URL
slug and the geocoder does the rest.

### Add photos

```
POST /api/v1/listings/{row_id}/images
```

Either `multipart/form-data` with one or more parts named `file` (up to 50 per request),
or a raw image body with its `Content-Type` (e.g. `image/jpeg`), optionally
`?filename=front`. Each image may be up to 25 MB. Response:
`{"row_id": 12, "uploaded": 3, "photo_count": 7}`.

```bash
curl -s -X POST "$API/api/v1/listings" -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' -d '{"url": "https://www.zillow.com/homedetails/x/46284123_zpid/"}'

curl -s -X POST "$API/api/v1/listings/12/images" -H "Authorization: Bearer $TOKEN" \
  -F file=@front.jpg -F file=@kitchen.jpg
```

`GET /health` is unauthenticated, for health checks.

## Development

```bash
cp .env.example .env   # API keys, data file paths, ingest token
uv sync
make dev               # UI at http://localhost:8000, API docs at /docs
make test
make lint              # make format to fix
```

Or in Docker: `docker compose up --build`. Put provider data files in `./data`; the
database is written to `./db`.

Local data files (a provider whose file isn't configured is skipped):

- `RAILLINES_PATH`: rail lines, GeoParquet (`.parquet`) or GeoJSON; the loader picks the
  reader by extension. Production gets GeoParquet: the howard-home Ansible role downloads
  the GeoJSON and converts it at deploy time. Abandoned and out-of-service track is
  ignored, and main lines are told apart from spurs and yards for noise.
- `HIGHWAYS_PATH`: major roads (Census TIGER primary and secondary roads) for highway
  distance and road noise. Build it with
  `uv run python scripts/build_highways.py data/highways.parquet`, or limit it to the
  states you're looking in (plus neighbors, for homes near a state line) with
  `--states FL GA AL`.

- `BROADBAND_PATH`: home internet providers by census block, from the FCC National
  Broadband Map. Download your state's Fixed Broadband availability CSVs (one per
  technology) from https://broadbandmap.fcc.gov/data-download/nationwide-data, then
  `uv run python scripts/build_broadband.py data/broadband.parquet ~/Downloads/bdc_12_*.zip`.
  Satellite is skipped (it's available everywhere). Refresh after each FCC release
  (twice a year).

The Florida hazard providers (sinkholes, contamination, impaired waters, evacuation zone)
query FDEP and state ArcGIS services; wetlands (USFWS) and elevation (USGS 3DEP) are
national. None needs a key.

The property record (Florida) is the county property appraiser's tax roll entry for the
parcel, from the Department of Revenue's statewide parcels on Florida GIO's ArcGIS
service: year built, living area, lot, use, quality, just and taxable value, homestead and
sales from this year and last. No key. It has no bed or bath counts; those come from the
listing.

Airports ship with the app (`app/data/airports.csv`, large and medium airports from
OurAirports); refresh the list with `uv run python scripts/build_airports.py`.

Walk, bike and transit scores (`WALKSCORE_API_KEY`) are the exception to "enrich once and
store": Walk Score's terms don't allow keeping its scores, so they are fetched each time a
property page is opened, shown with a link to Walk Score, and never saved. They aren't on
the property list for the same reason.

Google APIs: `GOOGLE_MAPS_API_KEY` needs Geocoding, Distance Matrix and Places (New).
`GOOGLE_MAPS_EMBED_KEY`, which the browser sees, needs the Maps Embed API (the Street View
viewer) and Street View Static API (the free panorama lookup that points the viewer at
the house). Without an embed key there is no Street View: the main key is never sent to
the browser.

Noise pollution is estimated from those distances by `app/services/noise.py`: each
source starts at a typical level for its kind and fades with distance (about 5 dB per
doubling for roads and railways, which are lines of sound; 6 dB for airports). Road
traffic is rated by its average level; trains by a train passing, since they're
intermittent but loud. The sources are combined as sound energy. It's a rough model for
comparing homes; tune the levels there. The UI computes it at display time, so
changing the model doesn't need a re-enrich.

## API usage

Every response from an external API is recorded in the `api_calls` table of the SQLite
database (`app/integrations/usage.py`), one row per request, retries included:

| Column        | Meaning                                                                  |
|---------------|--------------------------------------------------------------------------|
| `at`          | UTC time, RFC 3339                                                       |
| `service`     | The client, e.g. `google_maps`, `google_places`, `census`, `walkscore`   |
| `host`, `endpoint`, `method` | Where the request went (path only, never the query string) |
| `status`      | HTTP status                                                              |
| `duration_ms` | Time until the response headers arrived                                  |
| `sku`         | For billed Google requests, the product charged; `NULL` if free          |
| `units`       | Billable units: 1, or the number of destinations for Distance Matrix     |

Requests that get no response (connection errors, timeouts) aren't recorded. To chart it,
point Grafana's SQLite data source at the database file, read-only. Month-to-date billable
units per Google product, to compare with each one's free monthly allowance:

```sql
SELECT sku, SUM(units) AS units
FROM api_calls
WHERE sku IS NOT NULL AND status = 200 AND at >= strftime('%Y-%m-01', 'now')
GROUP BY sku;
```

## Layout

```
app/web/                  UI routes, Jinja templates, style.css
app/api/                  iOS Shortcut endpoints and bearer-token auth
app/db/                   SQLite schema and data access
app/services/             property_service.py (ingest + enrichment), property_view.py
                          (formats provider data for display), zillow_listing.py, geocoding
app/services/enrichment/  orchestrator + auto-discovered providers
app/integrations/         external API clients
scripts/                  build_highways.py, build_airports.py, build_broadband.py
tests/                    unit and endpoint tests (no network)
```

Adding a provider: drop a `BaseEnrichmentProvider` subclass in
`app/services/enrichment/providers/`. Its data is stored as-is under its name; show it by
adding rows to `build_view` in `app/services/property_view.py`.
