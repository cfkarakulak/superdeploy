#!/bin/bash
# Forgejo Backup Script
# Run via cron: 0 3 * * * /opt/superdeploy/scripts/backup/forgejo-backup.sh

set -euo pipefail

BACKUP_DIR="/opt/backups/forgejo"
CONTAINER_NAME="forgejo"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$BACKUP_DIR"

echo "🦊 Starting Forgejo backup: $TIMESTAMP"

# Forgejo dump (includes repos, DB, config)
docker exec "$CONTAINER_NAME" /bin/sh -c \
  "forgejo dump -c /data/gitea/conf/app.ini -f /tmp/forgejo-dump-${TIMESTAMP}.zip" || {
    echo "❌ Forgejo dump failed"
    exit 1
  }

# Copy dump out of container
docker cp "$CONTAINER_NAME:/tmp/forgejo-dump-${TIMESTAMP}.zip" "$BACKUP_DIR/"

# Cleanup inside container
docker exec "$CONTAINER_NAME" rm -f "/tmp/forgejo-dump-${TIMESTAMP}.zip"

BACKUP_SIZE=$(du -h "$BACKUP_DIR/forgejo-dump-${TIMESTAMP}.zip" | cut -f1)
echo "✅ Backup created: forgejo-dump-${TIMESTAMP}.zip ($BACKUP_SIZE)"

# Upload to GCS (optional)
if command -v gsutil &> /dev/null; then
  BUCKET="gs://superdeploy-backups-${GCP_PROJECT_ID}/forgejo"
  gsutil cp "$BACKUP_DIR/forgejo-dump-${TIMESTAMP}.zip" "$BUCKET/" 2>/dev/null && \
    echo "☁️  Uploaded to GCS: $BUCKET" || \
    echo "⚠️  GCS upload skipped"
fi

# Cleanup old backups
find "$BACKUP_DIR" -name "forgejo-dump-*.zip" -mtime +$RETENTION_DAYS -delete
echo "🧹 Cleaned backups older than $RETENTION_DAYS days"

echo "✅ Backup complete!"

