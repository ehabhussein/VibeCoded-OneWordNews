import tweepy
import os
import time
import json
from datetime import datetime
from typing import List, Dict, Any
import logging
from queue import Queue
import threading


class TwitterStreamListener(tweepy.StreamingClient):
    def __init__(self, bearer_token: str, message_queue: Queue, *args, **kwargs):
        super().__init__(bearer_token, *args, **kwargs)
        self.message_queue = message_queue
        self.logger = logging.getLogger(__name__)

    def on_tweet(self, tweet):
        """Called when a tweet is received"""
        try:
            # Extract tweet data
            tweet_data = {
                'tweet_id': str(tweet.id),
                'text': tweet.text,
                'created_at': datetime.utcnow().isoformat(),
                'author_id': str(tweet.author_id) if hasattr(tweet, 'author_id') else None,
                'raw_data': tweet.data
            }

            # Add to processing queue
            self.message_queue.put(tweet_data)
            self.logger.info(f"Received tweet: {tweet.id}")

        except Exception as e:
            self.logger.error(f"Error processing tweet: {e}")

    def on_errors(self, errors):
        """Called when errors occur"""
        self.logger.error(f"Stream errors: {errors}")

    def on_connection_error(self):
        """Called on connection error"""
        self.logger.error("Connection error occurred")

    def on_closed(self, response):
        """Called when stream is closed"""
        self.logger.warning("Stream closed")


