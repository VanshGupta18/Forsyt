#!/bin/bash
# Hourly cron: export today's scraped articles → preprocess → re-score today's GPR
# Crontab entry:  5 * * * *  /var/lib/forsyt/deploy/hourly_update.sh >> /var/log/forsyt/hourly_update.log 2>&1

set -euo pipefail
REPO=/var/lib/forsyt
VENV=$REPO/.venv

echo "===== $(date) ====="
$VENV/bin/python $REPO/main.py incremental-update
echo "[done] $(date)"
