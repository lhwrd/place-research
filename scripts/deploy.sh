#!/bin/bash
set -e

# =============================================================================
# Deployment Script
# =============================================================================
# Usage: ./deploy.sh <environment> <image-tag>
# Example: ./deploy.sh production v1.0.0
# =============================================================================

ENVIRONMENT=${1:-test}
IMAGE_TAG=${2:-latest}

echo "=========================================="
echo "Deploying to: $ENVIRONMENT"
echo "Image tag: $IMAGE_TAG"
echo "=========================================="

# Set environment-specific variables
if [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILE="/opt/place-research-prod/docker/docker-compose.prod.yml"
    ENV_FILE="/opt/place-research-prod/.env.prod"
    PROJECT_NAME="place-research-prod"
elif [ "$ENVIRONMENT" = "test" ]; then
    COMPOSE_FILE="/opt/place-research-test/docker/docker-compose.test.yml"
    ENV_FILE="/opt/place-research-test/.env.test"
    PROJECT_NAME="place-research-test"
else
    echo "Error: Invalid environment. Use 'test' or 'production'"
    exit 1
fi

# Export variables
export GITHUB_REPOSITORY=${GITHUB_REPOSITORY:-"lhwrd/place-research"}
export IMAGE_TAG=$IMAGE_TAG

# Load environment variables
set -a
source "$ENV_FILE"
set +a

echo "Step 1: Logging in to GitHub Container Registry..."
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_ACTOR --password-stdin 2>/dev/null || true

echo "Step 2: Pulling latest images..."
docker compose -f $COMPOSE_FILE -p $PROJECT_NAME pull

echo "Step 3: Creating backup of current state..."
if [ "$ENVIRONMENT" = "production" ]; then
    ./scripts/backup.sh
fi

echo "Step 4: Stopping old containers..."
docker compose -f $COMPOSE_FILE -p $PROJECT_NAME down --remove-orphans

echo "Step 5: Starting new containers (migrations run automatically on startup)..."
docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME up -d

echo "Step 6: Waiting for services to be healthy..."
sleep 10

# Check if services are running
if ! docker compose -f $COMPOSE_FILE -p $PROJECT_NAME ps | grep -q "Up"; then
    echo "Error: Services failed to start"
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME logs
    exit 1
fi

echo "Step 7: Cleaning up old images..."
docker image prune -f

echo "=========================================="
echo "Deployment completed successfully!"
echo "=========================================="
echo ""
echo "Service URLs:"
if [ "$ENVIRONMENT" = "production" ]; then
    echo "  Frontend: https://yourapp.com"
    echo "  Backend:  https://api.yourapp.com"
else
    echo "  Frontend: https://test.yourapp.com"
    echo "  Backend:  https://test-api.yourapp.com"
fi
echo ""
echo "To view logs:"
echo "  docker compose -f $COMPOSE_FILE -p $PROJECT_NAME logs -f"
echo ""
echo "To check status:"
echo "  docker compose -f $COMPOSE_FILE -p $PROJECT_NAME ps"
