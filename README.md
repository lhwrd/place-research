# Place Research

Research homes while browsing Zillow. Share a listing from your iPhone, and a row
with the listing's photos and facts appears in Baserow. The backend then enriches it with
walk/bike/transit scores, flood zone, rail and highway distance, road noise, climate,
air quality, nearby places and drive times to the people and places you care about.

- **Baserow** is the UI and the only data store (managed outside this repo).
- **The backend** (`apps/backend`, FastAPI) is stateless. It has an ingest API for
  the iOS Shortcut and a webhook that Baserow calls to trigger enrichment.

```
iPhone Shortcut ──▶ backend /api/v1/listings ──▶ Baserow ──webhook──▶ backend enrichment ──▶ Baserow
```

## Layout

```
apps/backend/   FastAPI app, enrichment providers, tests, scripts/baserow_setup.py
docker/         backend Dockerfile and compose files (local, test, prod)
env/            1Password-referenced env files for test and prod
scripts/        server setup, deploy, rollback, health check
docs/           BASEROW.md (schema + Shortcut API), DEPLOYMENT.md, logging, errors
```

## Quick start

```bash
cd apps/backend
cp .env.example .env    # fill in Baserow and API keys
uv sync
./run.sh                # http://localhost:8000/docs
```

Then follow [docs/BASEROW.md](docs/BASEROW.md) to create the Baserow tables and webhook,
and to wire up the Shortcut.

## Tests

```bash
cd apps/backend
uv run pytest
```

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md).
