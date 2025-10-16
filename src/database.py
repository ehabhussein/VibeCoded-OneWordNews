import sqlite3
import os
from datetime import datetime
from typing import List, Dict, Any, Optional
import json


class Database:
    def __init__(self, db_path: str = "data/twitter_bot.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.init_database()

    def get_connection(self):
        """Get database connection with optimized settings"""
        # Increased timeout to 30 seconds for high concurrency
        conn = sqlite3.connect(self.db_path, timeout=30.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row

        # Enable WAL mode for better concurrent writes
        conn.execute("PRAGMA journal_mode=WAL")

        # Optimize for performance
        conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes, still safe
        conn.execute("PRAGMA cache_size=10000")    # Larger cache
        conn.execute("PRAGMA temp_store=MEMORY")   # Use memory for temp tables

        return conn

    def init_database(self):
        """Initialize database schema"""
        conn = self.get_connection()
        cursor = conn.cursor()

        # Tweets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tweets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT UNIQUE NOT NULL,
                user_handle TEXT NOT NULL,
                user_name TEXT,
                text TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                retweet_count INTEGER DEFAULT 0,
                like_count INTEGER DEFAULT 0,
                reply_count INTEGER DEFAULT 0,
                category TEXT,
                url TEXT,
                raw_data TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Sentiment analysis table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sentiment_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT NOT NULL,
                sentiment_score REAL NOT NULL,
                sentiment_label TEXT NOT NULL,
                confidence REAL,
                model_response TEXT,
                analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tweet_id) REFERENCES tweets(tweet_id)
            )
        """)

        # Word frequency table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS word_frequency (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                word TEXT NOT NULL,
                count INTEGER DEFAULT 1,
                category TEXT,
                tweet_id TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tweet_id) REFERENCES tweets(tweet_id)
            )
        """)

        # Time series aggregations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS time_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                interval_start TIMESTAMP NOT NULL,
                interval_end TIMESTAMP NOT NULL,
                tweet_count INTEGER DEFAULT 0,
                avg_sentiment REAL,
                total_engagement INTEGER DEFAULT 0,
                top_words TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Alerts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                alert_type TEXT NOT NULL,
                category TEXT,
                severity TEXT,
                message TEXT NOT NULL,
                data TEXT,
                sent_to_telegram BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # User visits table (for "What Changed" feature)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT 'default',
                visit_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                session_id TEXT
            )
        """)

        # Trend history table (for momentum tracking)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trend_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword TEXT NOT NULL,
                article_count INTEGER DEFAULT 0,
                momentum REAL DEFAULT 0,
                avg_sentiment REAL DEFAULT 0,
                categories TEXT,
                trend_status TEXT,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Entities table (for named entity recognition)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS entities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT NOT NULL,
                entity_text TEXT NOT NULL,
                entity_label TEXT NOT NULL,
                entity_count INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tweet_id) REFERENCES tweets(tweet_id)
            )
        """)

        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tweets_created_at ON tweets(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tweets_category ON tweets(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tweets_user_handle ON tweets(user_handle)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_tweet_id ON sentiment_analysis(tweet_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_word_timestamp ON word_frequency(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_word_category ON word_frequency(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeseries_category ON time_series(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeseries_interval ON time_series(interval_start)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_tweet_id ON entities(tweet_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_text ON entities(entity_text)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_label ON entities(entity_label)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_entities_created_at ON entities(created_at)")

        # Migration: Add url column to existing tweets table if it doesn't exist
        cursor.execute("PRAGMA table_info(tweets)")
        columns = [column[1] for column in cursor.fetchall()]
        if 'url' not in columns:
            cursor.execute("ALTER TABLE tweets ADD COLUMN url TEXT")

        conn.commit()
        conn.close()

    def insert_tweet(self, tweet_data: Dict[str, Any]) -> bool:
        """Insert a new tweet into the database"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT OR IGNORE INTO tweets
                (tweet_id, user_handle, user_name, text, created_at, retweet_count,
                 like_count, reply_count, category, url, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tweet_data.get('tweet_id'),
                tweet_data.get('user_handle'),
                tweet_data.get('user_name'),
                tweet_data.get('text'),
                tweet_data.get('created_at'),
                tweet_data.get('retweet_count', 0),
                tweet_data.get('like_count', 0),
                tweet_data.get('reply_count', 0),
                tweet_data.get('category'),
                tweet_data.get('url', ''),
                json.dumps(tweet_data.get('raw_data', {}))
            ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error inserting tweet: {e}")
            return False

    def insert_sentiment(self, tweet_id: str, sentiment_score: float,
                        sentiment_label: str, confidence: float = None,
                        model_response: str = None) -> bool:
        """Insert sentiment analysis result"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO sentiment_analysis
                (tweet_id, sentiment_score, sentiment_label, confidence, model_response)
                VALUES (?, ?, ?, ?, ?)
            """, (tweet_id, sentiment_score, sentiment_label, confidence, model_response))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error inserting sentiment: {e}")
            return False

    def insert_word_frequency(self, word: str, category: str, tweet_id: str = None) -> bool:
        """Insert word frequency data"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO word_frequency (word, category, tweet_id)
                VALUES (?, ?, ?)
            """, (word.lower(), category, tweet_id))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error inserting word frequency: {e}")
            return False

    def insert_alert(self, alert_type: str, category: str, severity: str,
                     message: str, data: Dict = None) -> bool:
        """Insert an alert"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO alerts (alert_type, category, severity, message, data)
                VALUES (?, ?, ?, ?, ?)
            """, (alert_type, category, severity, message, json.dumps(data) if data else None))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error inserting alert: {e}")
            return False

    def get_recent_tweets(self, category: str = None, hours: int = None, limit: int = 100) -> List[Dict]:
        """Get recent tweets

        Args:
            category: Filter by category (optional)
            hours: Filter by hours (optional, if None returns all)
            limit: Maximum number of results
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if category and hours:
            cursor.execute("""
                SELECT t.*, s.sentiment_score, s.sentiment_label
                FROM tweets t
                LEFT JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
                WHERE t.category = ?
                AND datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                ORDER BY t.created_at DESC
                LIMIT ?
            """, (category, hours, limit))
        elif category:
            cursor.execute("""
                SELECT t.*, s.sentiment_score, s.sentiment_label
                FROM tweets t
                LEFT JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
                WHERE t.category = ?
                ORDER BY t.created_at DESC
                LIMIT ?
            """, (category, limit))
        elif hours:
            cursor.execute("""
                SELECT t.*, s.sentiment_score, s.sentiment_label
                FROM tweets t
                LEFT JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
                WHERE datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                ORDER BY t.created_at DESC
                LIMIT ?
            """, (hours, limit))
        else:
            cursor.execute("""
                SELECT t.*, s.sentiment_score, s.sentiment_label
                FROM tweets t
                LEFT JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
                ORDER BY t.created_at DESC
                LIMIT ?
            """, (limit,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_word_frequency_stats(self, category: str = None, hours: int = 24,
                                  limit: int = 50) -> List[Dict]:
        """Get word frequency statistics with timestamp information

        Uses the article's created_at time from tweets table for accurate time filtering
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if category:
            cursor.execute("""
                SELECT
                    wf.word,
                    COUNT(*) as count,
                    wf.category,
                    MIN(t.created_at) as first_seen,
                    MAX(t.created_at) as last_seen
                FROM word_frequency wf
                INNER JOIN tweets t ON wf.tweet_id = t.tweet_id
                WHERE wf.category = ?
                AND datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                GROUP BY wf.word, wf.category
                ORDER BY count DESC
                LIMIT ?
            """, (category, hours, limit))
        else:
            cursor.execute("""
                SELECT
                    wf.word,
                    COUNT(*) as count,
                    GROUP_CONCAT(DISTINCT wf.category) as category,
                    MIN(t.created_at) as first_seen,
                    MAX(t.created_at) as last_seen
                FROM word_frequency wf
                INNER JOIN tweets t ON wf.tweet_id = t.tweet_id
                WHERE datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                GROUP BY wf.word
                ORDER BY count DESC
                LIMIT ?
            """, (hours, limit))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_tweet_keywords(self, tweet_id: str, hours: int = 24) -> List[Dict]:
        """Get keywords for a specific tweet"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT word, category
            FROM word_frequency
            WHERE tweet_id = ?
            AND timestamp > datetime('now', '-' || ? || ' hours')
        """, (tweet_id, hours))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_tweets_by_keyword(self, keyword: str, hours: int = 24, limit: int = 50) -> List[Dict]:
        """Get tweets/news articles containing a specific keyword"""
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT
                t.tweet_id,
                t.user_handle,
                t.user_name,
                t.text,
                t.created_at,
                t.retweet_count,
                t.like_count,
                t.reply_count,
                t.category,
                t.url,
                s.sentiment_score,
                s.sentiment_label,
                wf.word
            FROM tweets t
            LEFT JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
            INNER JOIN word_frequency wf ON t.tweet_id = wf.tweet_id
            WHERE LOWER(wf.word) = LOWER(?)
            AND datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
            ORDER BY t.created_at DESC
            LIMIT ?
        """, (keyword, hours, limit))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def search_articles(self, query: str, category: str = None, hours: int = 24,
                       sentiment_filter: str = None, limit: int = 100) -> List[Dict]:
        """Advanced search for articles with multiple filters

        Args:
            query: Search query (searches in text and keywords)
            category: Filter by category (optional)
            hours: Time range in hours
            sentiment_filter: Filter by sentiment (positive/neutral/negative)
            limit: Maximum results
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Build the query based on filters
        query_parts = []
        params = []

        # Base query
        base_query = """
            SELECT DISTINCT
                t.tweet_id,
                t.user_handle,
                t.user_name,
                t.text,
                t.created_at,
                t.retweet_count,
                t.like_count,
                t.reply_count,
                t.category,
                t.url,
                s.sentiment_score,
                s.sentiment_label
            FROM tweets t
            LEFT JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
            LEFT JOIN word_frequency wf ON t.tweet_id = wf.tweet_id
            WHERE 1=1
        """

        # Time filter
        if hours:
            query_parts.append("AND datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')")
            params.append(hours)

        # Search query filter
        if query:
            query_parts.append("AND (LOWER(t.text) LIKE LOWER(?) OR LOWER(wf.word) LIKE LOWER(?))")
            params.append(f'%{query}%')
            params.append(f'%{query}%')

        # Category filter
        if category:
            query_parts.append("AND t.category = ?")
            params.append(category)

        # Sentiment filter
        if sentiment_filter:
            if sentiment_filter == 'positive':
                query_parts.append("AND s.sentiment_score > 0.1")
            elif sentiment_filter == 'negative':
                query_parts.append("AND s.sentiment_score < -0.1")
            elif sentiment_filter == 'neutral':
                query_parts.append("AND s.sentiment_score BETWEEN -0.1 AND 0.1")

        # Combine query
        full_query = base_query + ' ' + ' '.join(query_parts) + ' ORDER BY t.created_at DESC LIMIT ?'
        params.append(limit)

        cursor.execute(full_query, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_sentiment_time_series(self, category: str = None, hours: int = 24) -> List[Dict]:
        """Get sentiment time series data"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if category:
            cursor.execute("""
                SELECT
                    datetime(t.created_at) as timestamp,
                    AVG(s.sentiment_score) as avg_sentiment,
                    COUNT(*) as tweet_count,
                    t.category
                FROM tweets t
                JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
                WHERE t.category = ?
                AND datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                GROUP BY datetime(strftime('%Y-%m-%d %H:00:00', t.created_at)), t.category
                ORDER BY timestamp
            """, (category, hours))
        else:
            cursor.execute("""
                SELECT
                    datetime(t.created_at) as timestamp,
                    AVG(s.sentiment_score) as avg_sentiment,
                    COUNT(*) as tweet_count
                FROM tweets t
                JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
                WHERE datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                GROUP BY datetime(strftime('%Y-%m-%d %H:00:00', t.created_at))
                ORDER BY timestamp
            """, (hours,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_alerts(self, limit: int = 50, unsent_only: bool = False) -> List[Dict]:
        """Get recent alerts"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if unsent_only:
            cursor.execute("""
                SELECT * FROM alerts
                WHERE sent_to_telegram = 0
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))
        else:
            cursor.execute("""
                SELECT * FROM alerts
                ORDER BY created_at DESC
                LIMIT ?
            """, (limit,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def mark_alert_sent(self, alert_id: int) -> bool:
        """Mark an alert as sent to Telegram"""
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            cursor.execute("""
                UPDATE alerts
                SET sent_to_telegram = 1
                WHERE id = ?
            """, (alert_id,))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error marking alert as sent: {e}")
            return False

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get statistics for dashboard"""
        conn = self.get_connection()
        cursor = conn.cursor()

        stats = {}

        # Total tweets
        cursor.execute("SELECT COUNT(*) as count FROM tweets")
        stats['total_tweets'] = cursor.fetchone()['count']

        # Tweets by category
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM tweets
            GROUP BY category
        """)
        stats['tweets_by_category'] = [dict(row) for row in cursor.fetchall()]

        # Average sentiment by category
        cursor.execute("""
            SELECT t.category, AVG(s.sentiment_score) as avg_sentiment, COUNT(*) as count
            FROM tweets t
            JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
            GROUP BY t.category
        """)
        stats['sentiment_by_category'] = [dict(row) for row in cursor.fetchall()]

        # Recent alerts count
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM alerts
            WHERE created_at > datetime('now', '-24 hours')
        """)
        stats['recent_alerts'] = cursor.fetchone()['count']

        conn.close()
        return stats

    def cleanup_old_data(self, days_to_keep: int = 7) -> Dict[str, int]:
        """Clean up old data to prevent database bloat

        Args:
            days_to_keep: Number of days of data to keep (default 7)

        Returns:
            Dictionary with counts of deleted records
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            deleted_counts = {}

            # Delete old word frequency data
            cursor.execute("""
                DELETE FROM word_frequency
                WHERE timestamp < datetime('now', '-' || ? || ' days')
            """, (days_to_keep,))
            deleted_counts['word_frequency'] = cursor.rowcount

            # Delete old alerts (except forex_calendar which we want to keep longer)
            cursor.execute("""
                DELETE FROM alerts
                WHERE created_at < datetime('now', '-' || ? || ' days')
                AND alert_type != 'forex_calendar'
            """, (days_to_keep,))
            deleted_counts['alerts'] = cursor.rowcount

            # Delete forex alerts older than 14 days
            cursor.execute("""
                DELETE FROM alerts
                WHERE created_at < datetime('now', '-14 days')
                AND alert_type = 'forex_calendar'
            """)
            deleted_counts['forex_alerts'] = cursor.rowcount

            # Get old tweet IDs that will be deleted
            cursor.execute("""
                SELECT tweet_id FROM tweets
                WHERE created_at < datetime('now', '-' || ? || ' days')
            """, (days_to_keep,))
            old_tweet_ids = [row['tweet_id'] for row in cursor.fetchall()]

            if old_tweet_ids:
                # Delete sentiment analysis for old tweets
                placeholders = ','.join('?' * len(old_tweet_ids))
                cursor.execute(f"""
                    DELETE FROM sentiment_analysis
                    WHERE tweet_id IN ({placeholders})
                """, old_tweet_ids)
                deleted_counts['sentiment_analysis'] = cursor.rowcount

                # Delete old tweets
                cursor.execute(f"""
                    DELETE FROM tweets
                    WHERE tweet_id IN ({placeholders})
                """, old_tweet_ids)
                deleted_counts['tweets'] = cursor.rowcount
            else:
                deleted_counts['sentiment_analysis'] = 0
                deleted_counts['tweets'] = 0

            # Commit all changes first
            conn.commit()
            conn.close()

            # VACUUM must be run outside of a transaction
            # Open a new connection and run VACUUM
            vacuum_conn = sqlite3.connect(self.db_path, timeout=30.0)
            vacuum_conn.execute("VACUUM")
            vacuum_conn.close()

            return deleted_counts

        except Exception as e:
            print(f"Error during cleanup: {e}")
            return {}

    def clear_all_data(self) -> bool:
        """Clear all data from all tables (admin function)

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            # Delete all data from tables (in order due to foreign keys)
            cursor.execute("DELETE FROM sentiment_analysis")
            cursor.execute("DELETE FROM word_frequency")
            cursor.execute("DELETE FROM time_series")
            cursor.execute("DELETE FROM alerts")
            cursor.execute("DELETE FROM entities")
            cursor.execute("DELETE FROM tweets")

            conn.commit()
            conn.close()

            # VACUUM to reclaim space
            vacuum_conn = sqlite3.connect(self.db_path, timeout=30.0)
            vacuum_conn.execute("VACUUM")
            vacuum_conn.close()

            return True
        except Exception as e:
            print(f"Error clearing database: {e}")
            return False

    def insert_entities(self, tweet_id: str, entities: List[Dict[str, Any]]) -> bool:
        """Insert extracted entities for an article

        Args:
            tweet_id: The article/tweet ID
            entities: List of entity dicts with 'text', 'label', and 'count'
        """
        try:
            conn = self.get_connection()
            cursor = conn.cursor()

            for entity in entities:
                cursor.execute("""
                    INSERT INTO entities (tweet_id, entity_text, entity_label, entity_count)
                    VALUES (?, ?, ?, ?)
                """, (
                    tweet_id,
                    entity['text'],
                    entity['label'],
                    entity.get('count', 1)
                ))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error inserting entities: {e}")
            return False

    def get_trending_entities(self, hours: int = 24, entity_type: str = None,
                              limit: int = 50) -> List[Dict[str, Any]]:
        """Get trending entities across all articles

        Args:
            hours: Time range in hours
            entity_type: Filter by entity type (PERSON, ORG, GPE, etc.)
            limit: Maximum results

        Returns:
            List of entities with counts, sorted by frequency
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        if entity_type:
            cursor.execute("""
                SELECT
                    e.entity_text,
                    e.entity_label,
                    COUNT(DISTINCT e.tweet_id) as article_count,
                    SUM(e.entity_count) as total_mentions,
                    GROUP_CONCAT(DISTINCT t.category) as categories,
                    MAX(t.created_at) as last_seen
                FROM entities e
                INNER JOIN tweets t ON e.tweet_id = t.tweet_id
                WHERE e.entity_label = ?
                AND datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                GROUP BY e.entity_text, e.entity_label
                ORDER BY total_mentions DESC
                LIMIT ?
            """, (entity_type, hours, limit))
        else:
            cursor.execute("""
                SELECT
                    e.entity_text,
                    e.entity_label,
                    COUNT(DISTINCT e.tweet_id) as article_count,
                    SUM(e.entity_count) as total_mentions,
                    GROUP_CONCAT(DISTINCT t.category) as categories,
                    MAX(t.created_at) as last_seen
                FROM entities e
                INNER JOIN tweets t ON e.tweet_id = t.tweet_id
                WHERE datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                GROUP BY e.entity_text, e.entity_label
                ORDER BY total_mentions DESC
                LIMIT ?
            """, (hours, limit))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_entity_timeline(self, entity_text: str, hours: int = 168) -> List[Dict[str, Any]]:
        """Get timeline of articles mentioning a specific entity

        Args:
            entity_text: The entity to search for
            hours: Time range in hours (default 1 week)
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                t.tweet_id,
                t.text,
                t.user_handle as source,
                t.url,
                t.created_at,
                t.category,
                s.sentiment_score,
                s.sentiment_label,
                e.entity_count
            FROM entities e
            INNER JOIN tweets t ON e.tweet_id = t.tweet_id
            LEFT JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
            WHERE LOWER(e.entity_text) = LOWER(?)
            AND datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
            ORDER BY t.created_at DESC
        """, (entity_text, hours))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_entities_by_category(self, category: str, hours: int = 24,
                                  limit: int = 30) -> Dict[str, List[Dict]]:
        """Get entities grouped by type for a specific category

        Returns:
            {
                'persons': [...],
                'organizations': [...],
                'locations': [...]
            }
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                e.entity_text,
                e.entity_label,
                COUNT(DISTINCT e.tweet_id) as article_count,
                SUM(e.entity_count) as total_mentions
            FROM entities e
            INNER JOIN tweets t ON e.tweet_id = t.tweet_id
            WHERE t.category = ?
            AND datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
            GROUP BY e.entity_text, e.entity_label
            ORDER BY total_mentions DESC
        """, (category, hours))

        all_entities = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # Group by type
        result = {
            'persons': [],
            'organizations': [],
            'locations': [],
            'money': [],
            'products': [],
            'other': []
        }

        for entity in all_entities:
            label = entity['entity_label']
            if label == 'PERSON':
                result['persons'].append(entity)
            elif label == 'ORG':
                result['organizations'].append(entity)
            elif label in ('GPE', 'LOC'):
                result['locations'].append(entity)
            elif label == 'MONEY':
                result['money'].append(entity)
            elif label == 'PRODUCT':
                result['products'].append(entity)
            else:
                result['other'].append(entity)

        # Limit each category
        for key in result:
            result[key] = result[key][:limit]

        return result

    def get_entity_network(self, hours: int = 24, entity_type: str = None,
                          min_keyword_count: int = 3, entity_limit: int = 20,
                          keywords_per_entity: int = 10) -> Dict[str, Any]:
        """Get entity-keyword network data for visualization

        Returns nodes (entities and keywords) and links between them

        Args:
            hours: Time range in hours
            entity_type: Filter by entity type (PERSON, ORG, GPE, etc.)
            min_keyword_count: Minimum keyword frequency to include
            entity_limit: Maximum number of entity nodes
            keywords_per_entity: Max keywords to link per entity

        Returns:
            {
                'nodes': [
                    {'id': 'Bitcoin', 'type': 'entity', 'label': 'ORG', 'mentions': 10},
                    {'id': 'price', 'type': 'keyword', 'count': 25},
                    ...
                ],
                'links': [
                    {'source': 'Bitcoin', 'target': 'price', 'value': 15},
                    ...
                ]
            }
        """
        conn = self.get_connection()
        cursor = conn.cursor()

        # Get top entities as nodes
        if entity_type:
            cursor.execute("""
                SELECT
                    e.entity_text,
                    e.entity_label,
                    COUNT(DISTINCT e.tweet_id) as article_count,
                    SUM(e.entity_count) as total_mentions
                FROM entities e
                INNER JOIN tweets t ON e.tweet_id = t.tweet_id
                WHERE e.entity_label = ?
                AND datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                GROUP BY e.entity_text, e.entity_label
                ORDER BY total_mentions DESC
                LIMIT ?
            """, (entity_type, hours, entity_limit))
        else:
            cursor.execute("""
                SELECT
                    e.entity_text,
                    e.entity_label,
                    COUNT(DISTINCT e.tweet_id) as article_count,
                    SUM(e.entity_count) as total_mentions
                FROM entities e
                INNER JOIN tweets t ON e.tweet_id = t.tweet_id
                WHERE datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                GROUP BY e.entity_text, e.entity_label
                ORDER BY total_mentions DESC
                LIMIT ?
            """, (hours, entity_limit))

        # Build entity nodes
        entity_nodes = []
        entity_texts = []
        for row in cursor.fetchall():
            entity = dict(row)
            entity_nodes.append({
                'id': entity['entity_text'],
                'type': 'entity',
                'label': entity['entity_label'],
                'mentions': entity['total_mentions'],
                'articles': entity['article_count']
            })
            entity_texts.append(entity['entity_text'])

        # Get keywords for each entity
        keyword_counts = {}  # Track total keyword counts across all entities
        links = []

        for entity_text in entity_texts:
            # Get top keywords from articles mentioning this entity
            cursor.execute("""
                SELECT
                    wf.word,
                    COUNT(*) as count
                FROM word_frequency wf
                INNER JOIN entities e ON wf.tweet_id = e.tweet_id
                INNER JOIN tweets t ON wf.tweet_id = t.tweet_id
                WHERE LOWER(e.entity_text) = LOWER(?)
                AND datetime(t.created_at) > datetime('now', 'localtime', '-' || ? || ' hours')
                GROUP BY wf.word
                ORDER BY count DESC
                LIMIT ?
            """, (entity_text, hours, keywords_per_entity))

            for row in cursor.fetchall():
                keyword_data = dict(row)
                keyword = keyword_data['word']
                count = keyword_data['count']

                # Only include keywords with minimum frequency
                if count >= min_keyword_count:
                    # Track total keyword usage across all entities
                    if keyword not in keyword_counts:
                        keyword_counts[keyword] = 0
                    keyword_counts[keyword] += count

                    # Create link between entity and keyword
                    links.append({
                        'source': entity_text,
                        'target': keyword,
                        'value': count
                    })

        # Build keyword nodes
        keyword_nodes = [
            {
                'id': keyword,
                'type': 'keyword',
                'count': count
            }
            for keyword, count in keyword_counts.items()
        ]

        # Combine all nodes
        all_nodes = entity_nodes + keyword_nodes

        conn.close()

        return {
            'nodes': all_nodes,
            'links': links
        }
