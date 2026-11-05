#!/bin/bash
set -e

# =============================================================================
# Rollback Script
# =============================================================================
# Restarts the backend on the image that was running before the last deploy.
# deploy.sh tags that image as backend:rollback. The backend is stateless
# (Baserow holds the data), so there is nothing else to restore.
# Usage: ./rollback.sh <environment>
# =============================================================================

ENVIRONMENT=${1:-production}

echo "=========================================="
echo "Rolling back: $ENVIRONMENT"
echo "=========================================="

# Set environment-specific variables
if [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILE="/opt/place-research-prod/docker/docker-compose.prod.yml"
    ENV_FILE="/opt/place-research-prod/docker/.env"
    PROJECT_NAME="place-research-prod"
elif [ "$ENVIRONMENT" = "test" ]; then
    COMPOSE_FILE="/opt/place-research-test/docker/docker-compose.test.yml"
    ENV_FILE="/opt/place-research-test/docker/.env"
    PROJECT_NAME="place-research-test"
else
    echo "Error: Invalid environment. Use 'test' or 'production'"
    exit 1
fi

export GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-"lhwrd/place-research"}

if ! docker image inspect "ghcr.io/${GITHUB_REPOSITORY}/backend:rollback" > /dev/null 2>&1; then
    echo "Error: No backend:rollback image found (deploy.sh tags one before each deploy)"
    exit 1
fi

# Load environment variables
set -a
source "$ENV_FILE"
set +a

echo "Step 1: Restarting on the rollback image..."
IMAGE_TAG=rollback docker compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d --force-recreate --pull never

echo "Step 2: Waiting for services to be healthy..."
sleep 15

echo "=========================================="
echo "Rollback completed!"
echo "=========================================="
docker compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
