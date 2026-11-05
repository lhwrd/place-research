# Place Research

Research homes while browsing Zillow. Share a listing from your iPhone, and a row
with the listing's photos and facts appears in Baserow. This service then enriches it
with walk/bike/transit scores, flood zone, rail and highway distance, road noise,
climate, air quality, nearby places and drive times to the people and places you care
about.

```
iPhone Shortcut ──▶ /api/v1/listings ──▶ Baserow ──webhook──▶ enrichment ──▶ Baserow
```

Baserow is the UI and the only data store. This repo is a stateless FastAPI service
that CI publishes as `ghcr.io/<repo>/backend`. Baserow, the VM, environment config and
deployment live in howard-home.

See [docs/BASEROW.md](docs/BASEROW.md) for the data flow, the Baserow schema and the
iOS Shortcut API.

## Endpoints

| Endpoint                                | Caller        | Auth                                       |
| --------------------------------------- | ------------- | ------------------------------------------ |
| `POST /api/v1/listings`                 | iOS Shortcut  | `Authorization: Bearer INGEST_API_TOKEN`   |
| `POST /api/v1/listings/{row_id}/images` | iOS Shortcut  | `Authorization: Bearer INGEST_API_TOKEN`   |
| `POST /api/v1/webhooks/baserow`         | Baserow       | `X-Webhook-Secret: BASEROW_WEBHOOK_SECRET` |
| `GET /health`                           | Health checks | none                                       |

## Development

```bash
cp .env.example .env   # Baserow token/ids, API keys, data file paths
uv sync
make dev               # http://localhost:8000/docs
make test
make lint              # make format to fix
```

Or in Docker: `docker compose up --build`. Put provider data files in `./data`.

Create the Baserow fields, tables and webhook once with
`uv run python scripts/baserow_setup.py`.

## Layout

```
app/api/                  listings + webhook endpoints, auth dependencies
app/integrations/         external API clients, including baserow_api.py and baserow_schema.py
app/services/             baserow_enrichment.py (ingest + enrichment), zillow_listing.py
                          (listing JSON parser), baserow_mapper.py, geocoding, in-memory cache
app/services/enrichment/  orchestrator + auto-discovered providers
scripts/                  baserow_setup.py
tests/                    unit and endpoint tests (no network)
```

Adding a provider: drop a `BaseEnrichmentProvider` subclass in
`app/services/enrichment/providers/`, map its output to Baserow fields in
`app/services/baserow_mapper.py`, and add the fields to `app/integrations/baserow_schema.py`.
