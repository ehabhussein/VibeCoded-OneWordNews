import requests
import json
from datetime import datetime
from typing import Dict, List, Optional
import logging


class SlackNotifier:
    """Service for sending notifications to Slack via webhook"""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.logger = logging.getLogger(__name__)

    def send_message(self, text: str, blocks: List[Dict] = None,
                     attachments: List[Dict] = None) -> bool:
        """Send a message to Slack

        Args:
            text: Plain text message (fallback)
            blocks: Slack block kit formatted message
            attachments: Legacy attachments

        Returns:
            True if successful, False otherwise
        """
        try:
            payload = {"text": text}

            if blocks:
                payload["blocks"] = blocks

            if attachments:
                payload["attachments"] = attachments

            response = requests.post(
                self.webhook_url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            )

            if response.status_code == 200:
                self.logger.info("Slack notification sent successfully")
                return True
            else:
                self.logger.error(f"Slack notification failed: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            self.logger.error(f"Error sending Slack notification: {e}")
            return False

    def send_alert(self, title: str, message: str, severity: str = "info",
                   fields: Dict[str, str] = None) -> bool:
        """Send a formatted alert to Slack

        Args:
            title: Alert title
            message: Alert message
            severity: One of: critical, high, medium, low, info
            fields: Additional key-value pairs to display

        Returns:
            True if successful
        """
        # Color coding by severity
        color_map = {
            "critical": "#dc3545",
            "high": "#f91880",
            "medium": "#ffa500",
            "low": "#1da1f2",
            "info": "#17bf63"
        }

        color = color_map.get(severity, "#1da1f2")

        # Build attachment
        attachment = {
            "color": color,
            "title": title,
            "text": message,
            "footer": "OneWordNews Alert System",
            "ts": int(datetime.now().timestamp())
        }

        # Add fields if provided
        if fields:
            attachment["fields"] = [
                {"title": k, "value": str(v), "short": True}
                for k, v in fields.items()
            ]

        return self.send_message(
            text=f"{title}: {message}",
            attachments=[attachment]
        )

    def send_daily_brief(self, brief_type: str, summary: str,
                        stats: Dict[str, any], top_stories: List[Dict]) -> bool:
        """Send a daily briefing to Slack

        Args:
            brief_type: "morning", "midday", or "evening"
            summary: AI-generated summary text
            stats: Statistics dictionary
            top_stories: List of top story dictionaries

        Returns:
            True if successful
        """
        # Create blocks for rich formatting
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"📰 {brief_type.title()} News Brief",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": summary
                }
            },
            {
                "type": "divider"
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*📊 Total Articles:*\n{stats.get('total_articles', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*📈 Avg Sentiment:*\n{stats.get('avg_sentiment', 0):.2f}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*🔥 Trending Topics:*\n{stats.get('trending_count', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*📰 Top Category:*\n{stats.get('top_category', 'N/A')}"
                    }
                ]
            }
        ]

        # Add top stories
        if top_stories:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🔥 Top Stories:*"
                }
            })

            for i, story in enumerate(top_stories[:5], 1):
                sentiment_emoji = "🟢" if story.get('sentiment', 0) > 0.1 else "🔴" if story.get('sentiment', 0) < -0.1 else "⚪"
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"{sentiment_emoji} *{i}. {story.get('keyword', 'Unknown')}*\n_{story.get('summary', 'No summary available')}_"
                    }
                })

        return self.send_message(
            text=f"{brief_type.title()} News Brief",
            blocks=blocks
        )

    def send_trend_alert(self, keyword: str, momentum: float,
                        article_count: int, sentiment: float) -> bool:
        """Send a trending topic alert

        Args:
            keyword: The trending keyword
            momentum: Momentum score (velocity)
            article_count: Number of articles
            sentiment: Average sentiment

        Returns:
            True if successful
        """
        # Determine emoji based on momentum
        if momentum > 2.0:
            emoji = "🚀"
            trend = "Skyrocketing"
        elif momentum > 1.0:
            emoji = "📈"
            trend = "Rising Fast"
        elif momentum > 0.5:
            emoji = "📊"
            trend = "Trending Up"
        else:
            emoji = "💫"
            trend = "Emerging"

        sentiment_text = "Positive" if sentiment > 0.1 else "Negative" if sentiment < -0.1 else "Neutral"
        sentiment_emoji = "🟢" if sentiment > 0.1 else "🔴" if sentiment < -0.1 else "⚪"

        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"{emoji} Trending: {keyword}",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*Trend Status:*\n{trend}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Momentum Score:*\n{momentum:.2f}x"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Article Count:*\n{article_count}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*Sentiment:*\n{sentiment_emoji} {sentiment_text} ({sentiment:.2f})"
                    }
                ]
            }
        ]

        return self.send_message(
            text=f"Trending: {keyword} ({trend})",
            blocks=blocks
        )

    def send_what_changed(self, changes: Dict[str, any]) -> bool:
        """Send a 'What Changed' summary

        Args:
            changes: Dictionary with change statistics

        Returns:
            True if successful
        """
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📊 What's Changed Since Your Last Visit",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*🆕 New Articles:*\n{changes.get('new_articles', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*🔥 New Trending Topics:*\n{changes.get('new_trends', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*📈 Sentiment Shifts:*\n{changes.get('sentiment_changes', 0)}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*⏱️ Time Since Last Visit:*\n{changes.get('time_away', 'N/A')}"
                    }
                ]
            }
        ]

        # Add new trending topics
        if changes.get('new_trending_topics'):
            topics_text = "\n".join([f"• {t}" for t in changes['new_trending_topics'][:5]])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*New Trending Topics:*\n{topics_text}"
                }
            })

        return self.send_message(
            text="What's Changed Summary",
            blocks=blocks
        )
