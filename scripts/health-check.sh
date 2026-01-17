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
    ENV_FILE="/opt/place-research-prod/.env.prod"
elif [ "$ENVIRONMENT" = "test" ]; then
    BACKEND_URL="http://localhost:8000"
    FRONTEND_URL="http://localhost:3000"
    PROJECT_NAME="place-research-test"
    COMPOSE_FILE="docker/docker-compose.test.yml"
    ENV_FILE="/opt/place-research-test/.env.test"
else
    echo "Error: Invalid environment. Use 'test' or 'production'"
    exit 1
fi

echo "Checking container status..."
if ! docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME --env-file $ENV_FILE ps | grep -q "Up"; then
    echo "❌ ERROR: Some containers are not running"
    docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME --env-file $ENV_FILE ps
    EXIT_CODE=1
else
    echo "✅ All containers are running"
fi

echo ""
echo "Checking backend health endpoint..."
if curl -f -s -o /dev/null -w "%{http_code}" "$BACKEND_URL/health" | grep -q "200"; then
    echo "✅ Backend is healthy"
else
    echo "❌ ERROR: Backend health check failed"
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
if docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME --env-file $ENV_FILE exec -T postgres pg_isready > /dev/null 2>&1; then
    echo "✅ Database is ready"
else
    echo "❌ ERROR: Database is not ready"
    EXIT_CODE=1
fi

echo ""
echo "Checking API endpoints..."
if curl -f -s "$BACKEND_URL/api/v1/health" > /dev/null 2>&1; then
    echo "✅ API endpoints are responding"
else
    echo "⚠️  WARNING: API endpoints check failed (might be expected if not configured)"
fi

echo ""
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ All health checks passed!"
else
    echo "❌ Some health checks failed!"
    echo ""
    echo "Checking logs for errors..."
    docker compose -f $COMPOSE_FILE -p $PROJECT_NAME --env-file $ENV_FILE logs --tail=50
fi
echo "=========================================="

exit $EXIT_CODE
