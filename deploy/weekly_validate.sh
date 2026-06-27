#!/bin/bash
# Weekly cron: validate India GPR vs GPRC_IND and plot  (runs at 04:00 IST Sunday)
# Crontab entry:  0 4 * * 0 /var/lib/forsyt/deploy/weekly_validate.sh >> /var/log/forsyt/weekly_validate.log 2>&1

set -euo pipefail
REPO=/var/lib/forsyt
VENV=$REPO/.venv
TODAY=$(date +%Y-%m-%d)

echo "===== Weekly validate $(date) ====="

$VENV/bin/python $REPO/main.py validate \
    --output-dir  $REPO/outputs \
    --benchmark   all \
    --start-date  2025-01-01 \
    --end-date    "$TODAY"

$VENV/bin/python $REPO/main.py plot \
    --output-dir $REPO/outputs \
    --start-date 2025-01-01 \
    --end-date   "$TODAY"

echo "[done] $(date)"
