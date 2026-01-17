# CI/CD Pipeline Documentation

## Overview

This document describes the CI/CD pipeline for the Place Research monorepo, which includes automated testing, building, and deployment to separate test and production environments on Ubuntu servers.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub Repository                        │
│                     (lhwrd/place-research)                       │
└────────────────┬──────────────────────┬─────────────────────────┘
                 │                      │
        ┌────────▼────────┐    ┌───────▼────────┐
        │  frontend branch │    │   main branch  │
        │  (Test Env)      │    │  (Production)  │
        └────────┬─────────┘    └───────┬────────┘
                 │                      │
        ┌────────▼────────┐    ┌───────▼────────┐
        │   CI Tests      │    │   CI Tests     │
        │   Build Images  │    │   Build Images │
        └────────┬─────────┘    └───────┬────────┘
                 │                      │
        ┌────────▼────────┐    ┌───────▼────────┐
        │ Deploy to Test  │    │ Deploy to Prod │
        │ Ubuntu Server   │    │ Ubuntu Server  │
        └─────────────────┘    └────────────────┘
```

## Environments

### Test Environment

- **Branch**: `frontend`, `develop`
- **URL**: https://test.yourapp.com
- **API**: https://test-api.yourapp.com
- **Purpose**: Testing and QA
- **Auto-deploy**: Yes, on push to trigger branches
- **Authentication**: Enabled
- **Logging**: DEBUG level

### Production Environment

- **Branch**: `main`
- **URL**: https://yourapp.com
- **API**: https://api.yourapp.com
- **Purpose**: Live production
- **Auto-deploy**: Yes, on push to main or tags
- **Authentication**: Required
- **Logging**: WARNING level
- **Features**:
  - Automatic backups before deployment
  - Rollback on failure
  - Resource limits enforced

## Workflows

### 1. CI Tests (`ci-tests.yml`)

**Trigger**: Pull requests and pushes to `main` and `frontend` branches

**Jobs**:

- **Backend Tests**

  - Runs on Ubuntu with PostgreSQL service
  - Linting (ruff, black)
  - Type checking (mypy)
  - Unit tests with coverage
  - Uploads coverage to Codecov

- **Frontend Tests**
  - Runs on Ubuntu with Node.js 20
  - Linting (eslint)
  - Type checking (tsc)
  - Unit tests with coverage
  - Uploads coverage to Codecov

### 2. Build Images (`build-images.yml`)

**Trigger**: Pushes to `main`, `frontend` branches, or version tags

**Jobs**:

- **Build Backend Image**
  - Multi-stage Docker build
  - Pushes to GitHub Container Registry
  - Tags: branch name, SHA, latest (for main)
- **Build Frontend Image**
  - Multi-stage Docker build with Nginx
  - Pushes to GitHub Container Registry
  - Tags: branch name, SHA, latest (for main)

**Image Registry**: `ghcr.io/lhwrd/place-research`

### 3. Deploy to Test (`deploy-test.yml`)

**Trigger**: Pushes to `frontend` or `develop` branches, manual dispatch

**Steps**:

1. Connect to Tailscale network (ephemeral)
2. Setup SSH connection to test server
3. Create environment file with test secrets
4. Copy deployment files to server
5. Pull latest Docker images
6. Run deployment script
7. Health check verification
8. Slack notification (optional)

**Tailscale Integration**:

- Uses OAuth client for authentication
- Tagged with `tag:ci` for ACL management
- Connection automatically terminates after workflow

### 4. Deploy to Production (`deploy-production.yml`)

**Trigger**: Pushes to `main` branch, version tags, manual dispatch

**Steps**:

1. Connect to Tailscale network (ephemeral)
2. Setup SSH connection to production server
3. Create environment file with production secrets
4. Copy deployment files to server
5. **Create backup** of database and data
6. Pull latest Docker images
7. Run deployment script
8. Health check verification
9. **Rollback on failure**
10. Slack notification (optional)

## Server Setup

### Prerequisites

- Ubuntu 20.04+ server on Tailscale network
- Root or sudo access
- Tailscale installed and authenticated
- Domain name (optional, recommended)

### Initial Setup

1. **Ensure servers are on Tailscale network**:

```bash
# Install Tailscale on each server
curl -fsSL https://tailscale.com/install.sh | sh

# Authenticate
sudo tailscale up

# Verify connection
tailscale status
```

2. **Run the setup script on each server**:

```bash
# On test server
sudo bash setup-server.sh test

