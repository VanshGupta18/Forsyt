"""Gunicorn config for Forsyt API (≤10 concurrent users).

workers=1 is required, not just sufficient: news_dataset/api/cache.py is an
in-process dict, so multiple workers would each serve inconsistent cached
responses. Scale via threads, not workers, unless the cache is moved out of
process first.
"""

import os

bind = f"0.0.0.0:{os.environ.get('PORT', '5001')}"
workers = 1
threads = 4
timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"

# Run from repo root:
#   gunicorn -c news_dataset/gunicorn.conf.py news_dataset.api.server:app
