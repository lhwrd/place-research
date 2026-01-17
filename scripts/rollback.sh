#!/bin/bash
set -e

# =============================================================================
# Rollback Script
# =============================================================================
# Rolls back to the previous deployment
# =============================================================================

ENVIRONMENT=${1:-production}

echo "=========================================="
echo "Rolling back: $ENVIRONMENT"
echo "=========================================="

# Set environment-specific variables
if [ "$ENVIRONMENT" = "production" ]; then
    COMPOSE_FILE="docker/docker-compose.prod.yml"
    PROJECT_NAME="place-research-prod"
    CONTAINER_NAME="place-research-prod-db"
    ENV_FILE="/opt/place-research-prod/.env.prod"
elif [ "$ENVIRONMENT" = "test" ]; then
    COMPOSE_FILE="docker/docker-compose.test.yml"
    PROJECT_NAME="place-research-test"
    CONTAINER_NAME="place-research-test-db"
    ENV_FILE="/opt/place-research-test/.env.test"
else
    echo "Error: Invalid environment. Use 'test' or 'production'"
    exit 1
fi

# Find latest backup
LATEST_BACKUP=$(ls -t backups/db_backup_*.sql.gz 2>/dev/null | head -1)

if [ -z "$LATEST_BACKUP" ]; then
    echo "Error: No backup found for rollback"
    exit 1
fi

echo "Found backup: $LATEST_BACKUP"
read -p "Do you want to restore from this backup? (yes/no): " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo "Rollback cancelled"
    exit 0
fi

# Load environment variables
set -a
source "$ENV_FILE"
set +a

echo "Step 1: Stopping current containers..."
docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME down

echo "Step 2: Restoring database from backup..."
docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME --env-file $ENV_FILE up -d postgres

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to be ready..."
sleep 10

# Drop and recreate database
docker exec $CONTAINER_NAME psql -U ${POSTGRES_USER} -c "DROP DATABASE IF EXISTS ${POSTGRES_DB};"
docker exec $CONTAINER_NAME psql -U ${POSTGRES_USER} -c "CREATE DATABASE ${POSTGRES_DB};"

# Restore from backup
gunzip -c $LATEST_BACKUP | docker exec -i $CONTAINER_NAME psql -U ${POSTGRES_USER} ${POSTGRES_DB}

echo "Step 3: Restoring application data..."
LATEST_DATA_BACKUP=$(ls -t backups/data_backup_*.tar.gz 2>/dev/null | head -1)
if [ -n "$LATEST_DATA_BACKUP" ]; then
    rm -rf ./data
    tar -xzf $LATEST_DATA_BACKUP
fi

echo "Step 4: Starting all services..."
docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME --env-file $ENV_FILE up -d

echo "Step 5: Waiting for services to be healthy..."
sleep 15

echo "=========================================="
echo "Rollback completed!"
echo "=========================================="
echo "Services status:"
docker-compose -f $COMPOSE_FILE -p $PROJECT_NAME --env-file $ENV_FILE ps
