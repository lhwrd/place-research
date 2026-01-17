#!/bin/bash
set -e

# =============================================================================
# Backup Script
# =============================================================================
# Creates a backup of the database and application data
# =============================================================================

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_DIR="./backups"
CONTAINER_NAME="place-research-prod-db"

echo "=========================================="
echo "Creating backup: $TIMESTAMP"
echo "=========================================="

# Create backup directory if it doesn't exist
mkdir -p $BACKUP_DIR


# Load environment variables (inject secrets from 1Password if available)
export OP_SERVICE_ACCOUNT_TOKEN_FILE=/etc/place-research/op-token

if command -v op &> /dev/null && [ -f "env/prod.env" ]; then
    op inject -i env/prod.env -o .env.prod
fi
if [ -f ".env.prod" ]; then
    set -a
    source .env.prod
    set +a
fi

echo "Step 1: Backing up PostgreSQL database..."
docker exec $CONTAINER_NAME pg_dump -U ${POSTGRES_USER} ${POSTGRES_DB} | gzip > "$BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz"

echo "Step 2: Backing up application data..."
if [ -d "./data" ]; then
    tar -czf "$BACKUP_DIR/data_backup_$TIMESTAMP.tar.gz" ./data
fi

echo "Step 3: Backing up logs..."
if [ -d "./logs" ]; then
    tar -czf "$BACKUP_DIR/logs_backup_$TIMESTAMP.tar.gz" ./logs
fi

echo "Step 4: Creating backup manifest..."
cat > "$BACKUP_DIR/manifest_$TIMESTAMP.txt" << EOF
Backup created: $TIMESTAMP
Database: ${POSTGRES_DB}
Container: $CONTAINER_NAME
Files:
  - db_backup_$TIMESTAMP.sql.gz
  - data_backup_$TIMESTAMP.tar.gz
  - logs_backup_$TIMESTAMP.tar.gz
EOF

# Keep only last 7 days of backups
echo "Step 5: Cleaning up old backups (keeping last 7 days)..."
find $BACKUP_DIR -name "*.gz" -mtime +7 -delete
find $BACKUP_DIR -name "*.txt" -mtime +7 -delete

echo "=========================================="
echo "Backup completed successfully!"
echo "=========================================="
echo "Backup location: $BACKUP_DIR"
echo "Backup files:"
ls -lh $BACKUP_DIR/*$TIMESTAMP*
