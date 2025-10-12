"""
CPU-based Sentiment Analyzer using transformers (DistilBERT)
Fast, efficient, no GPU required
"""
import logging
from typing import Dict, Any
from transformers import pipeline
import re


class SentimentAnalyzerCPU:
    def __init__(self, cache_dir="/app/data/models"):
        """Initialize CPU-based sentiment analyzer

        Args:
            cache_dir: Directory to cache the model (default: /app/data/models)
        """
        self.logger = logging.getLogger(__name__)
        self.cache_dir = cache_dir

        try:
            # Use DistilBERT for sentiment analysis (CPU-friendly)
            # This model is specifically fine-tuned for sentiment
            self.logger.info(f"Loading DistilBERT sentiment model (CPU-only) from cache: {cache_dir}")

            # Create cache directory if it doesn't exist
            import os
            os.makedirs(cache_dir, exist_ok=True)

            # Set HuggingFace cache directory
            os.environ['TRANSFORMERS_CACHE'] = cache_dir
            os.environ['HF_HOME'] = cache_dir

            self.sentiment_pipeline = pipeline(
                "sentiment-analysis",
                model="distilbert-base-uncased-finetuned-sst-2-english",
                device=-1,  # Force CPU
                model_kwargs={'cache_dir': cache_dir}
            )
            self.logger.info("CPU sentiment model loaded successfully (cached)")
        except Exception as e:
            self.logger.error(f"Error loading sentiment model: {e}")
            self.sentiment_pipeline = None

    def analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text using DistilBERT (CPU)"""
        try:
            if not self.sentiment_pipeline:
                return self._get_fallback_sentiment(text)

            # Run sentiment analysis with proper truncation to 512 tokens
            # truncation=True and max_length=512 handle the token limit correctly
            result = self.sentiment_pipeline(text, truncation=True, max_length=512)[0]

            # Convert to our format
            label_map = {
                'POSITIVE': 'positive',
                'NEGATIVE': 'negative',
                'NEUTRAL': 'neutral'
            }

            # Map confidence to score (-1 to 1)
            base_label = result['label']
            confidence = result['score']

            if base_label == 'POSITIVE':
                score = confidence
                if confidence > 0.9:
                    label = 'very_positive'
                else:
                    label = 'positive'
            elif base_label == 'NEGATIVE':
                score = -confidence
                if confidence > 0.9:
                    label = 'very_negative'
                else:
                    label = 'negative'
            else:
                score = 0.0
                label = 'neutral'

            # Enhance with market context
            score = self._adjust_for_market_context(score, text)
            label = self._score_to_label(score)

            return {
                'score': score,
                'label': label,
                'confidence': confidence,
                'reasoning': f'DistilBERT: {base_label} ({confidence:.2f})',
                'raw_response': str(result)
            }

        except Exception as e:
            self.logger.error(f"Error analyzing sentiment: {e}")
            return self._get_fallback_sentiment(text)

    def _adjust_for_market_context(self, base_score: float, text: str) -> float:
        """Adjust sentiment score based on market/financial context"""
        text_lower = text.lower()

        # Negative market keywords - make more negative
        negative_market_terms = [
            'recession', 'inflation', 'rate hike', 'crash', 'collapse',
            'deficit', 'unemployment', 'bearish', 'sell-off', 'panic',
            'correction', 'plunge', 'decline', 'losses'
        ]

        # Positive market keywords - make more positive
        positive_market_terms = [
            'growth', 'rally', 'surge', 'bullish', 'gains', 'recovery',
            'boom', 'profit', 'record high', 'breakthrough'
        ]

        adjustment = 0.0

        for term in negative_market_terms:
            if term in text_lower:
                adjustment -= 0.1

        for term in positive_market_terms:
            if term in text_lower:
                adjustment += 0.1

        # Apply adjustment
        adjusted_score = base_score + adjustment

        # Keep in range
        return max(-1.0, min(1.0, adjusted_score))

    def _score_to_label(self, score: float) -> str:
        """Convert score to label"""
        if score <= -0.6:
            return 'very_negative'
        elif score <= -0.2:
            return 'negative'
        elif score <= 0.2:
            return 'neutral'
        elif score <= 0.6:
            return 'positive'
        else:
            return 'very_positive'

    def _get_fallback_sentiment(self, text: str) -> Dict[str, Any]:
        """Get fallback sentiment using keyword-based analysis"""
        text_lower = text.lower()

        # Negative keywords
        very_negative_keywords = [
            'crash', 'collapse', 'disaster', 'crisis', 'panic', 'plunge',
            'terrible', 'catastrophe', 'emergency', 'devastation'
        ]

        negative_keywords = [
            'recession', 'inflation', 'unemployment', 'deficit', 'debt',
            'decline', 'fall', 'drop', 'down', 'loss', 'losses', 'failed',
            'concern', 'worried', 'fear', 'risk', 'threat', 'warning',
            'bearish', 'sell-off', 'correction'
        ]

        # Positive keywords
        very_positive_keywords = [
            'boom', 'surge', 'soar', 'breakthrough', 'record high',
            'excellent', 'outstanding', 'amazing', 'incredible'
        ]

        positive_keywords = [
            'growth', 'gain', 'profit', 'rally', 'rise', 'up', 'increase',
            'improvement', 'recovery', 'success', 'bullish', 'optimistic',
            'confidence', 'strong', 'positive', 'good'
        ]

        # Count keywords
        very_neg_count = sum(1 for kw in very_negative_keywords if kw in text_lower)
        neg_count = sum(1 for kw in negative_keywords if kw in text_lower)
        very_pos_count = sum(1 for kw in very_positive_keywords if kw in text_lower)
        pos_count = sum(1 for kw in positive_keywords if kw in text_lower)

        # Calculate score
        total_negative = very_neg_count * 2 + neg_count
        total_positive = very_pos_count * 2 + pos_count

        if total_negative == 0 and total_positive == 0:
            score = 0.0
            label = 'neutral'
        else:
            # Scale to -1 to 1
            total = total_negative + total_positive
            score = (total_positive - total_negative) / max(total, 1)
            score = max(-1.0, min(1.0, score))
            label = self._score_to_label(score)

        return {
            'score': score,
            'label': label,
            'confidence': min(abs(score), 0.5),  # Lower confidence for fallback
            'reasoning': 'Fallback keyword-based analysis',
            'raw_response': None
        }

    def get_market_impact_score(self, sentiment: Dict[str, Any], text: str) -> float:
        """
        Calculate market impact score based on sentiment and context
        Returns a score from -1 (very bearish) to 1 (very bullish)
        """
        base_score = sentiment['score']

        # Amplify score for high-impact keywords
        text_lower = text.lower()

        high_impact_keywords = {
            'interest rate': 0.3,
            'fomc': 0.3,
            'recession': 0.3,
            'inflation': 0.25,
            'fed': 0.2,
            'gdp': 0.2,
            'unemployment': 0.2,
            'jobs report': 0.25,
            'trump': 0.2,
            'war': 0.3,
            'tariff': 0.25,
            'default': 0.3,
            'bankruptcy': 0.3
        }

        amplification = 0
        for keyword, weight in high_impact_keywords.items():
            if keyword in text_lower:
                amplification += weight

        # Amplify the score (make it more extreme)
        impact_score = base_score * (1 + amplification)

        # Keep in range
        impact_score = max(-1.0, min(1.0, impact_score))

        return impact_score