# On production server
sudo bash setup-server.sh production
```

This script will:

- Install Docker and Docker Compose
- Create application user and directories
- Configure firewall (UFW)
- Setup fail2ban
- Enable automatic security updates
- Create systemd service for auto-start
- Setup log rotation
- Schedule automated backups (production only)

2. **Setup SSH keys for deployment**:

```bash
# On your local machine, generate a deploy key
ssh-keygen -t ed25519 -C "deploy-key-test" -f ~/.ssh/place-research-test

# Copy public key to server
ssh-copy-id -i ~/.ssh/place-research-test.pub user@test-server

# Add private key to GitHub secrets
# Settings > Secrets > Actions > New repository secret
# Name: TEST_SERVER_SSH_KEY
# Value: <contents of ~/.ssh/place-research-test>
```

3. **Configure environment variables on server**:

```bash
# SSH into server
ssh user@server

# Create .env file
sudo -u placeapp-test nano /opt/place-research-test/.env.test

# Add all required variables (see .env.example)
```

## Secret Management with 1Password

This project uses [1Password Service Accounts](https://developer.1password.com/docs/service-accounts/) to securely manage secrets in CI/CD pipelines.

### Why 1Password?

- **Centralized secret management**: All secrets in one secure vault
- **Easy rotation**: Update secrets in 1Password, not GitHub
- **Audit trail**: Track when secrets are accessed
- **Better organization**: Structure secrets logically with items and fields
- **Service account isolation**: CI/CD uses dedicated service accounts with limited permissions

### 1Password Setup

#### 1. Create Vault Structure

Create a vault named `ci-cd` with the following items:

**Tailscale Network Access:**
- Item: `tailscale`
  - Field: `oauth-client-id` - Tailscale OAuth client ID
  - Field: `oauth-secret` - Tailscale OAuth secret

> Create OAuth credentials at https://login.tailscale.com/admin/settings/oauth with "Devices: Write" scope and `tag:ci` tag.

**Test Environment:**
- Item: `test-server`
  - Field: `ssh-private-key` - SSH private key for test server
  - Field: `hostname` - Test server Tailscale hostname (e.g., test-server)
  - Field: `username` - SSH username for test server

- Item: `test-database`
  - Field: `username` - PostgreSQL username
  - Field: `password` - PostgreSQL password
  - Field: `database-name` - PostgreSQL database name

- Item: `test-secrets`
  - Field: `jwt-secret-key` - JWT secret key

**Production Environment:**
- Item: `prod-server`
  - Field: `ssh-private-key` - SSH private key for production server
  - Field: `hostname` - Production server Tailscale hostname (e.g., prod-server)
  - Field: `username` - SSH username for production server

- Item: `prod-database`
  - Field: `username` - PostgreSQL username
  - Field: `password` - PostgreSQL password
  - Field: `database-name` - PostgreSQL database name
  - Field: `port` - PostgreSQL port

- Item: `prod-secrets`
  - Field: `jwt-secret-key` - JWT secret key

**Shared API Keys:**
- Item: `api-keys`
  - Field: `google-maps-api-key`
  - Field: `google-maps-map-id`
  - Field: `national-flood-data-api-key`
  - Field: `national-flood-data-client-id`
  - Field: `walkscore-api-key`
  - Field: `airnow-api-key`

**Email Configuration:**
- Item: `email`
  - Field: `smtp-server`
  - Field: `username`
  - Field: `password`
  - Field: `from-address`

#### 2. Create Service Account

1. Go to your 1Password account settings
2. Navigate to **Service Accounts**
3. Create a new service account with:
   - **Name**: `github-actions-place-research`
   - **Vaults**: Read access to `ci-cd` vault
4. Save the service account token securely (you'll only see it once)

#### 3. Add Service Account Token to GitHub

1. Go to your GitHub repository settings
2. Navigate to **Secrets and variables > Actions**
3. Create a new repository secret:
   - **Name**: `OP_SERVICE_ACCOUNT_TOKEN`
   - **Value**: Your 1Password service account token

That's it! Your workflows will now fetch secrets from 1Password automatically.

### Secret References in Workflows

Secrets are referenced using the `op://` URL format:

```
op://vault-name/item-name/field-name
```

