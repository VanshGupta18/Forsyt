# Deployment Guide — Forsyt India GPR Pipeline

Target: Hetzner CX22 or DigitalOcean Basic ($6/mo)
Requirements: 2 vCPU / 4 GB RAM (DistilBERT CPU fits in ~1.5 GB)

---

## 1. Server setup

```bash
sudo apt update && sudo apt install -y git python3-pip curl
curl -LsSf https://astral.sh/uv/install.sh | sh

sudo useradd -m -s /bin/bash forsyt
sudo mkdir -p /var/lib/forsyt /var/log/forsyt
sudo chown forsyt:forsyt /var/lib/forsyt /var/log/forsyt
```

## 2. Clone repo

```bash
sudo -u forsyt bash
cd /var/lib/forsyt
git clone -b news_gpr https://github.com/VanshGupta18/Forsyt.git .
```

## 3. Create virtualenv + install dependencies

```bash
uv venv .venv
uv pip install -r requirements.txt
```

## 4. Create required directories

```bash
mkdir -p data/india_db data/india_raw data/india_archive data/india_processed
mkdir -p data/gkg_raw data/gkg_processed data/benchmarks
mkdir -p outputs/news/validation outputs/gkg/validation outputs/compare
mkdir -p logs
```

## 5. Day 1 bootstrap (news path)

```bash
# Scrape once across all 10 outlets
python -m scraper once

# Export to JSONL
python main.py export-news

# Tag + preprocess (downloads DistilBERT models ~800MB on first run)
TODAY=$(date +%Y-%m-%d)
python main.py preprocess-india --start-date $TODAY --end-date $TODAY --force

# Build initial GPR index (sets anchor_date in data/india_archive/series_state.json)
python main.py gpr-news --start-date $TODAY --end-date $TODAY

echo "Anchor set: $(python -c "import json,pathlib; print(json.loads(pathlib.Path('data/india_archive/series_state.json').read_text()))")"
```

## 6. Systemd services

Copy service files:

```bash
sudo cp deploy/news-scheduler.service /etc/systemd/system/
sudo cp deploy/news-api.service       /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable news-scheduler news-api
sudo systemctl start  news-scheduler news-api
```

Check status:

```bash
sudo journalctl -u news-scheduler -f   # scraper loop (5-min cycle, 10 outlets)
sudo journalctl -u news-api -f          # Flask read API
```

## 7. Cron jobs

```bash
crontab -e
```

Add:

```cron
# Hourly: export today's articles → preprocess → re-score news GPR
5 * * * *   /var/lib/forsyt/deploy/hourly_update.sh >> /var/log/forsyt/hourly_update.log 2>&1

# Daily 03:00 IST: full news GPR rebuild for yesterday
0 3 * * *   /var/lib/forsyt/deploy/daily_gpr_india.sh >> /var/log/forsyt/daily_gpr_india.log 2>&1

# Weekly Sunday 04:00 IST: validate both paths + compare
0 4 * * 0   /var/lib/forsyt/deploy/weekly_validate.sh >> /var/log/forsyt/weekly_validate.log 2>&1
```

Make scripts executable:

```bash
chmod +x deploy/*.sh
```

## 8. GKG path (historical — run separately when needed)

```bash
python main.py download    --start-date 2025-01-01 --end-date 2025-12-31
python main.py preprocess  --start-date 2025-01-01 --end-date 2025-12-31
python main.py gpr-gkg     --start-date 2025-01-01 --end-date 2025-12-31
python main.py fill-gaps   --output-dir outputs/gkg \
    --start-date 2025-01-01 --end-date 2025-12-31
python main.py validate-gkg --start-date 2025-01-01 --end-date 2025-12-31
```

## 9. Compare news vs GKG (after both paths have data)

```bash
python main.py compare-gpr \
  --news-dir outputs/news \
  --gkg-dir  outputs/gkg
```

Results in `outputs/compare/`:
- `compare_news_vs_gkg.csv` — Pearson/Spearman correlations
- `spike_comparison.csv` — top-10 spike days per source
- `volume_news_vs_gkg.csv` — article volume per day

## 10. Theme tagger calibration (improve GPR hit rate)

If positive share < 10%, lower the similarity threshold:

```bash
# Run calibration on a sample day:
python -m scripts.theme_tagger calibrate data/india_raw/YYYY-MM-DD.jsonl.gz

# Edit scripts/theme_tagger.py: SIMILARITY_THRESHOLD = 0.35
# Reprocess with force:
python main.py preprocess-india --start-date ANCHOR --end-date TODAY --force
python main.py gpr-news --start-date ANCHOR --end-date TODAY
```

## 11. Monitoring

```bash
# Series state
python -c "import json,pathlib; print(json.loads(pathlib.Path('data/india_archive/series_state.json').read_text()))"

# Article counts per day
ls -la data/india_raw/*.jsonl.gz | tail -10

# Latest GPR
tail -5 outputs/news/gpr_daily_index.csv

# Validate quickly
python main.py validate-news --start-date ANCHOR --end-date TODAY
```

---

## Output directories

| Directory | Contents |
|-----------|----------|
| `outputs/news/` | Scraper-based GPR (forward from anchor) |
| `outputs/news/validation/` | Validation reports for news path |
| `outputs/gkg/` | GDELT GKG GPR (historical) |
| `outputs/gkg/validation/` | Validation reports for GKG path |
| `outputs/compare/` | Cross-path comparison |
