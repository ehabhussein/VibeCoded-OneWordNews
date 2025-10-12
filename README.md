# OneWordNews

Real-time monitoring platform for market-moving news with sentiment analysis, crypto price tracking, and keyword visualization.

## Features

- 📰 **100+ RSS News Feeds** - Real-time monitoring of major news sources
- 💰 **Crypto Price Tracking** - Live Binance prices for 11+ cryptocurrencies
- 📊 **Sentiment Analysis** - CPU-based analysis of all news content
- 🔥 **Keyword Heatmaps** - Interactive visualization with timeline/frequency views
- 📅 **Forex Calendar** - Automated high-impact USD event tracking
- 🐦 **Twitter Integration** - Optional monitoring (Trump & key accounts)
- 🎯 **Smart Categories** - Trump, FOMC, Markets, Crypto, Commodities, USA News

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Binance API credentials (required)
- Twitter API credentials (optional)

### Installation

1. **Clone the repository**
   ```bash
   cd D:\Repositories\OneWordNews
   ```

2. **Create `.env` file**
   ```bash
   cp env.example .env
   ```

3. **Add your Binance credentials** (required)
   ```env
   BINANCE_API_KEY=your_key_here
   BINANCE_API_SECRET=your_secret_here
   BINANCE_USE_TESTNET=false
   ```

   Get API keys: [Binance API Management](https://www.binance.com/) → Create API → Enable "Reading" permission only

4. **Start the application**
   ```bash
   docker-compose up --build
   ```

5. **Open dashboard**
   ```
   http://localhost:8080
   ```

## Dashboard Features

- **Real-time News Feed** with sentiment scores
- **Crypto Price Ticker** - Live prices with 24h % change
- **Keyword Heatmap** - 4 view modes:
  - Frequency (most common)
  - Timeline (chronological)
  - Semantic (alphabetical)
  - Category (by topic)
- **Sentiment Charts** - Time series analysis
- **Click any keyword** → See all related articles

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `BINANCE_API_KEY` | Binance API Key | ✅ Yes |
| `BINANCE_API_SECRET` | Binance API Secret | ✅ Yes |
| `BINANCE_USE_TESTNET` | Use testnet | No (default: false) |
| `TWITTER_API_KEY` | Twitter API Key | No |
| `TWITTER_API_SECRET` | Twitter API Secret | No |
| `TWITTER_BEARER_TOKEN` | Twitter Bearer Token | No |

### Monitored Cryptocurrencies

BTC, ETH, SOL, TRUMP, PEPE, DOGE, ANIME, PAXG, ADA, SUI, WLFI

## Troubleshooting

**Container won't start?**
```bash
docker-compose logs -f
docker-compose down && docker-compose up --build
```

**Binance connection issues?**
- Verify API keys in `.env`
- Ensure "Enable Reading" permission is enabled
- Check IP whitelist settings (if configured)

**No data showing?**
- Wait 2-5 minutes for RSS feeds to populate
- Check logs: `docker-compose logs -f`

## Project Structure

```
OneWordNews/
├── docker-compose.yml    # Docker setup
├── .env                  # Your credentials
├── src/                  # Python application
├── templates/            # Dashboard HTML
├── static/               # Dashboard JavaScript
├── data/                 # Database (auto-created)
└── logs/                 # Application logs
```

## Tech Stack

- Python 3.11 + Flask
- Binance WebSocket API
- Feedparser (RSS)
- Transformers (Sentiment)
- Redis (Real-time)
- SQLite (Storage)
- D3.js + Bootstrap (UI)

## License

MIT - Provided as-is for educational and monitoring purposes.
