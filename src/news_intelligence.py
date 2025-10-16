import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import logging
from collections import defaultdict
import schedule
import time
import threading

from slack_notifier import SlackNotifier
from ollama_ai import OllamaAI


class NewsIntelligence:
    """Service for news trend detection, analysis, and briefings"""

    def __init__(self, db, slack_notifier: SlackNotifier = None, ollama_ai: OllamaAI = None):
        """Initialize News Intelligence service

        Args:
            db: Database instance
            slack_notifier: SlackNotifier instance
            ollama_ai: OllamaAI instance
        """
        self.db = db
        self.slack = slack_notifier
        self.ai = ollama_ai
        self.logger = logging.getLogger(__name__)

        # Track last briefing times
        self.last_briefings = {
            'morning': None,
            'midday': None,
            'evening': None
        }

        # Start scheduler in background
        self._start_scheduler()

    def _start_scheduler(self):
        """Start background scheduler for daily briefings"""
        def run_scheduler():
            # Schedule daily briefings
            schedule.every().day.at("08:00").do(self._send_morning_brief)
            schedule.every().day.at("12:00").do(self._send_midday_brief)
            schedule.every().day.at("18:00").do(self._send_evening_brief)

            # Schedule trend detection every 30 minutes
            schedule.every(30).minutes.do(self._detect_and_alert_trends)

            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute

        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        self.logger.info("📅 News Intelligence scheduler started")

    def calculate_trend_momentum(self, keyword: str, hours: int = 6) -> Dict[str, any]:
        """Calculate trend momentum for a keyword

        Args:
            keyword: The keyword to analyze
            hours: Time window for analysis

        Returns:
            Dict with momentum metrics
        """
        # Get current period articles
        current_articles = self.db.get_tweets_by_keyword(keyword, hours=hours, limit=1000)
        current_count = len(current_articles)

        # Get previous period for comparison
        previous_start = hours
        previous_end = hours * 2
        # This requires a time-range query (simplified here)
        # In production, you'd need a more sophisticated query
        all_recent = self.db.get_tweets_by_keyword(keyword, hours=previous_end, limit=1000)
        previous_count = len(all_recent) - current_count

        # Calculate momentum (velocity)
        if previous_count > 0:
            momentum = current_count / previous_count
        else:
            momentum = current_count / max(1, hours)  # Normalize by time

        # Calculate average sentiment
        sentiments = [a.get('sentiment_score', 0) for a in current_articles if a.get('sentiment_score') is not None]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

        # Get categories
        categories = set(a.get('category') for a in current_articles if a.get('category'))

        return {
            'keyword': keyword,
            'current_count': current_count,
            'previous_count': previous_count,
            'momentum': round(momentum, 2),
            'avg_sentiment': round(avg_sentiment, 2),
            'categories': list(categories),
            'trend_status': self._classify_trend(momentum),
            'velocity': 'rising' if momentum > 1.0 else 'falling' if momentum < 0.8 else 'stable'
        }

    def _classify_trend(self, momentum: float) -> str:
        """Classify trend based on momentum"""
        if momentum > 2.0:
            return "skyrocketing"
        elif momentum > 1.5:
            return "rising_fast"
        elif momentum > 1.0:
            return "trending_up"
        elif momentum > 0.8:
            return "stable"
        elif momentum > 0.5:
            return "cooling"
        else:
            return "declining"

    def detect_trending_topics(self, hours: int = 6, min_articles: int = 5) -> List[Dict]:
        """Detect currently trending topics

        Args:
            hours: Time window
            min_articles: Minimum articles to be considered trending

        Returns:
            List of trending topics with metrics
        """
        try:
            # Get top keywords (limit to 20 for performance)
            keywords = self.db.get_word_frequency_stats(hours=hours, limit=20)

            trending = []
            for kw in keywords[:15]:  # Further limit to top 15 for speed
                if kw['count'] < min_articles:
                    continue

                try:
                    momentum_data = self.calculate_trend_momentum(kw['word'], hours=hours)

                    # Only include if momentum > 1.0 (rising)
                    if momentum_data['momentum'] > 1.0:
                        trending.append(momentum_data)
                except Exception as e:
                    self.logger.warning(f"Error calculating momentum for {kw['word']}: {e}")
                    continue

            # Sort by momentum
            trending.sort(key=lambda x: x['momentum'], reverse=True)
            return trending

        except Exception as e:
            self.logger.error(f"Error detecting trending topics: {e}")
            return []

    def _detect_and_alert_trends(self):
        """Background task to detect trends and send alerts"""
        try:
            trending = self.detect_trending_topics(hours=3, min_articles=5)

            for trend in trending[:5]:  # Top 5 trends
                if trend['momentum'] > 1.5:  # Alert threshold
                    if self.slack:
                        self.slack.send_trend_alert(
                            keyword=trend['keyword'],
                            momentum=trend['momentum'],
                            article_count=trend['current_count'],
                            sentiment=trend['avg_sentiment']
                        )

            self.logger.info(f"Detected {len(trending)} trending topics")

        except Exception as e:
            self.logger.error(f"Error in trend detection: {e}")

    def generate_daily_brief(self, brief_type: str) -> Dict[str, any]:
        """Generate a news brief

        Args:
            brief_type: "morning", "midday", "evening", "day", or "week"

        Returns:
            Brief data dictionary
        """
        # Determine time range and article limits based on brief type
        brief_config = {
            'morning': {'hours': 12, 'limit': 200},    # Overnight
            'midday': {'hours': 4, 'limit': 100},      # Morning
            'evening': {'hours': 8, 'limit': 150},     # Afternoon
            'day': {'hours': 24, 'limit': 500},        # Full day
            'week': {'hours': 168, 'limit': 1000}      # Full week
        }

        config = brief_config.get(brief_type, {'hours': 8, 'limit': 100})
        hours = config['hours']
        article_limit = config['limit']

        # Get recent articles (scaled by brief type)
        articles = self.db.get_recent_tweets(hours=hours, limit=article_limit)

        if not articles:
            return {
                'type': brief_type,
                'summary': "No new articles in this period.",
                'stats': {},
                'top_stories': []
            }

        # Calculate stats
        sentiments = [a.get('sentiment_score', 0) for a in articles if a.get('sentiment_score') is not None]
        avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

        # Get category breakdown
        categories = defaultdict(int)
        for a in articles:
            cat = a.get('category', 'unknown')
            categories[cat] += 1

        top_category = max(categories.items(), key=lambda x: x[1])[0] if categories else 'N/A'

        # Get trending topics
        trending = self.db.get_word_frequency_stats(hours=hours, limit=10)

        # Generate AI summary if available
        if self.ai:
            summary = self.ai.generate_daily_brief(articles, brief_type)
        else:
            summary = f"Found {len(articles)} articles in the last {hours} hours."

        # Prepare top stories
        top_stories = []
        for kw in trending[:5]:
            tldr = None
            if self.ai:
                kw_articles = self.db.get_tweets_by_keyword(kw['word'], hours=hours, limit=5)
                tldr = self.ai.generate_tldr(kw['word'], kw_articles)

            top_stories.append({
                'keyword': kw['word'],
                'count': kw['count'],
                'summary': tldr or f"{kw['count']} articles about {kw['word']}",
                'sentiment': 0  # Could calculate from articles
            })

        return {
            'type': brief_type,
            'summary': summary,
            'stats': {
                'total_articles': len(articles),
                'avg_sentiment': round(avg_sentiment, 2),
                'trending_count': len(trending),
                'top_category': top_category
            },
            'top_stories': top_stories
        }

    def _send_morning_brief(self):
        """Send morning briefing"""
        try:
            brief = self.generate_daily_brief('morning')

            if self.slack:
                self.slack.send_daily_brief(
                    brief_type='morning',
                    summary=brief['summary'],
                    stats=brief['stats'],
                    top_stories=brief['top_stories']
                )

            self.last_briefings['morning'] = datetime.now()
            self.logger.info("📰 Morning brief sent")

        except Exception as e:
            self.logger.error(f"Error sending morning brief: {e}")

    def _send_midday_brief(self):
        """Send midday briefing"""
        try:
            brief = self.generate_daily_brief('midday')

            if self.slack:
                self.slack.send_daily_brief(
                    brief_type='midday',
                    summary=brief['summary'],
                    stats=brief['stats'],
                    top_stories=brief['top_stories']
                )

            self.last_briefings['midday'] = datetime.now()
            self.logger.info("📰 Midday brief sent")

        except Exception as e:
            self.logger.error(f"Error sending midday brief: {e}")

    def _send_evening_brief(self):
        """Send evening briefing"""
        try:
            brief = self.generate_daily_brief('evening')

            if self.slack:
                self.slack.send_daily_brief(
                    brief_type='evening',
                    summary=brief['summary'],
                    stats=brief['stats'],
                    top_stories=brief['top_stories']
                )

            self.last_briefings['evening'] = datetime.now()
            self.logger.info("📰 Evening brief sent")

        except Exception as e:
            self.logger.error(f"Error sending evening brief: {e}")

    def get_what_changed(self, last_visit: datetime) -> Dict[str, any]:
        """Calculate what's changed since user's last visit

        Args:
            last_visit: Timestamp of last visit

        Returns:
            Dict with change statistics
        """
        # Calculate time away (remove timezone info if present)
        now = datetime.now()
        if hasattr(last_visit, 'tzinfo') and last_visit.tzinfo is not None:
            last_visit = last_visit.replace(tzinfo=None)
        time_diff = now - last_visit
        hours_away = time_diff.total_seconds() / 3600

        # Format time away
        if hours_away < 1:
            time_away_text = f"{int(time_diff.total_seconds() / 60)} minutes"
        elif hours_away < 24:
            time_away_text = f"{int(hours_away)} hours"
        else:
            time_away_text = f"{int(hours_away / 24)} days"

        # Get new articles since last visit
        # This requires filtering by timestamp (simplified)
        all_recent = self.db.get_recent_tweets(hours=int(hours_away) + 1, limit=1000)
        new_articles = len(all_recent)

        # Get current trending topics
        current_trending = self.db.get_word_frequency_stats(hours=6, limit=20)
        current_topics = [kw['word'] for kw in current_trending]

        # Get previous trending (approximate)
        old_trending = self.db.get_word_frequency_stats(hours=int(hours_away) + 6, limit=20)
        old_topics = [kw['word'] for kw in old_trending[:10]]

        # Find new topics
        new_trending_topics = [t for t in current_topics[:10] if t not in old_topics]

        # Count sentiment changes (simplified)
        sentiment_changes = 0

        changes = {
            'new_articles': new_articles,
            'new_trends': len(new_trending_topics),
            'new_trending_topics': new_trending_topics,
            'sentiment_changes': sentiment_changes,
            'time_away': time_away_text,
            'hours_away': hours_away
        }

        # Generate AI summary if available
        if self.ai:
            changes['summary'] = self.ai.generate_what_changed_summary(changes)
        else:
            changes['summary'] = f"{new_articles} new articles since your last visit."

        return changes

    def compare_sources(self, keyword: str, hours: int = 24) -> Dict[str, any]:
        """Compare how different sources cover a topic

        Args:
            keyword: Topic to analyze
            hours: Time window

        Returns:
            Source comparison data
        """
        # Get all articles for this keyword
        articles = self.db.get_tweets_by_keyword(keyword, hours=hours, limit=100)

        # Group by source
        by_source = defaultdict(list)
        for article in articles:
            source = article.get('user_handle', 'Unknown')
            by_source[source].append(article)

        # Filter sources with at least 2 articles
        source_articles = {
            source: arts for source, arts in by_source.items()
            if len(arts) >= 2
        }

        # Get AI comparisons if available
        comparisons = {}
        if self.ai and source_articles:
            comparisons = self.ai.compare_sources(keyword, source_articles)

        # Calculate metrics for each source
        source_metrics = {}
        for source, arts in source_articles.items():
            sentiments = [a.get('sentiment_score', 0) for a in arts if a.get('sentiment_score') is not None]
            avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0

            source_metrics[source] = {
                'article_count': len(arts),
                'avg_sentiment': round(avg_sentiment, 2),
                'sentiment_label': 'positive' if avg_sentiment > 0.1 else 'negative' if avg_sentiment < -0.1 else 'neutral',
                'perspective': comparisons.get(source, 'Coverage detected')
            }

        return {
            'keyword': keyword,
            'source_count': len(source_metrics),
            'sources': source_metrics
        }

    def detect_story_threads(self, keyword: str, hours: int = 48) -> Dict[str, any]:
        """Detect if articles form a developing story thread

        Args:
            keyword: Topic to analyze
            hours: Time window

        Returns:
            Story thread analysis
        """
        articles = self.db.get_tweets_by_keyword(keyword, hours=hours, limit=50)

        if len(articles) < 3:
            return {
                'is_story_thread': False,
                'article_count': len(articles),
                'analysis': 'Not enough articles to form a thread'
            }

        # Sort by time
        articles.sort(key=lambda x: x.get('created_at', ''))

        # Use AI to detect thread
        if self.ai:
            thread_data = self.ai.detect_story_thread(articles)
        else:
            thread_data = {
                'is_story_thread': len(articles) >= 5,
                'analysis': f"{len(articles)} articles found about {keyword}"
            }

        # Add timeline
        thread_data['timeline'] = [
            {
                'timestamp': a.get('created_at'),
                'text': a.get('text', '')[:200],
                'source': a.get('user_handle'),
                'sentiment': a.get('sentiment_score', 0)
            }
            for a in articles[:15]
        ]

        return thread_data
