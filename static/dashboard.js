// Dashboard JavaScript for Twitter Sentiment Bot

let socket;
let currentCategory = 'all';
let tweets = [];
let alerts = [];

// Debounce helper function
function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

// Debounced reload functions (wait 2 seconds before executing)
const debouncedLoadStats = debounce(loadStats, 2000);
const debouncedLoadSentimentChart = debounce(loadSentimentChart, 2000);
const debouncedLoadWordFrequencyChart = debounce(loadWordFrequencyChart, 2000);
const debouncedLoadCategoryChart = debounce(loadCategoryChart, 2000);
const debouncedLoadLatestKeywords = debounce(loadLatestKeywords, 2000);
const debouncedLoadCryptoChart = debounce(loadCryptoChart, 2000);

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Initialize WebSocket connection
    initializeWebSocket();

    // Load initial data
    loadStats();
    loadTweets();
    loadAlerts();
    createEntityNetwork(); // Load entity network
    loadCharts();
    loadForexCalendar();
    loadLatestKeywords();

    // Setup category filter buttons
    setupCategoryFilters();

    // Setup admin control buttons
    setupAdminButtons();

    // Setup entity type buttons
    setupEntityButtons();

    // No periodic polling - all updates via WebSocket real-time
});

// Initialize WebSocket connection
function initializeWebSocket() {
    socket = io();

    socket.on('connect', function() {
        updateConnectionStatus(true);
    });

    socket.on('disconnect', function() {
        updateConnectionStatus(false);
    });

    socket.on('new_tweet', function(data) {
        addNewTweet(data);

        // Add keywords to latest keywords display
        if (data.keywords && data.keywords.length > 0) {
            addLatestKeywords(data.keywords, data.category);
        }

        // Update visualizations using debounced functions (prevents too many requests)
        debouncedLoadStats();
        debouncedLoadSentimentChart();
        debouncedLoadWordFrequencyChart();
        debouncedLoadCategoryChart();
    });

    socket.on('new_alert', function(data) {
        addNewAlert(data);
        debouncedLoadStats();
    });

    socket.on('stats_update', function(data) {
        updateStats(data);
    });

    socket.on('crypto_update', function(data) {
        // Real-time crypto price update from Redis hub
        updateCryptoChartRealtime(data);
    });
}

// Update connection status indicator
function updateConnectionStatus(connected) {
    const indicator = document.getElementById('connectionStatus');
    if (indicator) {
        if (connected) {
            indicator.classList.remove('disconnected');
            indicator.classList.add('connected');
        } else {
            indicator.classList.remove('connected');
            indicator.classList.add('disconnected');
        }
    }
}

// Load statistics
function loadStats() {
    fetch('/api/stats')
        .then(response => response.json())
        .then(data => {
            updateStats(data);
        })
        .catch(error => {});
}

// Update statistics display
function updateStats(data) {
    document.getElementById('totalTweets').textContent = data.total_tweets || 0;
    document.getElementById('recentAlerts').textContent = data.recent_alerts || 0;

    // Calculate average sentiment
    if (data.sentiment_by_category && data.sentiment_by_category.length > 0) {
        const avgSentiment = data.sentiment_by_category.reduce((sum, cat) => sum + cat.avg_sentiment, 0) / data.sentiment_by_category.length;
        document.getElementById('avgSentiment').textContent = avgSentiment.toFixed(2);
        document.getElementById('avgSentiment').style.color = getSentimentColor(avgSentiment);
    }

    // Update last update time (if element exists)
    const lastUpdateEl = document.getElementById('lastUpdate');
    if (lastUpdateEl) {
        const now = new Date();
        lastUpdateEl.textContent = `Last update: ${now.toLocaleTimeString()}`;
    }
}

// Load tweets
function loadTweets() {
    const category = currentCategory === 'all' ? '' : currentCategory;
    // Use current24hTimeRange to filter tweets by time
    const hours = current24hTimeRange || 24;

    let url = `/api/tweets?hours=${hours}&limit=50`;
    if (category) {
        url += `&category=${category}`;
    }

    fetch(url)
        .then(response => response.json())
        .then(data => {
            tweets = data;
            displayTweets(data);
        })
        .catch(error => {});
}

// Display tweets
function displayTweets(tweetsData) {
    const container = document.getElementById('tweetsContainer');

    // Container no longer exists (Recent Tweets removed)
    if (!container) {
        return;
    }

    if (!tweetsData || tweetsData.length === 0) {
        container.innerHTML = '<p class="text-center text-muted">No tweets found</p>';
        return;
    }

    container.innerHTML = tweetsData.map(tweet => createTweetCard(tweet)).join('');
}

// Create tweet card HTML
function createTweetCard(tweet) {
    const sentiment = tweet.sentiment_label || 'neutral';
    const sentimentScore = tweet.sentiment_score || 0;
    const category = tweet.category || 'general';
    const userHandle = tweet.user_handle || 'Unknown';
    const text = tweet.text || '';
    const createdAt = new Date(tweet.created_at).toLocaleString();
    const articleUrl = tweet.url || '';

    return `
        <div class="tweet-card">
            <div class="d-flex justify-content-between align-items-start mb-2">
                <div>
                    <span class="category-badge">${category.toUpperCase()}</span>
                    <span class="sentiment-badge sentiment-${sentiment.replace('_', '-')}">${sentiment.replace('_', ' ').toUpperCase()}</span>
                </div>
                <small class="text-muted">${createdAt}</small>
            </div>
            <div class="mb-2">
                <strong>@${userHandle}</strong>
            </div>
            <p class="mb-2">${escapeHtml(text)}</p>
            <div class="d-flex justify-content-between align-items-center">
                <small class="text-muted">Sentiment Score: ${sentimentScore.toFixed(2)}</small>
                <div class="d-flex align-items-center">
                    <small class="text-muted me-3">❤️ ${tweet.like_count || 0}</small>
                    <small class="text-muted me-3">🔄 ${tweet.retweet_count || 0}</small>
                    <small class="text-muted me-3">💬 ${tweet.reply_count || 0}</small>
                    ${articleUrl ? `<a href="${articleUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary">Open Article</a>` : ''}
                </div>
            </div>
        </div>
    `;
}

// Add new tweet to the top of the list
function addNewTweet(tweetData) {
    const container = document.getElementById('tweetsContainer');

    // Container no longer exists (Recent Tweets removed), just update visualizations
    if (!container) {
        return;
    }

    // Check if container is empty
    if (container.querySelector('.text-muted')) {
        container.innerHTML = '';
    }

    const tweetCard = createTweetCard(tweetData);
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = tweetCard;
    const newCard = tempDiv.firstElementChild;
    newCard.classList.add('new');

    container.insertBefore(newCard, container.firstChild);

    // Remove 'new' class after animation
    setTimeout(() => newCard.classList.remove('new'), 1000);

    // Keep only the last 50 tweets
    while (container.children.length > 50) {
        container.removeChild(container.lastChild);
    }
}

// Load trending entities
// Track entity network state
let currentEntityNetworkData = null;
let currentEntityNetworkSimulation = null;
let entityNetworkElements = null;
let currentEntityType = '';

