"""scraper — async Indian news scraper package.

Ports the Newsemble news_scraper (origin/news_scraper branch) into the
gpr_index tree as a proper Python package with async I/O.

Usage:
  python -m scraper schedule          # 5-min continuous loop
  python -m scraper once              # single scrape cycle
  python -m scraper api               # start Flask read API
"""

__version__ = "1.0.0"
