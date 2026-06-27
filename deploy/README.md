# Deployment Guide — Forsyt India GPR Pipeline

## Target: Hetzner CX22 or DigitalOcean Basic ($6/mo)
Requirements: 2 vCPU / 4 GB RAM (DistilBERT CPU fits in ~1.5 GB)

---

## 1. Server setup

```bash
# On the VPS (Ubuntu 24.04 LTS)
sudo apt update && sudo apt install -y git python3-pip python3-venv curl

# Create service user
sudo useradd -m -s /bin/bash forsyt
sudo mkdir -p /var/lib/forsyt /var/log/forsyt
sudo chown forsyt:forsyt /var/lib/forsyt /var/log/forsyt

# Install uv (project uses uv, not pip)
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2. Clone repo

```bash
sudo -u forsyt bash
cd /var/lib/forsyt

git clone https://github.com/<your-org>/forsyt .
# news_scraper code is now part of this repo as scraper/ package — no worktree needed
```

## 3. Create virtualenv + install dependencies

```bash
uv venv .venv
uv pip install -r requirements.txt

# news_scraper also needs its own deps
uv pip install flask flask-restful feedparser beautifulsoup4 lxml requests
```

## 4. Create required directories

```bash
mkdir -p data/india_db data/india_raw data/india_archive data/india_processed
mkdir -p outputs/india/validation
```

## 5. Run backfill (one-time, ~3-5 days machine time)

```bash
# Start in a tmux/screen session — will take hours
python main.py backfill-india \
    --start-date 2026-01-01 \
    --end-date   2026-06-20 \
    --workers 4
```

Check coverage:
```bash
# After backfill
python -c "
import pandas as pd
df = pd.read_csv('data/india_archive/backfill_coverage.csv')
print(df.describe())
print('Days with ≥200 articles:', (df.articles>=200).sum())
"
```

## 6. Initial GPR run over backfill

```bash
python main.py preprocess-india --start-date 2026-01-01 --end-date 2026-06-20
python main.py gpr \
    --processed-dir data/india_processed \
    --output-dir    outputs/india \
    --start-date    2026-01-01 \
    --end-date      2026-06-20
python main.py fill-gaps \
    --output-dir outputs/india \
    --start-date 2026-01-01 \
    --end-date   2026-06-20
python main.py validate \
    --output-dir outputs/india \
    --benchmark gprc_ind \
    --start-date 2026-01-01 \
    --end-date   2026-06-20
```

## 7. Calibrate DistilBERT tone (after backfill)

Pick any day with a good number of articles:
```bash
python -m scripts.theme_tagger calibrate data/india_raw/2026-03-15.jsonl.gz --n 500
```
If the recommended TONE_SCALE differs significantly from 16.0, update `TONE_SCALE` in `scripts/theme_tagger.py` and re-run preprocess-india with `--force`.

## 8. Install systemd services

```bash
sudo cp deploy/news-scheduler.service /etc/systemd/system/
sudo cp deploy/news-api.service       /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable news-scheduler news-api
sudo systemctl start  news-scheduler news-api
```

## 9. Install cron jobs

```bash
chmod +x deploy/hourly_update.sh deploy/daily_gpr_india.sh deploy/weekly_validate.sh

# Edit crontab for forsyt user:
sudo -u forsyt crontab -e
# Add:
# 5 * * * *   /var/lib/forsyt/deploy/hourly_update.sh    >> /var/log/forsyt/hourly_update.log 2>&1
# 0 3 * * *   /var/lib/forsyt/deploy/daily_gpr_india.sh  >> /var/log/forsyt/daily_gpr_india.log 2>&1
# 0 4 * * 0   /var/lib/forsyt/deploy/weekly_validate.sh  >> /var/log/forsyt/weekly_validate.log 2>&1
```

The hourly cron (`hourly_update.sh`) provides ~1h article-to-index latency.
The daily cron is retained as a safety net and for gap-filling.


## 10. Backup raw JSONL (irreplaceable)

Install rclone and configure an S3/B2/R2 remote:
```bash
# Nightly backup of raw JSONL only (parquets are reproducible from JSONL)
# Add to crontab:
# 30 2 * * *  rclone sync /var/lib/forsyt/data/india_raw/ forsyt-backup:india-raw/
```

## Monitoring

```bash
sudo journalctl -u news-scheduler -f   # live scraper logs
sudo journalctl -u news-api -f         # API logs
tail -f /var/log/forsyt/daily_gpr_india.log
```

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NEWS_DB_PATH` | `news_scraper/news.db` | Override SQLite path |
| `FORSYT_ROOT`  | repo root | Override project root |