// Create Entity Network Graph
function createEntityNetwork(entityType = '') {
    const container = document.getElementById('entityNetworkContainer');
    currentEntityType = entityType;

    // Fetch entity-keyword network data
    const hours = 24;
    const entityLimit = 20;
    const keywordsPerEntity = 10;
    const minKeywordCount = 3;
    let url = `/api/entities/network?hours=${hours}&entity_limit=${entityLimit}&keywords_per_entity=${keywordsPerEntity}&min_keyword_count=${minKeywordCount}`;
    if (entityType) {
        url += `&type=${entityType}`;
    }

    // Show loading message
    container.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 800px; color: #8b98a5;"><span>Loading entity-keyword network...</span></div>';

    fetch(url)
        .then(response => response.json())
        .then(networkData => {
            if (!networkData.nodes || networkData.nodes.length === 0) {
                container.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 800px; color: #8b98a5;">No entities with keywords available</div>';
                return;
            }

            // Store network data
            currentEntityNetworkData = networkData;

            // Clear container
            container.innerHTML = '';

            // Make container relative and hide overflow to prevent graph escaping
            container.style.position = 'relative';
            container.style.overflow = 'hidden';

            const width = container.clientWidth;
            // Dynamic height based on number of nodes for better visibility
            const height = Math.max(800, networkData.nodes.length * 40);

            // Create SVG with viewBox for proper containment
            const svg = d3.select(container)
                .append('svg')
                .attr('width', width)
                .attr('height', height)
                .attr('viewBox', `0 0 ${width} ${height}`)
                .style('display', 'block');

            // Add zoom controls container
            const controls = d3.select(container)
                .append('div')
                .style('position', 'absolute')
                .style('top', '10px')
                .style('right', '10px')
                .style('display', 'flex')
                .style('gap', '5px')
                .style('z-index', '100');

            // Add zoom in button
            controls.append('button')
                .attr('title', 'Zoom In')
                .style('background', '#16181c')
                .style('border', '1px solid #2f3336')
                .style('color', '#e7e9ea')
                .style('padding', '8px 12px')
                .style('cursor', 'pointer')
                .style('border-radius', '4px')
                .style('font-size', '16px')
                .style('transition', 'all 0.2s')
                .html('➕')
                .on('mouseenter', function() {
                    d3.select(this).style('background', '#1da1f2').style('border-color', '#1da1f2');
                })
                .on('mouseleave', function() {
                    d3.select(this).style('background', '#16181c').style('border-color', '#2f3336');
                })
                .on('click', function() {
                    svg.transition().call(zoom.scaleBy, 1.3);
                });

            // Add zoom out button
            controls.append('button')
                .attr('title', 'Zoom Out')
                .style('background', '#16181c')
                .style('border', '1px solid #2f3336')
                .style('color', '#e7e9ea')
                .style('padding', '8px 12px')
                .style('cursor', 'pointer')
                .style('border-radius', '4px')
                .style('font-size', '16px')
                .style('transition', 'all 0.2s')
                .html('➖')
                .on('mouseenter', function() {
                    d3.select(this).style('background', '#1da1f2').style('border-color', '#1da1f2');
                })
                .on('mouseleave', function() {
                    d3.select(this).style('background', '#16181c').style('border-color', '#2f3336');
                })
                .on('click', function() {
                    svg.transition().call(zoom.scaleBy, 0.7);
                });

            // Add reset button
            controls.append('button')
                .attr('title', 'Reset View')
                .style('background', '#16181c')
                .style('border', '1px solid #2f3336')
                .style('color', '#e7e9ea')
                .style('padding', '8px 12px')
                .style('cursor', 'pointer')
                .style('border-radius', '4px')
                .style('font-size', '14px')
                .style('transition', 'all 0.2s')
                .html('⟲')
                .on('mouseenter', function() {
                    d3.select(this).style('background', '#17bf63').style('border-color', '#17bf63');
                })
                .on('mouseleave', function() {
                    d3.select(this).style('background', '#16181c').style('border-color', '#2f3336');
                })
                .on('click', function() {
                    svg.transition().duration(750).call(
                        zoom.transform,
                        d3.zoomIdentity
                    );
                });

            // Create zoom behavior
            const zoom = d3.zoom()
                .scaleExtent([0.5, 4])  // Allow zoom from 50% to 400%
                .on('zoom', (event) => {
                    g.attr('transform', event.transform);
                });

            // Apply zoom to SVG
            svg.call(zoom);

            // Create main group for zoom/pan
            const g = svg.append('g');

            // Create tooltip
            let tooltip = d3.select(container).select('.entity-network-tooltip');
            if (tooltip.empty()) {
                tooltip = d3.select(container)
                    .append('div')
                    .attr('class', 'entity-network-tooltip')
                    .style('position', 'absolute')
                    .style('visibility', 'hidden')
                    .style('background', 'rgba(15, 20, 25, 0.95)')
                    .style('border', '2px solid #1da1f2')
                    .style('border-radius', '8px')
                    .style('padding', '12px')
                    .style('color', '#e7e9ea')
                    .style('font-size', '13px')
                    .style('max-width', '300px')
                    .style('z-index', '1000')
                    .style('pointer-events', 'none');
            }

            // Create color scale based on entity type
            const entityColorScale = d3.scaleOrdinal()
                .domain(['PERSON', 'ORG', 'GPE', 'LOC', 'MONEY', 'PRODUCT', 'EVENT'])
                .range(['#1da1f2', '#17bf63', '#f91880', '#ffa500', '#ffd700', '#9b59b6', '#e74c3c']);

            // Keyword nodes get a neutral gray color
            const keywordColor = '#8b98a5';

            // Create link strength scale
            const maxValue = d3.max(networkData.links, d => d.value) || 1;
            const linkWidthScale = d3.scaleLinear()
                .domain([0, maxValue])
                .range([1, 4]);

            // Initialize nodes
            networkData.nodes.forEach(node => {
                node.x = width / 2 + (Math.random() - 0.5) * width * 0.8;
                node.y = height / 2 + (Math.random() - 0.5) * height * 0.8;
            });

            // Create force simulation with increased distance and spacing
            const simulation = d3.forceSimulation(networkData.nodes)
                .force('link', d3.forceLink(networkData.links)
                    .id(d => d.id)
                    .distance(d => {
                        // Much greater distance to prevent overlap
                        const sourceIsEntity = d.source.type === 'entity';
                        const targetIsEntity = d.target.type === 'entity';
                        if (sourceIsEntity && targetIsEntity) return 400;
                        return 180;
                    })
                    .strength(0.3))
                .force('charge', d3.forceManyBody()
                    .strength(d => d.type === 'entity' ? -1200 : -500))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collision', d3.forceCollide()
                    .radius(d => {
                        // Collision radius based on actual circle size + padding
                        if (d.type === 'entity') {
                            return Math.sqrt(d.mentions) * 0.5 + 20;
                        } else {
                            return Math.sqrt(d.count) * 0.4 + 15;
                        }
                    }))
                .velocityDecay(0.4);

            // Create links (inside zoom group)
            const linksGroup = g.append('g').attr('class', 'links');
            const linkElements = linksGroup.selectAll('line')
                .data(networkData.links)
                .enter()
                .append('line')
                .attr('stroke', '#536471')
                .attr('stroke-width', d => linkWidthScale(d.value))
                .attr('stroke-opacity', 0.4);

            linkElements.append('title')
                .text(d => `${d.value} co-occurrences`);

            // Create nodes (inside zoom group)
            const nodes = g.append('g')
                .selectAll('g')
                .data(networkData.nodes)
                .enter()
                .append('g')
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));

            // Add circles to nodes
            nodes.append('circle')
                .attr('r', d => {
                    if (d.type === 'entity') {
                        // Entity nodes: much smaller
                        return Math.sqrt(d.mentions) * 0.5 + 6;
                    } else {
                        // Keyword nodes: very small
                        return Math.sqrt(d.count) * 0.4 + 4;
                    }
                })
                .attr('fill', d => {
                    if (d.type === 'entity') {
                        return entityColorScale(d.label);
                    } else {
                        return keywordColor;
                    }
                })
                .attr('stroke', '#0f1419')
                .attr('stroke-width', 2)
                .style('cursor', 'pointer')
                .on('mouseover', function(event, d) {
                    if (d.type === 'entity') {
                        const labelEmoji = {
                            'PERSON': '👤',
                            'ORG': '🏢',
                            'GPE': '📍',
                            'LOC': '🌍',
                            'MONEY': '💰',
                            'PRODUCT': '📦',
                            'EVENT': '🎭'
                        };
                        const emoji = labelEmoji[d.label] || '🔖';
                        tooltip.html(`
                            <strong>${emoji} ${d.id}</strong><br/>
                            Type: ${d.label}<br/>
                            Mentions: ${d.mentions}<br/>
                            Articles: ${d.articles}<br/>
                            <em style="color: #1da1f2; font-size: 11px;">Click to see articles</em>
                        `);
                    } else {
                        tooltip.html(`
                            <strong>🔑 ${d.id}</strong><br/>
                            Type: Keyword<br/>
                            Total Count: ${d.count}<br/>
                            <em style="color: #1da1f2; font-size: 11px;">Click to see articles</em>
                        `);
                    }
                    tooltip.style('visibility', 'visible');
                    d3.select(this).attr('stroke', '#1da1f2').attr('stroke-width', 3);
                })
                .on('mousemove', function(event) {
                    tooltip
                        .style('top', (event.pageY - container.offsetTop + 10) + 'px')
                        .style('left', (event.pageX - container.offsetLeft + 10) + 'px');
                })
                .on('mouseout', function() {
                    tooltip.style('visibility', 'hidden');
                    d3.select(this).attr('stroke', '#0f1419').attr('stroke-width', 2);
                })
                .on('click', function(event, d) {
                    event.stopPropagation();
                    // Show articles modal for this entity or keyword
                    if (d.type === 'entity') {
                        showEntityArticlesModal(d.id);
                    } else {
                        // For keywords, use the existing keyword modal
                        showKeywordArticlesModal(d.id);
                    }
                });

            // Add labels to nodes
            nodes.append('text')
                .text(d => d.id.length > 10 ? d.id.substring(0, 10) + '...' : d.id)
                .attr('text-anchor', 'middle')
                .attr('dy', d => {
                    if (d.type === 'entity') {
                        return Math.sqrt(d.mentions) * 0.5 + 14;
                    } else {
                        return Math.sqrt(d.count) * 0.4 + 11;
                    }
                })
                .attr('fill', '#e7e9ea')
                .attr('font-size', d => d.type === 'entity' ? '10px' : '8px')
                .attr('font-weight', d => d.type === 'entity' ? '700' : '500')
                .style('pointer-events', 'none')
                .style('user-select', 'none');

            // Update positions on tick with boundary clamping
            simulation.on('tick', () => {
                // Clamp node positions to stay within bounds (prevent overflow)
                networkData.nodes.forEach(node => {
                    node.x = Math.max(60, Math.min(width - 60, node.x));
                    node.y = Math.max(60, Math.min(height - 60, node.y));
                });

                linkElements
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);

                nodes.attr('transform', d => `translate(${d.x},${d.y})`);
            });

            // Drag functions
            function dragstarted(event, d) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }

            function dragged(event, d) {
                d.fx = event.x;
                d.fy = event.y;
            }

            function dragended(event, d) {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }

            // Store simulation reference
            currentEntityNetworkSimulation = simulation;
            entityNetworkElements = { svg, g, zoom, linkElements, nodes, entityColorScale, linkWidthScale };
        })
        .catch(error => {
            console.error('Error loading entity-keyword network:', error);
            container.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 800px; color: #dc3545;">Error loading entity-keyword network</div>';
        });
}

// Load alerts
function loadAlerts() {
    fetch('/api/alerts?limit=50')
        .then(response => response.json())
        .then(data => {
            alerts = data;
            displayAlerts(data);
        })
        .catch(error => {});
}

// Display alerts
function displayAlerts(alertsData) {
    const container = document.getElementById('alertsContainer');

    if (!alertsData || alertsData.length === 0) {
        container.innerHTML = '<p class="text-center text-muted">No alerts</p>';
        return;
    }

    container.innerHTML = alertsData.map(alert => createAlertCard(alert)).join('');
}

// Create alert card HTML
function createAlertCard(alert) {
    const severity = alert.severity || 'medium';
    const alertType = alert.alert_type || 'general';
    const category = alert.category || 'general';
    const message = alert.message || '';
    const createdAt = new Date(alert.created_at).toLocaleString();

    return `
        <div class="alert-card ${severity}">
            <div class="d-flex justify-content-between align-items-start mb-2">
                <div>
                    <strong>${alertType.replace('_', ' ').toUpperCase()}</strong>
                    <span class="badge bg-danger ms-2">${severity.toUpperCase()}</span>
                    <span class="category-badge ms-2">${category.toUpperCase()}</span>
                </div>
                <small class="text-muted">${createdAt}</small>
            </div>
            <p class="mb-0" style="white-space: pre-line;">${escapeHtml(message)}</p>
        </div>
    `;
}

// Add new alert to the top of the list
function addNewAlert(alertData) {
    const container = document.getElementById('alertsContainer');

    if (container.querySelector('.text-muted')) {
        container.innerHTML = '';
    }

    const alertCard = createAlertCard(alertData);
    container.insertAdjacentHTML('afterbegin', alertCard);

    // Keep only the last 50 alerts
    while (container.children.length > 50) {
        container.removeChild(container.lastChild);
    }
}

// Load all charts
function loadCharts() {
    loadSentimentChart();
    loadWordFrequencyChart();
    loadCategoryChart();
    loadCryptoChart();
}

// Load Forex Factory calendar
function loadForexCalendar() {
    fetch('/api/forex/calendar')
        .then(response => response.json())
        .then(data => {
            displayForexCalendar(data.events || []);
        })
        .catch(error => {});
}

// Display Forex calendar events
function displayForexCalendar(events) {
    const container = document.getElementById('forexCalendarContainer');

    if (!events || events.length === 0) {
        container.innerHTML = '<p class="text-center text-muted">No upcoming high-impact events</p>';
        return;
    }

    container.innerHTML = events.map(event => createForexEventCard(event)).join('');
}

