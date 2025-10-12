import logging
import time
import threading
from typing import Dict, List, Optional
from datetime import datetime
from binance.client import Client
from binance.streams import ThreadedWebsocketManager
from binance.exceptions import BinanceAPIException
from message_queue import MessageQueue


class BinanceMonitor:
    def __init__(self, api_key: str, api_secret: str, symbols: List[str],
                 db, web_app=None, use_testnet: bool = False):
        """Initialize Binance price monitor with WebSocket streams"""
        self.api_key = api_key
        self.api_secret = api_secret
        self.symbols = symbols
        self.use_testnet = use_testnet
        self.db = db
        self.web_app = web_app

        self.logger = logging.getLogger(__name__)

        # Initialize message queue for Redis pub/sub
        self.mq = MessageQueue()

        # Initialize Binance client
        if use_testnet:
            self.client = Client(
                api_key=api_key,
                api_secret=api_secret,
                testnet=True
            )
            self.logger.info("Using Binance Testnet")
        else:
            self.client = Client(
                api_key=api_key,
                api_secret=api_secret
            )

        # WebSocket manager
        self.twm = None

        # Price tracking
        self.current_prices = {}
        self.price_history = {symbol: [] for symbol in symbols}
        self.baseline_prices = {}

        # Drop/spike thresholds
        self.drop_threshold = -3.0  # -3% drop triggers alert
        self.spike_threshold = 5.0  # +5% spike triggers alert
        self.monitoring_window = 300  # 5 minutes

        # Control
        self.running = False
        self.baseline_update_thread = None
        self.baseline_update_interval = 3600  # Update baseline every hour

        self.logger.info(f"Binance monitor initialized for {len(symbols)} symbols")

    def _handle_socket_message(self, msg):
        """Handle incoming WebSocket price messages"""
        try:
            if msg['e'] == 'error':
                self.logger.error(f"WebSocket error: {msg}")
                return

            # Parse ticker message
            symbol = msg['s']  # Symbol (e.g., BTCUSDT)
            price = float(msg['c'])  # Current close price

            # Get 24-hour price change percentage directly from the ticker message
            change_24h = float(msg['P']) if 'P' in msg else None  # Price change percent

            # Update current price
            old_price = self.current_prices.get(symbol)
            self.current_prices[symbol] = price

            # Add to history
            self.price_history[symbol].append({
                'price': price,
                'timestamp': datetime.now()
            })

            # Keep only recent history (5 minutes)
            cutoff_time = datetime.now().timestamp() - self.monitoring_window
            self.price_history[symbol] = [
                h for h in self.price_history[symbol]
                if h['timestamp'].timestamp() > cutoff_time
            ]

            # Calculate change from baseline for alert purposes only
            if symbol in self.baseline_prices:
                baseline_change_percent = self.calculate_price_change(symbol, price)

                if baseline_change_percent is not None:
                    # Check for alerts using baseline change
                    self.check_price_alerts(symbol, price, baseline_change_percent)

                # Publish update to Redis hub with 24h change from Binance
                if change_24h is not None:
                    self.mq.publish_crypto({
                        'symbol': symbol,
                        'price': price,
                        'change_percent': change_24h,  # Use Binance's 24h change
                        'baseline_price': self.baseline_prices[symbol]
                    })

        except Exception as e:
            self.logger.error(f"Error handling socket message: {e}", exc_info=True)

    def get_price_change_24h(self, symbol: str) -> Optional[Dict]:
        """Get 24h price change statistics"""
        try:
            ticker = self.client.get_ticker(symbol=symbol)
            return {
                'symbol': symbol,
                'price': float(ticker['lastPrice']),
                'change_24h': float(ticker['priceChangePercent']),
                'high_24h': float(ticker['highPrice']),
                'low_24h': float(ticker['lowPrice']),
                'volume': float(ticker['volume']),
                'quote_volume': float(ticker['quoteVolume'])
            }
        except BinanceAPIException as e:
            self.logger.error(f"Binance API error for {symbol}: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting 24h data for {symbol}: {e}")
            return None

    def calculate_price_change(self, symbol: str, current_price: float) -> Optional[float]:
        """Calculate price change from baseline"""
        if symbol not in self.baseline_prices:
            return None

        baseline = self.baseline_prices[symbol]
        change_percent = ((current_price - baseline) / baseline) * 100
        return change_percent

    def check_price_alerts(self, symbol: str, current_price: float, change_percent: float):
        """Check if price change triggers an alert"""
        try:
            # Drop alert (negative change)
            if change_percent <= self.drop_threshold:
                severity = 'high' if change_percent <= -5.0 else 'medium'

                message = f"🔴 CRYPTO PRICE DROP ALERT\n\n"
                message += f"Symbol: {symbol}\n"
                message += f"Current Price: ${current_price:,.2f}\n"
                message += f"Change: {change_percent:.2f}%\n"
                message += f"Baseline: ${self.baseline_prices[symbol]:,.2f}\n"
                message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

                # Get 24h stats for context
                stats = self.get_price_change_24h(symbol)
                if stats:
                    message += f"\n24h Stats:\n"
                    message += f"High: ${stats['high_24h']:,.2f}\n"
                    message += f"Low: ${stats['low_24h']:,.2f}\n"
                    message += f"24h Change: {stats['change_24h']:.2f}%\n"

                # Save alert
                self.db.insert_alert(
                    alert_type='crypto_price_drop',
                    category='crypto',
                    severity=severity,
                    message=message,
                    data={
                        'symbol': symbol,
                        'current_price': current_price,
                        'change_percent': change_percent,
                        'baseline_price': self.baseline_prices[symbol]
                    }
                )

                self.logger.warning(f"Price drop alert: {symbol} {change_percent:.2f}%")

            # Spike alert (positive change)
            elif change_percent >= self.spike_threshold:
                severity = 'medium' if change_percent >= 10.0 else 'low'

                message = f"🟢 CRYPTO PRICE SPIKE ALERT\n\n"
                message += f"Symbol: {symbol}\n"
                message += f"Current Price: ${current_price:,.2f}\n"
                message += f"Change: +{change_percent:.2f}%\n"
                message += f"Baseline: ${self.baseline_prices[symbol]:,.2f}\n"
                message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"

                # Get 24h stats for context
                stats = self.get_price_change_24h(symbol)
                if stats:
                    message += f"\n24h Stats:\n"
                    message += f"High: ${stats['high_24h']:,.2f}\n"
                    message += f"Low: ${stats['low_24h']:,.2f}\n"
                    message += f"24h Change: {stats['change_24h']:.2f}%\n"

                # Save alert
                self.db.insert_alert(
                    alert_type='crypto_price_spike',
                    category='crypto',
                    severity=severity,
                    message=message,
                    data={
                        'symbol': symbol,
                        'current_price': current_price,
                        'change_percent': change_percent,
                        'baseline_price': self.baseline_prices[symbol]
                    }
                )

                self.logger.info(f"Price spike alert: {symbol} +{change_percent:.2f}%")

        except Exception as e:
            self.logger.error(f"Error checking price alerts: {e}")

    def update_baseline_prices(self):
        """Update baseline prices (called periodically to reset baseline)"""
        self.baseline_prices = self.current_prices.copy()
        self.logger.info("Baseline prices updated")

    def baseline_update_loop(self):
        """Background thread to periodically update baseline prices"""
        self.logger.info("Starting baseline update loop")

        while self.running:
            try:
                time.sleep(self.baseline_update_interval)
                if self.running:
                    self.update_baseline_prices()
            except Exception as e:
                self.logger.error(f"Error in baseline update loop: {e}")

        self.logger.info("Baseline update loop stopped")

    def start(self):
        """Start WebSocket monitoring"""
        if self.running:
            self.logger.warning("Binance monitor already running")
            return

        try:
            self.running = True

            # Initialize WebSocket manager
            self.twm = ThreadedWebsocketManager(
                api_key=self.api_key,
                api_secret=self.api_secret,
                testnet=self.use_testnet
            )
            self.twm.start()

            # Get initial prices using REST API
            self.logger.info("Fetching initial prices...")
            for symbol in self.symbols:
                try:
                    ticker = self.client.get_ticker(symbol=symbol)
                    price = float(ticker['lastPrice'])
                    self.current_prices[symbol] = price
                    self.baseline_prices[symbol] = price
                    self.logger.info(f"{symbol}: ${price:,.2f}")
                except Exception as e:
                    self.logger.error(f"Error fetching initial price for {symbol}: {e}")

            # Start WebSocket streams for all symbols
            # Using ticker stream (24hr ticker) for each symbol
            for symbol in self.symbols:
                try:
                    symbol_lower = symbol.lower()
                    self.twm.start_symbol_ticker_socket(
                        callback=self._handle_socket_message,
                        symbol=symbol_lower
                    )
                    self.logger.info(f"Started WebSocket stream for {symbol}")
                except Exception as e:
                    self.logger.error(f"Error starting WebSocket for {symbol}: {e}")

            # Start baseline update thread
            self.baseline_update_thread = threading.Thread(
                target=self.baseline_update_loop,
                daemon=True
            )
            self.baseline_update_thread.start()

            self.logger.info("Binance WebSocket monitoring started successfully")

        except Exception as e:
            self.logger.error(f"Error starting Binance monitor: {e}", exc_info=True)
            self.running = False

    def stop(self):
        """Stop monitoring"""
        self.running = False

        if self.twm:
            try:
                self.twm.stop()
                self.logger.info("WebSocket manager stopped")
            except Exception as e:
                self.logger.error(f"Error stopping WebSocket manager: {e}")

        if self.baseline_update_thread:
            self.baseline_update_thread.join(timeout=5)

        self.logger.info("Binance monitor stopped")

    def get_current_status(self) -> Dict:
        """Get current status of all monitored symbols"""
        status = {}

        for symbol in self.symbols:
            if symbol in self.current_prices:
                current_price = self.current_prices[symbol]
                baseline_price = self.baseline_prices.get(symbol)

                change_percent = None
                if baseline_price:
                    change_percent = self.calculate_price_change(symbol, current_price)

                status[symbol] = {
                    'current_price': current_price,
                    'baseline_price': baseline_price,
                    'change_percent': change_percent,
                    'last_update': datetime.now().isoformat()
                }

        return status
