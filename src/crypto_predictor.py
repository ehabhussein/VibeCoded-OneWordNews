"""
Crypto Price Prediction based on News Sentiment Analysis

This module analyzes sentiment from crypto news articles and predicts
short-term price movements (1h, 6h, 24h) for cryptocurrencies.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
import statistics


class CryptoPredictor:
    """Predicts crypto price movements based on news sentiment"""

    def __init__(self, db):
        """Initialize crypto predictor

        Args:
            db: Database instance
        """
        self.db = db
        self.logger = logging.getLogger(__name__)

        # Crypto-related keywords to track
        self.crypto_keywords = {
            'bitcoin': ['bitcoin', 'btc'],
            'ethereum': ['ethereum', 'eth', 'ether'],
            'crypto': ['crypto', 'cryptocurrency', 'blockchain', 'defi', 'nft']
        }

        # Sentiment weights (more recent = higher weight)
        self.time_decay_weights = {
            '1h': 1.0,   # Last hour: full weight
            '3h': 0.7,   # 1-3 hours: 70% weight
            '6h': 0.5,   # 3-6 hours: 50% weight
            '12h': 0.3,  # 6-12 hours: 30% weight
            '24h': 0.1   # 12-24 hours: 10% weight
        }

        self.logger.info("Crypto Predictor initialized")

    def _get_crypto_sentiment(self, symbol: str, hours: int = 24) -> List[Dict]:
        """Get all crypto-related articles with sentiment for a time period

        Args:
            symbol: Crypto symbol (e.g., 'bitcoin', 'ethereum')
            hours: Time window in hours

        Returns:
            List of articles with sentiment data
        """
        try:
            # Get cutoff time
            cutoff_time = datetime.now() - timedelta(hours=hours)

            # Get keywords for this crypto
            keywords = self.crypto_keywords.get(symbol.lower(), [symbol.lower()])

            # Query database for crypto articles
            query = """
                SELECT
                    t.text,
                    s.sentiment_score,
                    s.sentiment_label,
                    t.created_at,
                    t.category,
                    t.user_handle as source
                FROM tweets t
                LEFT JOIN sentiment_analysis s ON t.tweet_id = s.tweet_id
                WHERE
                    (t.category = 'crypto' OR t.category = 'markets')
                    AND t.created_at >= ?
                    AND (
                        LOWER(t.text) LIKE ?
                        OR LOWER(t.text) LIKE ?
                    )
                ORDER BY t.created_at DESC
            """

            # Build LIKE patterns for keywords - ensure we have exactly 2
            keyword_patterns = [f'%{kw}%' for kw in keywords[:2]]
            # Pad with duplicate if only 1 keyword
            if len(keyword_patterns) == 1:
                keyword_patterns.append(keyword_patterns[0])

            # Execute query using database connection
            conn = self.db.get_connection()
            cursor = conn.cursor()
            cursor.execute(query, (cutoff_time.isoformat(), *keyword_patterns))
            rows = cursor.fetchall()
            conn.close()

            articles = []
            for row in rows:
                # Skip if no sentiment score available
                if row[1] is None:
                    continue

                articles.append({
                    'text': row[0],
                    'sentiment_score': row[1],
                    'sentiment_label': row[2],
                    'created_at': datetime.fromisoformat(row[3]),
                    'category': row[4],
                    'source': row[5]
                })

            return articles

        except Exception as e:
            self.logger.error(f"Error getting crypto sentiment: {e}")
            return []

    def _calculate_weighted_sentiment(self, articles: List[Dict]) -> Dict:
        """Calculate time-weighted sentiment score

        More recent articles have higher weight. Uses exponential time decay.

        Args:
            articles: List of articles with sentiment data

        Returns:
            Dictionary with weighted sentiment metrics
        """
        if not articles:
            return {
                'weighted_score': 0.0,
                'confidence': 0.0,
                'article_count': 0,
                'positive_ratio': 0.0,
                'negative_ratio': 0.0,
                'neutral_ratio': 0.0
            }

        now = datetime.now()
        weighted_scores = []
        total_weight = 0.0

        sentiment_counts = {'positive': 0, 'negative': 0, 'neutral': 0}

        for article in articles:
            # Calculate time difference in hours
            time_diff = (now - article['created_at']).total_seconds() / 3600

            # Apply exponential decay: weight = e^(-0.1 * hours)
            # This gives: 1h = 0.90, 3h = 0.74, 6h = 0.55, 12h = 0.30, 24h = 0.09
            import math
            weight = math.exp(-0.1 * time_diff)

            # Add weighted sentiment score
            sentiment_score = article['sentiment_score']
            weighted_scores.append(sentiment_score * weight)
            total_weight += weight

            # Count sentiment labels
            label = article['sentiment_label']
            if 'positive' in label:
                sentiment_counts['positive'] += 1
            elif 'negative' in label:
                sentiment_counts['negative'] += 1
            else:
                sentiment_counts['neutral'] += 1

        # Calculate weighted average
        avg_weighted_score = sum(weighted_scores) / total_weight if total_weight > 0 else 0.0

        # Calculate confidence based on article count and recency
        # More articles + more recent = higher confidence
        article_count = len(articles)
        confidence = min(1.0, article_count / 20.0)  # Max confidence at 20+ articles

        # Calculate sentiment distribution
        total_articles = len(articles)
        positive_ratio = sentiment_counts['positive'] / total_articles
        negative_ratio = sentiment_counts['negative'] / total_articles
        neutral_ratio = sentiment_counts['neutral'] / total_articles

        return {
            'weighted_score': avg_weighted_score,
            'confidence': confidence,
            'article_count': article_count,
            'positive_ratio': positive_ratio,
            'negative_ratio': negative_ratio,
            'neutral_ratio': neutral_ratio
        }

    def predict_price_movement(self, symbol: str, timeframe: str = '24h') -> Dict:
        """Predict price movement for a cryptocurrency

        Args:
            symbol: Crypto symbol (e.g., 'bitcoin', 'ethereum', 'btc', 'eth')
            timeframe: Prediction timeframe ('2h', '24h', '168h' for week)

        Returns:
            Prediction dictionary with signal, confidence, and reasoning
        """
        try:
            # Map common symbols
            symbol_map = {
                'btc': 'bitcoin',
                'eth': 'ethereum'
            }
            crypto_name = symbol_map.get(symbol.lower(), symbol.lower())

            # Convert timeframe string to hours
            timeframe_hours = int(timeframe.replace('h', ''))

            # Get articles from specified timeframe
            articles = self._get_crypto_sentiment(crypto_name, hours=timeframe_hours)

            if not articles:
                return {
                    'symbol': symbol.upper(),
                    'signal': 'NEUTRAL',
                    'confidence': 0.0,
                    'weighted_sentiment': 0.0,
                    'article_count': 0,
                    'reasoning': 'Insufficient data - no recent news articles found',
                    'timeframe': timeframe
                }

            # Calculate weighted sentiment
            sentiment_metrics = self._calculate_weighted_sentiment(articles)

            weighted_score = sentiment_metrics['weighted_score']
            confidence = sentiment_metrics['confidence']

            # Determine signal based on weighted sentiment score
            # Thresholds: > 0.3 = Bullish, < -0.3 = Bearish, else Neutral
            if weighted_score > 0.3:
                signal = 'BULLISH'
                emoji = '🟢'
            elif weighted_score < -0.3:
                signal = 'BEARISH'
                emoji = '🔴'
            else:
                signal = 'NEUTRAL'
                emoji = '🟡'

            # Build reasoning string
            reasoning_parts = []
            reasoning_parts.append(f"Based on {sentiment_metrics['article_count']} articles")
            reasoning_parts.append(f"Sentiment: {weighted_score:.2f}")
            reasoning_parts.append(
                f"({sentiment_metrics['positive_ratio']*100:.0f}% positive, "
                f"{sentiment_metrics['negative_ratio']*100:.0f}% negative)"
            )

            reasoning = ' | '.join(reasoning_parts)

            return {
                'symbol': symbol.upper(),
                'signal': signal,
                'emoji': emoji,
                'confidence': confidence,
                'weighted_sentiment': weighted_score,
                'article_count': sentiment_metrics['article_count'],
                'positive_ratio': sentiment_metrics['positive_ratio'],
                'negative_ratio': sentiment_metrics['negative_ratio'],
                'neutral_ratio': sentiment_metrics['neutral_ratio'],
                'reasoning': reasoning,
                'timeframe': timeframe,
                'timestamp': datetime.now().isoformat()
            }

        except Exception as e:
            self.logger.error(f"Error predicting price movement for {symbol}: {e}", exc_info=True)
            return {
                'symbol': symbol.upper(),
                'signal': 'ERROR',
                'confidence': 0.0,
                'weighted_sentiment': 0.0,
                'article_count': 0,
                'reasoning': f'Error: {str(e)}',
                'timeframe': timeframe
            }

    def predict_multiple_cryptos(self, symbols: List[str], timeframe: str = '24h') -> List[Dict]:
        """Predict price movements for multiple cryptocurrencies

        Args:
            symbols: List of crypto symbols
            timeframe: Prediction timeframe

        Returns:
            List of prediction dictionaries
        """
        predictions = []
        for symbol in symbols:
            prediction = self.predict_price_movement(symbol, timeframe)
            predictions.append(prediction)

        return predictions

    def get_sentiment_trend(self, symbol: str, hours: int = 24) -> Dict:
        """Analyze sentiment trend over time

        Args:
            symbol: Crypto symbol
            hours: Time window in hours

        Returns:
            Trend analysis with hourly breakdown
        """
        try:
            # Map symbol
            symbol_map = {'btc': 'bitcoin', 'eth': 'ethereum'}
            crypto_name = symbol_map.get(symbol.lower(), symbol.lower())

            # Get all articles
            articles = self._get_crypto_sentiment(crypto_name, hours=hours)

            if not articles:
                return {
                    'symbol': symbol.upper(),
                    'trend': 'NEUTRAL',
                    'hourly_sentiment': [],
                    'article_count': 0
                }

            # Group articles by hour
            now = datetime.now()
            hourly_data = defaultdict(list)

            for article in articles:
                hours_ago = int((now - article['created_at']).total_seconds() / 3600)
                if hours_ago < hours:
                    hourly_data[hours_ago].append(article['sentiment_score'])

            # Calculate average sentiment per hour
            hourly_sentiment = []
            for hour in range(hours):
                if hour in hourly_data:
                    avg_sentiment = statistics.mean(hourly_data[hour])
                    hourly_sentiment.append({
                        'hours_ago': hour,
                        'avg_sentiment': avg_sentiment,
                        'article_count': len(hourly_data[hour])
                    })

            # Determine trend (comparing recent vs older sentiment)
            if len(hourly_sentiment) >= 2:
                recent_sentiment = statistics.mean([h['avg_sentiment'] for h in hourly_sentiment[:6]])  # Last 6 hours
                older_sentiment = statistics.mean([h['avg_sentiment'] for h in hourly_sentiment[6:]])  # 6+ hours ago

                if recent_sentiment > older_sentiment + 0.2:
                    trend = 'IMPROVING'
                elif recent_sentiment < older_sentiment - 0.2:
                    trend = 'DECLINING'
                else:
                    trend = 'STABLE'
            else:
                trend = 'NEUTRAL'

            return {
                'symbol': symbol.upper(),
                'trend': trend,
                'hourly_sentiment': hourly_sentiment,
                'article_count': len(articles)
            }

        except Exception as e:
            self.logger.error(f"Error getting sentiment trend for {symbol}: {e}")
            return {
                'symbol': symbol.upper(),
                'trend': 'ERROR',
                'hourly_sentiment': [],
                'article_count': 0
            }
