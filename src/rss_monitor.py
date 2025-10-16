import feedparser
import logging
import time
import threading
from typing import Dict, List, Optional, Callable
from datetime import datetime, timedelta
from collections import defaultdict
import hashlib
import re
from html import unescape


class RSSFeedConfig:
    """Configuration for RSS feeds with priority levels"""

    # High-frequency feeds (check every 1-2 minutes) - Breaking news
    HIGH_PRIORITY_FEEDS = {
        # Reuters
        'reuters_world': {
            'url': 'http://feeds.reuters.com/Reuters/worldNews',
            'category': 'usa_news',
            'interval': 120  # 2 minutes
        },
        'reuters_politics': {
            'url': 'http://feeds.reuters.com/Reuters/PoliticsNews',
            'category': 'usa_news',
            'interval': 120
        },
        'reuters_top': {
            'url': 'http://feeds.reuters.com/reuters/topNews',
            'category': 'usa_news',
            'interval': 120
        },

        # Fox News - Politics (fox_trump URL is broken, using politics feed)

        'fox_politics': {
            'url': 'https://moxie.foxnews.com/google-publisher/politics.xml',
            'category': 'usa_news',
            'interval': 120
        },

        # CNN Politics - Note: RSS feed appears to be stale/deprecated
        # Keeping it enabled but it may not return recent articles
        'cnn_politics': {
            'url': 'http://rss.cnn.com/rss/cnn_allpolitics.rss',
            'category': 'usa_news',
            'interval': 120
        },

        # Politico (politico_trump URL is broken, using politics feed)
        'politico_politics': {
            'url': 'https://rss.politico.com/politics-news.xml',
            'category': 'usa_news',
            'interval': 120
        },


        # Bloomberg
        'bloomberg_politics': {
            'url': 'https://feeds.bloomberg.com/politics/news.rss',
            'category': 'usa_news',
            'interval': 120
        },
        'bloomberg_markets': {
            'url': 'https://feeds.bloomberg.com/markets/news.rss',
            'category': 'markets',
            'interval': 120
        },
    }

    # Medium-frequency feeds (check every 2 minutes)
    MEDIUM_PRIORITY_FEEDS = {
        # CNBC
        'cnbc_top': {
            'url': 'https://www.cnbc.com/id/100003114/device/rss/rss.html',
            'category': 'usa_news',
            'interval': 120
        },
        'cnbc_politics': {
            'url': 'https://www.cnbc.com/id/10000113/device/rss/rss.html',
            'category': 'usa_news',
            'interval': 120
        },

        # The Hill
        'thehill_news': {
            'url': 'https://thehill.com/feed/',
            'category': 'usa_news',
            'interval': 120
        },

        # Wall Street Journal
        'wsj_world': {
            'url': 'https://feeds.a.dj.com/rss/RSSWorldNews.xml',
            'category': 'usa_news',
            'interval': 120
        },
        'wsj_markets': {
            'url': 'https://feeds.a.dj.com/rss/RSSMarketsMain.xml',
            'category': 'markets',
            'interval': 120
        },

        # MarketWatch
        'marketwatch_top': {
            'url': 'http://feeds.marketwatch.com/marketwatch/topstories/',
            'category': 'markets',
            'interval': 120
        },

        # CoinDesk (Crypto)
        'coindesk_news': {
            'url': 'https://www.coindesk.com/arc/outboundfeeds/rss/',
            'category': 'crypto',
            'interval': 120
        },

        # CoinTelegraph
        'cointelegraph': {
            'url': 'https://cointelegraph.com/rss',
            'category': 'crypto',
            'interval': 120
        },


        # Investing.com - Commodities Analysis
        'investing_commodities': {
            'url': 'https://www.investing.com/rss/commodities.rss',
            'category': 'commodities',
            'interval': 120
        },
        'investing_metals': {
            'url': 'https://www.investing.com/rss/commodities_Metals.rss',
            'category': 'commodities',
            'interval': 120
        },
        'investing_energy': {
            'url': 'https://www.investing.com/rss/commodities_Energy.rss',
            'category': 'commodities',
            'interval': 120
        },

        # Investing.com - News & Markets
        'investing_news': {
            'url': 'https://www.investing.com/rss/news.rss',
            'category': 'markets',
            'interval': 120
        },
        'investing_stock_news': {
            'url': 'https://www.investing.com/rss/news_285.rss',
            'category': 'markets',
            'interval': 120
        },
        'investing_forex_news': {
            'url': 'https://www.investing.com/rss/news_1.rss',
            'category': 'markets',
            'interval': 120
        },
        'investing_crypto_news': {
            'url': 'https://www.investing.com/rss/news_301.rss',
            'category': 'crypto',
            'interval': 120
        },
        'investing_economy': {
            'url': 'https://www.investing.com/rss/news_95.rss',
            'category': 'usa_news',
            'interval': 120
        },
    }

    # Low-frequency feeds (check every 2 minutes) - Analysis/Opinion
    LOW_PRIORITY_FEEDS = {
        # BBC
        'bbc_world': {
            'url': 'http://feeds.bbci.co.uk/news/world/rss.xml',
            'category': 'usa_news',
            'interval': 120
        },
        'bbc_business': {
            'url': 'http://feeds.bbci.co.uk/news/business/rss.xml',
            'category': 'markets',
            'interval': 120
        },
        'bbc_us': {
            'url': 'http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml',
            'category': 'usa_news',
            'interval': 120
        },

        # NPR
        'npr_news': {
            'url': 'https://feeds.npr.org/1001/rss.xml',
            'category': 'usa_news',
            'interval': 120
        },
        'npr_politics': {
            'url': 'https://feeds.npr.org/1014/rss.xml',
            'category': 'usa_news',
            'interval': 120
        },
        'npr_business': {
            'url': 'https://feeds.npr.org/1006/rss.xml',
            'category': 'markets',
            'interval': 120
        },

        # New York Times (direct RSS)
        'nyt_world': {
            'url': 'https://rss.nytimes.com/services/xml/rss/nyt/World.xml',
            'category': 'usa_news',
            'interval': 120
        },
        'nyt_politics': {
            'url': 'https://rss.nytimes.com/services/xml/rss/nyt/Politics.xml',
            'category': 'usa_news',
            'interval': 120
        },
        'nyt_business': {
            'url': 'https://rss.nytimes.com/services/xml/rss/nyt/Business.xml',
            'category': 'markets',
            'interval': 120
        },

        # The Guardian
        'guardian_us': {
            'url': 'https://www.theguardian.com/us-news/rss',
            'category': 'usa_news',
            'interval': 120
        },
        'guardian_business': {
            'url': 'https://www.theguardian.com/business/rss',
            'category': 'markets',
            'interval': 120
        },
        'guardian_world': {
            'url': 'https://www.theguardian.com/world/rss',
            'category': 'usa_news',
            'interval': 120
        },

        # Washington Post (direct RSS)
        'washingtonpost_politics': {
            'url': 'https://feeds.washingtonpost.com/rss/politics',
            'category': 'usa_news',
            'interval': 120
        },
        'washingtonpost_world': {
            'url': 'https://feeds.washingtonpost.com/rss/world',
            'category': 'usa_news',
            'interval': 120
        },
        'washingtonpost_business': {
            'url': 'https://feeds.washingtonpost.com/rss/business',
            'category': 'markets',
            'interval': 120
        },

        # USA Today
        'usatoday_news': {
            'url': 'http://rssfeeds.usatoday.com/usatoday-NewsTopStories',
            'category': 'usa_news',
            'interval': 120
        },

        # ABC News
        'abc_top': {
            'url': 'https://abcnews.go.com/abcnews/topstories',
            'category': 'usa_news',
            'interval': 120
        },
        'abc_politics': {
            'url': 'https://abcnews.go.com/abcnews/politicsheadlines',
            'category': 'usa_news',
            'interval': 120
        },

        # NBC News
        'nbc_top': {
            'url': 'https://feeds.nbcnews.com/nbcnews/public/news',
            'category': 'usa_news',
            'interval': 120
        },
        'nbc_politics': {
            'url': 'https://feeds.nbcnews.com/nbcnews/public/politics',
            'category': 'usa_news',
            'interval': 120
        },

        # CBS News
        'cbs_top': {
            'url': 'https://www.cbsnews.com/latest/rss/main',
            'category': 'usa_news',
            'interval': 120
        },
        'cbs_politics': {
            'url': 'https://www.cbsnews.com/latest/rss/politics',
            'category': 'usa_news',
            'interval': 120
        },

        # MSNBC
        'msnbc_top': {
            'url': 'https://www.msnbc.com/feeds/latest',
            'category': 'usa_news',
            'interval': 120
        },

        # Associated Press (AP)
        'ap_top': {
            'url': 'https://apnews.com/apf-topnews',
            'category': 'usa_news',
            'interval': 120
        },
        'ap_us': {
            'url': 'https://apnews.com/apf-usnews',
            'category': 'usa_news',
            'interval': 120
        },
        'ap_world': {
            'url': 'https://apnews.com/apf-worldnews',
            'category': 'usa_news',
            'interval': 120
        },
        'ap_business': {
            'url': 'https://apnews.com/apf-business',
            'category': 'markets',
            'interval': 120
        },

        # Axios
        'axios_politics': {
            'url': 'https://api.axios.com/feed/',
            'category': 'usa_news',
            'interval': 120
        },

        # Newsweek
        'newsweek': {
            'url': 'https://www.newsweek.com/rss',
            'category': 'usa_news',
            'interval': 120
        },

        # Time Magazine
        'time_politics': {
            'url': 'https://time.com/feed/',
            'category': 'usa_news',
            'interval': 120
        },

        # The Atlantic
        'theatlantic': {
            'url': 'https://www.theatlantic.com/feed/all/',
            'category': 'usa_news',
            'interval': 120
        },

        # Politico Europe (for international perspective)
        'politico_europe': {
            'url': 'https://www.politico.eu/feed/',
            'category': 'usa_news',
            'interval': 120
        },

        # LA Times
        'latimes_politics': {
            'url': 'https://www.latimes.com/politics/rss2.0.xml',
            'category': 'usa_news',
            'interval': 120
        },
        'latimes_business': {
            'url': 'https://www.latimes.com/business/rss2.0.xml',
            'category': 'markets',
            'interval': 120
        },

        # Financial Times
        'ft_world': {
            'url': 'https://www.ft.com/rss/world',
            'category': 'usa_news',
            'interval': 120
        },
        'ft_markets': {
            'url': 'https://www.ft.com/rss/markets',
            'category': 'markets',
            'interval': 120
        },
        'ft_companies': {
            'url': 'https://www.ft.com/rss/companies',
            'category': 'markets',
            'interval': 120
        },

        # Yahoo Finance
        'yahoo_finance': {
            'url': 'https://finance.yahoo.com/news/rssindex',
            'category': 'markets',
            'interval': 120
        },

        # Barron's (updated URL)
        'barrons_market': {
            'url': 'https://feeds.a.dj.com/rss/RSSMarketsMain.xml',
            'category': 'markets',
            'interval': 120
        },

        # Forbes
        'forbes_business': {
            'url': 'https://www.forbes.com/business/feed/',
            'category': 'markets',
            'interval': 120
        },

        # Business Insider
        'businessinsider': {
            'url': 'https://www.businessinsider.com/rss',
            'category': 'markets',
            'interval': 120
        },

        # Seeking Alpha
        'seekingalpha_news': {
            'url': 'https://seekingalpha.com/feed.xml',
            'category': 'markets',
            'interval': 120
        },

        # CryptoNews
        'cryptonews': {
            'url': 'https://cryptonews.com/news/feed/',
            'category': 'crypto',
            'interval': 120
        },

        # Decrypt (Crypto)
        'decrypt_crypto': {
            'url': 'https://decrypt.co/feed',
            'category': 'crypto',
            'interval': 120
        },

        # The Block (Crypto) - Updated URL
        'theblock_crypto': {
            'url': 'https://www.theblock.co/rss.xml',
            'category': 'crypto',
            'interval': 120
        },

        # Crypto.news (Comprehensive crypto coverage)
        'crypto_news': {
            'url': 'https://crypto.news/feed',
            'category': 'crypto',
            'interval': 120
        },

        # Crypto Briefing
        'crypto_briefing': {
            'url': 'https://cryptobriefing.com/feed',
            'category': 'crypto',
            'interval': 120
        },

        # Bitcoinist
        'bitcoinist': {
            'url': 'https://bitcoinist.com/feed',
            'category': 'crypto',
            'interval': 120
        },

        # U.Today (Crypto news)
        'utoday_crypto': {
            'url': 'https://u.today/rss',
            'category': 'crypto',
            'interval': 120
        },

        # ForexLive/InvestingLive (Real-time forex & markets)
        'investinglive': {
            'url': 'https://investinglive.com/feed',
            'category': 'markets',
            'interval': 120
        },

        # Sky News World
        'skynews_world': {
            'url': 'https://feeds.skynews.com/feeds/rss/world.xml',
            'category': 'usa_news',
            'interval': 120
        },

        # Al Jazeera
        'aljazeera': {
            'url': 'https://www.aljazeera.com/xml/rss/all.xml',
            'category': 'usa_news',
            'interval': 120
        },

        # France 24
        'france24': {
            'url': 'https://www.france24.com/en/rss',
            'category': 'usa_news',
            'interval': 120
        },


        # OilPrice.com
        'oilprice_news': {
            'url': 'https://oilprice.com/rss/main',
            'category': 'commodities',
            'interval': 120
        },

        # The Economist
        'economist': {
            'url': 'https://www.economist.com/finance-and-economics/rss.xml',
            'category': 'markets',
            'interval': 120
        },

        # Reuters Crypto
        'reuters_crypto': {
            'url': 'https://www.reuters.com/technology/crypto-currency',
            'category': 'crypto',
            'interval': 120
        },

        # FXStreet (Forex & Crypto)
        'fxstreet': {
            'url': 'https://www.fxstreet.com/rss/fxstreet-forex-news.xml',
            'category': 'markets',
            'interval': 120
        },

        # DailyFX
        'dailyfx': {
            'url': 'https://www.dailyfx.com/feeds/market-news',
            'category': 'markets',
            'interval': 120
        },

        # Bitcoin.com
        'bitcoin_com': {
            'url': 'https://blog.bitcoin.com/feed',
            'category': 'crypto',
            'interval': 120
        },

        # Gold & Commodity News
        'kitco_gold': {
            'url': 'https://www.kitco.com/rss/live_news_gold.xml',
            'category': 'commodities',
            'interval': 120
        },

        # Energy Intelligence
        'natural_gas_intel': {
            'url': 'https://www.naturalgasintel.com/feed/',
            'category': 'commodities',
            'interval': 120
        },

        # More Crypto Sources
        'coinmarketcap': {
            'url': 'https://coinmarketcap.com/headlines/rss/',
            'category': 'crypto',
            'interval': 120
        },
        'beincrypto': {
            'url': 'https://beincrypto.com/feed/',
            'category': 'crypto',
            'interval': 120
        },
    }

    @classmethod
    def get_all_feeds(cls) -> Dict:
        """Get all feeds combined"""
        all_feeds = {}
        all_feeds.update(cls.HIGH_PRIORITY_FEEDS)
        all_feeds.update(cls.MEDIUM_PRIORITY_FEEDS)
        all_feeds.update(cls.LOW_PRIORITY_FEEDS)
        return all_feeds


