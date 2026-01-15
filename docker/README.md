# Docker Deployment Guide

This directory contains Docker configurations for deploying the Property Research application.

## Files

- `backend.Dockerfile` - Multi-stage build for FastAPI backend
- `frontend.Dockerfile` - Multi-stage build for React frontend with Nginx
- `docker-compose.yml` - Orchestrates all services (PostgreSQL, Backend, Frontend)
- `nginx.conf` - Nginx configuration for serving the frontend
- `.env.example` - Example environment variables

## Quick Start

### 1. Setup Environment Variables

```bash
cd docker
cp .env.example .env
# Edit .env and set your configuration
```

**Important:** Generate a secure JWT secret key:

```bash
openssl rand -hex 32
```

### 2. Build and Run

```bash
# Build and start all services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Stop and remove volumes (WARNING: deletes database data)
docker-compose down -v
```

### 3. Access the Application

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Database**: localhost:5432

## Service Architecture

```
┌─────────────┐
│   Frontend  │  (React + Vite + Nginx)
│   :3000     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Backend   │  (FastAPI + Uvicorn)
│   :8000     │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  PostgreSQL │
│   :5432     │
└─────────────┘
```

## Development vs Production

### Development

The docker-compose.yml is configured for development by default:

- Database exposed on host port 5432
- Hot reload enabled
- Debug logging
- Volume mounts for code changes

### Production Deployment

For production, consider these modifications:

1. **Environment Variables**:

   - Set strong passwords
   - `REQUIRE_AUTHENTICATION=true`
   - `LOG_LEVEL=WARNING` or `ERROR`
   - Set all required API keys

2. **Security**:

   - Use secrets management (Docker secrets, Kubernetes secrets)
   - Don't expose PostgreSQL port externally
   - Enable HTTPS with a reverse proxy
   - Use specific image tags (not `latest`)

3. **Scaling**:

   - Use an external managed database (AWS RDS, Google Cloud SQL)
   - Add Redis for caching
   - Use a load balancer for multiple backend instances
   - Implement proper backup strategies

4. **Monitoring**:
   - Add health check endpoints
   - Implement logging aggregation
   - Set up metrics collection (Prometheus)
   - Configure alerts

## Commands

### Build only (without starting)

```bash
docker-compose build
```

### Rebuild specific service

```bash
docker-compose build backend
docker-compose build frontend
```

### Run database migrations

```bash
docker-compose exec backend alembic upgrade head
```

### Access container shell

```bash
# Backend
docker-compose exec backend bash

# Database
docker-compose exec postgres psql -U place_research
```

### View service status

```bash
docker-compose ps
```

### Check logs for specific service

```bash
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f postgres
```

## Volume Management

### Backup Database

```bash
docker-compose exec postgres pg_dump -U place_research place_research > backup.sql
```

### Restore Database

```bash
cat backup.sql | docker-compose exec -T postgres psql -U place_research place_research
```

### Clear all data and restart

```bash
docker-compose down -v
docker-compose up -d
```

## Troubleshooting

### Backend won't start

- Check database is healthy: `docker-compose ps`
- Check environment variables in `.env`
- View logs: `docker-compose logs backend`

### Frontend can't reach backend

- Ensure `VITE_API_BASE_URL` is set correctly
- Check if backend is healthy: http://localhost:8000/health
- Verify network connectivity: `docker-compose exec frontend ping backend`

### Database connection issues

- Verify credentials in `.env`
- Check if PostgreSQL is running: `docker-compose ps postgres`
- Check PostgreSQL logs: `docker-compose logs postgres`

### Port conflicts

- Change ports in `.env` file
- Check what's using the port: `lsof -i :8000`

## Performance Tuning

### PostgreSQL

Edit `docker-compose.yml` to add PostgreSQL configuration:

```yaml
command:
  - "postgres"
  - "-c"
  - "max_connections=100"
  - "-c"
  - "shared_buffers=256MB"
```

### Backend Workers

For production, use multiple Uvicorn workers:

```yaml
command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

## Resource Limits

Add resource limits to prevent services from consuming too much:

```yaml
services:
  backend:
    deploy:
      resources:
        limits:
          cpus: "2"
          memory: 2G
        reservations:
          cpus: "1"
          memory: 1G
```

## Additional Notes

- Images use multi-stage builds to minimize size
- Services run as non-root users for security
- Health checks ensure services are ready before marking as healthy
- All services restart automatically unless stopped
- PostgreSQL data persists in a named volume