class TwitterMonitor:
    def __init__(self, api_key: str, api_secret: str, bearer_token: str,
                 access_token: str = None, access_secret: str = None):
        """Initialize Twitter monitor"""
        self.api_key = api_key
        self.api_secret = api_secret
        self.bearer_token = bearer_token
        self.access_token = access_token
        self.access_secret = access_secret

        self.message_queue = Queue()
        self.stream_client = None
        self.api_client = None
        self.running = False
        self.poll_thread = None

        self.logger = logging.getLogger(__name__)

        # Initialize API client for user lookups
        self._init_api_client()

    def _init_api_client(self):
        """Initialize Twitter API v2 client"""
        try:
            self.api_client = tweepy.Client(
                bearer_token=self.bearer_token,
                consumer_key=self.api_key,
                consumer_secret=self.api_secret,
                access_token=self.access_token,
                access_token_secret=self.access_secret,
                wait_on_rate_limit=True
            )
            self.logger.info("Twitter API client initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize API client: {e}")

    def start_stream(self, keywords: List[str], usernames: List[str] = None):
        """Start streaming tweets"""
        try:
            # Create streaming client
            self.stream_client = TwitterStreamListener(
                self.bearer_token,
                self.message_queue
            )

            # Delete existing rules
            rules = self.stream_client.get_rules()
            if rules.data:
                rule_ids = [rule.id for rule in rules.data]
                self.stream_client.delete_rules(rule_ids)
                self.logger.info(f"Deleted {len(rule_ids)} existing rules")

            # Build query
            rules_to_add = []

            # Add keyword rules
            if keywords:
                keyword_query = ' OR '.join([f'"{kw}"' for kw in keywords])
                rules_to_add.append(tweepy.StreamRule(keyword_query))

            # Add username rules
            if usernames:
                for username in usernames:
                    rules_to_add.append(tweepy.StreamRule(f"from:{username}"))

            # Add rules
            if rules_to_add:
                self.stream_client.add_rules(rules_to_add)
                self.logger.info(f"Added {len(rules_to_add)} streaming rules")

            # Start filtering
            self.logger.info("Starting Twitter stream...")
            self.stream_client.filter(
                tweet_fields=['created_at', 'public_metrics', 'author_id', 'conversation_id'],
                threaded=True
            )

        except Exception as e:
            self.logger.error(f"Error starting stream: {e}")
            raise

    def stop_stream(self):
        """Stop streaming"""
        if self.stream_client:
            self.stream_client.disconnect()
            self.logger.info("Stream stopped")

    def search_recent_tweets(self, query: str, max_results: int = 100) -> List[Dict]:
        """Search for recent tweets"""
        try:
            tweets = self.api_client.search_recent_tweets(
                query=query,
                max_results=max_results,
                tweet_fields=['created_at', 'public_metrics', 'author_id'],
                user_fields=['username', 'name'],
                expansions=['author_id']
            )

            results = []
            if tweets.data:
                # Create user lookup dictionary
                users = {user.id: user for user in tweets.includes.get('users', [])}

                for tweet in tweets.data:
                    user = users.get(tweet.author_id)

                    tweet_data = {
                        'tweet_id': str(tweet.id),
                        'text': tweet.text,
                        'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                        'user_handle': user.username if user else None,
                        'user_name': user.name if user else None,
                        'retweet_count': tweet.public_metrics.get('retweet_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                        'like_count': tweet.public_metrics.get('like_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                        'reply_count': tweet.public_metrics.get('reply_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                        'raw_data': tweet.data
                    }
                    results.append(tweet_data)

            self.logger.info(f"Retrieved {len(results)} tweets for query: {query}")
            return results

        except Exception as e:
            self.logger.error(f"Error searching tweets: {e}")
            return []

    def get_user_tweets(self, username: str, max_results: int = 100) -> List[Dict]:
        """Get tweets from a specific user"""
        try:
            # Get user ID
            user = self.api_client.get_user(username=username)
            if not user.data:
                self.logger.warning(f"User not found: {username}")
                return []

            user_id = user.data.id

            # Get tweets
            tweets = self.api_client.get_users_tweets(
                id=user_id,
                max_results=max_results,
                tweet_fields=['created_at', 'public_metrics'],
                exclude=['retweets', 'replies']
            )

            results = []
            if tweets.data:
                for tweet in tweets.data:
                    tweet_data = {
                        'tweet_id': str(tweet.id),
                        'text': tweet.text,
                        'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                        'user_handle': username,
                        'user_name': user.data.name,
                        'retweet_count': tweet.public_metrics.get('retweet_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                        'like_count': tweet.public_metrics.get('like_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                        'reply_count': tweet.public_metrics.get('reply_count', 0) if hasattr(tweet, 'public_metrics') else 0,
                        'raw_data': tweet.data
                    }
                    results.append(tweet_data)

            self.logger.info(f"Retrieved {len(results)} tweets from @{username}")
            return results

        except Exception as e:
            self.logger.error(f"Error getting user tweets: {e}")
            return []

    def get_queue(self) -> Queue:
        """Get the message queue"""
        return self.message_queue

    def start_polling(self, keywords: List[str], poll_interval: int = 60):
        """Start polling for tweets (Free tier compatible)"""
        self.running = True
        self.poll_thread = threading.Thread(
            target=self._poll_loop,
            args=(keywords, poll_interval),
            daemon=True
        )
        self.poll_thread.start()
        self.logger.info(f"Started Twitter polling (every {poll_interval}s)")

    def _poll_loop(self, keywords: List[str], poll_interval: int):
        """Poll for tweets periodically"""
        last_tweet_ids = set()

        while self.running:
            try:
                # Build search query (limit to top 3 keywords to stay within rate limits)
                query = ' OR '.join([f'"{kw}"' for kw in keywords[:3]])
                query += ' -is:retweet'  # Exclude retweets

                # Search for recent tweets (max 10 to conserve API quota)
                tweets = self.search_recent_tweets(query, max_results=10)

                # Add new tweets to queue
                new_count = 0
                for tweet in tweets:
                    tweet_id = tweet['tweet_id']
                    if tweet_id not in last_tweet_ids:
                        self.message_queue.put(tweet)
                        last_tweet_ids.add(tweet_id)
                        new_count += 1

                # Keep only recent 1000 IDs in memory
                if len(last_tweet_ids) > 1000:
                    last_tweet_ids = set(list(last_tweet_ids)[-1000:])

                if new_count > 0:
                    self.logger.info(f"Polled {new_count} new tweets")

                # Sleep before next poll
                time.sleep(poll_interval)

            except Exception as e:
                self.logger.error(f"Error in polling loop: {e}")
                time.sleep(poll_interval)

        self.logger.info("Polling stopped")

    def start_user_polling(self, username: str, poll_interval: int = 300):
        """Start polling for a specific user's tweets (Free tier compatible)"""
        self.running = True
        self.poll_thread = threading.Thread(
            target=self._user_poll_loop,
            args=(username, poll_interval),
            daemon=True
        )
        self.poll_thread.start()
        self.logger.info(f"Started user polling for @{username} (every {poll_interval}s)")

    def _user_poll_loop(self, username: str, poll_interval: int):
        """Poll for a specific user's tweets periodically"""
        last_tweet_ids = set()

        while self.running:
            try:
                # Get tweets from specific user (much more efficient than keyword search)
                tweets = self.get_user_tweets(username, max_results=10)

                # Add new tweets to queue
                new_count = 0
                for tweet in tweets:
                    tweet_id = tweet['tweet_id']
                    if tweet_id not in last_tweet_ids:
                        self.message_queue.put(tweet)
                        last_tweet_ids.add(tweet_id)
                        new_count += 1

                # Keep only recent 500 IDs in memory
                if len(last_tweet_ids) > 500:
                    last_tweet_ids = set(list(last_tweet_ids)[-500:])

                if new_count > 0:
                    self.logger.info(f"Polled {new_count} new tweets from @{username}")

                # Sleep before next poll
                time.sleep(poll_interval)

            except Exception as e:
                self.logger.error(f"Error in user polling loop: {e}")
                time.sleep(poll_interval)

        self.logger.info("User polling stopped")

    def stop_polling(self):
        """Stop polling"""
        self.running = False
        self.logger.info("Stopping Twitter polling...")


class TwitterConfig:
    """Configuration for Twitter monitoring - @realDonaldTrump ONLY"""

    # Only monitor Trump's main account
    TRUMP_ACCOUNTS = ['realDonaldTrump']

    # No keywords - direct account monitoring only
    KEYWORDS = []

    # No hashtags - direct account monitoring only
    HASHTAGS = []

    @classmethod
    def get_all_usernames(cls) -> List[str]:
        """Get all usernames to monitor"""
        return cls.TRUMP_ACCOUNTS

    @classmethod
    def get_all_keywords(cls) -> List[str]:
        """Get all keywords to monitor - empty for direct account monitoring"""
        return []
