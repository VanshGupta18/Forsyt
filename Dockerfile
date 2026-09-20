# Local-dev reproducibility only — build/run with Finch (or Docker) instead
# of hand-building a .venv. Does not change how this is hosted in production.
# Build from the repo root: finch build -t forsyt-backend .
FROM python:3.11-slim

WORKDIR /app

# Requirements first, so the pip layer stays cached independently of the source
# below. requirements.txt is `-r` includes of the news_dataset lists, so those
# files have to be present at install time.
COPY requirements.txt ./
COPY news_dataset/requirements.txt news_dataset/requirements-ai.txt ./news_dataset/
RUN pip install --no-cache-dir -r requirements.txt

COPY news_dataset/ ./news_dataset/
COPY gpr_index/ ./gpr_index/
COPY nifty-50/ ./nifty-50/
COPY Procfile ./

EXPOSE 5001

CMD ["gunicorn", "-c", "news_dataset/gunicorn.conf.py", "news_dataset.api.server:app"]
