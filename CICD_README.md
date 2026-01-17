# Place Research CI/CD Setup

Complete CI/CD pipeline for deploying frontend and backend to test and production environments.

## Quick Links

- 📘 [Full CI/CD Documentation](./docs/CICD.md) - Complete reference guide
- 🚀 [Quick Start Guide](./docs/CICD_QUICKSTART.md) - Get started in minutes
- 🔒 [1Password Migration Guide](./docs/1PASSWORD_MIGRATION.md) - Migrate from GitHub Secrets to 1Password
- 🌐 [Tailscale Setup Guide](./docs/TAILSCALE_SETUP.md) - Secure private network configuration
- 📝 [Tailscale CI/CD Summary](./docs/TAILSCALE_CICD_SUMMARY.md) - Quick overview of Tailscale integration
- 🐳 [Docker Deployment](./docker/README.md) - Docker setup and usage

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

### 1. Configure 1Password for Secret Management

This project uses [1Password Service Accounts](https://developer.1password.com/docs/service-accounts/) to securely manage secrets in CI/CD pipelines.

#### 1Password Setup

The repository includes environment file templates (`env/test.env` and `env/prod.env`) with 1Password secret references. During deployment, the CI/CD workflow uses `op inject` to replace these references with actual values.

1. **Create a 1Password vault** named `ci-cd` (or use an existing vault)

2. **Create items in your vault** with the following structure:

**Tailscale Network:**
- Item name: `tailscale`
  - Field: `oauth-client-id` - From https://login.tailscale.com/admin/settings/oauth
  - Field: `oauth-secret` - OAuth secret (create with "Devices: Write" scope)

**Test Environment:**
- Item name: `test-server`
  - Field: `ssh-private-key` - SSH private key for test server
  - Field: `hostname` - Tailscale hostname (e.g., test-server)
  - Field: `username` - SSH username

- Item name: `test-database`
  - Field: `username` - PostgreSQL username
  - Field: `password` - PostgreSQL password
  - Field: `database-name` - Database name

- Item name: `test-secrets`
  - Field: `jwt-secret-key` - JWT secret for authentication

**Production Environment:**
- Item name: `prod-server`
  - Field: `ssh-private-key` - SSH private key for production server
  - Field: `hostname` - Tailscale hostname (e.g., prod-server)
  - Field: `username` - SSH username

- Item name: `prod-database`
  - Field: `username` - PostgreSQL username
  - Field: `password` - PostgreSQL password
  - Field: `database-name` - Database name
  - Field: `port` - PostgreSQL port

- Item name: `prod-secrets`
  - Field: `jwt-secret-key` - JWT secret for authentication

**API Keys (shared):**
- Item name: `api-keys`
  - Field: `google-maps-api-key`
  - Field: `google-maps-map-id`
  - Field: `national-flood-data-api-key`
  - Field: `national-flood-data-client-id`
  - Field: `walkscore-api-key`
  - Field: `airnow-api-key`

- Item name: `email`
  - Field: `smtp-server`
  - Field: `username`
  - Field: `password`
  - Field: `from-address`

3. **Create a Service Account**
   - Go to your 1Password account settings
   - Navigate to Service Accounts
   - Create a new service account with read access to the `ci-cd` vault
   - Save the service account token securely

4. **Add Service Account Token to GitHub**
   - Go to your GitHub repository settings
   - Navigate to Secrets and variables > Actions
   - Create a new repository secret named `OP_SERVICE_ACCOUNT_TOKEN`
   - Paste your 1Password service account token as the value

That's it! Your workflows will now securely fetch all secrets from 1Password during deployment.

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
- ✅ Secret management via 1Password Service Accounts
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
