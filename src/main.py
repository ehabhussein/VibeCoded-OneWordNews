#!/usr/bin/env python3
"""
OneWordNews - Main Application
Real-time monitoring of news, crypto prices, and market events
"""

import os
import sys
import logging
import time
import threading
from queue import Empty
from datetime import datetime, timedelta

# Import our modules
from database import Database
from twitter_stream import TwitterMonitor, TwitterConfig
from text_processor import TextProcessor
from sentiment_analyzer_cpu import SentimentAnalyzerCPU  # CPU-based sentiment analysis
from entity_extractor import EntityExtractor  # Entity recognition
from web_app import WebApp
from binance_monitor import BinanceMonitor
from rss_monitor import RSSMonitor
from forex_factory_scraper import ForexFactoryScraper
from message_queue import MessageQueue
from slack_notifier import SlackNotifier
from ollama_ai import OllamaAI
from news_intelligence import NewsIntelligence


# Configure logging - WARNING level only (less verbose)
logging.basicConfig(
    level=logging.WARNING,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/app/logs/twitter_bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

# Set all library loggers to WARNING or higher
logging.getLogger('werkzeug').setLevel(logging.WARNING)
logging.getLogger('engineio').setLevel(logging.WARNING)
logging.getLogger('socketio').setLevel(logging.WARNING)
logging.getLogger('urllib3').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('rss_monitor').setLevel(logging.WARNING)
logging.getLogger('sentiment_analyzer_cpu').setLevel(logging.WARNING)
logging.getLogger('twitter_stream').setLevel(logging.WARNING)
logging.getLogger('binance_monitor').setLevel(logging.WARNING)
logging.getLogger('web_app').setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


class OneWordNews:
    def __init__(self):
        """Initialize One Word News"""
        logger.info("Initializing One Word News...")

        # Get environment variables
        self.twitter_api_key = os.getenv('TWITTER_API_KEY')
        self.twitter_api_secret = os.getenv('TWITTER_API_SECRET')
        self.twitter_bearer_token = os.getenv('TWITTER_BEARER_TOKEN')
        self.twitter_access_token = os.getenv('TWITTER_ACCESS_TOKEN')
        self.twitter_access_secret = os.getenv('TWITTER_ACCESS_SECRET')

        self.db_path = os.getenv('DATABASE_PATH', '/app/data/twitter_bot.db')

        # Binance settings
        self.binance_api_key = os.getenv('BINANCE_API_KEY')
        self.binance_api_secret = os.getenv('BINANCE_API_SECRET')
        self.binance_use_testnet = os.getenv('BINANCE_USE_TESTNET', 'false').lower() == 'true'
        self.binance_symbols = os.getenv('BINANCE_SYMBOLS', 'BTCUSDT,ETHUSDT,SOLUSDT,TRUMPUSDT,PEPEUSDT,ANIMEUSDT,PAXGUSDT,ADAUSDT,SUIUSDT,WLFIUSDT,DOGEUSDT').split(',')

        # Initialize components
        self.db = Database(self.db_path)
        self.text_processor = TextProcessor()
        self.sentiment_analyzer = SentimentAnalyzerCPU()  # CPU-based sentiment analysis
        self.entity_extractor = EntityExtractor()  # Named entity recognition

        # Initialize Twitter monitor if credentials available
        self.twitter_monitor = None
        if self.twitter_bearer_token:
            self.twitter_monitor = TwitterMonitor(
                api_key=self.twitter_api_key,
                api_secret=self.twitter_api_secret,
                bearer_token=self.twitter_bearer_token,
                access_token=self.twitter_access_token,
                access_secret=self.twitter_access_secret
            )
        else:
            logger.warning("Twitter credentials not found. Streaming disabled.")

        # Initialize Binance monitor
        self.binance_monitor = None
        if self.binance_api_key and self.binance_api_secret:
            self.binance_monitor = BinanceMonitor(
                api_key=self.binance_api_key,
                api_secret=self.binance_api_secret,
                symbols=self.binance_symbols,
                db=self.db,
                use_testnet=self.binance_use_testnet
            )
            logger.info(f"Binance monitor initialized for {len(self.binance_symbols)} symbols")
        else:
            logger.warning("Binance credentials not found. Price monitoring disabled.")

        # Initialize RSS monitor first (needed for WebApp reference)
        self.rss_monitor = RSSMonitor(
            db=self.db,
            text_processor=self.text_processor,
            callback=None  # Will be set in process_article
        )

        # Initialize news intelligence services
        self.slack_webhook_url = os.getenv('SLACK_WEBHOOK_URL')
        self.ollama_base_url = os.getenv('OLLAMA_BASE_URL', 'http://host.docker.internal:11434')
        self.ollama_model = os.getenv('OLLAMA_MODEL', 'phi4:latest')

        self.slack_notifier = None
        self.ollama_ai = None
        self.news_intelligence = None

        if self.slack_webhook_url:
            self.slack_notifier = SlackNotifier(webhook_url=self.slack_webhook_url)
            logger.info("Slack notifier initialized")
        else:
            logger.warning("Slack webhook URL not found. Notifications disabled.")

        # Initialize Ollama AI
        try:
            self.ollama_ai = OllamaAI(base_url=self.ollama_base_url, model=self.ollama_model)
            logger.info(f"Ollama AI initialized with model: {self.ollama_model}")
        except Exception as e:
            logger.warning(f"Ollama AI initialization failed: {e}. AI features disabled.")

        # Initialize news intelligence (combines all intelligence features)
        self.news_intelligence = NewsIntelligence(
            db=self.db,
            slack_notifier=self.slack_notifier,
            ollama_ai=self.ollama_ai
        )
        logger.info("News Intelligence service initialized with scheduled briefings and trend detection")

        # Initialize web app (pass binance_monitor for crypto price display and rss_monitor for admin controls)
        self.web_app = WebApp(
            db=self.db,
            binance_monitor=self.binance_monitor,
            rss_monitor=self.rss_monitor,
            news_intelligence=self.news_intelligence,
            port=8080
        )

        # Initialize message queue for Redis pub/sub
        self.mq = MessageQueue()

        # Set web_app reference in binance_monitor for real-time updates
        if self.binance_monitor:
            self.binance_monitor.web_app = self.web_app

        # Set callback for RSS monitor after initialization
        self.rss_monitor.callback = self.process_article

        # Initialize Forex Factory scraper
        self.forex_scraper = ForexFactoryScraper()
        self.forex_monitoring_thread = None
        self.last_forex_events = {}

        # Processing thread control
        self.running = False
        self.processing_thread = None
        self.cleanup_thread = None

        logger.info("Bot initialized successfully")

    def process_article(self, article_data: dict):
        """Process a single RSS article"""
        try:
            text = article_data.get('text', '')
            if not text:
                return

            logger.info(f"Processing article: {article_data.get('title', '')[:80]}")

            # Extract keywords
            keywords = self.text_processor.extract_keywords(text)
            hashtags = self.text_processor.extract_hashtags(text)

            # Category is already set by RSS monitor
            category = article_data.get('category', 'usa_news')

            # Analyze sentiment
            sentiment = self.sentiment_analyzer.analyze_sentiment(text)

            # Calculate market impact
            market_impact = self.sentiment_analyzer.get_market_impact_score(sentiment, text)

            # Extract entities (companies, people, locations, etc.)
            entities_data = self.entity_extractor.extract_entities(text)

            # Convert article to tweet-like structure for database
            tweet_data = {
                'tweet_id': article_data['article_id'],
                'text': article_data['title'],  # Use title as main text
                'created_at': article_data['published_at'],
                'user_handle': article_data['source'],
                'user_name': article_data['source'],
                'retweet_count': 0,
                'like_count': 0,
                'reply_count': 0,
                'category': category
            }

            # Save to database
            self.db.insert_tweet(tweet_data)
            self.db.insert_sentiment(
                tweet_id=article_data['article_id'],
                sentiment_score=sentiment['score'],
                sentiment_label=sentiment['label'],
                confidence=sentiment.get('confidence'),
                model_response=sentiment.get('raw_response')
            )

            # Save keywords
            for keyword in keywords[:20]:  # Limit to top 20
                if self.text_processor.is_relevant_keyword(keyword):
                    self.db.insert_word_frequency(
                        word=keyword,
                        category=category,
                        tweet_id=article_data['article_id']
                    )

            # Save entities
            if entities_data and entities_data.get('all_entities'):
                self.db.insert_entities(
                    tweet_id=article_data['article_id'],
                    entities=entities_data['all_entities']
                )

            # Publish to Redis hub
            article_with_sentiment = {
                **tweet_data,
                'sentiment': sentiment,
                'sentiment_score': sentiment['score'],
                'sentiment_label': sentiment['label'],
                'market_impact': market_impact,
                'keywords': keywords[:10],
                'link': article_data.get('link', '')
            }
            self.mq.publish_tweet(article_with_sentiment)

            logger.info(f"Article processed: {category} | Sentiment: {sentiment['label']} ({sentiment['score']:.2f})")

        except Exception as e:
            logger.error(f"Error processing article: {e}", exc_info=True)

    def process_tweet(self, tweet_data: dict):
        """Process a single tweet"""
        try:
            text = tweet_data.get('text', '')
            if not text:
                return

            logger.info(f"Processing tweet: {tweet_data.get('tweet_id')}")

            # Extract keywords
            keywords = self.text_processor.extract_keywords(text)
            hashtags = self.text_processor.extract_hashtags(text)

            # Categorize
            category = self.text_processor.categorize_text(text, hashtags)
            tweet_data['category'] = category

            # Analyze sentiment
            sentiment = self.sentiment_analyzer.analyze_sentiment(text)

            # Calculate market impact
            market_impact = self.sentiment_analyzer.get_market_impact_score(sentiment, text)

            # Save to database
            self.db.insert_tweet(tweet_data)
            self.db.insert_sentiment(
                tweet_id=tweet_data['tweet_id'],
                sentiment_score=sentiment['score'],
                sentiment_label=sentiment['label'],
                confidence=sentiment.get('confidence'),
                model_response=sentiment.get('raw_response')
            )

            # Save keywords
            for keyword in keywords[:20]:  # Limit to top 20
                if self.text_processor.is_relevant_keyword(keyword):
                    self.db.insert_word_frequency(
                        word=keyword,
                        category=category,
                        tweet_id=tweet_data['tweet_id']
                    )

            # Publish to Redis hub
            tweet_with_sentiment = {
                **tweet_data,
                'sentiment': sentiment,
                'sentiment_score': sentiment['score'],
                'sentiment_label': sentiment['label'],
                'market_impact': market_impact,
                'keywords': keywords[:10]
            }
            self.mq.publish_tweet(tweet_with_sentiment)

            logger.info(f"Tweet processed: {category} | Sentiment: {sentiment['label']} ({sentiment['score']:.2f})")

        except Exception as e:
            logger.error(f"Error processing tweet: {e}", exc_info=True)

    def process_queue(self):
        """Process tweets from the queue"""
        logger.info("Starting queue processing thread")

        while self.running:
            try:
                # Get tweet from queue with timeout
                tweet_data = self.twitter_monitor.get_queue().get(timeout=1)
                self.process_tweet(tweet_data)

            except Empty:
                # No tweets in queue, continue
                continue
            except Exception as e:
                logger.error(f"Error in queue processing: {e}", exc_info=True)
                time.sleep(1)

        logger.info("Queue processing thread stopped")

    def fetch_historical_tweets(self):
        """Fetch historical tweets to populate database"""
        logger.info("Fetching historical tweets...")

        if not self.twitter_monitor:
            logger.warning("Twitter monitor not available")
            return

        try:
            # Fetch tweets from key accounts
            for username in TwitterConfig.get_all_usernames()[:5]:  # Limit to first 5
                try:
                    logger.info(f"Fetching tweets from @{username}")
                    tweets = self.twitter_monitor.get_user_tweets(username, max_results=20)

                    for tweet in tweets:
                        self.process_tweet(tweet)

                    time.sleep(2)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error fetching tweets from @{username}: {e}")

            # Search for keywords
            for keyword in ['Trump', 'FOMC', 'Bitcoin', 'inflation']:
                try:
                    logger.info(f"Searching tweets for: {keyword}")
                    tweets = self.twitter_monitor.search_recent_tweets(keyword, max_results=20)

                    for tweet in tweets:
                        self.process_tweet(tweet)

                    time.sleep(2)  # Rate limiting
                except Exception as e:
                    logger.error(f"Error searching for {keyword}: {e}")

            logger.info("Historical tweets fetched successfully")

        except Exception as e:
            logger.error(f"Error fetching historical tweets: {e}")

    def start_streaming(self):
        """Start Twitter polling (Free tier compatible)"""
        if not self.twitter_monitor:
            logger.warning("Cannot start polling - Twitter monitor not available")
            return

        try:
            logger.info("Starting Twitter polling for @realDonaldTrump...")

            # Get username to monitor
            usernames = TwitterConfig.get_all_usernames()

            if not usernames:
                logger.warning("No Twitter usernames configured")
                return

            # Use user-specific polling instead of keyword search
            # Poll every 300 seconds (5 minutes) for Trump's account
            self.twitter_monitor.start_user_polling(
                username=usernames[0],  # realDonaldTrump
                poll_interval=300  # 5 minutes between polls
            )

            logger.info(f"Twitter polling started for @{usernames[0]} (checking every 5 minutes)")

        except Exception as e:
            logger.error(f"Error starting polling: {e}")

    def start(self):
        """Start the bot"""
        try:
            logger.info("=" * 60)
            logger.info("ONE WORD NEWS STARTING")
            logger.info("=" * 60)

            self.running = True

            # Start RSS monitoring
            self.rss_monitor.start()
            logger.info("RSS feed monitoring started")

            # Start Forex Factory calendar monitoring
            self.forex_monitoring_thread = threading.Thread(
                target=self.monitor_forex_calendar,
                daemon=True
            )
            self.forex_monitoring_thread.start()
            logger.info("Forex Factory calendar monitoring started")

            # Start database cleanup monitoring
            self.cleanup_thread = threading.Thread(
                target=self.monitor_database_cleanup,
                daemon=True
            )
            self.cleanup_thread.start()
            logger.info("Database cleanup monitoring started (runs daily)")

            # Start Binance monitoring if available
            if self.binance_monitor:
                self.binance_monitor.start()
                logger.info("Binance price monitoring started")

            # Start Twitter monitoring if available (Trump only)
            if self.twitter_monitor:
                # Start streaming
                self.start_streaming()

                # Start queue processing thread
                self.processing_thread = threading.Thread(
                    target=self.process_queue,
                    daemon=True
                )
                self.processing_thread.start()

                # Note: Historical tweets disabled to avoid rate limits
                # You can uncomment this to fetch historical data
                # historical_thread = threading.Thread(
                #     target=self.fetch_historical_tweets,
                #     daemon=True
                # )
                # historical_thread.start()
                logger.info("Twitter streaming started (historical fetch disabled to avoid rate limits)")
            else:
                logger.warning("Running in web-only mode (no Twitter streaming)")

            # Start web app (blocking) - this MUST be last
            logger.info("Starting web dashboard...")
            self.web_app.run()

        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            self.stop()
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            self.stop()

    def monitor_forex_calendar(self):
        """Monitor Forex Factory calendar for high-impact USD events"""
        logger.warning("Starting Forex Factory calendar monitoring (USD events only)")

        while self.running:
            try:
                # Get current week and next week data (using synchronous method)
                logger.warning("Fetching Forex Factory calendar data for current and next week...")

                # Get current week
                current_week_data = self.forex_scraper.get_week_data()

                # Get next week (7 days from now)
                next_week_date = datetime.now() + timedelta(days=7)
                next_week_data = self.forex_scraper.get_week_data_by_date(next_week_date)

                # Combine events from both weeks
                events = []
                if current_week_data and current_week_data.get('events'):
                    events.extend(current_week_data['events'])
                if next_week_data and next_week_data.get('events'):
                    events.extend(next_week_data['events'])

                if events:
                    logger.warning(f"Forex Factory returned {len(events)} total events from both weeks")

                    # Process high and medium impact USD events only
                    usd_events_processed = 0
                    today = datetime.now().date()

                    for event in events:
                        event_id = event.get('id')
                        impact = event.get('impact', '')
                        currency = event.get('currency', '')
                        event_date_str = event.get('date')

                        # Parse event date
                        try:
                            if event_date_str:
                                event_date = datetime.fromisoformat(event_date_str).date()
                            else:
                                event_date = today
                        except:
                            event_date = today

                        # Only process events from today onwards
                        if event_date < today:
                            continue

                        # Only process USD events
                        if currency != 'USD':
                            continue

                        # Process High, Medium, and Low impact events
                        if impact not in ['High', 'Medium', 'Low']:
                            continue

                        # Check if we've already alerted for this event
                        if event_id in self.last_forex_events:
                            continue

                        # Mark as seen
                        self.last_forex_events[event_id] = True
                        usd_events_processed += 1

                        # Create alert for high-impact events
                        event_name = event.get('event_name', 'Unknown Event')
                        event_time = event.get('time', '')

                        # Format the date nicely
                        date_str = event_date.strftime('%A, %B %d, %Y')
                        if event_date == today:
                            date_str = f"TODAY ({date_str})"
                        elif event_date == today + timedelta(days=1):
                            date_str = f"TOMORROW ({date_str})"

                        message = f"FOREX CALENDAR EVENT\n\n"
                        message += f"Date: {date_str}\n"
                        message += f"Time: {event_time}\n"
                        message += f"Impact: {impact.upper()}\n"
                        message += f"Currency: {currency}\n"
                        message += f"Event: {event_name}\n"

                        if event.get('forecast'):
                            message += f"Forecast: {event['forecast']}\n"
                        if event.get('previous'):
                            message += f"Previous: {event['previous']}\n"

                        severity = 'high' if impact == 'High' else ('medium' if impact == 'Medium' else 'low')

                        self.db.insert_alert(
                            alert_type='forex_calendar',
                            category='forex',
                            severity=severity,
                            message=message,
                            data=event
                        )

                        logger.warning(f"Forex calendar alert created: {impact} USD - {event_name} on {date_str}")

                    logger.warning(f"Processed {usd_events_processed} new USD events (from today onwards)")
                else:
                    logger.warning("No events returned from Forex Factory")

                # Check every 30 minutes
                logger.warning("Forex calendar check complete. Sleeping for 30 minutes...")
                time.sleep(1800)

            except Exception as e:
                logger.error(f"Error in Forex calendar monitoring: {e}", exc_info=True)
                time.sleep(300)  # Wait 5 minutes on error before retry

        logger.info("Forex calendar monitoring stopped")

    def monitor_database_cleanup(self):
        """Monitor and cleanup old database records daily"""
        logger.warning("Starting database cleanup monitoring (runs daily)")

        # Initial cleanup on startup
        try:
            logger.warning("Running initial database cleanup...")
            deleted_counts = self.db.cleanup_old_data(days_to_keep=7)

            if deleted_counts:
                logger.warning(f"Database cleanup completed:")
                logger.warning(f"  - Word frequency records deleted: {deleted_counts.get('word_frequency', 0)}")
                logger.warning(f"  - Tweets deleted: {deleted_counts.get('tweets', 0)}")
                logger.warning(f"  - Sentiment analysis records deleted: {deleted_counts.get('sentiment_analysis', 0)}")
                logger.warning(f"  - General alerts deleted: {deleted_counts.get('alerts', 0)}")
                logger.warning(f"  - Forex alerts (>14 days) deleted: {deleted_counts.get('forex_alerts', 0)}")
        except Exception as e:
            logger.error(f"Error during initial cleanup: {e}", exc_info=True)

        # Sleep for 24 hours between cleanups
        while self.running:
            try:
                # Sleep for 24 hours (86400 seconds)
                time.sleep(86400)

                if not self.running:
                    break

                logger.warning("Running scheduled database cleanup...")
                deleted_counts = self.db.cleanup_old_data(days_to_keep=7)

                if deleted_counts:
                    logger.warning(f"Database cleanup completed:")
                    logger.warning(f"  - Word frequency records deleted: {deleted_counts.get('word_frequency', 0)}")
                    logger.warning(f"  - Tweets deleted: {deleted_counts.get('tweets', 0)}")
                    logger.warning(f"  - Sentiment analysis records deleted: {deleted_counts.get('sentiment_analysis', 0)}")
                    logger.warning(f"  - General alerts deleted: {deleted_counts.get('alerts', 0)}")
                    logger.warning(f"  - Forex alerts (>14 days) deleted: {deleted_counts.get('forex_alerts', 0)}")
                else:
                    logger.warning("Database cleanup completed with no records deleted")

            except Exception as e:
                logger.error(f"Error in database cleanup monitoring: {e}", exc_info=True)
                time.sleep(3600)  # Wait 1 hour on error before retry

        logger.info("Database cleanup monitoring stopped")

    def stop(self):
        """Stop the bot"""
        logger.info("Stopping bot...")

        self.running = False

        if self.rss_monitor:
            self.rss_monitor.stop()

        if self.binance_monitor:
            self.binance_monitor.stop()

        if self.twitter_monitor:
            self.twitter_monitor.stop_polling()

        if self.processing_thread:
            self.processing_thread.join(timeout=5)

        if self.forex_monitoring_thread:
            self.forex_monitoring_thread.join(timeout=5)

        if self.cleanup_thread:
            self.cleanup_thread.join(timeout=5)

        logger.info("Bot stopped")


def main():
    """Main entry point"""
    # Create necessary directories
    os.makedirs('/app/data', exist_ok=True)
    os.makedirs('/app/logs', exist_ok=True)

    # Create and start bot
    bot = OneWordNews()
    bot.start()


if __name__ == '__main__':
    main()
