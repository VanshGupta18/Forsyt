"""Flask read-only REST API — port of origin/news_scraper app.py.

Endpoints:
  GET /news               all articles (up to 500)
  GET /news/<source>      filtered by outlet code
  GET /health             liveness probe

Run with:
  gunicorn -w 2 -b 0.0.0.0:8080 "scraper.api:create_app()"
or:
  python -m scraper api
"""

from __future__ import annotations

from flask import Flask, jsonify
from flask_restful import Api, Resource

from .utils import read_data_db

VALID_SOURCES = {
    "tie", "toi", "ndtv", "it", "th",
    "au", "bbc", "oi", "lh", "n18",
    "all",
}


class NewsResource(Resource):
    def get(self, source: str = "all"):
        source = source.lower()
        if source not in VALID_SOURCES:
            return (
                "Invalid source. Valid: TIE, TOI, NDTV, IT, TH, AU, BBC, OI, LH, N18, ALL",
                404,
            )
        return read_data_db(source)


class HealthResource(Resource):
    def get(self):
        from .db import get_total_count  # noqa: PLC0415
        return {"status": "ok", "total_articles": get_total_count()}


def create_app() -> Flask:
    app = Flask(__name__)
    api = Api(app)
    api.add_resource(NewsResource, "/news", "/news/", "/news/<string:source>")
    api.add_resource(HealthResource, "/health")
    return app


# For `python scraper/api.py` direct execution
app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=8080)
