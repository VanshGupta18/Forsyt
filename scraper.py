"""
Authors: Rishabh Gupta (rg089), Vishal Singhania (vishalvvs)
Updated: 2026 - Rewrote scrapers to use RSS feeds + updated BeautifulSoup selectors
"""

import requests
from bs4 import BeautifulSoup
import feedparser
from datetime import datetime
import re
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
}


def safe_get(url, timeout=15):
    """Safely fetch a URL with error handling."""
    try:
        resp = requests.get(url, headers=HEADERS, timeout=timeout)
        resp.raise_for_status()
        return resp
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


def parse_feed(url, retries=2, backoff=3):
    """Parse an RSS feed with a browser User-Agent and retry on transient failures.

    feedparser's default User-Agent gets rate-limited/blocked by some sites more
    readily than a browser UA (seen intermittently on Live Hindustan from shared
    GitHub Actions runner IPs), and a single network hiccup would otherwise drop
    that source's articles for the whole run.
    """
    last_exc = None
    for attempt in range(retries + 1):
        try:
            feed = feedparser.parse(url, request_headers=HEADERS)
            if feed.entries:
                return feed
            last_exc = feed.bozo_exception if feed.bozo else None
        except Exception as e:
            last_exc = e

        if attempt < retries:
            time.sleep(backoff)

    logger.warning(f"parse_feed: no entries from {url} after {retries + 1} attempts: {last_exc}")
    return feedparser.parse(url, request_headers=HEADERS)


def parse_rss_time(entry):
    """Extract and format time from an RSS feed entry."""
    time_str = None
    if hasattr(entry, "published_parsed") and entry.published_parsed:
        try:
            dt = datetime(*entry.published_parsed[:6])
            time_str = dt.strftime("%B %d, %Y %H:%M")
        except Exception:
            pass
    if not time_str and hasattr(entry, "updated_parsed") and entry.updated_parsed:
        try:
            dt = datetime(*entry.updated_parsed[:6])
            time_str = dt.strftime("%B %d, %Y %H:%M")
        except Exception:
            pass
    return time_str


class IndiaToday:
    RSS_URL = "https://www.indiatoday.in/rss/home"

    @staticmethod
    def get_content(url):
        """Extract article content from an India Today article page."""
        resp = safe_get(url)
        if resp is None:
            return None, None
        soup = BeautifulSoup(resp.text, "lxml")

        # Try multiple selectors for the article body
        content_div = None
        for selector in [
            {"itemprop": "articleBody"},
            {"class": re.compile(r"Story_description")},
            {"class": re.compile(r"description")},
            {"class": "story-right"},
        ]:
            content_div = soup.find("div", selector)
            if content_div:
                break

        if content_div is None:
            return None, None

        paragraphs = content_div.find_all("p")
        content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Try to get time from the page
        time_str = None
        time_el = soup.find("span", class_=re.compile(r"date|time|update", re.I))
        if time_el:
            time_str = time_el.get_text(strip=True)
            time_str = re.sub(r"Updated:|IST|AM|PM", "", time_str, flags=re.IGNORECASE).strip()

        return content if content else None, time_str

    @staticmethod
    def generate_dataset():
        data = []
        feed = parse_feed(IndiaToday.RSS_URL)
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                rss_time = parse_rss_time(entry)
                content, page_time = IndiaToday.get_content(link)

                if not content:
                    continue

                article = {
                    "link": link,
                    "content": content,
                    "source": "IT",
                    "title": title,
                    "time": page_time or rss_time,
                }
                data.append(article)
            except Exception as e:
                logger.warning(f"IndiaToday: error processing entry: {e}")
                continue

        logger.info(f"IndiaToday: scraped {len(data)} articles")
        return data