// Create Forex event card HTML
function createForexEventCard(alert) {
    const severity = alert.severity || 'medium';
    const message = alert.message || '';

    // Parse the message to extract event details
    const lines = message.split('\n');
    let eventDate = '';
    let eventTime = '';
    let impact = '';
    let currency = '';
    let eventName = '';
    let forecast = '';
    let previous = '';

    for (let line of lines) {
        if (line.startsWith('Date:')) {
            eventDate = line.replace('Date:', '').trim();
        } else if (line.startsWith('Time:')) {
            eventTime = line.replace('Time:', '').trim();
        } else if (line.startsWith('Impact:')) {
            impact = line.replace('Impact:', '').trim();
        } else if (line.startsWith('Currency:')) {
            currency = line.replace('Currency:', '').trim();
        } else if (line.startsWith('Event:')) {
            eventName = line.replace('Event:', '').trim();
        } else if (line.startsWith('Forecast:')) {
            forecast = line.replace('Forecast:', '').trim();
        } else if (line.startsWith('Previous:')) {
            previous = line.replace('Previous:', '').trim();
        }
    }

    // Determine badge color based on impact
    const impactColor = impact === 'HIGH' ? 'danger' : (impact === 'MEDIUM' ? 'warning' : 'info');
    const impactIcon = impact === 'HIGH' ? '🔴' : (impact === 'MEDIUM' ? '🟠' : '🟡');

    return `
        <div class="forex-event-card ${severity} mb-3" style="background: #16181c; border: 1px solid #2f3336; border-left: 4px solid ${impactColor === 'danger' ? '#dc3545' : (impactColor === 'warning' ? '#ffc107' : '#17a2b8')}; border-radius: 8px; padding: 16px; transition: all 0.3s;">
            <div class="d-flex justify-content-between align-items-start mb-3">
                <div>
                    <h6 class="mb-1" style="color: #e7e9ea; font-weight: 600;">
                        ${impactIcon} ${escapeHtml(eventName)}
                    </h6>
                    <span class="badge bg-${impactColor} me-2">${impact}</span>
                    <span class="badge bg-secondary">${currency}</span>
                </div>
            </div>
            <div class="row g-2 mb-2">
                <div class="col-md-6">
                    <small class="text-muted d-block">📅 Date</small>
                    <strong style="color: #1da1f2; font-size: 0.95rem;">${escapeHtml(eventDate)}</strong>
                </div>
                <div class="col-md-6">
                    <small class="text-muted d-block">🕐 Time</small>
                    <strong style="color: #e7e9ea; font-size: 0.95rem;">${escapeHtml(eventTime)}</strong>
                </div>
            </div>
            ${forecast || previous ? `
            <div class="row g-2" style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #2f3336;">
                ${forecast ? `
                <div class="col-md-6">
                    <small class="text-muted d-block">📊 Forecast</small>
                    <strong style="color: #17bf63; font-size: 0.9rem;">${escapeHtml(forecast)}</strong>
                </div>
                ` : ''}
                ${previous ? `
                <div class="col-md-6">
                    <small class="text-muted d-block">📈 Previous</small>
                    <strong style="color: #8b98a5; font-size: 0.9rem;">${escapeHtml(previous)}</strong>
                </div>
                ` : ''}
            </div>
            ` : ''}
        </div>
    `;
}

// Load sentiment time series chart
function loadSentimentChart() {
    const category = currentCategory === 'all' ? '' : currentCategory;
    const hours = current24hTimeRange || 24;
    const url = category ? `/api/visualizations/sentiment-chart?category=${category}&hours=${hours}` : `/api/visualizations/sentiment-chart?hours=${hours}`;

    fetch(url)
        .then(response => response.json())
        .then(chartData => {
            if (chartData.data && chartData.layout) {
                Plotly.newPlot('sentimentChart', chartData.data, {
                    ...chartData.layout,
                    paper_bgcolor: '#16181c',
                    plot_bgcolor: '#16181c',
                    font: { color: '#e7e9ea' },
                    xaxis: { ...chartData.layout.xaxis, gridcolor: '#2f3336' },
                    yaxis: { ...chartData.layout.yaxis, gridcolor: '#2f3336' }
                }, { responsive: true });
            }
        })
        .catch(error => {});
}

// Load word frequency chart (Top Keywords with dynamic time range)
function loadWordFrequencyChart() {
    const category = currentCategory === 'all' ? '' : currentCategory;
    // Fetch raw data instead of plotly chart - use current time range
    const url = category ? `/api/wordcloud?category=${category}&hours=${current24hTimeRange}&limit=100` : `/api/wordcloud?hours=${current24hTimeRange}&limit=100`;

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (!data || data.length === 0) {
                const container = document.getElementById('wordFrequencyChart');
                container.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #8b98a5;">No keywords available yet</div>';
                return;
            }

            // Store data for view switching
            latest24hKeywordsData = data;

            // Render based on current view mode
            render24hKeywordsVisualization(data);
        })
        .catch(error => {
            console.error('Error loading 24h keywords:', error);
        });
}

function render24hKeywordsVisualization(data) {
    // Render based on current 24h view mode
    if (current24hViewMode === 'frequency') {
        create24hTreemap(data, 'frequency');
    } else if (current24hViewMode === 'timeline') {
        create24hTimelineGrid(data);
    } else if (current24hViewMode === 'semantic') {
        create24hTreemap(data, 'semantic');
    } else if (current24hViewMode === 'category') {
        create24hTreemap(data, 'category');
    }
}

function create24hTreemap(data, mode = 'frequency') {
    const container = document.getElementById('wordFrequencyChart');
    container.innerHTML = '';

    const width = container.clientWidth;
    const height = Math.max(500, Math.ceil(data.length / 5) * 120);

    const maxCount = d3.max(data, d => d.count);
    const colorScale = d3.scaleLinear()
        .domain([0, maxCount / 2, maxCount])
        .range(['#1da1f2', '#17bf63', '#f91880']);

    // Sort data based on mode
    let sortedData = [...data];

    if (mode === 'timeline') {
        // Sort by first_seen timestamp (chronological - oldest to newest)
        sortedData.sort((a, b) => {
            const timeA = new Date(a.first_seen || 0).getTime();
            const timeB = new Date(b.first_seen || 0).getTime();
            return timeA - timeB;
        });
    } else if (mode === 'semantic') {
        // Group semantically related keywords together
        // Simple approach: sort by word similarity (alphabetically with clustering)
        sortedData.sort((a, b) => {
            // First sort by first letter for basic grouping
            const letterCompare = a.word[0].localeCompare(b.word[0]);
            if (letterCompare !== 0) return letterCompare;
            // Then by count within each letter group
            return b.count - a.count;
        });
    } else if (mode === 'category') {
        // Group by category, then by count within each category
        sortedData.sort((a, b) => {
            const catA = a.category || 'unknown';
            const catB = b.category || 'unknown';
            const categoryCompare = catA.localeCompare(catB);
            if (categoryCompare !== 0) return categoryCompare;
            // Within same category, sort by count
            return b.count - a.count;
        });
    } else {
        // Default: frequency (by count DESC)
        sortedData.sort((a, b) => b.count - a.count);
    }

    const root = d3.hierarchy({
        children: sortedData.map(d => ({
            name: d.word,
            value: d.count,
            category: d.category,
            first_seen: d.first_seen,
            last_seen: d.last_seen
        }))
    })
    .sum(d => d.value);

    // Use different tiling methods based on mode
    const treemap = d3.treemap()
        .size([width, height])
        .padding(2)
        .round(true);

    // For timeline mode, use binary tiling for balanced left-to-right, top-to-bottom reading
    if (mode === 'timeline') {
        treemap.tile(d3.treemapBinary);
    }

    treemap(root);

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    const cells = svg.selectAll('g')
        .data(root.leaves())
        .enter()
        .append('g')
        .attr('class', 'treemap-cell')
        .attr('transform', d => `translate(${d.x0},${d.y0})`);

    cells.append('rect')
        .attr('width', d => d.x1 - d.x0)
        .attr('height', d => d.y1 - d.y0)
        .attr('fill', d => colorScale(d.value))
        .attr('stroke', '#2f3336')
        .attr('stroke-width', 2)
        .style('opacity', 0.9);

    cells.append('text')
        .attr('class', 'treemap-text')
        .attr('x', d => (d.x1 - d.x0) / 2)
        .attr('y', d => (d.y1 - d.y0) / 2)
        .attr('text-anchor', 'middle')
        .attr('dy', '.3em')
        .style('fill', '#e7e9ea')
        .style('font-size', d => {
            const width = d.x1 - d.x0;
            const height = d.y1 - d.y0;
            const minDim = Math.min(width, height);
            return Math.min(minDim / 5, 16) + 'px';
        })
        .style('font-weight', '600')
        .text(d => d.data.name)
        .each(function(d) {
            const textWidth = (d.x1 - d.x0) - 10;
            let text = d.data.name;
            this.textContent = text;

            while (this.getComputedTextLength() > textWidth && text.length > 0) {
                text = text.slice(0, -1);
                this.textContent = text + '...';
            }
        });

    cells.on('mouseenter', function(event, d) {
        d3.select(this).select('rect')
            .transition()
            .duration(200)
            .style('opacity', 1)
            .attr('stroke-width', 3);
    })
    .on('mouseleave', function(event, d) {
        d3.select(this).select('rect')
            .transition()
            .duration(200)
            .style('opacity', 0.9)
            .attr('stroke-width', 2);
    })
    .on('click', function(event, d) {
        showKeywordArticlesModal(d.data.name);
    })
    .append('title')
        .text(d => `${d.data.name}: ${d.value} occurrences\n\nClick to see articles`);

    container.style.height = height + 'px';
}

