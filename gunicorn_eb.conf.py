"""Gunicorn config for Forsyt API — Elastic Beanstalk uses port 8000 behind nginx proxy."""

bind = "0.0.0.0:8000"
workers = 2
threads = 4
timeout = 30
accesslog = "-"
errorlog = "-"
loglevel = "info"
