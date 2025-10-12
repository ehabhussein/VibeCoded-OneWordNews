"""
Redis Message Queue for Hub Architecture
Centralizes all pub/sub communication between workers and web clients
"""
import redis
import json
import logging
import os
from typing import Dict, Any, Optional


class MessageQueue:
    """Redis-based message queue for publishing updates to the hub"""

    # Channel names
    CHANNEL_TWEETS = 'channel:tweets'
    CHANNEL_ALERTS = 'channel:alerts'
    CHANNEL_STATS = 'channel:stats'
    CHANNEL_CRYPTO = 'channel:crypto'
    CHANNEL_FOREX = 'channel:forex'

    def __init__(self, redis_url: Optional[str] = None):
        """
        Initialize Redis connection

        Args:
            redis_url: Redis connection URL (defaults to REDIS_URL env var or localhost)
        """
        self.logger = logging.getLogger(__name__)

        # Get Redis URL from environment or use default
        self.redis_url = redis_url or os.getenv('REDIS_URL', 'redis://localhost:6379')

        try:
            self.redis_client = redis.from_url(
                self.redis_url,
                decode_responses=True,  # Auto-decode to strings
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30
            )

            # Test connection
            self.redis_client.ping()
            self.logger.info(f"✅ Connected to Redis at {self.redis_url}")

        except Exception as e:
            self.logger.error(f"❌ Failed to connect to Redis: {e}")
            self.redis_client = None

    def is_connected(self) -> bool:
        """Check if Redis is connected"""
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except:
            return False

    def publish(self, channel: str, message: Dict[str, Any]) -> bool:
        """
        Publish a message to a Redis channel

        Args:
            channel: Channel name
            message: Dictionary to publish (will be JSON-encoded)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            self.logger.warning(f"Redis not connected, skipping publish to {channel}")
            return False

        try:
            json_message = json.dumps(message)
            self.redis_client.publish(channel, json_message)
            self.logger.debug(f"📤 Published to {channel}: {len(json_message)} bytes")
            return True

        except Exception as e:
            self.logger.error(f"Failed to publish to {channel}: {e}")
            return False

    def publish_tweet(self, tweet_data: Dict[str, Any]) -> bool:
        """Publish new tweet event"""
        return self.publish(self.CHANNEL_TWEETS, {
            'type': 'new_tweet',
            'data': tweet_data
        })

    def publish_alert(self, alert_data: Dict[str, Any]) -> bool:
        """Publish new alert event"""
        return self.publish(self.CHANNEL_ALERTS, {
            'type': 'new_alert',
            'data': alert_data
        })

    def publish_stats(self, stats_data: Dict[str, Any]) -> bool:
        """Publish stats update event"""
        return self.publish(self.CHANNEL_STATS, {
            'type': 'stats_update',
            'data': stats_data
        })

    def publish_crypto(self, crypto_data: Dict[str, Any]) -> bool:
        """Publish crypto price update event"""
        return self.publish(self.CHANNEL_CRYPTO, {
            'type': 'crypto_update',
            'data': crypto_data
        })

    def publish_forex(self, forex_data: Dict[str, Any]) -> bool:
        """Publish forex event"""
        return self.publish(self.CHANNEL_FOREX, {
            'type': 'forex_event',
            'data': forex_data
        })

    def subscribe(self, *channels):
        """
        Subscribe to one or more channels

        Args:
            *channels: Channel names to subscribe to

        Returns:
            PubSub object for listening
        """
        if not self.is_connected():
            self.logger.error("Cannot subscribe: Redis not connected")
            return None

        try:
            pubsub = self.redis_client.pubsub()
            pubsub.subscribe(*channels)
            self.logger.info(f"📥 Subscribed to channels: {', '.join(channels)}")
            return pubsub

        except Exception as e:
            self.logger.error(f"Failed to subscribe: {e}")
            return None

    def get_message(self, pubsub, timeout: float = 1.0) -> Optional[Dict[str, Any]]:
        """
        Get next message from subscription

        Args:
            pubsub: PubSub object from subscribe()
            timeout: Timeout in seconds

        Returns:
            Decoded message dictionary or None
        """
        try:
            message = pubsub.get_message(timeout=timeout)

            if message and message['type'] == 'message':
                data = json.loads(message['data'])
                return data

            return None

        except Exception as e:
            self.logger.error(f"Failed to get message: {e}")
            return None

    def close(self):
        """Close Redis connection"""
        if self.redis_client:
            try:
                self.redis_client.close()
                self.logger.info("Redis connection closed")
            except Exception as e:
                self.logger.error(f"Error closing Redis: {e}")

    def clear_all(self) -> bool:
        """Clear all Redis keys (admin function)

        Returns:
            True if successful, False otherwise
        """
        if not self.is_connected():
            self.logger.warning("Redis not connected, cannot clear")
            return False

        try:
            # Flush all keys in the current database
            self.redis_client.flushdb()
            self.logger.warning("🗑️ Cleared all Redis cache")
            return True
        except Exception as e:
            self.logger.error(f"Error clearing Redis: {e}")
            return False


# Global singleton instance
_message_queue = None

def get_message_queue() -> MessageQueue:
    """Get or create global MessageQueue instance"""
    global _message_queue
    if _message_queue is None:
        _message_queue = MessageQueue()
    return _message_queue
