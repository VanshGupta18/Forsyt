#!/bin/bash
# Weekly cron: validate both paths + compare news vs GKG (runs Sunday 04:00 IST)
# Crontab entry:  0 4 * * 0 /var/lib/forsyt/deploy/weekly_validate.sh >> /var/log/forsyt/weekly_validate.log 2>&1

set -euo pipefail
REPO=/var/lib/forsyt
VENV=$REPO/.venv
TODAY=$(date +%Y-%m-%d)

# Read anchor from series_state
ANCHOR=$($VENV/bin/python -c "
import json, pathlib
s = pathlib.Path('$REPO/data/india_archive/series_state.json')
print(json.loads(s.read_text())['anchor_date'] if s.exists() else '$TODAY')
")

echo "===== $(date) ====="

echo "[1/3] validate-news ($ANCHOR → $TODAY)"
$VENV/bin/python $REPO/main.py validate-news \
    --start-date "$ANCHOR" \
    --end-date   "$TODAY" || true

echo "[2/3] validate-gkg (2025)"
$VENV/bin/python $REPO/main.py validate-gkg \
    --start-date 2025-01-01 \
    --end-date   2025-12-31 || true

echo "[3/3] compare-gpr"
$VENV/bin/python $REPO/main.py compare-gpr \
    --news-dir $REPO/outputs/news \
    --gkg-dir  $REPO/outputs/gkg \
    --out-dir  $REPO/outputs/compare \
    --start-date "$ANCHOR" \
    --end-date   "$TODAY" || true

echo "[done] $(date)"