Example:
```yaml
- name: Load secrets from 1Password
  uses: 1password/load-secrets-action@v2
  with:
    export-env: true
  env:
    OP_SERVICE_ACCOUNT_TOKEN: ${{ secrets.OP_SERVICE_ACCOUNT_TOKEN }}
    POSTGRES_PASSWORD: op://ci-cd/test-database/password
    JWT_SECRET_KEY: op://ci-cd/test-secrets/jwt-secret-key
```

### Tailscale ACL Configuration

Add to your Tailscale ACL to allow CI access:

```json
{
  "tagOwners": {
    "tag:ci": ["autogroup:admin"]
  },
  "acls": [
    {
      "action": "accept",
      "src": ["tag:ci"],
      "dst": ["tag:server:22"]
    }
  ]
}
```

Tag your servers with `tag:server` for CI access.

## Deployment Scripts

### deploy.sh

Main deployment script that:

- Pulls latest Docker images
- Creates backups (production)
- Runs database migrations
- Stops old containers
- Starts new containers
- Verifies health

**Usage**:

```bash
./scripts/deploy.sh <environment> <image-tag>
./scripts/deploy.sh test frontend-abc123
./scripts/deploy.sh production main-def456
```

### backup.sh

Creates timestamped backups of:

- PostgreSQL database (compressed SQL dump)
- Application data directory
- Application logs
- Keeps last 7 days of backups

**Usage**:

```bash
./scripts/backup.sh
```

### rollback.sh

Rolls back to previous deployment by:

- Stopping current containers
- Restoring database from latest backup
- Restoring application data
- Restarting services

**Usage**:

```bash
./scripts/rollback.sh production
```

### health-check.sh

Verifies all services are healthy:

- Container status
- Backend health endpoint
- Frontend accessibility
- Database connectivity
- API endpoints

**Usage**:

```bash
./scripts/health-check.sh production
```

### setup-server.sh

Initial server setup (run once per server):

- Installs dependencies
- Creates users and directories
- Configures security
- Sets up automation

**Usage**:

```bash
sudo bash setup-server.sh production
```

## Deployment Flow

### Test Environment

```
1. Developer pushes to 'frontend' branch
2. CI tests run automatically
3. Docker images build and push to registry
4. Deploy workflow triggers
5. SSH connection to test server
6. Environment file created
7. Latest images pulled
8. Deployment script runs
9. Health checks verify deployment
10. Notification sent (optional)
```

### Production Environment

```
1. Developer merges to 'main' branch or creates tag
2. CI tests run automatically
3. Docker images build and push to registry
4. Deploy workflow triggers (requires approval)
5. SSH connection to production server
6. Environment file created
7. Database backup created
8. Latest images pulled
9. Deployment script runs
10. Health checks verify deployment
11. On failure: automatic rollback
12. Notification sent (optional)
```

## Manual Operations

### Manual Deployment

Trigger deployment without code push:

1. Go to Actions tab
2. Select "Deploy to Test" or "Deploy to Production"
3. Click "Run workflow"
4. Select branch and confirm

### View Deployment Logs

```bash
# SSH into server
ssh user@server

# View all logs
/opt/place-research-prod/logs.sh

# View specific service
/opt/place-research-prod/logs.sh backend
/opt/place-research-prod/logs.sh frontend
/opt/place-research-prod/logs.sh postgres
```

### Check Service Status

```bash
# Using helper script
/opt/place-research-prod/status.sh

# Or directly
docker-compose -f docker/docker-compose.prod.yml ps
```

### Manual Backup

```bash
cd /opt/place-research-prod
./scripts/backup.sh
```

### Manual Rollback

```bash
cd /opt/place-research-prod
./scripts/rollback.sh production
```

### Restart Services

```bash
# Using systemd
sudo systemctl restart place-research-production

# Or using Docker Compose
cd /opt/place-research-prod
docker-compose -f docker/docker-compose.prod.yml restart
```

## Monitoring and Maintenance

### Log Locations

- **Application logs**: `/opt/place-research-{env}/logs/`
- **Backup logs**: `/opt/place-research-{env}/logs/backup.log`
- **Docker logs**: Via `docker logs <container-name>`
- **System logs**: `/var/log/syslog`

### Monitoring Checklist

- [ ] Check service health regularly
- [ ] Monitor disk space for backups
- [ ] Review application logs for errors
- [ ] Verify backups are being created
- [ ] Check database performance
- [ ] Monitor resource usage (CPU, memory)

### Maintenance Tasks

**Daily**:

- Automated backups (2 AM)
- Log rotation

