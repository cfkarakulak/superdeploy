#!/bin/bash
# PostgreSQL Backup Script
# Run via cron: 0 2 * * * /opt/superdeploy/scripts/backup/postgres-backup.sh

set -euo pipefail

BACKUP_DIR="/opt/backups/postgres"
CONTAINER_NAME="superdeploy-postgres"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Source environment variables
set -a
source /opt/superdeploy/.env
set +a

echo "🗄️  Starting PostgreSQL backup: $TIMESTAMP"

# Perform backup
docker exec "$CONTAINER_NAME" pg_dump \
  -U "${POSTGRES_USER}" \
  -d "${POSTGRES_DB}" \
  --no-owner \
  --no-acl \
  | gzip > "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz"

# Calculate size
BACKUP_SIZE=$(du -h "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz" | cut -f1)
echo "✅ Backup created: postgres_${TIMESTAMP}.sql.gz ($BACKUP_SIZE)"

# Upload to GCS (optional - requires gsutil configured)
if command -v gsutil &> /dev/null; then
  BUCKET="gs://superdeploy-backups-${GCP_PROJECT_ID}/postgres"
  gsutil cp "$BACKUP_DIR/postgres_${TIMESTAMP}.sql.gz" "$BUCKET/" 2>/dev/null && \
    echo "☁️  Uploaded to GCS: $BUCKET" || \
    echo "⚠️  GCS upload failed (bucket may not exist)"
fi

# Cleanup old backups (local)
find "$BACKUP_DIR" -name "postgres_*.sql.gz" -mtime +$RETENTION_DAYS -delete
echo "🧹 Cleaned backups older than $RETENTION_DAYS days"

echo "✅ Backup complete!"