// Show keyword articles modal
function showKeywordArticlesModal(keyword) {
    // Get modal element
    const modal = new bootstrap.Modal(document.getElementById('keywordArticlesModal'));

    // Update modal title
    document.getElementById('keywordArticlesModalLabel').textContent = `Articles containing "${keyword}"`;

    // Show loading spinner
    document.getElementById('keywordArticlesContent').innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;

    // Show modal
    modal.show();

    // Fetch articles for this keyword using current time range
    const hours = current24hTimeRange || 24;
    fetch(`/api/keyword/${encodeURIComponent(keyword)}/articles?hours=${hours}&limit=50`)
        .then(response => response.json())
        .then(data => {
            if (data.articles && data.articles.length > 0) {
                // Render articles
                const articlesHTML = data.articles.map(article => {
                    const sentiment = article.sentiment_label || 'neutral';
                    const sentimentScore = article.sentiment_score || 0;
                    const category = article.category || 'general';
                    const createdAt = new Date(article.created_at).toLocaleString();
                    const articleUrl = article.url || '';

                    return `
                        <div class="tweet-card mb-3">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <span class="category-badge">${category.toUpperCase()}</span>
                                    <span class="sentiment-badge sentiment-${sentiment.replace('_', '-')}">${sentiment.replace('_', ' ').toUpperCase()}</span>
                                </div>
                                <small style="color: white;">${createdAt}</small>
                            </div>
                            <div class="mb-2">
                                <strong>@${article.user_handle || 'Unknown'}</strong>
                            </div>
                            <p class="mb-2">${escapeHtml(article.text)}</p>
                            <div class="d-flex justify-content-between align-items-center">
                                <small class="text-muted">Sentiment: ${sentimentScore.toFixed(2)}</small>
                                <div class="d-flex align-items-center">
                                    <small class="text-muted me-3">❤️ ${article.like_count || 0}</small>
                                    <small class="text-muted me-3">🔄 ${article.retweet_count || 0}</small>
                                    <small class="text-muted me-3">💬 ${article.reply_count || 0}</small>
                                    ${articleUrl ? `<a href="${articleUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary">Open Article</a>` : ''}
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');

                // Create time range text
                const hours = current24hTimeRange || 24;
                let timeText = 'last 24 hours';
                if (hours === 9999) timeText = 'all time';
                else if (hours === 168) timeText = 'last week';
                else if (hours === 24) timeText = 'last 24 hours';
                else if (hours === 12) timeText = 'last 12 hours';
                else if (hours === 6) timeText = 'last 6 hours';
                else if (hours === 5) timeText = 'last 5 hours';
                else if (hours === 4) timeText = 'last 4 hours';
                else if (hours === 3) timeText = 'last 3 hours';
                else if (hours === 2) timeText = 'last 2 hours';
                else if (hours === 1) timeText = 'last hour';
                else timeText = `last ${hours} hours`;

                document.getElementById('keywordArticlesContent').innerHTML = `
                    <p class="text-muted mb-3">Found ${data.count} articles mentioning "<strong>${keyword}</strong>" in the ${timeText}</p>
                    ${articlesHTML}
                `;
            } else {
                // Create time range text for no results message
                const hours = current24hTimeRange || 24;
                let timeText = 'last 24 hours';
                if (hours === 9999) timeText = 'all time';
                else if (hours === 168) timeText = 'last week';
                else if (hours === 24) timeText = 'last 24 hours';
                else if (hours === 12) timeText = 'last 12 hours';
                else if (hours === 6) timeText = 'last 6 hours';
                else if (hours === 5) timeText = 'last 5 hours';
                else if (hours === 4) timeText = 'last 4 hours';
                else if (hours === 3) timeText = 'last 3 hours';
                else if (hours === 2) timeText = 'last 2 hours';
                else if (hours === 1) timeText = 'last hour';
                else timeText = `last ${hours} hours`;

                document.getElementById('keywordArticlesContent').innerHTML = `
                    <p class="text-center text-muted">No articles found for "${keyword}" in the ${timeText}</p>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading keyword articles:', error);
            document.getElementById('keywordArticlesContent').innerHTML = `
                <p class="text-center text-danger">Error loading articles. Please try again.</p>
            `;
        });
}

// Show articles for a specific entity (person, company, location, etc.)
function showEntityArticlesModal(entityText) {
    // Get modal element
    const modal = new bootstrap.Modal(document.getElementById('keywordArticlesModal'));

    // Update modal title
    document.getElementById('keywordArticlesModalLabel').textContent = `Articles mentioning "${entityText}"`;

    // Show loading spinner
    document.getElementById('keywordArticlesContent').innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;

    // Show modal
    modal.show();

    // Fetch articles for this entity using current time range
    const hours = current24hTimeRange || 24;
    fetch(`/api/entity/${encodeURIComponent(entityText)}/articles?hours=${hours}&limit=50`)
        .then(response => response.json())
        .then(data => {
            if (data.articles && data.articles.length > 0) {
                // Render articles
                const articlesHTML = data.articles.map(article => {
                    const sentiment = article.sentiment_label || 'neutral';
                    const sentimentScore = article.sentiment_score || 0;
                    const category = article.category || 'general';
                    const createdAt = new Date(article.created_at).toLocaleString();
                    const articleUrl = article.url || '';

                    return `
                        <div class="tweet-card mb-3">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <span class="category-badge">${category.toUpperCase()}</span>
                                    <span class="sentiment-badge sentiment-${sentiment.replace('_', '-')}">${sentiment.replace('_', ' ').toUpperCase()}</span>
                                </div>
                                <small style="color: white;">${createdAt}</small>
                            </div>
                            <div class="mb-2">
                                <strong>@${article.source || article.user_handle || 'Unknown'}</strong>
                            </div>
                            <p class="mb-2">${escapeHtml(article.text)}</p>
                            <div class="d-flex justify-content-between align-items-center">
                                <small class="text-muted">Sentiment: ${sentimentScore.toFixed(2)}</small>
                                ${articleUrl ? `<a href="${articleUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary">Open Article</a>` : ''}
                            </div>
                        </div>
                    `;
                }).join('');

                // Create time range text
                const hours = current24hTimeRange || 24;
                let timeText = 'last 24 hours';
                if (hours === 9999) timeText = 'all time';
                else if (hours === 168) timeText = 'last week';
                else if (hours === 24) timeText = 'last 24 hours';
                else if (hours === 12) timeText = 'last 12 hours';
                else if (hours === 6) timeText = 'last 6 hours';
                else if (hours === 5) timeText = 'last 5 hours';
                else if (hours === 4) timeText = 'last 4 hours';
                else if (hours === 3) timeText = 'last 3 hours';
                else if (hours === 2) timeText = 'last 2 hours';
                else if (hours === 1) timeText = 'last hour';
                else timeText = `last ${hours} hours`;

                document.getElementById('keywordArticlesContent').innerHTML = `
                    <p class="text-muted mb-3">Found ${data.count} articles mentioning "<strong>${entityText}</strong>" in the ${timeText}</p>
                    ${articlesHTML}
                `;
            } else {
                // Create time range text for no results message
                const hours = current24hTimeRange || 24;
                let timeText = 'last 24 hours';
                if (hours === 9999) timeText = 'all time';
                else if (hours === 168) timeText = 'last week';
                else if (hours === 24) timeText = 'last 24 hours';
                else if (hours === 12) timeText = 'last 12 hours';
                else if (hours === 6) timeText = 'last 6 hours';
                else if (hours === 5) timeText = 'last 5 hours';
                else if (hours === 4) timeText = 'last 4 hours';
                else if (hours === 3) timeText = 'last 3 hours';
                else if (hours === 2) timeText = 'last 2 hours';
                else if (hours === 1) timeText = 'last hour';
                else timeText = `last ${hours} hours`;

                document.getElementById('keywordArticlesContent').innerHTML = `
                    <p class="text-center text-muted">No articles found mentioning "${entityText}" in the ${timeText}</p>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading entity articles:', error);
            document.getElementById('keywordArticlesContent').innerHTML = `
                <p class="text-center text-danger">Error loading articles. Please try again.</p>
            `;
        });
}

// Create equal-sized grid layout for timeline mode
function create24hTimelineGrid(data) {
    const container = document.getElementById('wordFrequencyChart');
    container.innerHTML = '';

    // Sort by first_seen timestamp (chronological - oldest to newest)
    const sortedData = [...data].sort((a, b) => {
        const timeA = new Date(a.first_seen || 0).getTime();
        const timeB = new Date(b.first_seen || 0).getTime();
        return timeA - timeB;
    });

    const width = container.clientWidth;
    const itemsPerRow = 5; // 5 items per row for good readability
    const cellWidth = (width / itemsPerRow) - 4; // -4 for padding
    const cellHeight = 100; // Fixed height for each cell
    const rows = Math.ceil(sortedData.length / itemsPerRow);
    const height = rows * (cellHeight + 4) + 20; // +4 for gaps, +20 for margins

    // Create color scale based on frequency (light to dark red)
    const maxCount = d3.max(sortedData, d => d.count);
    const colorScale = d3.scaleLinear()
        .domain([0, maxCount])
        .range(['#ffcccc', '#dc3545']); // Light red to dark red

    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Create grid cells
    const cells = svg.selectAll('g')
        .data(sortedData)
        .enter()
        .append('g')
        .attr('class', 'timeline-cell')
        .attr('transform', (d, i) => {
            const row = Math.floor(i / itemsPerRow);
            const col = i % itemsPerRow;
            const x = col * (cellWidth + 4) + 2;
            const y = row * (cellHeight + 4) + 2;
            return `translate(${x},${y})`;
        });

    // Add rectangles
    cells.append('rect')
        .attr('width', cellWidth)
        .attr('height', cellHeight)
        .attr('fill', d => colorScale(d.count))
        .attr('stroke', '#2f3336')
        .attr('stroke-width', 2)
        .attr('rx', 5)
        .style('opacity', 0.9);

    // Add text labels
    cells.append('text')
        .attr('x', cellWidth / 2)
        .attr('y', cellHeight / 2)
        .attr('text-anchor', 'middle')
        .attr('dy', '.3em')
        .style('fill', '#000')
        .style('font-size', '14px')
        .style('font-weight', '600')
        .style('pointer-events', 'none')
        .text(d => {
            // Truncate long words
            return d.word.length > 12 ? d.word.substring(0, 12) + '...' : d.word;
        });

    // Add hover effects and click handler
    cells.on('mouseenter', function(event, d) {
        d3.select(this).select('rect')
            .transition()
            .duration(200)
            .style('opacity', 1)
            .attr('stroke-width', 3)
            .attr('stroke', '#1da1f2');
    })
    .on('mouseleave', function(event, d) {
        d3.select(this).select('rect')
            .transition()
            .duration(200)
            .style('opacity', 0.9)
            .attr('stroke-width', 2)
            .attr('stroke', '#2f3336');
    })
    .on('click', function(event, d) {
        showKeywordArticlesModal(d.word);
    })
    .append('title')
        .text(d => {
            const time = d.first_seen ? new Date(d.first_seen).toLocaleString() : 'Unknown';
            return `${d.word}\nOccurrences: ${d.count}\nFirst seen: ${time}\n\nClick to see articles`;
        });

    container.style.height = height + 'px';
}

// Load category distribution chart
function loadCategoryChart() {
    fetch('/api/visualizations/category-distribution')
        .then(response => response.json())
        .then(chartData => {
            if (chartData.data && chartData.layout) {
                Plotly.newPlot('categoryChart', chartData.data, {
                    ...chartData.layout,
                    paper_bgcolor: '#16181c',
                    plot_bgcolor: '#16181c',
                    font: { color: '#e7e9ea' }
                }, { responsive: true });
            }
        })
        .catch(error => {});
}

// Load crypto price chart
function loadCryptoChart() {
    fetch('/api/visualizations/crypto-chart')
        .then(response => response.json())
        .then(chartData => {
            if (chartData.data && chartData.layout) {
                Plotly.newPlot('cryptoChart', chartData.data, {
                    ...chartData.layout,
                    paper_bgcolor: '#16181c',
                    plot_bgcolor: '#16181c',
                    font: { color: '#e7e9ea' },
                    xaxis: { ...chartData.layout.xaxis, gridcolor: '#2f3336' },
                    yaxis: { ...chartData.layout.yaxis, gridcolor: '#2f3336' }
                }, { responsive: true });
            }
        })
        .catch(error => {});
}

// Update crypto chart with real-time data (direct Plotly update)
function updateCryptoChartRealtime(data) {
    // data contains: symbol, price, change_percent, baseline_price
    try {
        const symbol = data.symbol.replace('USDT', '');
        const price = data.price;
        const changePercent = data.change_percent;

        // Get the crypto chart element
        const chartDiv = document.getElementById('cryptoChart');

        if (!chartDiv || !chartDiv.data || chartDiv.data.length === 0) {
            // Chart not loaded yet, skip
            return;
        }

        // Find the bar index for this symbol in the x-axis data
        const trace = chartDiv.data[0]; // There's only one trace (bars)
        const xData = trace.x;
        const barIndex = xData.indexOf(symbol);

        if (barIndex === -1) {
            return;
        }

        // Update the price value
        const newY = [...trace.y];
        newY[barIndex] = price;

        // Update the color based on change percentage
        let color = '#1da1f2'; // default blue
        if (changePercent > 0) {
            color = '#17bf63'; // green for positive
        } else if (changePercent < 0) {
            color = '#dc3545'; // red for negative
        }

        const newColors = [...trace.marker.color];
        newColors[barIndex] = color;

        // Format price label based on magnitude
        let priceLabel;
        const changeSign = changePercent >= 0 ? '+' : '';
        const changeStr = `${changeSign}${changePercent.toFixed(2)}%`;

        if (price < 0.01) {
            priceLabel = `$${price.toFixed(8)}\n${changeStr}`;
        } else if (price < 1) {
            priceLabel = `$${price.toFixed(6)}\n${changeStr}`;
        } else if (price < 100) {
            priceLabel = `$${price.toFixed(4)}\n${changeStr}`;
        } else {
            priceLabel = `$${price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}\n${changeStr}`;
        }

        const newText = [...trace.text];
        newText[barIndex] = priceLabel;

        // Update the trace using Plotly.restyle
        Plotly.restyle(chartDiv, {
            'y': [newY],
            'marker.color': [newColors],
            'text': [newText]
        }, 0);

    } catch (error) {
        // Silently handle errors
    }
}

// Setup category filter buttons
function setupCategoryFilters() {
    const filterButtons = document.querySelectorAll('.filter-btn');

    filterButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons
            filterButtons.forEach(btn => btn.classList.remove('active'));

            // Add active class to clicked button
            this.classList.add('active');

            // Update current category
            currentCategory = this.dataset.category;

            // Reload data
            loadTweets();
            loadCharts();
            loadLatestKeywords();
        });
    });
}

// Setup admin control buttons
function setupAdminButtons() {
    // Refresh RSS button
    const refreshRssBtn = document.getElementById('refreshRssBtn');
    if (refreshRssBtn) {
        refreshRssBtn.addEventListener('click', function() {
            // Disable button and show loading state
            this.disabled = true;
            const originalHtml = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Refreshing...';

            // Call API endpoint
            fetch('/api/admin/refresh-rss', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Show success message
                    this.innerHTML = '<svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16" style="margin-right: 5px;"><path d="M10.97 4.97a.75.75 0 0 1 1.07 1.05l-3.99 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 0 1 .02-.022z"/></svg>Refreshed!';
                    this.classList.add('btn-success');
                    this.classList.remove('btn-primary');

                    // Reset button after 3 seconds
                    setTimeout(() => {
                        this.innerHTML = originalHtml;
                        this.disabled = false;
                        this.classList.remove('btn-success');
                        this.classList.add('btn-primary');
                    }, 3000);

                    // Reload alerts and data after a short delay
                    setTimeout(() => {
                        loadAlerts();
                        loadStats();
                        loadCharts();
                        loadLatestKeywords();
                    }, 1000);
                } else {
                    // Show error
                    this.innerHTML = 'Error!';
                    this.classList.add('btn-warning');
                    this.classList.remove('btn-primary');
                    setTimeout(() => {
                        this.innerHTML = originalHtml;
                        this.disabled = false;
                        this.classList.remove('btn-warning');
                        this.classList.add('btn-primary');
                    }, 3000);
                }
            })
            .catch(error => {
                console.error('Error refreshing RSS:', error);
                this.innerHTML = 'Error!';
                this.classList.add('btn-warning');
                this.classList.remove('btn-primary');
                setTimeout(() => {
                    this.innerHTML = originalHtml;
                    this.disabled = false;
                    this.classList.remove('btn-warning');
                    this.classList.add('btn-primary');
                }, 3000);
            });
        });
    }

    // Clear database button
    const clearDatabaseBtn = document.getElementById('clearDatabaseBtn');
    if (clearDatabaseBtn) {
        clearDatabaseBtn.addEventListener('click', function() {
            // Confirm action
            if (!confirm('Are you sure you want to clear all database tables and Redis cache? This action cannot be undone!')) {
                return;
            }

            // Disable button and show loading state
            this.disabled = true;
            const originalHtml = this.innerHTML;
            this.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Clearing...';

            // Call API endpoint
            fetch('/api/admin/clear-database', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    // Show success message
                    this.innerHTML = '<svg width="16" height="16" fill="currentColor" viewBox="0 0 16 16" style="margin-right: 5px;"><path d="M10.97 4.97a.75.75 0 0 1 1.07 1.05l-3.99 4.99a.75.75 0 0 1-1.08.02L4.324 8.384a.75.75 0 1 1 1.06-1.06l2.094 2.093 3.473-4.425a.267.267 0 0 1 .02-.022z"/></svg>Cleared!';
                    this.classList.add('btn-success');
                    this.classList.remove('btn-danger');

                    // Reset button after 3 seconds
                    setTimeout(() => {
                        this.innerHTML = originalHtml;
                        this.disabled = false;
                        this.classList.remove('btn-success');
                        this.classList.add('btn-danger');
                    }, 3000);

                    // Reload all data after a short delay
                    setTimeout(() => {
                        loadStats();
                        loadTweets();
                        loadAlerts();
                        loadCharts();
                        loadForexCalendar();
                        loadLatestKeywords();
                    }, 1000);
                } else {
                    // Show error
                    this.innerHTML = 'Error!';
                    this.classList.add('btn-warning');
                    this.classList.remove('btn-danger');
                    setTimeout(() => {
                        this.innerHTML = originalHtml;
                        this.disabled = false;
                        this.classList.remove('btn-warning');
                        this.classList.add('btn-danger');
                    }, 3000);
                }
            })
            .catch(error => {
                console.error('Error clearing database:', error);
                this.innerHTML = 'Error!';
                this.classList.add('btn-warning');
                this.classList.remove('btn-danger');
                setTimeout(() => {
                    this.innerHTML = originalHtml;
                    this.disabled = false;
                    this.classList.remove('btn-warning');
                    this.classList.add('btn-danger');
                }, 3000);
            });
        });
    }
}

// Setup entity type filter buttons
function setupEntityButtons() {
    const entityButtons = document.querySelectorAll('.entity-type-btn');

    entityButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons
            entityButtons.forEach(btn => btn.classList.remove('active'));

            // Add active class to clicked button
            this.classList.add('active');

            // Load entity network with selected type
            const entityType = this.dataset.type;
            createEntityNetwork(entityType);
        });
    });
}

// Get color based on sentiment score
function getSentimentColor(score) {
    if (score <= -0.6) return '#dc3545';
    if (score <= -0.2) return '#f91880';
    if (score <= 0.2) return '#536471';
    if (score <= 0.6) return '#1d9bf0';
    return '#17bf63';
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Load latest keywords - view mode (bubble or heatmap)
let bubbleChart = null;
let currentViewMode = 'bubble';
let latestKeywordsData = null;

// View mode for 24h keywords - frequency, timeline, semantic, or category
let current24hViewMode = 'frequency';
let latest24hKeywordsData = null;
let current24hTimeRange = 24; // Default to 24 hours

// Setup view toggle buttons
document.addEventListener('DOMContentLoaded', function() {
    // Toggle buttons for Latest Keywords (5 hours)
    const viewToggleButtons = document.querySelectorAll('.view-toggle-btn');

    viewToggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons in this group
            viewToggleButtons.forEach(btn => btn.classList.remove('active'));

            // Add active class to clicked button
            this.classList.add('active');

            // Update current view mode
            currentViewMode = this.dataset.view;

            // Reload visualization with new view mode
            if (latestKeywordsData) {
                renderKeywordsVisualization(latestKeywordsData);
            }
        });
    });

    // Toggle buttons for 24h Keywords
    const view24hToggleButtons = document.querySelectorAll('.view-toggle-btn-24h');

    view24hToggleButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons in this group
            view24hToggleButtons.forEach(btn => btn.classList.remove('active'));

            // Add active class to clicked button
            this.classList.add('active');

            // Update current 24h view mode
            current24hViewMode = this.dataset.view;

            // Reload visualization with new view mode
            if (latest24hKeywordsData) {
                render24hKeywordsVisualization(latest24hKeywordsData);
            }
        });
    });

    // Time Range toggle buttons for Top Keywords
    const timeRange24hButtons = document.querySelectorAll('.time-range-btn-24h');

    timeRange24hButtons.forEach(button => {
        button.addEventListener('click', function() {
            // Remove active class from all buttons in this group
            timeRange24hButtons.forEach(btn => btn.classList.remove('active'));

            // Add active class to clicked button
            this.classList.add('active');

            // Update current time range
            current24hTimeRange = parseInt(this.dataset.hours);

            // Update the time label in the title
            const label = document.getElementById('topKeywordsTimeLabel');
            if (label) {
                if (current24hTimeRange === 9999) {
                    label.textContent = '(All Data)';
                } else if (current24hTimeRange === 168) {
                    label.textContent = '(Last Week)';
                } else if (current24hTimeRange === 24) {
                    label.textContent = '(Last 24 Hours)';
                } else if (current24hTimeRange === 12) {
                    label.textContent = '(Last 12 Hours)';
                } else if (current24hTimeRange === 6) {
                    label.textContent = '(Last 6 Hours)';
                } else if (current24hTimeRange === 5) {
                    label.textContent = '(Last 5 Hours)';
                } else if (current24hTimeRange === 4) {
                    label.textContent = '(Last 4 Hours)';
                } else if (current24hTimeRange === 3) {
                    label.textContent = '(Last 3 Hours)';
                } else if (current24hTimeRange === 2) {
                    label.textContent = '(Last 2 Hours)';
                } else if (current24hTimeRange === 1) {
                    label.textContent = '(Last Hour)';
                }
            }

            // Reload data with new time range
            loadWordFrequencyChart();
            loadSentimentChart(); // Reload sentiment chart with new time range
            loadTweets(); // Reload tweets with new time range
        });
    });
});

function loadLatestKeywords() {
    const category = currentCategory === 'all' ? '' : currentCategory;
    // Get the most recent keywords (last 5 hours, limit 100)
    const url = category ? `/api/wordcloud?category=${category}&hours=5&limit=100` : '/api/wordcloud?hours=5&limit=100';

    fetch(url)
        .then(response => response.json())
        .then(data => {
            if (!data || data.length === 0) {
                // Show empty state
                const container = document.getElementById('latestKeywordsBubbleChart');
                container.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #8b98a5;">No keywords available yet</div>';
                return;
            }

            // Store data for view switching
            latestKeywordsData = data;

            // Render based on current view mode
            renderKeywordsVisualization(data);
        })
        .catch(error => {
            console.error('Error loading latest keywords:', error);
        });
}

function renderKeywordsVisualization(data) {
    if (currentViewMode === 'bubble') {
        createD3BubbleChart(data);
    } else if (currentViewMode === 'heatmap') {
        createD3Treemap(data);
    } else if (currentViewMode === 'network') {
        createD3NetworkGraph();
    }
}

function createD3BubbleChart(data) {
    const container = document.getElementById('latestKeywordsBubbleChart');
    container.innerHTML = ''; // Clear previous chart

    const width = container.clientWidth;
    // Dynamic height based on number of items - more items = taller chart
    const height = Math.max(600, Math.ceil(data.length / 6) * 150);

    // Update container height
    container.style.height = height + 'px';

    // Create color scale
    const maxCount = d3.max(data, d => d.count);
    const colorScale = d3.scaleLinear()
        .domain([0, maxCount / 2, maxCount])
        .range(['#1da1f2', '#17bf63', '#f91880']);

    // Prepare nodes with radius based on count
    const nodes = data.map((d, i) => ({
        id: d.word,
        word: d.word,
        count: d.count,
        radius: Math.sqrt(d.count) * 8 + 15, // Scale bubble size
        x: width / 2 + (Math.random() - 0.5) * 100, // Start near center with some randomness
        y: height / 2 + (Math.random() - 0.5) * 100
    }));

    // Create SVG
    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Create force simulation
    const simulation = d3.forceSimulation(nodes)
        .force('charge', d3.forceManyBody().strength(5))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => d.radius + 2))
        .force('x', d3.forceX(width / 2).strength(0.05))
        .force('y', d3.forceY(height / 2).strength(0.05));

    // Create bubble groups
    const bubbles = svg.selectAll('.bubble-node')
        .data(nodes)
        .enter()
        .append('g')
        .attr('class', 'bubble-node');

    // Add circles
    bubbles.append('circle')
        .attr('r', d => d.radius)
        .attr('fill', d => colorScale(d.count))
        .attr('stroke', '#2f3336')
        .attr('stroke-width', 2)
        .style('opacity', 0.9);

    // Add text labels
    bubbles.append('text')
        .attr('class', 'bubble-text')
        .attr('text-anchor', 'middle')
        .attr('dy', '.3em')
        .style('fill', '#e7e9ea')
        .style('font-size', d => Math.min(d.radius / 3, 14) + 'px')
        .style('font-weight', '600')
        .text(d => d.word);

    // Add hover effects and click handler
    bubbles.on('mouseenter', function(event, d) {
        d3.select(this).select('circle')
            .transition()
            .duration(200)
            .style('opacity', 1)
            .attr('stroke-width', 3);
    })
    .on('mouseleave', function(event, d) {
        d3.select(this).select('circle')
            .transition()
            .duration(200)
            .style('opacity', 0.9)
            .attr('stroke-width', 2);
    })
    .on('click', function(event, d) {
        showKeywordArticlesModal(d.word);
    })
    .style('cursor', 'pointer')
    .append('title')
        .text(d => `${d.word}: ${d.count} occurrences\n\nClick to see articles`);

    // Update positions on each tick of the simulation
    simulation.on('tick', () => {
        bubbles.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    // Stop simulation after a few seconds to save CPU
    setTimeout(() => {
        simulation.stop();
    }, 3000);

    // Store reference for potential updates
    bubbleChart = { svg, simulation, nodes };
}

// Create D3 Treemap (Heatmap squares)
function createD3Treemap(data) {
    const container = document.getElementById('latestKeywordsBubbleChart');
    container.innerHTML = ''; // Clear previous chart

    const width = container.clientWidth;
    const height = Math.max(800, Math.ceil(data.length / 5) * 120); // Dynamic height based on data

    // Create color scale
    const maxCount = d3.max(data, d => d.count);
    const colorScale = d3.scaleLinear()
        .domain([0, maxCount / 2, maxCount])
        .range(['#1da1f2', '#17bf63', '#f91880']);

    // Prepare hierarchical data for treemap
    const root = d3.hierarchy({
        children: data.map(d => ({
            name: d.word,
            value: d.count
        }))
    })
    .sum(d => d.value);

    // Create treemap layout
    const treemap = d3.treemap()
        .size([width, height])
        .padding(2)
        .round(true);

    treemap(root);

    // Create SVG
    const svg = d3.select(container)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Create cells
    const cells = svg.selectAll('g')
        .data(root.leaves())
        .enter()
        .append('g')
        .attr('class', 'treemap-cell')
        .attr('transform', d => `translate(${d.x0},${d.y0})`);

    // Add rectangles
    cells.append('rect')
        .attr('width', d => d.x1 - d.x0)
        .attr('height', d => d.y1 - d.y0)
        .attr('fill', d => colorScale(d.value))
        .attr('stroke', '#2f3336')
        .attr('stroke-width', 2)
        .style('opacity', 0.9);

    // Add text labels
    cells.append('text')
        .attr('class', 'treemap-text')
        .attr('x', d => (d.x1 - d.x0) / 2)
        .attr('y', d => (d.y1 - d.y0) / 2)
        .attr('text-anchor', 'middle')
        .attr('dy', '.3em')
        .style('fill', '#e7e9ea')
        .style('font-size', d => {
            const width = d.x1 - d.x0;
            const height = d.y1 - d.y0;
            const minDim = Math.min(width, height);
            return Math.min(minDim / 5, 16) + 'px';
        })
        .style('font-weight', '600')
        .text(d => d.data.name)
        .each(function(d) {
            // Truncate text if it doesn't fit
            const textWidth = (d.x1 - d.x0) - 10;
            let text = d.data.name;
            this.textContent = text;

            while (this.getComputedTextLength() > textWidth && text.length > 0) {
                text = text.slice(0, -1);
                this.textContent = text + '...';
            }
        });

    // Add hover effects and click handler
    cells.on('mouseenter', function(event, d) {
        d3.select(this).select('rect')
            .transition()
            .duration(200)
            .style('opacity', 1)
            .attr('stroke-width', 3);
    })
    .on('mouseleave', function(event, d) {
        d3.select(this).select('rect')
            .transition()
            .duration(200)
            .style('opacity', 0.9)
            .attr('stroke-width', 2);
    })
    .on('click', function(event, d) {
        showKeywordArticlesModal(d.data.name);
    })
    .style('cursor', 'pointer')
    .append('title')
        .text(d => `${d.data.name}: ${d.value} occurrences\n\nClick to see articles`);

    // Update container height
    container.style.height = height + 'px';
}

// Track network graph state
let networkLoading = false;
let currentNetworkSimulation = null;
let currentNetworkData = null;
let networkGraphElements = null; // Store SVG elements for updates

// Create D3 Force-Directed Network Graph
function createD3NetworkGraph() {
    const container = document.getElementById('latestKeywordsBubbleChart');

    // Fetch source network data
    const category = currentCategory === 'all' ? '' : currentCategory;
    const url = category ? `/api/source-network?category=${category}&hours=5` : '/api/source-network?hours=5';

    // If graph already exists, just update it
    if (currentNetworkSimulation && networkGraphElements) {
        updateNetworkGraph(url);
        return;
    }

    // Prevent multiple simultaneous initial loads
    if (networkLoading) {
        return;
    }
    networkLoading = true;

    // Show loading message for initial load only
    const loadingDiv = document.createElement('div');
    loadingDiv.id = 'network-loading';
    loadingDiv.style.cssText = 'position: absolute; top: 0; left: 0; right: 0; bottom: 0; display: flex; align-items: center; justify-content: center; background: rgba(15, 20, 25, 0.8); color: #8b98a5; z-index: 1000;';
    loadingDiv.innerHTML = '<span>Loading source network...</span>';
    container.appendChild(loadingDiv);

    fetch(url)
        .then(response => response.json())
        .then(networkData => {
            // Remove loading message
            const loading = document.getElementById('network-loading');
            if (loading) loading.remove();
            networkLoading = false;

            if (!networkData.nodes || networkData.nodes.length === 0) {
                container.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 800px; color: #8b98a5;">No source connections available</div>';
                return;
            }

            // Store network data
            currentNetworkData = networkData;

            // Clear container for initial render
            container.innerHTML = '';

            // Make container relative and hide overflow
            container.style.position = 'relative';
            container.style.overflow = 'hidden';

            const width = container.clientWidth;
            // Increased height for better visibility - much taller graph
            const height = Math.max(1200, networkData.nodes.length * 150);

            // Create SVG with viewBox for better containment
            const svg = d3.select(container)
                .append('svg')
                .attr('width', width)
                .attr('height', height)
                .attr('viewBox', `0 0 ${width} ${height}`)
                .style('display', 'block')
                .on('click', function() {
                    // Click on background unpins and hides tooltip
                    tooltipPinned = false;
                    tooltip.style('visibility', 'hidden')
                        .style('border', '2px solid #1da1f2');
                });

            // Create tooltip div for showing keywords
            let tooltip = d3.select(container).select('.network-tooltip');
            let tooltipPinned = false; // Track if tooltip is pinned
            if (tooltip.empty()) {
                tooltip = d3.select(container)
                    .append('div')
                    .attr('class', 'network-tooltip')
                    .style('position', 'absolute')
                    .style('visibility', 'hidden')
                    .style('background', 'rgba(15, 20, 25, 0.95)')
                    .style('border', '2px solid #1da1f2')
                    .style('border-radius', '8px')
                    .style('padding', '12px')
                    .style('color', '#e7e9ea')
                    .style('font-size', '13px')
                    .style('max-width', '350px')
                    .style('max-height', '500px')
                    .style('overflow-y', 'auto')
                    .style('z-index', '1000')
                    .style('pointer-events', 'auto')
                    .style('box-shadow', '0 4px 12px rgba(0,0,0,0.5)');
            }

            // Create color scale based on number of keywords
            const maxKeywords = d3.max(networkData.nodes, d => d.keywords);
            const colorScale = d3.scaleLinear()
                .domain([0, maxKeywords / 2, maxKeywords])
                .range(['#1da1f2', '#17bf63', '#f91880']);

            // Create link strength scale
            const maxShared = d3.max(networkData.links, d => d.value) || 1;
            const linkWidthScale = d3.scaleLinear()
                .domain([0, maxShared])
                .range([1, 8]);

            // Initialize nodes with circular layout for better spread
            const nodeCount = networkData.nodes.length;
            const radius = Math.min(width, height) * 0.35; // Use 35% of smaller dimension
            networkData.nodes.forEach((node, i) => {
                const angle = (i / nodeCount) * 2 * Math.PI;
                node.x = width / 2 + radius * Math.cos(angle);
                node.y = height / 2 + radius * Math.sin(angle);
            });

            // Create force simulation optimized for compact layout with boundary containment
            const simulation = d3.forceSimulation(networkData.nodes)
                .force('link', d3.forceLink(networkData.links)
                    .id(d => d.id)
                    .distance(d => 180 - (d.value * 8))  // Reduced distance for more compact layout
                    .strength(0.3))  // Stronger link strength to keep related nodes closer
                .force('charge', d3.forceManyBody().strength(-1500))  // Reduced repulsion for tighter clustering
                .force('center', d3.forceCenter(width / 2, height / 2).strength(0.1))  // Stronger centering
                .force('collision', d3.forceCollide().radius(d => Math.sqrt(d.keywords) * 4 + 45))  // Slightly reduced padding
                .force('x', d3.forceX(width / 2).strength(0.08))  // Stronger x-axis pull to keep nodes in bounds
                .force('y', d3.forceY(height / 2).strength(0.08))  // Stronger y-axis pull to keep nodes in bounds
                .force('boundaryX', d3.forceX().x(d => Math.max(60, Math.min(width - 60, d.x))).strength(0.1))  // Hard boundary on x
                .force('boundaryY', d3.forceY().y(d => Math.max(60, Math.min(height - 60, d.y))).strength(0.1))  // Hard boundary on y
                .velocityDecay(0.4)  // Higher friction for more stable layout
                .alphaDecay(0.02);  // Slightly faster cooling

            // Create links group (must be before nodes for proper z-index)
            const linksGroup = svg.append('g')
                .attr('class', 'links');

            // Create links
            const linkElements = linksGroup.selectAll('line')
                .data(networkData.links)
                .enter()
                .append('line')
                .attr('stroke', '#536471')
                .attr('stroke-width', d => linkWidthScale(d.value))
                .attr('stroke-opacity', 0.6);

            // Add tooltips to links
            linkElements.append('title')
                .text(d => `${d.value} shared keywords: ${d.keywords.join(', ')}`);

            // Create node groups
            const nodes = svg.append('g')
                .selectAll('g')
                .data(networkData.nodes)
                .enter()
                .append('g')
                .attr('class', 'network-node')
                .call(d3.drag()
                    .on('start', dragstarted)
                    .on('drag', dragged)
                    .on('end', dragended));

            // Add circles for nodes (smaller size)
            nodes.append('circle')
                .attr('r', d => Math.sqrt(d.keywords) * 4 + 20)  // Reduced from 8 to 4 for smaller bubbles
                .attr('fill', d => colorScale(d.keywords))
                .attr('stroke', '#2f3336')
                .attr('stroke-width', 2)
                .style('opacity', 0.9);

            // Add labels for nodes
            nodes.append('text')
                .attr('text-anchor', 'middle')
                .attr('dy', '.3em')
                .style('fill', '#e7e9ea')
                .style('font-size', '12px')
                .style('font-weight', '600')
                .style('pointer-events', 'none')
                .text(d => {
                    // Truncate long source names
                    const name = d.name.startsWith('@') ? d.name : '@' + d.name;
                    return name.length > 15 ? name.substring(0, 15) + '...' : name;
                });

            // Add tooltips
            nodes.append('title')
                .text(d => `${d.name}\n${d.keywords} keywords`);

            // Add hover effects
            nodes.on('mouseenter', function(event, d) {
                d3.select(this).select('circle')
                    .transition()
                    .duration(200)
                    .style('opacity', 1)
                    .attr('stroke-width', 4);

                // Collect connected nodes and their shared keywords
                const connections = networkData.links
                    .filter(link => {
                        const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
                        const targetId = typeof link.target === 'object' ? link.target.id : link.target;
                        return sourceId === d.id || targetId === d.id;
                    })
                    .map(link => {
                        const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
                        const targetId = typeof link.target === 'object' ? link.target.id : link.target;
                        const targetNode = sourceId === d.id ?
                            (typeof link.target === 'object' ? link.target : networkData.nodes.find(n => n.id === targetId)) :
                            (typeof link.source === 'object' ? link.source : networkData.nodes.find(n => n.id === sourceId));
                        return {
                            name: targetNode.name,
                            keywords: link.keywords || [],
                            count: link.value
                        };
                    });

                // Build tooltip content
                let tooltipHTML = `<div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">`;
                tooltipHTML += `<div style="font-weight: 600; color: #1da1f2; font-size: 14px;">${d.name}</div>`;
                tooltipHTML += `<div style="color: #8b98a5; font-size: 11px; font-style: italic;">Click to pin</div>`;
                tooltipHTML += `</div>`;
                tooltipHTML += `<div style="margin-bottom: 8px; color: #8b98a5;">Total Keywords: ${d.keywords}</div>`;

                if (connections.length > 0) {
                    tooltipHTML += `<div style="border-top: 1px solid #2f3336; margin-top: 8px; padding-top: 8px;">`;
                    tooltipHTML += `<div style="font-weight: 600; margin-bottom: 6px; color: #17bf63;">Connected Sources:</div>`;
                    connections.forEach(conn => {
                        tooltipHTML += `<div style="margin-bottom: 8px;">`;
                        tooltipHTML += `<div style="color: #e7e9ea; font-weight: 500;">→ ${conn.name} <span style="color: #8b98a5;">(${conn.count} shared)</span></div>`;
                        if (conn.keywords.length > 0) {
                            const keywordTags = conn.keywords.map(kw =>
                                `<span style="display: inline-block; background: #1da1f2; padding: 2px 6px; border-radius: 4px; margin: 2px; font-size: 11px;">${kw}</span>`
                            ).join('');
                            tooltipHTML += `<div style="margin-top: 4px;">${keywordTags}</div>`;
                        }
                        tooltipHTML += `</div>`;
                    });
                    tooltipHTML += `</div>`;
                } else {
                    tooltipHTML += `<div style="color: #8b98a5; margin-top: 8px; font-style: italic;">No connections</div>`;
                }

                // Show tooltip with smart positioning (to the right, with boundary checking)
                tooltip.html(tooltipHTML);

                const tooltipNode = tooltip.node();
                const tooltipWidth = tooltipNode.offsetWidth;
                const tooltipHeight = tooltipNode.offsetHeight;
                const containerRect = container.getBoundingClientRect();

                // Start position: to the right of cursor
                let left = event.pageX - container.offsetLeft + 20;
                let top = event.pageY - container.offsetTop - tooltipHeight / 2;

                // Check right boundary
                if (left + tooltipWidth > width - 20) {
                    // Position to the left of cursor instead
                    left = event.pageX - container.offsetLeft - tooltipWidth - 20;
                }

                // Check bottom boundary
                if (top + tooltipHeight > height - 20) {
                    top = height - tooltipHeight - 20;
                }

                // Check top boundary
                if (top < 20) {
                    top = 20;
                }

                tooltip
                    .style('visibility', 'visible')
                    .style('left', left + 'px')
                    .style('top', top + 'px');

                // Show only connected links, hide others
                linkElements
                    .transition()
                    .duration(200)
                    .style('opacity', link => {
                        const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
                        const targetId = typeof link.target === 'object' ? link.target.id : link.target;
                        return (sourceId === d.id || targetId === d.id) ? 1 : 0; // Hide unconnected
                    })
                    .style('stroke-opacity', link => {
                        const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
                        const targetId = typeof link.target === 'object' ? link.target.id : link.target;
                        return (sourceId === d.id || targetId === d.id) ? 1 : 0;
                    })
                    .style('stroke-width', link => {
                        const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
                        const targetId = typeof link.target === 'object' ? link.target.id : link.target;
                        return (sourceId === d.id || targetId === d.id) ? linkWidthScale(link.value) + 2 : linkWidthScale(link.value);
                    });

                // Dim unconnected nodes
                nodes.selectAll('circle')
                    .transition()
                    .duration(200)
                    .style('opacity', node => {
                        if (node.id === d.id) return 1; // Hovered node stays bright
                        // Check if connected
                        const isConnected = networkData.links.some(link => {
                            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
                            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
                            return (sourceId === d.id && targetId === node.id) || (targetId === d.id && sourceId === node.id);
                        });
                        return isConnected ? 0.9 : 0.2; // Dim unconnected nodes
                    });

                nodes.selectAll('text')
                    .transition()
                    .duration(200)
                    .style('opacity', node => {
                        if (node.id === d.id) return 1;
                        const isConnected = networkData.links.some(link => {
                            const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
                            const targetId = typeof link.target === 'object' ? link.target.id : link.target;
                            return (sourceId === d.id && targetId === node.id) || (targetId === d.id && sourceId === node.id);
                        });
                        return isConnected ? 1 : 0.2;
                    });
            })
            .on('click', function(event, d) {
                event.stopPropagation();
                // Toggle pin state
                tooltipPinned = !tooltipPinned;

                if (tooltipPinned) {
                    // Change border to indicate pinned state
                    tooltip.style('border', '2px solid #17bf63');
                } else {
                    tooltip.style('border', '2px solid #1da1f2');
                }
            })
            .on('mousemove', function(event, d) {
                // Only update tooltip position if not pinned
                if (!tooltipPinned) {
                    const tooltipNode = tooltip.node();
                    const tooltipWidth = tooltipNode.offsetWidth;
                    const tooltipHeight = tooltipNode.offsetHeight;

                    let left = event.pageX - container.offsetLeft + 20;
                    let top = event.pageY - container.offsetTop - tooltipHeight / 2;

                    if (left + tooltipWidth > width - 20) {
                        left = event.pageX - container.offsetLeft - tooltipWidth - 20;
                    }

                    if (top + tooltipHeight > height - 20) {
                        top = height - tooltipHeight - 20;
                    }

                    if (top < 20) {
                        top = 20;
                    }

                    tooltip
                        .style('left', left + 'px')
                        .style('top', top + 'px');
                }
            })
            .on('mouseleave', function(event, d) {
                // Only hide tooltip if not pinned
                if (!tooltipPinned) {
                    tooltip.style('visibility', 'hidden');
                }

                d3.select(this).select('circle')
                    .transition()
                    .duration(200)
                    .style('opacity', 0.9)
                    .attr('stroke-width', 2);

                // Reset all link styles
                linkElements
                    .transition()
                    .duration(200)
                    .style('opacity', 1)
                    .style('stroke-opacity', 0.6)
                    .style('stroke-width', link => linkWidthScale(link.value));

                // Reset all node opacity
                nodes.selectAll('circle')
                    .transition()
                    .duration(200)
                    .style('opacity', 0.9);

                nodes.selectAll('text')
                    .transition()
                    .duration(200)
                    .style('opacity', 1);
            });

            // Update positions on each tick with position clamping
            simulation.on('tick', () => {
                // Clamp node positions to stay within bounds
                networkData.nodes.forEach(node => {
                    node.x = Math.max(60, Math.min(width - 60, node.x));
                    node.y = Math.max(60, Math.min(height - 60, node.y));
                });

                linkElements
                    .attr('x1', d => d.source.x)
                    .attr('y1', d => d.source.y)
                    .attr('x2', d => d.target.x)
                    .attr('y2', d => d.target.y);

                nodes.attr('transform', d => `translate(${d.x},${d.y})`);
            });

            // Drag functions
            function dragstarted(event, d) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }

            function dragged(event, d) {
                d.fx = event.x;
                d.fy = event.y;
            }

            function dragended(event, d) {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }

            // Store simulation and graph elements for updates
            currentNetworkSimulation = simulation;
            networkGraphElements = {
                svg,
                linksGroup,
                linkElements,
                nodesGroup: nodes,
                colorScale,
                linkWidthScale,
                dragstarted,
                dragged,
                dragended
            };

            // Update container height
            container.style.height = height + 'px';
        })
        .catch(error => {
            console.error('Error loading source network:', error);
            networkLoading = false;
            const loading = document.getElementById('network-loading');
            if (loading) loading.remove();
            container.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 800px; color: #dc3545;">Error loading network data</div>';
        });
}

// Update existing network graph with new data
function updateNetworkGraph(url) {
    fetch(url)
        .then(response => response.json())
        .then(networkData => {
            if (!networkData.nodes || networkData.nodes.length === 0) {
                return;
            }

            // Update stored data
            currentNetworkData = networkData;

            const { svg, linkElements, nodesGroup, colorScale, linkWidthScale } = networkGraphElements;

            // Update or add nodes
            const nodeMap = new Map(currentNetworkSimulation.nodes().map(n => [n.id, n]));

            networkData.nodes.forEach(newNode => {
                if (nodeMap.has(newNode.id)) {
                    // Update existing node data
                    const existingNode = nodeMap.get(newNode.id);
                    existingNode.keywords = newNode.keywords;
                } else {
                    // Add new node with random position near center
                    const width = svg.attr('width');
                    const height = svg.attr('height');
                    newNode.x = width / 2 + (Math.random() - 0.5) * 200;
                    newNode.y = height / 2 + (Math.random() - 0.5) * 200;
                    newNode.vx = 0;
                    newNode.vy = 0;
                    currentNetworkSimulation.nodes().push(newNode);
                }
            });

            // Update links
            const linkData = networkData.links;

            // Update link elements
            const linkSelection = linkElements.data(linkData, d => `${d.source.id || d.source}-${d.target.id || d.target}`);

            // Remove old links
            linkSelection.exit().remove();

            // Add new links
            const newLinks = linkSelection.enter()
                .append('line')
                .attr('stroke', '#536471')
                .attr('stroke-width', d => linkWidthScale(d.value))
                .attr('stroke-opacity', 0.6);

            newLinks.append('title')
                .text(d => `${d.value} shared keywords: ${d.keywords.join(', ')}`);

            // Update existing links
            linkSelection
                .attr('stroke-width', d => linkWidthScale(d.value));

            // Update node visuals
            const nodeSelection = nodesGroup.data(currentNetworkSimulation.nodes(), d => d.id);

            // Update existing nodes
            nodeSelection.select('circle')
                .attr('r', d => Math.sqrt(d.keywords) * 4 + 20)
                .attr('fill', d => colorScale(d.keywords));

            nodeSelection.select('title')
                .text(d => `${d.name}\n${d.keywords} keywords`);

            // Restart simulation with new data
            currentNetworkSimulation.nodes(currentNetworkSimulation.nodes());
            currentNetworkSimulation.force('link').links(linkData);
            currentNetworkSimulation.alpha(0.3).restart();
        })
        .catch(error => {
            console.error('Error updating source network:', error);
        });
}

// Add latest keywords to the visualization (real-time update)
function addLatestKeywords(keywords, category) {
    // Filter based on current category
    if (currentCategory !== 'all' && currentCategory !== category) {
        return; // Don't update chart for other categories
    }

    // Don't reload if in network view (network view fetches its own data)
    if (currentViewMode === 'network') {
        return;
    }

    // Reload the visualization using debounced function
    debouncedLoadLatestKeywords();
}

// Crypto Price Predictions
let currentPredictionTimeframe = '24h';

// Load crypto predictions on page load
document.addEventListener('DOMContentLoaded', function() {
    loadCryptoPredictions();
    
    // Setup prediction timeframe buttons
    const timeframeButtons = document.querySelectorAll('.prediction-timeframe-btn');
    timeframeButtons.forEach(button => {
        button.addEventListener('click', function() {
            timeframeButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            currentPredictionTimeframe = this.dataset.timeframe;
            loadCryptoPredictions();
        });
    });
});

function loadCryptoPredictions() {
    const container = document.getElementById('cryptoPredictionsContainer');
    
    if (!container) return;
    
    container.innerHTML = '<p class="text-center text-muted">Loading predictions...</p>';
    
    fetch(`/api/crypto/predictions?timeframe=${currentPredictionTimeframe}`)
        .then(response => response.json())
        .then(data => {
            if (data.predictions && data.predictions.length > 0) {
                displayPredictions(data.predictions);
            } else {
                container.innerHTML = '<p class="text-center text-muted">No predictions available</p>';
            }
        })
        .catch(error => {
            console.error('Error loading predictions:', error);
            container.innerHTML = '<p class="text-center text-danger">Error loading predictions</p>';
        });
}

function displayPredictions(predictions) {
    const container = document.getElementById('cryptoPredictionsContainer');

    const html = `
        <div class="row">
            ${predictions.map(pred => createPredictionCard(pred)).join('')}
        </div>
    `;

    container.innerHTML = html;

    // Add click handlers to prediction cards
    predictions.forEach((pred, index) => {
        const card = container.querySelectorAll('.prediction-card')[index];
        if (card) {
            card.style.cursor = 'pointer';
            card.addEventListener('click', function() {
                showCryptoArticlesModal(pred);
            });
        }
    });
}

// Show crypto articles modal
function showCryptoArticlesModal(prediction) {
    // Get modal element
    const modal = new bootstrap.Modal(document.getElementById('keywordArticlesModal'));

    // Update modal title with crypto symbol and signal
    document.getElementById('keywordArticlesModalLabel').textContent =
        `${prediction.symbol} ${prediction.emoji} ${prediction.signal} - Articles Analyzed`;

    // Show loading spinner
    document.getElementById('keywordArticlesContent').innerHTML = `
        <div class="text-center">
            <div class="spinner-border text-primary" role="status">
                <span class="visually-hidden">Loading...</span>
            </div>
        </div>
    `;

    modal.show();

    // Map crypto symbols to keywords
    const symbolKeywordMap = {
        'BTC': 'bitcoin',
        'ETH': 'ethereum',
        'SOL': 'solana',
        'BNB': 'binance',
        'XRP': 'ripple',
        'ADA': 'cardano',
        'DOGE': 'dogecoin',
        'DOT': 'polkadot',
        'MATIC': 'polygon',
        'LTC': 'litecoin',
        'SHIB': 'shiba',
        'AVAX': 'avalanche',
        'UNI': 'uniswap',
        'LINK': 'chainlink',
        'XLM': 'stellar'
    };

    const keyword = symbolKeywordMap[prediction.symbol] || prediction.symbol.toLowerCase();
    const timeframeHours = parseInt(prediction.timeframe.replace('h', ''));

    // Fetch articles for this crypto
    fetch(`/api/keyword/${encodeURIComponent(keyword)}/articles?hours=${timeframeHours}&limit=50`)
        .then(response => response.json())
        .then(data => {
            if (data.articles && data.articles.length > 0) {
                // Calculate sentiment distribution
                const sentimentCounts = {
                    positive: 0,
                    negative: 0,
                    neutral: 0
                };

                data.articles.forEach(article => {
                    const sentiment = article.sentiment_label || 'neutral';
                    if (sentiment.includes('positive')) sentimentCounts.positive++;
                    else if (sentiment.includes('negative')) sentimentCounts.negative++;
                    else sentimentCounts.neutral++;
                });

                // Render articles with sentiment summary
                const articlesHTML = data.articles.map(article => {
                    const sentiment = article.sentiment_label || 'neutral';
                    const sentimentScore = article.sentiment_score || 0;
                    const category = article.category || 'general';
                    const createdAt = new Date(article.created_at).toLocaleString();
                    const articleUrl = article.url || '';

                    return `
                        <div class="tweet-card mb-3">
                            <div class="d-flex justify-content-between align-items-start mb-2">
                                <div>
                                    <span class="category-badge">${category.toUpperCase()}</span>
                                    <span class="sentiment-badge sentiment-${sentiment.replace('_', '-')}">${sentiment.replace('_', ' ').toUpperCase()}</span>
                                </div>
                                <small style="color: white;">${createdAt}</small>
                            </div>
                            <div class="mb-2">
                                <strong>@${article.user_handle || 'Unknown'}</strong>
                            </div>
                            <p class="mb-2">${escapeHtml(article.text)}</p>
                            <div class="d-flex justify-content-between align-items-center">
                                <small class="text-muted">Sentiment: ${sentimentScore.toFixed(2)}</small>
                                <div class="d-flex align-items-center">
                                    <small class="text-muted me-3">❤️ ${article.like_count || 0}</small>
                                    <small class="text-muted me-3">🔄 ${article.retweet_count || 0}</small>
                                    <small class="text-muted me-3">💬 ${article.reply_count || 0}</small>
                                    ${articleUrl ? `<a href="${articleUrl}" target="_blank" rel="noopener noreferrer" class="btn btn-sm btn-outline-primary">Open Article</a>` : ''}
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');

                // Create sentiment summary
                const total = data.articles.length;
                const posPercent = ((sentimentCounts.positive / total) * 100).toFixed(0);
                const negPercent = ((sentimentCounts.negative / total) * 100).toFixed(0);
                const neuPercent = ((sentimentCounts.neutral / total) * 100).toFixed(0);

                const timeText = timeframeHours === 168 ? 'last week' :
                                timeframeHours === 24 ? 'last 24 hours' :
                                timeframeHours === 12 ? 'last 12 hours' :
                                timeframeHours === 6 ? 'last 6 hours' :
                                timeframeHours === 5 ? 'last 5 hours' :
                                timeframeHours === 4 ? 'last 4 hours' :
                                timeframeHours === 3 ? 'last 3 hours' :
                                timeframeHours === 2 ? 'last 2 hours' :
                                timeframeHours === 1 ? 'last hour' :
                                `last ${timeframeHours} hours`;

                document.getElementById('keywordArticlesContent').innerHTML = `
                    <div class="mb-3">
                        <p class="text-muted mb-2">Found ${data.count} articles mentioning "<strong>${keyword}</strong>" in the ${timeText}</p>
                        <div class="d-flex gap-2 mb-3">
                            <span class="badge bg-success">Positive: ${posPercent}%</span>
                            <span class="badge bg-danger">Negative: ${negPercent}%</span>
                            <span class="badge bg-secondary">Neutral: ${neuPercent}%</span>
                        </div>
                        <div class="mb-2">
                            <strong>Prediction Summary:</strong><br>
                            <span style="color: ${prediction.signal === 'Bullish' ? '#17bf63' : prediction.signal === 'Bearish' ? '#dc3545' : '#8b98a5'};">
                                ${prediction.signal} ${prediction.emoji}
                            </span>
                            (Confidence: ${(prediction.confidence * 100).toFixed(0)}%)
                        </div>
                        <div class="mb-3" style="font-size: 0.9rem; color: #8b98a5; line-height: 1.4;">
                            ${prediction.reasoning}
                        </div>
                    </div>
                    ${articlesHTML}
                `;
            } else {
                const timeText = timeframeHours === 168 ? 'last week' :
                                timeframeHours === 24 ? 'last 24 hours' :
                                timeframeHours === 12 ? 'last 12 hours' :
                                timeframeHours === 6 ? 'last 6 hours' :
                                timeframeHours === 5 ? 'last 5 hours' :
                                timeframeHours === 4 ? 'last 4 hours' :
                                timeframeHours === 3 ? 'last 3 hours' :
                                timeframeHours === 2 ? 'last 2 hours' :
                                timeframeHours === 1 ? 'last hour' :
                                `last ${timeframeHours} hours`;

                document.getElementById('keywordArticlesContent').innerHTML = `
                    <p class="text-center text-muted">No articles found for "${keyword}" in the ${timeText}</p>
                `;
            }
        })
        .catch(error => {
            console.error('Error loading crypto articles:', error);
            document.getElementById('keywordArticlesContent').innerHTML = `
                <p class="text-center text-danger">Error loading articles. Please try again.</p>
            `;
        });
}

function createPredictionCard(prediction) {
    const signalClass = prediction.signal.toLowerCase();
    const emoji = prediction.emoji || '🟡';
    const confidence = (prediction.confidence * 100).toFixed(0);
    
    return `
        <div class="col-md-4 mb-3">
            <div class="prediction-card ${signalClass}">
                <div class="d-flex align-items-center mb-3">
                    <span class="prediction-emoji">${emoji}</span>
                    <div class="flex-grow-1">
                        <h4 class="mb-0">${prediction.symbol}</h4>
                        <div class="prediction-signal ${signalClass}">${prediction.signal}</div>
                    </div>
                </div>
                
                <div class="prediction-meta">
                    <div class="mb-2">
                        <strong>Confidence:</strong> ${confidence}%
                        <div class="confidence-bar">
                            <div class="confidence-fill" style="width: ${confidence}%"></div>
                        </div>
                    </div>
                    
                    <div class="mb-2">
                        <strong>Sentiment Score:</strong> ${prediction.weighted_sentiment.toFixed(2)}
                    </div>
                    
                    <div class="mb-2">
                        <strong>Articles Analyzed:</strong> ${prediction.article_count}
                    </div>
                    
                    <div class="mt-3" style="font-size: 0.85rem; line-height: 1.4;">
                        ${prediction.reasoning}
                    </div>
                </div>
            </div>
        </div>
    `;
}