**Weekly**:

- Review application errors
- Check backup integrity
- Monitor resource usage

**Monthly**:

- Security updates (automatic)
- Review and cleanup old backups
- Performance optimization review

## Troubleshooting

### Deployment Fails

1. **Check workflow logs** in GitHub Actions
2. **SSH into server** and check container status
3. **View application logs**:
   ```bash
   docker-compose -f docker/docker-compose.{env}.yml logs
   ```
4. **Check health status**:
   ```bash
   ./scripts/health-check.sh {environment}
   ```

### Database Connection Issues

1. **Verify database is running**:
   ```bash
   docker ps | grep postgres
   ```
2. **Check database logs**:
   ```bash
   docker logs place-research-{env}-db
   ```
3. **Test connection**:
   ```bash
   docker exec place-research-{env}-db pg_isready
   ```

### Image Pull Failures

1. **Verify GitHub token permissions**
2. **Check image exists** in container registry
3. **Login to registry** manually:
   ```bash
   echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_ACTOR --password-stdin
   ```

### Health Check Failures

1. **Run detailed health check**:
   ```bash
   ./scripts/health-check.sh {environment}
   ```
2. **Check individual services**:
   ```bash
   curl http://localhost:8000/health
   curl http://localhost:3000
   ```
3. **Inspect container health**:
   ```bash
   docker inspect <container-name> | grep Health
   ```

## Security Best Practices

1. **SSH Keys**: Use SSH key authentication, disable password auth
2. **Secrets**: Use 1Password for centralized secret management, never commit secrets to repository
3. **Firewall**: Only open required ports
4. **Updates**: Keep system and packages updated
5. **Backups**: Encrypt backups for production
6. **SSL/TLS**: Use HTTPS in production (configure reverse proxy)
7. **Rate Limiting**: Implement API rate limiting
8. **Monitoring**: Set up intrusion detection
9. **Access Control**: Limit SSH access to specific IPs
10. **Database**: Use strong passwords, separate credentials per environment
11. **Service Accounts**: Use dedicated 1Password service accounts with minimal required permissions

## Adding New Environments

To add a new environment (e.g., staging):

1. Create `docker-compose.staging.yml`
2. Create `.github/workflows/deploy-staging.yml`
3. Add staging secrets to 1Password vault (create new items or fields as needed)
4. Run `setup-server.sh staging` on staging server
5. Update DNS/domains
6. Configure reverse proxy

## Reverse Proxy Setup (Recommended)

For production, use Nginx or Traefik as a reverse proxy:

**Benefits**:

- SSL/TLS termination
- Load balancing
- Rate limiting
- Centralized logging
- Domain routing

**Example Nginx config** (separate from app):

```nginx
server {
    listen 443 ssl http2;
    server_name yourapp.com;

    ssl_certificate /etc/letsencrypt/live/yourapp.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourapp.com/privkey.pem;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    location /api {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## Performance Optimization

### Database

- Regular VACUUM and ANALYZE
- Add appropriate indexes
- Connection pooling
- Read replicas for scaling

### Backend

- Multiple Uvicorn workers
- Redis for caching
- Background task queue (Celery)
- CDN for static assets

### Frontend

- Asset optimization
- Lazy loading
- Service worker caching
- CDN delivery

## Scaling Considerations

When traffic grows:

1. **Horizontal Scaling**: Add more servers with load balancer
2. **Database**: Migrate to managed PostgreSQL (RDS, Cloud SQL)
3. **Caching**: Add Redis layer
4. **CDN**: Use CloudFlare or AWS CloudFront
5. **Monitoring**: Add Prometheus + Grafana
6. **Container Orchestration**: Consider Kubernetes

## Support and Resources

- **GitHub Repository**: https://github.com/lhwrd/place-research
- **Documentation**: `/docs` directory
- **Issues**: GitHub Issues
- **Docker Docs**: https://docs.docker.com
- **GitHub Actions**: https://docs.github.com/actions

## Changelog

Track significant changes to CI/CD infrastructure:

- **2026-01-16**: Migrated to 1Password for secret management
  - Replaced GitHub Secrets with 1Password Service Accounts
  - Updated deployment workflows to use 1Password CLI
  - Enhanced security with centralized secret management
- **2026-01-12**: Initial CI/CD pipeline setup
  - GitHub Actions workflows
  - Test and production environments
  - Automated backups and rollback
  - Server setup scripts
