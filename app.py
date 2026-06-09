"""
Authors: Vishal Singhania (vishalvvs), Rishabh Gupta (rg089)
"""

from flask import Flask
from flask_restful import Api, Resource
from utils import read_data_db

app = Flask(__name__)
api = Api(app)

class News(Resource):
    def get(self, source="all"):
        source = source.lower()
        papers = [
            # English
            "tie", "toi", "ndtv", "it", "th",
            # Hindi
            "au", "bbc", "oi", "lh", "n18",
            "all",
        ]
        if source in papers:
            return read_data_db(source)
        s = """
        Valid sources:
        ENGLISH: TIE (Indian Express), TOI (Times of India), NDTV, IT (India Today), TH (The Hindu)
        HINDI: AU (Amar Ujala), BBC (BBC Hindi), OI (OneIndia Hindi), LH (Live Hindustan), N18 (News18 Hindi)
        ALL: All sources combined
        """
        return s, 404

api.add_resource(News, "/news", "/news/","/news/<string:source>")
if __name__ == '__main__':
    app.run(debug=True)
