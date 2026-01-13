# Place Research CI/CD Setup

Complete CI/CD pipeline for deploying frontend and backend to test and production environments.

## Quick Links

- 📘 [Full CI/CD Documentation](./docs/CICD.md) - Complete reference guide
- 🚀 [Quick Start Guide](./docs/CICD_QUICKSTART.md) - Get started in minutes
- � [Tailscale Setup Guide](./docs/TAILSCALE_SETUP.md) - Secure private network configuration
- 📝 [Tailscale CI/CD Summary](./docs/TAILSCALE_CICD_SUMMARY.md) - Quick overview of Tailscale integration
- �🐳 [Docker Deployment](./docker/README.md) - Docker setup and usage

## Overview

This repository uses GitHub Actions to automatically:

- ✅ Run tests on every pull request
- 🐳 Build Docker images
- � Connect to private Tailscale network
- 🚀 Deploy to test environment (frontend/develop branches)
- 🎯 Deploy to production (main branch)

## Network Architecture

**Servers are on a private Tailscale network** - not publicly accessible:

- GitHub Actions connects via ephemeral Tailscale client
- Zero-trust security with OAuth authentication
- No public IP exposure or port forwarding required
- Automatic disconnect after deployment

## Environments

| Environment    | Branch                | URL                      | Auto-Deploy | Network   |
| -------------- | --------------------- | ------------------------ | ----------- | --------- |
| **Test**       | `frontend`, `develop` | https://test.yourapp.com | ✅ Yes      | Tailscale |
| **Production** | `main`                | https://yourapp.com      | ✅ Yes      | Tailscale |

## Project Structure

```
.github/
  workflows/
    ci-tests.yml           # Run tests on PR/push
    build-images.yml       # Build and push Docker images
    deploy-test.yml        # Deploy to test environment
    deploy-production.yml  # Deploy to production
docker/
  backend.Dockerfile       # Backend image
  frontend.Dockerfile      # Frontend image
  nginx.conf              # Nginx config for frontend
  docker-compose.yml      # Local development
  docker-compose.test.yml # Test environment
  docker-compose.prod.yml # Production environment
scripts/
  setup-server.sh         # Initial server setup
  deploy.sh               # Deployment automation
  backup.sh               # Database backups
  rollback.sh             # Rollback deployments
  health-check.sh         # Verify service health
docs/
  CICD.md                 # Complete CI/CD documentation
  CICD_QUICKSTART.md      # Quick start guide
```

## Prerequisites

- GitHub repository with Actions enabled
- Two Ubuntu 20.04+ servers on your **Tailscale network**
- Tailscale account with OAuth credentials
- Docker installed on servers
- Domain names (optional but recommended)
- API keys for external services

## Setup Steps

### 1. Configure GitHub Secrets

Add these secrets in Settings > Secrets and variables > Actions:

**Tailscale Network:**

- `TS_OAUTH_CLIENT_ID` - From https://login.tailscale.com/admin/settings/oauth
- `TS_OAUTH_SECRET` - OAuth secret (create with "Devices: Write" scope)

**Test Environment:**

- `TEST_SERVER_SSH_KEY`
- `TEST_SERVER_HOST` - Tailscale hostname (e.g., test-server)
- `TEST_SERVER_USER`
- `TEST_POSTGRES_USER`
- `TEST_POSTGRES_PASSWORD`
- `TEST_POSTGRES_DB`
- `TEST_JWT_SECRET_KEY`

**Production Environment:**

- `PROD_SERVER_SSH_KEY`
- `PROD_SERVER_HOST` - Tailscale hostname (e.g., prod-server)
- `PROD_SERVER_USER`
- `PROD_POSTGRES_USER`
- `PROD_POSTGRES_PASSWORD`
- `PROD_POSTGRES_DB`
- `PROD_JWT_SECRET_KEY`

**API Keys (shared):**

- `GOOGLE_MAPS_API_KEY`
- `NATIONAL_FLOOD_DATA_API_KEY`
- `WALKSCORE_API_KEY`
- etc.

### 2. Setup Tailscale on Servers

On each server:

```bash
# Install Tailscale
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Verify connection
tailscale status
```

### 3. Setup Servers

Run on each server:

```bash
# Test server
sudo bash scripts/setup-server.sh test

# Production server
sudo bash scripts/setup-server.sh production
```

### 3. Create Environment Files

On each server, create `.env.{environment}` file with required variables.

### 4. Deploy

Push to trigger automatic deployment:

```bash
# Deploy to test
git push origin frontend

# Deploy to production
git push origin main
```

## Workflows

### CI Tests

Runs on every PR and push to `main`/`frontend`:

- Backend: pytest, linting, type checking
- Frontend: vitest, eslint, type checking
- Coverage reports to Codecov

### Build Images

Builds and pushes Docker images to GitHub Container Registry:

- Tagged with branch name, SHA, and 'latest'
- Multi-stage builds for optimization

### Deploy to Test

Automatic deployment when pushing to `frontend` or `develop`:

1. SSH to test server
2. Pull latest images
3. Run deployment script
4. Health check verification

### Deploy to Production

Automatic deployment when pushing to `main`:

1. SSH to production server
2. Create backup
3. Pull latest images
4. Run deployment script
5. Health check verification
6. Rollback on failure

## Manual Operations

### View Logs

```bash
ssh user@server
/opt/place-research-{env}/logs.sh
```

### Check Status

```bash
/opt/place-research-{env}/status.sh
```

### Manual Backup

```bash
cd /opt/place-research-{env}
./scripts/backup.sh
```

### Manual Rollback

```bash
cd /opt/place-research-{env}
./scripts/rollback.sh {environment}
```

### Health Check

```bash
./scripts/health-check.sh
```

## Security Features

- ✅ Non-root container users
- ✅ Secret management via GitHub Secrets
- ✅ Automated backups (production)
- ✅ Automatic rollback on failure
- ✅ Firewall configuration
- ✅ Fail2ban protection
- ✅ Automatic security updates
- ✅ Health checks on all services

## Monitoring

### Logs

- Application: `/opt/place-research-{env}/logs/`
- Docker: `docker logs <container-name>`
- System: `/var/log/syslog`

### Health Checks

- Backend: `http://server:8000/health`
- Frontend: `http://server:3000`
- Database: `pg_isready` in container

### Backups

- Automated daily backups at 2 AM (production)
- 7-day retention
- Database, data, and logs backed up

## Troubleshooting

### Deployment Failed

1. Check GitHub Actions logs
2. SSH to server and run health check
3. View container logs
4. Check environment variables

### Database Issues

```bash
docker exec place-research-{env}-db pg_isready
docker logs place-research-{env}-db
```

### Network Issues

```bash
docker network ls
docker network inspect place-research-{env}_network
```

## Support

- 📖 [Full Documentation](./docs/CICD.md)
- 🐛 [Report Issues](https://github.com/lhwrd/place-research/issues)
- 💬 [Discussions](https://github.com/lhwrd/place-research/discussions)

## License

See LICENSE file for details.
