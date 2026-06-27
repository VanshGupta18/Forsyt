#!/bin/bash
# Daily cron: preprocess yesterday → full GPR suite → fill-gaps  (runs at 03:00 IST)
# Uses the Indian newspaper scraper as data source; produces the same output as GKG path.
# Crontab entry:  0 3 * * * /var/lib/forsyt/deploy/daily_gpr_india.sh >> /var/log/forsyt/daily_gpr_india.log 2>&1

set -euo pipefail
REPO=/var/lib/forsyt
VENV=$REPO/.venv
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)
START_DATE=2025-01-01   # set to earliest backfill date

echo "===== $(date) ====="

echo "[1/3] preprocess-india $YESTERDAY"
$VENV/bin/python $REPO/main.py preprocess-india \
    --start-date "$YESTERDAY" --end-date "$YESTERDAY"

echo "[2/3] gpr (scraper → full GPR suite)"
$VENV/bin/python $REPO/main.py gpr \
    --processed-dir $REPO/data/india_processed \
    --output-dir    $REPO/outputs \
    --start-date    $START_DATE \
    --end-date      "$YESTERDAY"

echo "[3/3] fill-gaps"
$VENV/bin/python $REPO/main.py fill-gaps \
    --output-dir  $REPO/outputs \
    --start-date  $START_DATE \
    --end-date    "$YESTERDAY"

echo "[done] $(date)"
