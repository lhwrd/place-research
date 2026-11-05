# Place Research backend

A stateless FastAPI service that adds Zillow listings to Baserow and enriches them. See
[../../docs/BASEROW.md](../../docs/BASEROW.md) for the data flow, the Baserow schema and
the iOS Shortcut API.

## Endpoints

| Endpoint                               | Caller       | Auth                                   |
| -------------------------------------- | ------------ | -------------------------------------- |
| `POST /api/v1/listings`                | iOS Shortcut | `Authorization: Bearer INGEST_API_TOKEN` |
| `POST /api/v1/listings/{row_id}/images` | iOS Shortcut | `Authorization: Bearer INGEST_API_TOKEN` |
| `POST /api/v1/webhooks/baserow`        | Baserow      | `X-Webhook-Secret: BASEROW_WEBHOOK_SECRET` |
| `GET /health`                          | Deploy checks | none                                  |

## Development

```bash
cp .env.example .env   # Baserow token/ids, API keys, data file paths
uv sync
./run.sh               # or ./dev.sh for debug logging
```

Create the Baserow fields, tables and webhook once with `uv run python scripts/baserow_setup.py`.

`RAILLINES_PATH` can point at GeoParquet (`.parquet`) or GeoJSON; the loader picks the
reader by extension. Production gets GeoParquet: the howard-home Ansible role downloads
the GeoJSON and converts it at deploy time.

## Layout

```
app/api/              listings + webhook endpoints, auth dependencies
app/integrations/     external API clients, including baserow_api.py and baserow_schema.py
app/services/         baserow_enrichment.py (ingest + enrichment), zillow_listing.py
                      (listing JSON parser), baserow_mapper.py, geocoding, in-memory cache
app/services/enrichment/  orchestrator + auto-discovered providers
scripts/              baserow_setup.py
```

Adding a provider: drop a `BaseEnrichmentProvider` subclass in
`app/services/enrichment/providers/`, then map its output to Baserow fields in
`app/services/baserow_mapper.py` and add the fields to `app/integrations/baserow_schema.py`.

## Tests

```bash
uv run pytest
uv run ruff check . && uv run black --check .
```
