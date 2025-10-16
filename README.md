# OneWordNews

[![Docker](https://img.shields.io/badge/docker-ready-blue.svg)](https://www.docker.com/)
[![Python](https://img.shields.io/badge/python-3.11-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

Real-time news intelligence platform with AI-powered entity recognition, sentiment analysis, crypto price tracking, and interactive network visualizations.

## Demo Video

[![OneWordNews Demo](https://img.youtube.com/vi/2GX7jer5lWw/maxresdefault.jpg)](https://www.youtube.com/watch?v=2GX7jer5lWw)

**Watch the full demo:** [https://www.youtube.com/watch?v=2GX7jer5lWw](https://www.youtube.com/watch?v=2GX7jer5lWw)

## Features

### Core Intelligence
- 📰 **87 RSS News Feeds** - Real-time monitoring from Reuters, Bloomberg, CNBC, CoinDesk, Cointelegraph, NYT, BBC, and 80+ more sources
- 🤖 **AI Entity Recognition (spaCy NER)** - Extracts people, organizations, locations with context-aware classification
- 📊 **BERT Sentiment Analysis** - Advanced sentiment scoring (-1 to +1) for all articles
- 💰 **Live Crypto Prices** - Binance WebSocket integration for BTC, ETH, SOL, TRUMP, and 7 more

### Visualizations
- 🔗 **Entity Network Graph** - Interactive D3.js force-directed graph showing entities with linked keywords
- 🌐 **Source Network** - Reveals relationships between news sources based on shared keywords
- 🔥 **Keyword Visualizations** - Bubble charts, treemaps, and heatmaps with real-time updates
- 📈 **Sentiment Time Series** - Track sentiment trends across categories and time periods
- 🎨 **Zoom & Pan Controls** - Navigate large network graphs with smooth zoom (0.5x to 4x)

### Intelligence Features
- 🔮 **Crypto Price Predictions** - Sentiment-based signals (Bullish/Bearish/Neutral) with confidence scores
- 📅 **Forex Factory Calendar** - Automated scraping of high-impact USD events with alerts
- 🔔 **Real-time Alerts** - WebSocket-powered live updates for significant sentiment shifts
- 🔍 **Advanced Search** - Search articles by keyword with instant results
- 📊 **Word Frequency Analysis** - Track trending words across all categories
- 🎯 **Smart Categories** - Trump, FOMC, Markets, Crypto, Commodities, USA News

### Integrations
- 🤖 **Ollama AI** - Local LLM integration for article summaries and analysis (Phi-4 or any model)
- 💬 **Slack Notifications** - Send alerts and updates to Slack channels
- 🐦 **Twitter Integration** - Optional monitoring of key accounts (currently disabled)

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Binance API credentials (required)
- Ollama (optional - for AI summaries)
- Slack Webhook URL (optional - for notifications)
- Twitter API credentials (optional)

### Installation

1. **Clone the repository**
   ```bash
   cd D:\Repositories\OneWordNews
   ```

2. **Create `.env` file**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables** in `.env`:

   **Required:**
   ```env
   BINANCE_API_KEY=your_key_here
   BINANCE_API_SECRET=your_secret_here
   BINANCE_USE_TESTNET=false
   ```
   Get API keys: [Binance API Management](https://www.binance.com/) → Create API → Enable "Reading" permission only

   **Optional - Ollama AI Integration:**
   ```env
   OLLAMA_BASE_URL=http://host.docker.internal:11434
   OLLAMA_MODEL=phi4:latest
   ```
   Install Ollama: [https://ollama.com/download](https://ollama.com/download)

   Pull a model: `ollama pull phi4` or `ollama pull llama3.2`

   **Optional - Slack Notifications:**
   ```env
   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
   ```
   Create webhook: [Slack Incoming Webhooks](https://api.slack.com/messaging/webhooks)

4. **Start the application**
   ```bash
   docker-compose up --build
   ```

5. **Open dashboard**
   ```
   http://localhost:8080
   ```

## Dashboard Features

### Main Views
- **📊 Statistics Overview** - Total articles, categories, sentiment breakdown
- **📰 Real-time News Feed** - Live articles with sentiment scores and category tags
- **💰 Crypto Price Ticker** - Live Binance WebSocket prices with 24h % change
- **📈 Sentiment Time Series** - Track sentiment trends over time by category

### Entity Recognition (NEW! 🔥)
- **🔗 Entity Network Graph** - Interactive visualization showing:
  - **Entity Nodes** (colored by type):
    - 👤 Blue = People (PERSON)
    - 🏢 Green = Organizations (ORG)
    - 📍 Pink = Locations (GPE)
  - **Keyword Nodes** (gray) - Words associated with each entity
  - **Links** - Connections showing entity-keyword relationships
- **Zoom Controls** (➕ ➖ ⟲) - Zoom in/out and reset view
- **Mouse Wheel Zoom** - Scroll to zoom, click and drag to pan
- **Filter by Type** - View All, People, Organizations, or Locations
- **Interactive Tooltips** - Hover over nodes to see details

### Keyword Analysis
- **🔥 Latest Keywords (Real-time)** - 3 visualization modes:
  - **Bubble Chart** - Size based on frequency
  - **Heatmap/Treemap** - Grid layout showing density
  - **Source Network** - Interactive graph showing which sources share keywords
- **📊 Word Frequency Chart** - Bar chart of top words
- **🔍 Click any keyword** → See all related articles in modal

### Price Predictions
- **🔮 Crypto Price Predictions** - Sentiment-based analysis for:
  - BTC, ETH, SOL, TRUMP, PEPE, DOGE, ANIME, PAXG, ADA, SUI, WLFI
  - Signals: Bullish 📈 / Bearish 📉 / Neutral ➡️
  - Confidence scores based on article count and sentiment

### Additional Features
- **📅 Forex Calendar** - High-impact USD events from Forex Factory
- **🎯 Category Filters** - Filter by: All, Trump, FOMC, Markets, Crypto, Commodities, USA News
- **🔔 Alerts** - Real-time sentiment alerts and forex event notifications
- **🔄 Admin Controls** - Refresh RSS feeds, clear database, view logs

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| **Binance (Crypto Prices)** |
| `BINANCE_API_KEY` | Binance API Key | ✅ Yes | - |
| `BINANCE_API_SECRET` | Binance API Secret | ✅ Yes | - |
| `BINANCE_USE_TESTNET` | Use testnet | No | `false` |
| `BINANCE_SYMBOLS` | Crypto pairs to track | No | See below |
| **Ollama (AI Summaries)** |
| `OLLAMA_BASE_URL` | Ollama API endpoint | No | `http://host.docker.internal:11434` |
| `OLLAMA_MODEL` | Model to use | No | `phi4:latest` |
| **Slack (Notifications)** |
| `SLACK_WEBHOOK_URL` | Incoming webhook URL | No | - |
| **Twitter (Optional Monitoring)** |
| `TWITTER_API_KEY` | Twitter API Key | No | - |
| `TWITTER_API_SECRET` | Twitter API Secret | No | - |
| `TWITTER_BEARER_TOKEN` | Twitter Bearer Token | No | - |
| `TWITTER_ACCESS_TOKEN` | Access Token | No | - |
| `TWITTER_ACCESS_SECRET` | Access Secret | No | - |

### Monitored Cryptocurrencies

BTC, ETH, SOL, TRUMP, PEPE, DOGE, ANIME, PAXG, ADA, SUI, WLFI

### RSS News Sources (87 Total)

**Crypto News (15 sources):**
- CoinDesk, Cointelegraph, The Block, Crypto.news, Crypto Briefing
- Bitcoinist, U.Today, Decrypt, Cryptonews, BeInCrypto
- Bitcoin.com, CoinMarketCap, Reuters Crypto, InvestingLive, Kitco Gold

**Forex & Commodities (10 sources):**
- Investing.com (News, Forex, Stocks, Crypto, Economics - 5 feeds)
- DailyFX, FXStreet, OilPrice, Natural Gas Intel, Kitco Gold

**Major News Networks (30+ sources):**
- **Reuters** (World, Politics, Top News)
- **Bloomberg** (Politics, Markets)
- **CNBC** (Politics, Market Insider)
- **BBC** (World, Business, US/Canada)
- **NPR** (News, Politics, Business)
- **New York Times** (World, Politics, Business)
- **The Guardian** (US, Business, World)
- **Washington Post** (Politics, World, Business)
- **Associated Press** (Top, US, World, Business)
- **NBC News** (News, Politics)
- **CBS News** (Main, Politics)
- **ABC News** (Top Stories, Politics)
- **Fox News** (Politics)
- **CNN** (All Politics)

**Financial & Business (15+ sources):**
- Wall Street Journal (World, Markets - 2 feeds)
- Financial Times (World, Markets, Companies)
- MarketWatch, Yahoo Finance, Forbes, Business Insider, Seeking Alpha
- The Economist, LA Times Business, Politico, The Hill

**International (8 sources):**
- Al Jazeera, France 24, Sky News, Politico EU
- USA Today, Axios, Newsweek, Time, The Atlantic

**Total: 87 active RSS feeds monitoring crypto, forex, markets, politics, and commodities**

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

**Ollama connection issues?**
```bash
# Check if Ollama is running
curl http://localhost:11434/api/tags

# Check if model is installed
ollama list

# View Ollama logs
docker-compose logs -f | grep -i ollama
```

**Entity Network not showing?**
- Wait for articles to populate (needs at least 10-20 articles)
- Check browser console for JavaScript errors
- Refresh the page after articles are loaded

**Slow performance?**
- Sentiment analysis is CPU-intensive, consider limiting RSS feed frequency
- Close other resource-intensive applications
- For production, use GPU-accelerated sentiment analysis

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

### Backend
- **Python 3.11** - Core application
- **Flask** - Web framework
- **Flask-SocketIO** - WebSocket support for real-time updates
- **spaCy** (en_core_web_sm) - Named Entity Recognition (NER)
- **Transformers (BERT)** - Sentiment analysis
- **Feedparser** - RSS feed parsing
- **Redis** - Pub/sub messaging and caching
- **SQLite** - Data storage with WAL mode

### Frontend
- **D3.js v7** - Interactive visualizations (force-directed graphs, networks)
- **Bootstrap 5** - UI framework
- **Socket.IO** - Real-time WebSocket client
- **Plotly.js** - Charts and graphs

### Integrations
- **Binance WebSocket API** - Live crypto prices
- **Forex Factory** - Economic calendar scraping
- **Ollama** - Local LLM integration (optional)
- **Slack Webhooks** - Notifications (optional)

### Infrastructure
- **Docker + Docker Compose** - Containerization
- **Redis 7 Alpine** - Message broker
- **Python 3.11 Slim** - Base image

## Ollama Integration (Optional)

OneWordNews supports local AI integration via [Ollama](https://ollama.com) for:
- Article summarization
- Sentiment context analysis
- Entity relationship insights
- Custom prompts and analysis

### Setup Ollama

1. **Install Ollama**
   ```bash
   # macOS/Linux
   curl -fsSL https://ollama.com/install.sh | sh

   # Windows: Download from https://ollama.com/download
   ```

2. **Pull a model**
   ```bash
   # Recommended: Phi-4 (3.8B parameters, fast)
   ollama pull phi4

   # Or use Llama 3.2 (3B parameters)
   ollama pull llama3.2

   # Or larger models
   ollama pull llama3:8b
   ollama pull mistral
   ```

3. **Configure in `.env`**
   ```env
   OLLAMA_BASE_URL=http://host.docker.internal:11434
   OLLAMA_MODEL=phi4:latest
   ```

4. **Verify connection**
   ```bash
   curl http://localhost:11434/api/tags
   ```

### Available Models
- **phi4** (3.8B) - Fast, good quality, recommended
- **llama3.2** (3B) - Meta's smaller model, efficient
- **llama3:8b** (8B) - Higher quality, slower
- **mistral** (7B) - Great for analysis tasks
- **qwen2.5** (7B) - Excellent for coding/technical content

### Docker Networking
The container uses `host.docker.internal` to access Ollama running on your host machine. This is automatically configured in the `.env` file.

## Key Implementation Details

### Entity Recognition
- Uses **spaCy's en_core_web_sm** model for Named Entity Recognition (NER)
- **Context-aware classification**: Pattern matching and sentence analysis to correctly classify entities
- **No hardcoding**: Dynamically learns from article content and entity context
- Extracts: PERSON, ORG (organizations), GPE (geopolitical entities), LOC (locations), MONEY, PRODUCT, EVENT
- Stores entity-keyword relationships in SQLite for network visualization

### Network Visualizations
- **D3.js force-directed graphs** with interactive physics simulation
- **Zoom controls**: Mouse wheel zoom (0.5x to 4x), pan by dragging, reset button
- **Boundary clamping**: Prevents nodes from escaping container
- **Dynamic sizing**: Node size based on mention frequency and keyword count
- **Real-time updates**: WebSocket integration for live data updates

### Sentiment Analysis
- **BERT-based** using `distilbert-base-uncased-finetuned-sst-2-english`
- Scores range from -1 (very negative) to +1 (very positive)
- Runs on CPU (no GPU required)
- Cached in SQLite for performance

### Data Flow
1. **RSS Monitor** fetches feeds every 5 minutes
2. **Sentiment Analysis** processes each article
3. **Entity Extraction** identifies people, companies, locations
4. **Keyword Analysis** extracts frequent words
5. **Database Storage** (SQLite with WAL mode)
6. **WebSocket Broadcast** sends updates to dashboard
7. **Real-time Visualization** updates graphs and charts

## Use Cases

- 📊 **Crypto Traders** - Monitor sentiment shifts for BTC, ETH, SOL and altcoins
- 💹 **Forex Traders** - Track high-impact economic events and market sentiment
- 📰 **Journalists** - Identify trending topics and entity mentions across sources
- 🔍 **Researchers** - Analyze media coverage patterns and entity relationships
- 🤖 **Data Scientists** - Study news sentiment correlation with market movements
- 📈 **Analysts** - Track keyword trends and source credibility over time

## Performance

- **RSS Refresh**: Every 5 minutes (configurable)
- **WebSocket Updates**: Real-time (sub-second latency)
- **Sentiment Processing**: ~0.5-1s per article (CPU)
- **Entity Extraction**: ~0.2-0.3s per article
- **Database**: SQLite with WAL mode for concurrent reads
- **Memory Usage**: ~500MB - 1GB (depending on model and article count)
- **Disk Space**: ~100MB for database (grows with article history)

## License

MIT - Provided as-is for educational and monitoring purposes.
