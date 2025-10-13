from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
from flask_cors import CORS
import plotly.graph_objs as go
import plotly.utils
import json
from datetime import datetime, timedelta
import logging
import os
import threading
from message_queue import MessageQueue
from crypto_predictor import CryptoPredictor


class WebApp:
    def __init__(self, db, binance_monitor=None, rss_monitor=None, port=8080):
        """Initialize Flask web application with Redis hub"""
        self.db = db
        self.binance_monitor = binance_monitor
        self.rss_monitor = rss_monitor
        self.port = port

        # Initialize crypto predictor
        self.crypto_predictor = CryptoPredictor(db)

        self.app = Flask(__name__,
                         template_folder='../templates',
                         static_folder='../static')
        self.app.config['SECRET_KEY'] = 'twitter-sentiment-bot-secret-key'

        CORS(self.app)

        # Configure Socket.IO with Redis message queue for hub architecture
        redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.socketio = SocketIO(
            self.app,
            cors_allowed_origins="*",
            message_queue=redis_url,  # Enable Redis adapter for multi-server support
            async_mode='threading'
        )

        self.logger = logging.getLogger(__name__)

        # Initialize message queue for subscribing to worker updates
        self.mq = MessageQueue(redis_url)

        # Start Redis subscription thread
        self._start_redis_subscriber()

        # Register routes
        self._register_routes()

    def _register_routes(self):
        """Register Flask routes"""

        @self.app.route('/')
        def index():
            """Main dashboard"""
            return render_template('dashboard.html')

        @self.app.route('/api/stats')
        def get_stats():
            """Get dashboard statistics"""
            try:
                stats = self.db.get_dashboard_stats()
                return jsonify(stats)
            except Exception as e:
                self.logger.error(f"Error getting stats: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/tweets')
        def get_tweets():
            """Get recent tweets"""
            try:
                category = request.args.get('category', None)
                hours = request.args.get('hours', None)
                hours = int(hours) if hours else None
                limit = int(request.args.get('limit', 100))

                tweets = self.db.get_recent_tweets(category=category, hours=hours, limit=limit)
                return jsonify(tweets)
            except Exception as e:
                self.logger.error(f"Error getting tweets: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/wordcloud')
        def get_wordcloud():
            """Get word frequency data for word cloud"""
            try:
                category = request.args.get('category', None)
                hours = int(request.args.get('hours', 24))
                limit = int(request.args.get('limit', 100))

                words = self.db.get_word_frequency_stats(
                    category=category,
                    hours=hours,
                    limit=limit
                )

                return jsonify(words)
            except Exception as e:
                self.logger.error(f"Error getting word cloud data: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/sentiment/timeseries')
        def get_sentiment_timeseries():
            """Get sentiment time series data"""
            try:
                category = request.args.get('category', None)
                hours = int(request.args.get('hours', 24))

                data = self.db.get_sentiment_time_series(category=category, hours=hours)
                return jsonify(data)
            except Exception as e:
                self.logger.error(f"Error getting time series: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/alerts')
        def get_alerts():
            """Get recent alerts"""
            try:
                limit = int(request.args.get('limit', 50))
                alerts = self.db.get_alerts(limit=limit)
                return jsonify(alerts)
            except Exception as e:
                self.logger.error(f"Error getting alerts: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/forex/calendar')
        def get_forex_calendar():
            """Get Forex Factory calendar events for current week"""
            try:
                # Import here to avoid circular dependency
                from main import OneWordNews

                # Access the forex scraper through the main app instance
                # For now, return empty data - will be populated by forex monitoring thread
                # This endpoint will be used to fetch stored forex events from alerts table

                # Get recent forex calendar alerts
                all_alerts = self.db.get_alerts(limit=200)
                forex_alerts = [a for a in all_alerts if a.get('alert_type') == 'forex_calendar']

                # Sort by event date (extract from message)
                def get_event_date(alert):
                    try:
                        # Extract date from message (format: "Date: Thursday, October 16, 2025")
                        message = alert.get('message', '')
                        for line in message.split('\n'):
                            if line.startswith('Date:'):
                                date_str = line.replace('Date:', '').strip()
                                # Remove TODAY/TOMORROW prefix if present
                                if '(' in date_str:
                                    date_str = date_str.split('(')[1].replace(')', '')
                                # Parse date
                                return datetime.strptime(date_str, '%A, %B %d, %Y')
                    except:
                        pass
                    # Fallback to created_at
                    return datetime.fromisoformat(alert.get('created_at', datetime.now().isoformat()))

                forex_alerts_sorted = sorted(forex_alerts, key=get_event_date)

                return jsonify({
                    'week': datetime.now().strftime("%b %d, %Y"),
                    'last_updated': datetime.now().isoformat(),
                    'events': forex_alerts_sorted[:50]  # Return up to 50 forex events
                })
            except Exception as e:
                self.logger.error(f"Error getting forex calendar: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/visualizations/sentiment-chart')
        def sentiment_chart():
            """Generate sentiment time series chart"""
            try:
                category = request.args.get('category', None)
                hours = int(request.args.get('hours', 24))

                data = self.db.get_sentiment_time_series(category=category, hours=hours)

                if not data:
                    return jsonify({'data': [], 'layout': {}})

                # Create Plotly chart
                timestamps = [d['timestamp'] for d in data]
                sentiments = [d['avg_sentiment'] for d in data]
                counts = [d['tweet_count'] for d in data]

                fig = go.Figure()

                # Sentiment line
                fig.add_trace(go.Scatter(
                    x=timestamps,
                    y=sentiments,
                    mode='lines+markers',
                    name='Sentiment Score',
                    line=dict(color='blue', width=2),
                    hovertemplate='%{x}<br>Sentiment: %{y:.2f}<extra></extra>'
                ))

                # Add zero line
                fig.add_hline(y=0, line_dash="dash", line_color="gray", opacity=0.5)

                fig.update_layout(
                    title=f'Sentiment Over Time - {category.upper() if category else "All"}',
                    xaxis_title='Time',
                    yaxis_title='Sentiment Score',
                    hovermode='x unified',
                    plot_bgcolor='white',
                    yaxis=dict(range=[-1, 1])
                )

                return jsonify(json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)))

            except Exception as e:
                self.logger.error(f"Error creating sentiment chart: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/visualizations/word-frequency')
        def word_frequency_chart():
            """Generate word frequency bar chart"""
            try:
                category = request.args.get('category', None)
                hours = int(request.args.get('hours', 24))
                limit = int(request.args.get('limit', 100))

                words = self.db.get_word_frequency_stats(
                    category=category,
                    hours=hours,
                    limit=limit
                )

                if not words:
                    return jsonify({'data': [], 'layout': {}})

                # Create bar chart
                word_list = [w['word'] for w in words]
                counts = [w['count'] for w in words]

                fig = go.Figure(data=[
                    go.Bar(
                        x=word_list,
                        y=counts,
                        marker_color='lightblue',
                        hovertemplate='%{x}<br>Count: %{y}<extra></extra>'
                    )
                ])

                fig.update_layout(
                    title=f'Top Keywords - {category.upper() if category else "All"}',
                    xaxis_title='Keywords',
                    yaxis_title='Frequency',
                    plot_bgcolor='white',
                    xaxis_tickangle=-45
                )

                return jsonify(json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)))

            except Exception as e:
                self.logger.error(f"Error creating word frequency chart: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/visualizations/category-distribution')
        def category_distribution():
            """Generate category distribution pie chart"""
            try:
                stats = self.db.get_dashboard_stats()
                tweets_by_cat = stats.get('tweets_by_category', [])

                if not tweets_by_cat:
                    return jsonify({'data': [], 'layout': {}})

                categories = [c['category'] for c in tweets_by_cat]
                counts = [c['count'] for c in tweets_by_cat]

                fig = go.Figure(data=[
                    go.Pie(
                        labels=categories,
                        values=counts,
                        hole=0.3,
                        hovertemplate='%{label}<br>Count: %{value}<br>%{percent}<extra></extra>'
                    )
                ])

                fig.update_layout(
                    title='Tweet Distribution by Category',
                    plot_bgcolor='white'
                )

                return jsonify(json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)))

            except Exception as e:
                self.logger.error(f"Error creating category distribution chart: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/crypto/prices')
        def crypto_prices():
            """Get current crypto prices"""
            try:
                if not self.binance_monitor:
                    return jsonify({'error': 'Binance monitor not available'}), 503

                status = self.binance_monitor.get_current_status()
                return jsonify(status)
            except Exception as e:
                self.logger.error(f"Error getting crypto prices: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/visualizations/crypto-chart')
        def crypto_chart():
            """Generate crypto price chart"""
            try:
                if not self.binance_monitor:
                    return jsonify({'data': [], 'layout': {}})

                status = self.binance_monitor.get_current_status()

                if not status:
                    return jsonify({'data': [], 'layout': {}})

                # Create chart with current prices and changes
                symbols = []
                prices = []
                changes = []
                colors = []
                price_labels = []

                for symbol, data in status.items():
                    symbols.append(symbol.replace('USDT', ''))
                    price = data['current_price']
                    prices.append(price)
                    change = data.get('change_percent', 0)
                    changes.append(change if change else 0)
                    colors.append('green' if change and change > 0 else 'red' if change and change < 0 else 'gray')

                    # Format price based on magnitude (show more decimals for small prices)
                    # Also include the percentage change
                    change_sign = '+' if change > 0 else ''
                    change_str = f'{change_sign}{change:.2f}%' if change else '0.00%'

                    if price < 0.01:
                        price_labels.append(f'${price:.8f}\n{change_str}')  # 8 decimals for very small prices like PEPE
                    elif price < 1:
                        price_labels.append(f'${price:.6f}\n{change_str}')  # 6 decimals for small prices
                    elif price < 100:
                        price_labels.append(f'${price:.4f}\n{change_str}')  # 4 decimals for medium prices
                    else:
                        price_labels.append(f'${price:,.2f}\n{change_str}')  # 2 decimals for large prices

                fig = go.Figure()

                # Price bars
                fig.add_trace(go.Bar(
                    x=symbols,
                    y=prices,
                    name='Current Price',
                    marker_color=colors,
                    text=price_labels,
                    textposition='auto',
                    hovertemplate='%{x}<br>Price: %{text}<br>Change: %{customdata:.2f}%<extra></extra>',
                    customdata=changes
                ))

                fig.update_layout(
                    title='Crypto Prices (Real-time WebSocket)',
                    xaxis_title='Symbol',
                    yaxis_title='Price (USDT)',
                    plot_bgcolor='white',
                    yaxis_type='log',  # Log scale for better visualization
                    showlegend=False
                )

                return jsonify(json.loads(json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)))

            except Exception as e:
                self.logger.error(f"Error creating crypto chart: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/crypto/predictions')
        def crypto_predictions():
            """Get crypto price predictions based on sentiment"""
            try:
                # Get predictions for major cryptos
                symbols = ['BTC', 'ETH', 'SOL', 'BNB', 'XRP']
                timeframe = request.args.get('timeframe', '6h')

                predictions = self.crypto_predictor.predict_multiple_cryptos(symbols, timeframe)

                return jsonify({
                    'predictions': predictions,
                    'generated_at': datetime.now().isoformat(),
                    'timeframe': timeframe
                })
            except Exception as e:
                self.logger.error(f"Error getting crypto predictions: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/crypto/prediction/<symbol>')
        def crypto_prediction_single(symbol):
            """Get price prediction for a specific crypto"""
            try:
                timeframe = request.args.get('timeframe', '6h')
                prediction = self.crypto_predictor.predict_price_movement(symbol, timeframe)

                return jsonify(prediction)
            except Exception as e:
                self.logger.error(f"Error getting crypto prediction for {symbol}: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/crypto/sentiment-trend/<symbol>')
        def crypto_sentiment_trend(symbol):
            """Get sentiment trend analysis for a crypto"""
            try:
                hours = int(request.args.get('hours', 24))
                trend = self.crypto_predictor.get_sentiment_trend(symbol, hours)

                return jsonify(trend)
            except Exception as e:
                self.logger.error(f"Error getting sentiment trend for {symbol}: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/admin/refresh-rss', methods=['POST'])
        def refresh_rss():
            """Force refresh all RSS feeds"""
            try:
                if not self.rss_monitor:
                    return jsonify({'error': 'RSS monitor not available'}), 503

                # Trigger immediate RSS fetch
                self.logger.info("Admin triggered RSS refresh")
                self.rss_monitor.fetch_all_feeds()

                return jsonify({
                    'status': 'success',
                    'message': 'RSS feeds refreshed successfully'
                })
            except Exception as e:
                self.logger.error(f"Error refreshing RSS feeds: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/admin/clear-database', methods=['POST'])
        def clear_database():
            """Clear all database tables and Redis cache"""
            try:
                self.logger.warning("Admin triggered database and cache clear")

                # Clear database tables
                self.db.clear_all_data()

                # Clear Redis cache
                self.mq.clear_all()

                return jsonify({
                    'status': 'success',
                    'message': 'Database and Redis cache cleared successfully'
                })
            except Exception as e:
                self.logger.error(f"Error clearing database: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/keyword/<keyword>/articles')
        def get_keyword_articles(keyword):
            """Get news articles for a specific keyword"""
            try:
                hours = int(request.args.get('hours', 24))
                limit = int(request.args.get('limit', 50))

                articles = self.db.get_tweets_by_keyword(
                    keyword=keyword,
                    hours=hours,
                    limit=limit
                )

                return jsonify({
                    'keyword': keyword,
                    'count': len(articles),
                    'articles': articles
                })
            except Exception as e:
                self.logger.error(f"Error getting keyword articles: {e}")
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/source-network')
        def source_network():
            """Get source-keyword network data"""
            try:
                category = request.args.get('category', None)
                hours = int(request.args.get('hours', 2))

                # Get recent tweets with their sources
                tweets = self.db.get_recent_tweets(category=category, limit=200)

                # Build source-keyword mapping
                source_keywords = {}
                for tweet in tweets:
                    source = tweet.get('user_handle', 'Unknown')
                    tweet_id = tweet.get('tweet_id')

                    # Get keywords for this tweet
                    keywords = self.db.get_tweet_keywords(tweet_id, hours=hours)

                    if source not in source_keywords:
                        source_keywords[source] = set()

                    for kw in keywords:
                        source_keywords[source].add(kw.get('word', ''))

                # Build network graph data
                nodes = []
                links = []

                # Add source nodes
                source_list = list(source_keywords.keys())
                for idx, source in enumerate(source_list):
                    nodes.append({
                        'id': source,
                        'name': source,
                        'type': 'source',
                        'keywords': len(source_keywords[source])
                    })

                # Calculate similarity between sources
                for i in range(len(source_list)):
                    for j in range(i + 1, len(source_list)):
                        source1 = source_list[i]
                        source2 = source_list[j]

                        # Find shared keywords
                        shared = source_keywords[source1] & source_keywords[source2]

                        if len(shared) > 0:  # Only create link if they share keywords
                            links.append({
                                'source': source1,
                                'target': source2,
                                'value': len(shared),
                                'keywords': list(shared)[:5]  # Top 5 shared keywords
                            })

                return jsonify({
                    'nodes': nodes,
                    'links': links
                })

            except Exception as e:
                self.logger.error(f"Error creating source network: {e}")
                return jsonify({'error': str(e)}), 500

        @self.socketio.on('connect')
        def handle_connect():
            """Handle WebSocket connection"""
            self.logger.info('Client connected')
            emit('connected', {'data': 'Connected to sentiment bot'})

        @self.socketio.on('disconnect')
        def handle_disconnect():
            """Handle WebSocket disconnection"""
            self.logger.info('Client disconnected')

    def _start_redis_subscriber(self):
        """Start background thread to subscribe to Redis channels"""
        def redis_subscriber():
            self.logger.info("🔄 Starting Redis subscriber thread...")

            # Subscribe to all worker channels
            pubsub = self.mq.subscribe(
                MessageQueue.CHANNEL_TWEETS,
                MessageQueue.CHANNEL_ALERTS,
                MessageQueue.CHANNEL_STATS,
                MessageQueue.CHANNEL_CRYPTO,
                MessageQueue.CHANNEL_FOREX
            )

            if not pubsub:
                self.logger.error("Failed to subscribe to Redis channels")
                return

            self.logger.info("✅ Redis subscriber ready, listening for worker updates...")

            # Listen for messages and broadcast to all clients
            while True:
                try:
                    message = self.mq.get_message(pubsub, timeout=1.0)

                    if message:
                        msg_type = message.get('type')
                        data = message.get('data')

                        # Broadcast to all connected Socket.IO clients
                        if msg_type == 'new_tweet':
                            self.socketio.emit('new_tweet', data)
                            self.logger.debug(f"📤 Broadcasted new_tweet to all clients")

                        elif msg_type == 'new_alert':
                            self.socketio.emit('new_alert', data)
                            self.logger.debug(f"📤 Broadcasted new_alert to all clients")

                        elif msg_type == 'stats_update':
                            self.socketio.emit('stats_update', data)
                            self.logger.debug(f"📤 Broadcasted stats_update to all clients")

                        elif msg_type == 'crypto_update':
                            self.socketio.emit('crypto_update', data)
                            self.logger.debug(f"📤 Broadcasted crypto_update to all clients")

                        elif msg_type == 'forex_event':
                            self.socketio.emit('forex_event', data)
                            self.logger.debug(f"📤 Broadcasted forex_event to all clients")

                except Exception as e:
                    self.logger.error(f"Error in Redis subscriber: {e}")
                    # Continue listening even if there's an error

        # Start subscriber thread
        subscriber_thread = threading.Thread(target=redis_subscriber, daemon=True)
        subscriber_thread.start()

    # OLD METHODS REMOVED - Now workers publish to Redis, hub broadcasts to clients
    # def emit_new_tweet(), emit_new_alert(), emit_stats_update(), emit_crypto_update()
    # are replaced by Redis pub/sub architecture

    def run(self):
        """Run the Flask application"""
        self.logger.info(f"🚀 Starting web server on port {self.port}")
        self.logger.info(f"🎯 Hub architecture enabled - broadcasting updates from Redis")
        self.socketio.run(self.app, host='0.0.0.0', port=self.port, debug=False, allow_unsafe_werkzeug=True)
