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

## GitHub Secrets Configuration

### Repository Secrets Required

#### Tailscale Network Access

- `TS_OAUTH_CLIENT_ID` - Tailscale OAuth client ID
- `TS_OAUTH_SECRET` - Tailscale OAuth secret

> Create OAuth credentials at https://login.tailscale.com/admin/settings/oauth with "Devices: Write" scope and `tag:ci` tag.

#### Test Environment

- `TEST_SERVER_SSH_KEY` - SSH private key for test server
- `TEST_SERVER_HOST` - Test server Tailscale hostname (e.g., test-server or test-server.tail1234.ts.net)
- `TEST_SERVER_USER` - SSH username for test server
- `TEST_POSTGRES_USER` - PostgreSQL username
- `TEST_POSTGRES_PASSWORD` - PostgreSQL password
- `TEST_POSTGRES_DB` - PostgreSQL database name
- `TEST_JWT_SECRET_KEY` - JWT secret key

#### Production Environment

- `PROD_SERVER_SSH_KEY` - SSH private key for production server
- `PROD_SERVER_HOST` - Production server Tailscale hostname (e.g., prod-server or prod-server.tail1234.ts.net)
- `PROD_SERVER_USER` - SSH username for production server
- `PROD_POSTGRES_USER` - PostgreSQL username
- `PROD_POSTGRES_PASSWORD` - PostgreSQL password
- `PROD_POSTGRES_DB` - PostgreSQL database name
- `PROD_JWT_SECRET_KEY` - JWT secret key

#### Shared Secrets (Both Environments)

- `GOOGLE_MAPS_API_KEY`
- `GOOGLE_MAPS_MAP_ID`
- `NATIONAL_FLOOD_DATA_API_KEY`
- `NATIONAL_FLOOD_DATA_CLIENT_ID`
- `WALKSCORE_API_KEY`
- `AIRNOW_API_KEY`
- `FBI_API_KEY`

#### Optional

- `SLACK_WEBHOOK` - For deployment notifications
- `GITHUB_TOKEN` - Automatically provided by GitHub Actions

### Adding Secrets

1. Go to repository Settings > Secrets and variables > Actions
2. Click "New repository secret"
3. Add each secret with exact name and value

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
2. **Secrets**: Never commit secrets to repository
3. **Firewall**: Only open required ports
4. **Updates**: Keep system and packages updated
5. **Backups**: Encrypt backups for production
6. **SSL/TLS**: Use HTTPS in production (configure reverse proxy)
7. **Rate Limiting**: Implement API rate limiting
8. **Monitoring**: Set up intrusion detection
9. **Access Control**: Limit SSH access to specific IPs
10. **Database**: Use strong passwords, separate credentials per environment

## Adding New Environments

To add a new environment (e.g., staging):

1. Create `docker-compose.staging.yml`
2. Create `.github/workflows/deploy-staging.yml`
3. Add staging secrets to GitHub
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

- **2026-01-12**: Initial CI/CD pipeline setup
  - GitHub Actions workflows
  - Test and production environments
  - Automated backups and rollback
  - Server setup scripts