class TheHindu:
    # "latest-news" feeder is stale/frozen on The Hindu's side (returns mostly
    # 2023-dated entries) despite the name; "news" feeder is a genuinely live,
    # fast-rotating feed (~30 new items/hour).
    RSS_URL = "https://www.thehindu.com/news/feeder/default.rss"

    @staticmethod
    def get_content(url):
        """Extract article content from a The Hindu article page."""
        resp = safe_get(url)
        if resp is None:
            return None, None
        soup = BeautifulSoup(resp.text, "lxml")

        # Try multiple selectors
        content_div = None
        for selector in [
            {"class": "articlebodycontent"},
            {"itemprop": "articleBody"},
            {"class": re.compile(r"article-body|paywall")},
        ]:
            content_div = soup.find("div", selector)
            if content_div:
                break

        if content_div is None:
            return None, None

        paragraphs = content_div.find_all("p")
        content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Time
        time_str = None
        time_el = soup.find("span", class_=re.compile(r"date|time|update|publish", re.I))
        if time_el:
            time_str = time_el.get_text(strip=True)
            time_str = re.sub(r"Updated:|Published:|IST|AM|PM", "", time_str, flags=re.IGNORECASE).strip()

        return content if content else None, time_str

    @staticmethod
    def generate_dataset():
        data = []
        feed = parse_feed(TheHindu.RSS_URL)
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                rss_time = parse_rss_time(entry)
                content, page_time = TheHindu.get_content(link)

                if not content:
                    continue

                article = {
                    "link": link,
                    "content": content,
                    "source": "TH",
                    "title": title,
                    "time": page_time or rss_time,
                }
                data.append(article)
            except Exception as e:
                logger.warning(f"TheHindu: error processing entry: {e}")
                continue

        logger.info(f"TheHindu: scraped {len(data)} articles")
        return data


class TimesOfIndiaNews:
    RSS_URL = "https://timesofindia.indiatimes.com/rssfeedstopstories.cms"

    @staticmethod
    def get_content(url):
        """Extract article content from a TOI article page.
        Primary method: LD+JSON articleBody (most reliable).
        Fallback: HTML div selectors.
        """
        resp = safe_get(url)
        if resp is None:
            return None, None
        soup = BeautifulSoup(resp.text, "lxml")

        content = None
        time_str = None

        # Primary: extract from LD+JSON structured data
        import json as _json
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld_data = _json.loads(script.string)
                if isinstance(ld_data, dict) and "articleBody" in ld_data:
                    content = ld_data["articleBody"].strip()
                    # Also try to get time from LD+JSON
                    date_mod = ld_data.get("dateModified") or ld_data.get("datePublished")
                    if date_mod:
                        try:
                            dt = datetime.fromisoformat(date_mod.replace("Z", "+00:00"))
                            time_str = dt.strftime("%b %d, %Y, %H:%M")
                        except Exception:
                            time_str = date_mod
                    break
            except Exception:
                continue

        # Fallback: try HTML selectors
        if not content:
            for selector in [
                {"itemprop": "articleBody"},
                {"class": re.compile(r"ga-headlines|article-body|story-content")},
                {"class": "Normal"},
            ]:
                content_div = soup.find("div", selector)
                if content_div:
                    paras = content_div.find_all("p")
                    content = " ".join(p.get_text(strip=True) for p in paras if p.get_text(strip=True))
                    if content:
                        break

        # Fallback: arttextxml
        if not content:
            arttextxml = soup.find("arttextxml")
            if arttextxml:
                content = arttextxml.get_text(strip=True)

        # Time fallback from HTML
        if not time_str:
            time_el = soup.find("div", class_=re.compile(r"byline|xf8Pm|publish", re.I))
            if time_el:
                span = time_el.find("span")
                if span:
                    time_str = span.get_text(strip=True)
                    time_str = re.sub(r"Updated:|IST|AM|PM", "", time_str, flags=re.IGNORECASE).strip()

        return content if content else None, time_str

    @staticmethod
    def generate_dataset():
        data = []
        feed = parse_feed(TimesOfIndiaNews.RSS_URL)
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                rss_time = parse_rss_time(entry)
                content, page_time = TimesOfIndiaNews.get_content(link)

                if not content:
                    continue

                article = {
                    "link": link,
                    "content": content,
                    "source": "TOI",
                    "title": title,
                    "time": page_time or rss_time,
                }
                data.append(article)
            except Exception as e:
                logger.warning(f"TOI: error processing entry: {e}")
                continue

        logger.info(f"TimesOfIndia: scraped {len(data)} articles")
        return data


