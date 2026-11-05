# Docker

- `backend.Dockerfile`: multi-stage build of the FastAPI backend (`apps/backend`).
- `docker-compose.yml`: local build, port `${BACKEND_PORT:-8000}`.
- `docker-compose.test.yml` / `docker-compose.prod.yml`: pull `ghcr.io/<repo>/backend`,
  ports 8000 / 8001. Used by `scripts/deploy.sh`. See [../docs/DEPLOYMENT.md](../docs/DEPLOYMENT.md).
- `.env.example`: variables the compose files read.

## Local

```bash
cd docker
cp .env.example .env    # Baserow token/ids, ingest token, API keys
docker compose up -d --build
docker compose logs -f backend
```

The API is at http://localhost:8000 and the docs at http://localhost:8000/docs.

The container is stateless. `./data` holds the providers' data files (rail lines, climate
normals); point `RAILLINES_PATH` / `ANNUAL_CLIMATE_PATH` at `/app/data/...`. `./logs` holds
application logs.