class RSSMonitor:
    def __init__(self, db, text_processor, callback: Optional[Callable] = None):
        """Initialize RSS monitor

        Args:
            db: Database instance
            text_processor: TextProcessor instance for categorization
            callback: Optional callback function to process each new article
        """
        self.db = db
        self.text_processor = text_processor
        self.callback = callback

        self.logger = logging.getLogger(__name__)

        # Feed configuration
        self.feeds = RSSFeedConfig.get_all_feeds()

        # Track last check times and ETags
        self.last_check = defaultdict(lambda: datetime.min)
        self.etags = {}
        self.last_modified = {}

        # Track seen article IDs to avoid duplicates
        self.seen_articles = set()

        # Control
        self.running = False
        self.threads = []

        self.logger.info(f"RSS Monitor initialized with {len(self.feeds)} feeds")

    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and clean up text"""
        if not text:
            return ""

        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)

        # Decode HTML entities (&amp; -> &, &lt; -> <, etc.)
        text = unescape(text)

        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)

        # Remove common artifacts
        text = re.sub(r'\[.*?\]', '', text)  # Remove [brackets]
        text = re.sub(r'\(.*?\)', '', text)  # Remove (parentheses) with content

        return text.strip()

    def _generate_article_id(self, entry: Dict) -> str:
        """Generate unique ID for article"""
        # Use link or guid, fallback to hash of title+published
        if hasattr(entry, 'id'):
            return hashlib.md5(entry.id.encode()).hexdigest()
        elif hasattr(entry, 'link'):
            return hashlib.md5(entry.link.encode()).hexdigest()
        else:
            # Fallback: hash title + published date
            unique_str = f"{entry.get('title', '')}_{entry.get('published', '')}"
            return hashlib.md5(unique_str.encode()).hexdigest()

    def _fetch_feed(self, feed_name: str, feed_config: Dict) -> Optional[feedparser.FeedParserDict]:
        """Fetch RSS feed with conditional GET support"""
        try:
            url = feed_config['url']

            # Build request with ETag/Last-Modified headers
            request_headers = {}
            if feed_name in self.etags:
                request_headers['If-None-Match'] = self.etags[feed_name]
            if feed_name in self.last_modified:
                request_headers['If-Modified-Since'] = self.last_modified[feed_name]

            # Parse feed
            feed = feedparser.parse(url, etag=request_headers.get('If-None-Match'),
                                   modified=request_headers.get('If-Modified-Since'))

            # Check status
            if hasattr(feed, 'status'):
                if feed.status == 304:
                    # Not modified - no new content
                    self.logger.debug(f"{feed_name}: Not modified (304)")
                    return None
                elif feed.status == 200:
                    # Success - update ETags
                    if hasattr(feed, 'etag'):
                        self.etags[feed_name] = feed.etag
                    if hasattr(feed, 'modified'):
                        self.last_modified[feed_name] = feed.modified
                elif feed.status >= 400:
                    self.logger.error(f"{feed_name}: HTTP {feed.status}")
                    return None

            return feed

        except Exception as e:
            self.logger.error(f"Error fetching {feed_name}: {e}")
            return None

    def _process_entry(self, entry: Dict, feed_name: str, feed_config: Dict):
        """Process a single RSS entry"""
        try:
            # Generate unique ID
            article_id = self._generate_article_id(entry)

            # Skip if already seen
            if article_id in self.seen_articles:
                return

            # Extract article data
            title = self._clean_html(entry.get('title', ''))
            link = entry.get('link', '').strip()
            summary = self._clean_html(entry.get('summary', entry.get('description', '')))

            # Get published date
            published = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                published = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                published = datetime(*entry.updated_parsed[:6])
            else:
                published = datetime.now()

            # ⚠️ FILTER: Only process articles from the last 7 days (1 week)
            now = datetime.now()
            time_diff = now - published
            if time_diff.total_seconds() > 604800:  # 604800 seconds = 7 days (168 hours)
                self.logger.debug(f"Skipping old article (published {time_diff} ago): {title[:50]}")
                return

            # Mark as seen AFTER time check (don't mark old articles as seen)
            self.seen_articles.add(article_id)

            # Combine title and summary for analysis
            full_text = f"{title}. {summary}" if summary else title

            # Get category from feed config or auto-categorize
            category = feed_config.get('category', 'usa_news')

            # Build article data structure (similar to tweet structure)
            article_data = {
                'article_id': article_id,
                'source': feed_name,
                'title': title,
                'text': full_text,
                'link': link,
                'summary': summary,
                'published_at': published.isoformat(),
                'created_at': datetime.now().isoformat(),
                'category': category,
                'source_type': 'rss'
            }

            self.logger.info(f"New article from {feed_name}: {title[:80]}")

            # Call callback if provided (for sentiment analysis pipeline)
            if self.callback:
                self.callback(article_data)

        except Exception as e:
            self.logger.error(f"Error processing entry from {feed_name}: {e}", exc_info=True)

    def _monitor_feed(self, feed_name: str, feed_config: Dict):
        """Monitor a single feed in a loop"""
        interval = feed_config['interval']

        self.logger.info(f"Starting monitor for {feed_name} (interval: {interval}s)")

        while self.running:
            try:
                # Check if it's time to fetch this feed
                now = datetime.now()
                if (now - self.last_check[feed_name]).total_seconds() < interval:
                    time.sleep(1)
                    continue

                # Update last check time
                self.last_check[feed_name] = now

                # Fetch feed
                feed = self._fetch_feed(feed_name, feed_config)

                if feed and hasattr(feed, 'entries'):
                    # Process new entries
                    for entry in feed.entries:
                        if not self.running:
                            break
                        self._process_entry(entry, feed_name, feed_config)

                    if feed.entries:
                        self.logger.info(f"{feed_name}: Processed {len(feed.entries)} entries")

                # Sleep a bit before checking again
                time.sleep(5)

            except Exception as e:
                self.logger.error(f"Error in monitor loop for {feed_name}: {e}", exc_info=True)
                time.sleep(60)  # Wait a minute before retrying

        self.logger.info(f"Monitor stopped for {feed_name}")

    def start(self):
        """Start monitoring all RSS feeds"""
        if self.running:
            self.logger.warning("RSS monitor already running")
            return

        self.running = True

        # Start a thread for each feed
        for feed_name, feed_config in self.feeds.items():
            thread = threading.Thread(
                target=self._monitor_feed,
                args=(feed_name, feed_config),
                daemon=True,
                name=f"RSS-{feed_name}"
            )
            thread.start()
            self.threads.append(thread)

        self.logger.info(f"RSS monitoring started with {len(self.threads)} feed threads")

    def stop(self):
        """Stop monitoring"""
        self.logger.info("Stopping RSS monitor...")
        self.running = False

        # Wait for threads to finish
        for thread in self.threads:
            thread.join(timeout=5)

        self.threads.clear()
        self.logger.info("RSS monitor stopped")

    def get_stats(self) -> Dict:
        """Get monitoring statistics"""
        return {
            'total_feeds': len(self.feeds),
            'articles_seen': len(self.seen_articles),
            'feeds_status': {
                name: {
                    'last_check': self.last_check[name].isoformat() if name in self.last_check else None,
                    'interval': config['interval'],
                    'category': config['category']
                }
                for name, config in self.feeds.items()
            }
        }

    def fetch_all_feeds(self):
        """Force immediate refresh of all RSS feeds (admin function)"""
        try:
            self.logger.warning("⚡ Admin triggered RSS refresh - fetching all feeds immediately")

            # Reset last check times to force immediate fetch
            for feed_name in self.feeds.keys():
                self.last_check[feed_name] = datetime.min

            self.logger.warning(f"✅ RSS refresh triggered for {len(self.feeds)} feeds")
            return True
        except Exception as e:
            self.logger.error(f"Error triggering RSS refresh: {e}")
            return False