class NDTVNEWS:
    RSS_URL = "https://feeds.feedburner.com/ndtvnews-top-stories"

    @staticmethod
    def generate_dataset():
        """NDTV blocks all server-side requests (403 Forbidden).
        We extract content directly from the RSS feed instead.
        The RSS provides title, link, summary, and publish time.
        """
        data = []
        feed = parse_feed(NDTVNEWS.RSS_URL)
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                # Strip #publisher=newsstand from URLs
                link = link.split("#")[0]

                rss_time = parse_rss_time(entry)

                # Get content from RSS (summary or content field)
                content = ""
                if hasattr(entry, "content") and entry.content:
                    # Use the longest content entry
                    content = max(
                        (c.get("value", "") for c in entry.content),
                        key=len, default=""
                    )
                if not content and hasattr(entry, "summary"):
                    content = entry.summary

                # Clean HTML tags from RSS content
                if content:
                    content_soup = BeautifulSoup(content, "lxml")
                    content = content_soup.get_text(strip=True)

                if not content:
                    continue

                article = {
                    "link": link,
                    "content": content,
                    "source": "NDTV",
                    "title": title,
                    "time": rss_time,
                }
                data.append(article)
            except Exception as e:
                logger.warning(f"NDTV: error processing entry: {e}")
                continue

        logger.info(f"NDTV: scraped {len(data)} articles")
        return data


class TheIndianExpress:
    RSS_URL = "https://indianexpress.com/section/india/feed/"

    @staticmethod
    def get_content(url):
        """Extract article content from an Indian Express article page."""
        resp = safe_get(url)
        if resp is None:
            return None, None
        soup = BeautifulSoup(resp.text, "lxml")

        # Try multiple selectors
        content_div = None
        for selector in [
            {"id": "pcl-full-content"},
            {"itemprop": "articleBody"},
            {"class": re.compile(r"full-details|story_details")},
        ]:
            content_div = soup.find("div", selector)
            if content_div:
                break

        if content_div is None:
            return None, None

        paragraphs = content_div.find_all("p")
        content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Time
        time_str = None
        time_el = soup.find("span", {"itemprop": "dateModified"})
        if not time_el:
            time_el = soup.find("span", class_=re.compile(r"date|time|update", re.I))
        if time_el:
            time_str = time_el.get_text(strip=True)
            time_str = re.sub(r"Updated:|IST|AM|PM", "", time_str, flags=re.IGNORECASE).strip()

        return content if content else None, time_str

    @staticmethod
    def generate_dataset():
        data = []
        feed = parse_feed(TheIndianExpress.RSS_URL)
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                rss_time = parse_rss_time(entry)
                content, page_time = TheIndianExpress.get_content(link)

                if not content:
                    continue

                article = {
                    "link": link,
                    "content": content.strip(),
                    "source": "TIE",
                    "title": title.strip(),
                    "time": page_time or rss_time,
                }
                data.append(article)
            except Exception as e:
                logger.warning(f"IndianExpress: error processing entry: {e}")
                continue

        logger.info(f"IndianExpress: scraped {len(data)} articles")
        return data


# ============================================================
# HINDI NEWS SOURCES
# ============================================================


class AmarUjala:
    RSS_URL = "https://www.amarujala.com/rss/breaking-news.xml"

    @staticmethod
    def get_content(url):
        """Extract article content from Amar Ujala via LD+JSON."""
        resp = safe_get(url)
        if resp is None:
            return None, None
        soup = BeautifulSoup(resp.text, "lxml")

        content = None
        time_str = None

        # Primary: LD+JSON
        import json as _json
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld_data = _json.loads(script.string)
                if isinstance(ld_data, dict) and "articleBody" in ld_data:
                    content = ld_data["articleBody"].strip()
                    date_mod = ld_data.get("dateModified") or ld_data.get("datePublished")
                    if date_mod:
                        try:
                            dt = datetime.fromisoformat(date_mod.replace("Z", "+00:00"))
                            time_str = dt.strftime("%b %d, %Y, %H:%M")
                        except Exception:
                            time_str = date_mod
                    break
            except Exception:
                continue

        return content if content else None, time_str

    @staticmethod
    def generate_dataset():
        data = []
        feed = parse_feed(AmarUjala.RSS_URL)
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                rss_time = parse_rss_time(entry)
                content, page_time = AmarUjala.get_content(link)

                if not content:
                    continue

                article = {
                    "link": link,
                    "content": content,
                    "source": "AU",
                    "title": title,
                    "time": page_time or rss_time,
                }
                data.append(article)
            except Exception as e:
                logger.warning(f"AmarUjala: error processing entry: {e}")
                continue

        logger.info(f"AmarUjala: scraped {len(data)} articles")
        return data


