#!/bin/bash

# =============================================================================
# Health Check Script
# =============================================================================
# Checks if all services are healthy and responsive
# =============================================================================

ENVIRONMENT=${1:-production}
EXIT_CODE=0

echo "=========================================="
echo "Health Check: $ENVIRONMENT"
echo "=========================================="


# Set environment-specific variables
if [ "$ENVIRONMENT" = "production" ]; then
    BACKEND_URL="http://localhost:8001"
    FRONTEND_URL="http://localhost:3001"
    PROJECT_NAME="place-research-prod"
    COMPOSE_FILE="docker/docker-compose.prod.yml"
elif [ "$ENVIRONMENT" = "test" ]; then
    BACKEND_URL="http://localhost:8000"
    FRONTEND_URL="http://localhost:3000"
    PROJECT_NAME="place-research-test"
    COMPOSE_FILE="docker/docker-compose.test.yml"
else
    echo "Error: Invalid environment. Use 'test' or 'production'"
    exit 1
fi

echo "Checking container status..."
if ! docker compose -f $COMPOSE_FILE -p $PROJECT_NAME ps | grep -q "Up"; then
    echo "❌ ERROR: Some containers are not running"
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME ps
    EXIT_CODE=1
else
    echo "✅ All containers are running"
fi

echo ""
echo "Checking backend health endpoint..."
MAX_RETRIES=30
RETRY_COUNT=0
BACKEND_HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/health" | grep -q "200"; then
        echo "✅ Backend is healthy"
        BACKEND_HEALTHY=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
        echo "Backend not ready yet, retrying... ($RETRY_COUNT/$MAX_RETRIES)"
        sleep 2
    fi
done

if [ "$BACKEND_HEALTHY" = false ]; then
    echo "❌ ERROR: Backend health check failed after $MAX_RETRIES attempts"
    EXIT_CODE=1
fi

echo ""
echo "Checking frontend accessibility..."
if curl -f -s -o /dev/null -w "%{http_code}" "$FRONTEND_URL" | grep -q "200"; then
    echo "✅ Frontend is accessible"
else
    echo "❌ ERROR: Frontend is not accessible"
    EXIT_CODE=1
fi

echo ""
echo "Checking database connectivity..."
if docker compose -f $COMPOSE_FILE -p $PROJECT_NAME exec -T postgres pg_isready > /dev/null 2>&1; then
    echo "✅ Database is ready"
else
    echo "❌ ERROR: Database is not ready"
    EXIT_CODE=1
fi

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All health checks passed!"
else
    echo "❌ Some health checks failed!"
    echo ""
    echo "Checking logs for errors..."
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME logs --tail=50
fi
echo "=========================================="

exit $EXIT_CODE
