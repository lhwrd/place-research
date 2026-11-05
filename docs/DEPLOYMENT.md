# Deployment

The backend runs as a single container per environment on one server, reached over
Tailscale by the iOS Shortcut and Baserow's webhook.

| Environment | Directory                  | Port | Branch    | Compose file                     |
| ----------- | -------------------------- | ---- | --------- | -------------------------------- |
| test        | `/opt/place-research-test` | 8000 | `develop` | `docker/docker-compose.test.yml` |
| production  | `/opt/place-research-prod` | 8001 | `main`    | `docker/docker-compose.prod.yml` |

There is no database. All data lives in Baserow, so deploys and rollbacks only swap
the container image.

## Workflows

- **CI - Tests** (`ci-tests.yml`) runs on PRs and on pushes to `main`/`develop`: ruff,
  black, mypy (advisory) and pytest with coverage.
- **Build and Push Docker Images** (`build-images.yml`) builds `docker/backend.Dockerfile`
  and pushes `ghcr.io/<repo>/backend` tagged with the branch, semver, sha and `latest`
  (for `main`).
- **Deploy to Test** / **Deploy to Production** connect to the tailnet (`tag:ci`),
  copy `docker/`, `scripts/` and `env/` to the server, then run `scripts/deploy.sh` and
  `scripts/health-check.sh`. If production fails its health check, `scripts/rollback.sh
  production` runs.

## Secrets (1Password)

The workflows read the Tailscale OAuth client and server SSH details from the
*Place Research - Test* and *Place Research - Prod* vaults (`tailscale`, `server`). The
`env/*.env` files reference these app secrets in the matching vault:

| Item                  | Field         | Variable                      |
| --------------------- | ------------- | ----------------------------- |
| `baserow`             | `api-token`   | `BASEROW_API_TOKEN`           |
| `baserow`             | `webhook-secret` | `BASEROW_WEBHOOK_SECRET`   |
| `ingest`              | `token`       | `INGEST_API_TOKEN`            |
| `google-maps`         | `credential`  | `GOOGLE_MAPS_API_KEY`         |
| `national-flood-data` | `credential`  | `NATIONAL_FLOOD_DATA_API_KEY` |
| `walkscore`           | `credential`  | `WALKSCORE_API_KEY`           |
| `airnow`              | `credential`  | `AIRNOW_API_KEY`              |

`docker/.env` on the server holds the resolved values, which compose and the scripts
load. For example:

```bash
op inject -i env/prod.env -o docker/.env
```

Set the `BASEROW_*_TABLE_ID` values in `env/*.env` from the output of
`apps/backend/scripts/baserow_setup.py`. Give test its own Baserow database: if both
environments use the same tables, they both enrich the same rows.

## Server setup

```bash
sudo bash scripts/setup-server.sh prod   # or: test
```

This installs Docker, creates the app user and directories, and allows the backend
port on `tailscale0` only. It also sets up fail2ban, unattended upgrades, log rotation
and a systemd unit. Tailscale must already be installed and logged in on the server.
See [TAILSCALE_SETUP.md](TAILSCALE_SETUP.md) for the CI side.

## Deploy, rollback, health

```bash
bash scripts/deploy.sh production latest   # tags the running image as backend:rollback, pulls, restarts
bash scripts/rollback.sh production        # restarts on backend:rollback
bash scripts/health-check.sh production    # container up + GET /health
```