class BBCHindi:
    RSS_URL = "https://www.bbc.com/hindi/index.xml"

    @staticmethod
    def get_content(url):
        """Extract article content from BBC Hindi via <main> tag."""
        resp = safe_get(url)
        if resp is None:
            return None, None
        soup = BeautifulSoup(resp.text, "lxml")

        content = None
        time_str = None

        # BBC Hindi uses <main> tag for article content
        main = soup.find("main")
        if main:
            paragraphs = main.find_all("p")
            content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Fallback: <article> tag
        if not content:
            article = soup.find("article")
            if article:
                paragraphs = article.find_all("p")
                content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        # Time from LD+JSON or time tag
        time_el = soup.find("time")
        if time_el and time_el.get("datetime"):
            try:
                dt = datetime.fromisoformat(time_el["datetime"].replace("Z", "+00:00"))
                time_str = dt.strftime("%b %d, %Y, %H:%M")
            except Exception:
                time_str = time_el.get_text(strip=True)

        return content if content else None, time_str

    @staticmethod
    def generate_dataset():
        data = []
        feed = parse_feed(BBCHindi.RSS_URL)
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                # Strip tracking params
                link = link.split("?")[0]

                rss_time = parse_rss_time(entry)
                content, page_time = BBCHindi.get_content(link)

                if not content:
                    continue

                article = {
                    "link": link,
                    "content": content,
                    "source": "BBC",
                    "title": title,
                    "time": page_time or rss_time,
                }
                data.append(article)
            except Exception as e:
                logger.warning(f"BBCHindi: error processing entry: {e}")
                continue

        logger.info(f"BBCHindi: scraped {len(data)} articles")
        return data


class OneIndiaHindi:
    RSS_URL = "https://hindi.oneindia.com/rss/feeds/oneindia-hindi-fb.xml"

    @staticmethod
    def get_content(url):
        """Extract article content from OneIndia Hindi via LD+JSON or HTML."""
        resp = safe_get(url)
        if resp is None:
            return None, None
        soup = BeautifulSoup(resp.text, "lxml")

        content = None
        time_str = None

        # Primary: LD+JSON
        import json as _json
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld_data = _json.loads(script.string)
                if isinstance(ld_data, dict) and "articleBody" in ld_data:
                    content = ld_data["articleBody"].strip()
                    date_mod = ld_data.get("dateModified") or ld_data.get("datePublished")
                    if date_mod:
                        try:
                            dt = datetime.fromisoformat(date_mod.replace("Z", "+00:00"))
                            time_str = dt.strftime("%b %d, %Y, %H:%M")
                        except Exception:
                            time_str = date_mod
                    break
            except Exception:
                continue

        # Fallback: HTML article-body
        if not content:
            content_div = soup.find("div", class_=re.compile(r"article.?body", re.I))
            if content_div:
                paragraphs = content_div.find_all("p")
                content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        return content if content else None, time_str

    @staticmethod
    def generate_dataset():
        data = []
        feed = parse_feed(OneIndiaHindi.RSS_URL)
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                rss_time = parse_rss_time(entry)
                content, page_time = OneIndiaHindi.get_content(link)

                if not content:
                    continue

                article = {
                    "link": link,
                    "content": content,
                    "source": "OI",
                    "title": title,
                    "time": page_time or rss_time,
                }
                data.append(article)
            except Exception as e:
                logger.warning(f"OneIndiaHindi: error processing entry: {e}")
                continue

        logger.info(f"OneIndiaHindi: scraped {len(data)} articles")
        return data


