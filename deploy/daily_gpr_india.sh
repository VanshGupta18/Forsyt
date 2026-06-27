#!/bin/bash
# Daily cron: preprocess yesterday → full news GPR suite (runs at 03:00 IST)
# No Caldara fill — forward-only series from anchor_date.
# Crontab entry:  0 3 * * * /var/lib/forsyt/deploy/daily_gpr_india.sh >> /var/log/forsyt/daily_gpr_india.log 2>&1

set -euo pipefail
REPO=/var/lib/forsyt
VENV=$REPO/.venv
YESTERDAY=$(date -d "yesterday" +%Y-%m-%d 2>/dev/null || date -v-1d +%Y-%m-%d)

# Read anchor_date from series_state.json
ANCHOR=$($VENV/bin/python -c "
import json, pathlib
s = pathlib.Path('$REPO/data/india_archive/series_state.json')
print(json.loads(s.read_text())['anchor_date'] if s.exists() else '$YESTERDAY')
")

echo "===== $(date) ====="
echo "[anchor] $ANCHOR"

echo "[1/2] preprocess-india $YESTERDAY"
$VENV/bin/python $REPO/main.py preprocess-india \
    --start-date "$YESTERDAY" --end-date "$YESTERDAY"

echo "[2/2] gpr-news ($ANCHOR → $YESTERDAY)"
$VENV/bin/python $REPO/main.py gpr-news \
    --start-date "$ANCHOR" \
    --end-date   "$YESTERDAY"

echo "[done] $(date)"
