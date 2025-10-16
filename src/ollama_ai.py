import requests
import json
from typing import List, Dict, Optional
import logging


class OllamaAI:
    """Service for interacting with Ollama AI for news analysis and summaries"""

    def __init__(self, base_url: str = "http://host.docker.internal:11434", model: str = "phi4:latest"):
        """Initialize Ollama AI service

        Args:
            base_url: Ollama API base URL (use Docker internal networking)
            model: Model to use for generation
        """
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.logger = logging.getLogger(__name__)

    def generate(self, prompt: str, system: str = None, max_tokens: int = 500) -> Optional[str]:
        """Generate text using Ollama

        Args:
            prompt: The prompt to send
            system: System message for context
            max_tokens: Maximum tokens to generate

        Returns:
            Generated text or None if failed
        """
        try:
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "num_predict": max_tokens,
                    "temperature": 0.7
                }
            }

            if system:
                payload["system"] = system

            response = requests.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=60
            )

            if response.status_code == 200:
                result = response.json()
                return result.get('response', '').strip()
            else:
                self.logger.error(f"Ollama API error: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            self.logger.error(f"Error calling Ollama API: {e}")
            return None

    def generate_daily_brief(self, articles: List[Dict], brief_type: str) -> str:
        """Generate a news brief summary

        Args:
            articles: List of article dictionaries
            brief_type: "morning", "midday", "evening", "day", or "week"

        Returns:
            Summary text
        """
        # Determine how many articles to analyze based on brief type
        article_count = {
            'morning': 30,
            'midday': 20,
            'evening': 25,
            'day': 40,
            'week': 50
        }.get(brief_type, 20)

        # Prepare article summaries
        article_texts = []
        for i, article in enumerate(articles[:article_count], 1):
            sentiment = article.get('sentiment_score', 0)
            sentiment_label = "positive" if sentiment > 0.1 else "negative" if sentiment < -0.1 else "neutral"
            article_texts.append(
                f"{i}. [{article.get('category', 'N/A')}] {article.get('text', '')[:150]}... "
                f"(Sentiment: {sentiment_label})"
            )

        articles_summary = "\n".join(article_texts)

        # Create prompt based on brief type
        time_context = {
            "morning": "overnight and early morning",
            "midday": "this morning",
            "evening": "today",
            "day": "in the past 24 hours",
            "week": "over the past week"
        }

        system_prompt = """You are a professional news analyst. Create concise, informative summaries
        of news events. Focus on the most important developments and their implications.
        Be objective and factual."""

        prompt = f"""Analyze these news articles from {time_context.get(brief_type, 'today')} and create a brief {brief_type} summary.

Articles:
{articles_summary}

Create a summary highlighting:
1. The most significant news event
2. Key market or economic developments
3. Notable sentiment trends

Length: {"3-4 sentences" if brief_type in ['morning', 'midday', 'evening'] else "5-7 sentences for comprehensive overview"}

Summary:"""

        # Adjust token limit based on brief type
        token_limit = {
            'morning': 300,
            'midday': 250,
            'evening': 300,
            'day': 400,
            'week': 500
        }.get(brief_type, 300)

        summary = self.generate(prompt, system=system_prompt, max_tokens=token_limit)
        return summary or "Unable to generate summary at this time."

    def generate_tldr(self, keyword: str, articles: List[Dict]) -> str:
        """Generate a TL;DR summary for a specific topic/keyword

        Args:
            keyword: The keyword/topic
            articles: Related articles

        Returns:
            One-line summary
        """
        # Get article texts
        article_texts = [a.get('text', '')[:200] for a in articles[:10]]
        combined = " | ".join(article_texts)

        system_prompt = "You are a news summarizer. Create ultra-concise one-sentence summaries."

        prompt = f"""Create a single-sentence TL;DR summary for the topic "{keyword}" based on these articles:

{combined}

TL;DR (one sentence, max 20 words):"""

        tldr = self.generate(prompt, system=system_prompt, max_tokens=50)
        return tldr or f"{keyword}: Multiple articles discussing this topic."

    def compare_sources(self, keyword: str, source_articles: Dict[str, List[Dict]]) -> Dict[str, str]:
        """Compare how different sources report on the same topic

        Args:
            keyword: The topic being covered
            source_articles: Dict mapping source names to their articles

        Returns:
            Dict mapping source names to their perspective summaries
        """
        comparisons = {}

        for source, articles in source_articles.items():
            if not articles:
                continue

            article_texts = [a.get('text', '')[:150] for a in articles[:5]]
            combined = " ".join(article_texts)

            avg_sentiment = sum(a.get('sentiment_score', 0) for a in articles) / len(articles)
            sentiment_label = "positive" if avg_sentiment > 0.1 else "negative" if avg_sentiment < -0.1 else "neutral"

            system_prompt = "You are a media analyst. Summarize how a specific news source is covering a topic."

            prompt = f"""Analyze how "{source}" is covering the topic "{keyword}":

Articles from {source}:
{combined}

Average sentiment: {sentiment_label}

In one sentence, describe their perspective or angle on this topic:"""

            comparison = self.generate(prompt, system=system_prompt, max_tokens=100)
            comparisons[source] = comparison or f"{source}: {sentiment_label} coverage"

        return comparisons

    def detect_story_thread(self, articles: List[Dict]) -> Dict[str, any]:
        """Analyze articles to detect if they're part of the same story

        Args:
            articles: List of articles to analyze

        Returns:
            Dict with story analysis
        """
        # Extract key information
        article_summaries = []
        for i, article in enumerate(articles[:15], 1):
            article_summaries.append(
                f"{i}. [{article.get('created_at', '')}] {article.get('text', '')[:200]}"
            )

        combined = "\n".join(article_summaries)

        system_prompt = """You are a news analyst specializing in story tracking.
        Identify if articles are covering the same developing story."""

        prompt = f"""Analyze these articles and determine if they're covering the same developing story:

{combined}

Answer in this format:
- Is this one story?: Yes/No
- Story title: [brief title]
- Key developments: [2-3 bullet points of how the story evolved]

Analysis:"""

        analysis = self.generate(prompt, system=system_prompt, max_tokens=300)

        # Parse the response (simplified)
        is_thread = "yes" in (analysis or "").lower()[:50]

        return {
            "is_story_thread": is_thread,
            "analysis": analysis or "Unable to analyze story thread",
            "article_count": len(articles)
        }

    def explain_trend(self, keyword: str, stats: Dict[str, any]) -> str:
        """Generate an explanation for why a topic is trending

        Args:
            keyword: The trending keyword
            stats: Statistics about the trend

        Returns:
            Explanation text
        """
        system_prompt = "You are a trend analyst. Explain why topics are trending in the news."

        prompt = f"""The topic "{keyword}" is currently trending with these stats:
- Article count: {stats.get('count', 0)}
- Time period: {stats.get('hours', 24)} hours
- Sentiment: {stats.get('sentiment', 0):.2f}
- Momentum: {stats.get('momentum', 1.0):.2f}x
- Categories: {stats.get('categories', [])}

In 2-3 sentences, explain why this topic is trending and what it indicates:"""

        explanation = self.generate(prompt, system=system_prompt, max_tokens=200)
        return explanation or f"{keyword} is generating significant news coverage."

    def generate_what_changed_summary(self, changes: Dict[str, any]) -> str:
        """Generate a narrative summary of what changed

        Args:
            changes: Dictionary of changes

        Returns:
            Natural language summary
        """
        system_prompt = "You are a news briefing assistant. Create engaging summaries of news changes."

        new_topics = changes.get('new_trending_topics', [])
        topics_text = ", ".join(new_topics[:5]) if new_topics else "none"

        prompt = f"""Since the user's last visit:
- New articles: {changes.get('new_articles', 0)}
- New trending topics: {topics_text}
- Sentiment shifts detected: {changes.get('sentiment_changes', 0)}
- Time away: {changes.get('time_away', 'unknown')}

Create a friendly 2-sentence summary of what's changed:"""

        summary = self.generate(prompt, system=system_prompt, max_tokens=150)
        return summary or "Several new developments since your last visit."