class LiveHindustan:
    RSS_URL = "https://feed.livehindustan.com/rss/3127"

    @staticmethod
    def get_content(url):
        """Extract article content from Live Hindustan via LD+JSON."""
        resp = safe_get(url)
        if resp is None:
            return None, None
        soup = BeautifulSoup(resp.text, "lxml")

        content = None
        time_str = None

        # Primary: LD+JSON
        import json as _json
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                ld_data = _json.loads(script.string)
                if isinstance(ld_data, dict) and "articleBody" in ld_data:
                    content = ld_data["articleBody"].strip()
                    date_mod = ld_data.get("dateModified") or ld_data.get("datePublished")
                    if date_mod:
                        try:
                            dt = datetime.fromisoformat(date_mod.replace("Z", "+00:00"))
                            time_str = dt.strftime("%b %d, %Y, %H:%M")
                        except Exception:
                            time_str = date_mod
                    break
            except Exception:
                continue

        # Fallback: story-content div
        if not content:
            content_div = soup.find("div", class_=re.compile(r"story.?content", re.I))
            if content_div:
                paragraphs = content_div.find_all("p")
                content = " ".join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))

        return content if content else None, time_str

    @staticmethod
    def generate_dataset():
        data = []
        feed = parse_feed(LiveHindustan.RSS_URL)
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                rss_time = parse_rss_time(entry)
                content, page_time = LiveHindustan.get_content(link)

                if not content:
                    continue

                article = {
                    "link": link,
                    "content": content,
                    "source": "LH",
                    "title": title,
                    "time": page_time or rss_time,
                }
                data.append(article)
            except Exception as e:
                logger.warning(f"LiveHindustan: error processing entry: {e}")
                continue

        logger.info(f"LiveHindustan: scraped {len(data)} articles")
        return data


class News18Hindi:
    RSS_URL = "https://hindi.news18.com/rss/khabar/nation/nation.xml"

    @staticmethod
    def generate_dataset():
        """News18 Hindi blocks server-side requests to article pages (403 Forbidden).
        We extract content directly from the RSS feed instead.
        """
        data = []
        feed = parse_feed(News18Hindi.RSS_URL)
        for entry in feed.entries:
            try:
                title = entry.get("title", "").strip()
                link = entry.get("link", "").strip()
                if not title or not link:
                    continue

                rss_time = parse_rss_time(entry)

                # Extract content from the RSS summary/description
                content = entry.get("summary", "")
                if content:
                    content_soup = BeautifulSoup(content, "lxml")
                    content = content_soup.get_text(strip=True)

                if not content:
                    continue

                article = {
                    "link": link,
                    "content": content.strip(),
                    "source": "N18",
                    "title": title.strip(),
                    "time": rss_time,
                }
                data.append(article)
            except Exception as e:
                logger.warning(f"News18Hindi: error processing entry: {e}")
                continue

        logger.info(f"News18Hindi: scraped {len(data)} articles")
        return data


# ============================================================
# DATA COLLECTOR
# ============================================================


class Data:
    @staticmethod
    def collect(source="all"):
        """
        Input : Ticker of News Site to Scrape, Default : all
        Output: List of Dictionary of the scraped articles from the source site
        """
        d = {
            # English
            "toi": TimesOfIndiaNews,
            "tie": TheIndianExpress,
            "th": TheHindu,
            "it": IndiaToday,
            "ndtv": NDTVNEWS,
            # Hindi
            "au": AmarUjala,
            "bbc": BBCHindi,
            "oi": OneIndiaHindi,
            "lh": LiveHindustan,
            "n18": News18Hindi,
        }
        if source in d:
            news = d[source].generate_dataset()
            return news
        elif source == "all":
            papers = [
                # English
                IndiaToday, TheHindu, TimesOfIndiaNews, NDTVNEWS, TheIndianExpress,
                # Hindi
                AmarUjala, BBCHindi, OneIndiaHindi, LiveHindustan, News18Hindi,
            ]
            articles = []
            for paper in papers:
                try:
                    articles += paper.generate_dataset()
                except Exception as e:
                    logger.error(f"Error scraping {paper.__name__}: {e}")
                    continue
            return articles
        return None
