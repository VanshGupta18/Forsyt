"""Gunicorn config for Forsyt API (≤10 concurrent users)."""

bind = "0.0.0.0:5001"
workers = 1
threads = 4
timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Run from repo root:
#   gunicorn -c news_dataset/gunicorn.conf.py news_dataset.api.server:app
