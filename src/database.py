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

        # Create indexes for better query performance
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tweets_created_at ON tweets(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tweets_category ON tweets(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tweets_user_handle ON tweets(user_handle)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sentiment_tweet_id ON sentiment_analysis(tweet_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_word_timestamp ON word_frequency(timestamp)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_word_category ON word_frequency(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeseries_category ON time_series(category)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timeseries_interval ON time_series(interval_start)")

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
                 like_count, reply_count, category, raw_data)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def get_recent_tweets(self, category: str = None, limit: int = 100) -> List[Dict]:
        """Get recent tweets"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if category:
            cursor.execute("""
                SELECT t.*, s.sentiment_score, s.sentiment_label
                FROM tweets t
                LEFT JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
                WHERE t.category = ?
                ORDER BY t.created_at DESC
                LIMIT ?
            """, (category, limit))
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
        """Get word frequency statistics with timestamp information"""
        conn = self.get_connection()
        cursor = conn.cursor()

        if category:
            cursor.execute("""
                SELECT
                    word,
                    COUNT(*) as count,
                    category,
                    MIN(timestamp) as first_seen,
                    MAX(timestamp) as last_seen
                FROM word_frequency
                WHERE category = ?
                AND timestamp > datetime('now', '-' || ? || ' hours')
                GROUP BY word, category
                ORDER BY count DESC
                LIMIT ?
            """, (category, hours, limit))
        else:
            cursor.execute("""
                SELECT
                    word,
                    COUNT(*) as count,
                    GROUP_CONCAT(DISTINCT category) as category,
                    MIN(timestamp) as first_seen,
                    MAX(timestamp) as last_seen
                FROM word_frequency
                WHERE timestamp > datetime('now', '-' || ? || ' hours')
                GROUP BY word
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
                s.sentiment_score,
                s.sentiment_label,
                wf.word
            FROM tweets t
            LEFT JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
            INNER JOIN word_frequency wf ON t.tweet_id = wf.tweet_id
            WHERE LOWER(wf.word) = LOWER(?)
            AND wf.timestamp > datetime('now', '-' || ? || ' hours')
            ORDER BY t.created_at DESC
            LIMIT ?
        """, (keyword, hours, limit))

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
                AND t.created_at > datetime('now', '-' || ? || ' hours')
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
                WHERE t.created_at > datetime('now', '-' || ? || ' hours')
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
