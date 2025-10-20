#!/bin/bash
# Setup backup cron jobs
# Run once: sudo bash /opt/superdeploy/scripts/backup/setup-cron.sh

set -euo pipefail

echo "📅 Setting up backup cron jobs..."

# Make scripts executable
chmod +x /opt/superdeploy/scripts/backup/*.sh

# Add cron jobs for superdeploy user
(crontab -u superdeploy -l 2>/dev/null || true; cat <<EOF
# PostgreSQL backup (daily at 2 AM UTC)
0 2 * * * /opt/superdeploy/scripts/backup/postgres-backup.sh >> /var/log/superdeploy-backup.log 2>&1

# Forgejo backup (daily at 3 AM UTC)
0 3 * * * /opt/superdeploy/scripts/backup/forgejo-backup.sh >> /var/log/superdeploy-backup.log 2>&1
EOF
) | crontab -u superdeploy -

echo "✅ Cron jobs installed for user: superdeploy"
echo ""
echo "Scheduled backups:"
echo "  - PostgreSQL: 02:00 UTC daily"
echo "  - Forgejo:    03:00 UTC daily"
echo "  - Retention:  7 days"
echo "  - Logs:       /var/log/superdeploy-backup.log"
echo ""
echo "💡 To verify: crontab -u superdeploy -l"

