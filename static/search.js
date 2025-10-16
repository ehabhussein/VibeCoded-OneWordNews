// Search page JavaScript
let currentSearchResults = [];
let currentFilters = {
    time: 24,
    category: 'all',
    sentiment: 'all',
    sort: 'relevance'
};

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    setupEventListeners();

    // Check if there's a query parameter in URL
    const urlParams = new URLSearchParams(window.location.search);
    const query = urlParams.get('q');
    if (query) {
        document.getElementById('searchInput').value = query;
        performSearch();
    }
});

function setupEventListeners() {
    // Search button click
    document.getElementById('searchBtn').addEventListener('click', performSearch);

    // Enter key in search input
    document.getElementById('searchInput').addEventListener('keypress', function(e) {
        if (e.key === 'Enter') {
            performSearch();
        }
    });

    // Filter chips
    document.querySelectorAll('.filter-chip').forEach(chip => {
        chip.addEventListener('click', function() {
            const filterType = this.dataset.filterType;
            const value = this.dataset.value;

            // Update active state
            this.parentElement.querySelectorAll('.filter-chip').forEach(c => c.classList.remove('active'));
            this.classList.add('active');

            // Update filter
            currentFilters[filterType] = value;

            // Re-search if we have results
            if (currentSearchResults.length > 0) {
                performSearch();
            }
        });
    });
}

async function performSearch() {
    const query = document.getElementById('searchInput').value.trim();

    if (!query) {
        alert('Please enter a search query');
        return;
    }

    // Show loading
    showLoading();
    hideResults();
    hideNoResults();

    try {
        // Build search URL
        const params = new URLSearchParams({
            q: query,
            hours: currentFilters.time,
            category: currentFilters.category,
            sentiment: currentFilters.sentiment,
            sort: currentFilters.sort,
            limit: 100
        });

        const response = await fetch(`/api/search?${params}`);
        const data = await response.json();

        hideLoading();

        if (data.total > 0) {
            currentSearchResults = data.articles;
            displayResults(data);
        } else {
            showNoResults();
        }
    } catch (error) {
        console.error('Search error:', error);
        hideLoading();
        alert('Search failed. Please try again.');
    }
}

function displayResults(data) {
    // Update summary stats
    document.getElementById('totalArticles').textContent = data.total;
    document.getElementById('avgSentiment').textContent = data.analytics.avg_sentiment;
    document.getElementById('uniqueSources').textContent = data.analytics.unique_sources;
    document.getElementById('timeSpan').textContent = data.analytics.time_span;

    // Show results container
    document.getElementById('resultsSummary').style.display = 'block';
    document.getElementById('analysisContainer').style.display = 'block';

    // Display articles
    displayArticles(data.articles);

    // Display timeline
    displayTimeline(data.articles);

    // Display sentiment analysis
    displaySentimentAnalysis(data.articles);

    // Display keyword network
    displayKeywordNetwork(data.articles);

    // Display source analysis
    displaySourceAnalysis(data.articles);
}

function displayArticles(articles) {
    const container = document.getElementById('articlesContainer');

    if (articles.length === 0) {
        container.innerHTML = '<p class="text-center text-muted">No articles found</p>';
        return;
    }

    const articlesHTML = articles.map(article => {
        const sentiment = getSentimentClass(article.sentiment_score);
        const sentimentLabel = article.sentiment_label || 'Neutral';
        const date = new Date(article.created_at).toLocaleString();

        return `
            <div class="article-card">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                        <span class="source-badge">${article.user_handle || 'Unknown'}</span>
                        <span class="category-badge">${article.category || 'N/A'}</span>
                    </div>
                    <span class="sentiment-badge ${sentiment}">${sentimentLabel}</span>
                </div>
                <p class="mb-2">${article.text}</p>
                <small class="text-muted">${date}</small>
            </div>
        `;
    }).join('');

    container.innerHTML = articlesHTML;
}

function displayTimeline(articles) {
    // Group articles by hour
    const hourlyData = {};

    articles.forEach(article => {
        const date = new Date(article.created_at);
        const hourKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:00`;

        if (!hourlyData[hourKey]) {
            hourlyData[hourKey] = {
                count: 0,
                sentiment: 0,
                articles: []
            };
        }

        hourlyData[hourKey].count++;
        hourlyData[hourKey].sentiment += article.sentiment_score || 0;
        hourlyData[hourKey].articles.push(article);
    });

    // Prepare data for Plotly
    const timestamps = Object.keys(hourlyData).sort();
    const counts = timestamps.map(t => hourlyData[t].count);
    const avgSentiments = timestamps.map(t =>
        hourlyData[t].sentiment / hourlyData[t].count
    );

    const trace1 = {
        x: timestamps,
        y: counts,
        type: 'bar',
        name: 'Article Count',
        yaxis: 'y',
        marker: { color: '#1da1f2' }
    };

    const trace2 = {
        x: timestamps,
        y: avgSentiments,
        type: 'scatter',
        mode: 'lines+markers',
        name: 'Avg Sentiment',
        yaxis: 'y2',
        line: { color: '#17bf63', width: 2 },
        marker: { size: 8 }
    };

    const layout = {
        title: 'Article Timeline',
        xaxis: { title: 'Time' },
        yaxis: { title: 'Article Count' },
        yaxis2: {
            title: 'Avg Sentiment',
            overlaying: 'y',
            side: 'right',
            range: [-1, 1]
        },
        plot_bgcolor: '#0f1419',
        paper_bgcolor: '#16181c',
        font: { color: '#e7e9ea' },
        hovermode: 'x unified'
    };

    Plotly.newPlot('timelineChart', [trace1, trace2], layout, {responsive: true});
}

function displaySentimentAnalysis(articles) {
    // Sentiment over time
    const hourlyData = {};

    articles.forEach(article => {
        const date = new Date(article.created_at);
        const hourKey = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:00`;

        if (!hourlyData[hourKey]) {
            hourlyData[hourKey] = [];
        }

        hourlyData[hourKey].push(article.sentiment_score || 0);
    });

    const timestamps = Object.keys(hourlyData).sort();
    const avgSentiments = timestamps.map(t => {
        const sentiments = hourlyData[t];
        return sentiments.reduce((a, b) => a + b, 0) / sentiments.length;
    });

    const timeTrace = {
        x: timestamps,
        y: avgSentiments,
        type: 'scatter',
        mode: 'lines+markers',
        fill: 'tozeroy',
        line: { color: '#1da1f2', width: 2 },
        marker: { size: 6 }
    };

    const timeLayout = {
        title: 'Sentiment Trend',
        xaxis: { title: 'Time' },
        yaxis: { title: 'Sentiment Score', range: [-1, 1] },
        plot_bgcolor: '#0f1419',
        paper_bgcolor: '#16181c',
        font: { color: '#e7e9ea' },
        shapes: [{
            type: 'line',
            x0: timestamps[0],
            x1: timestamps[timestamps.length - 1],
            y0: 0,
            y1: 0,
            line: { color: '#8b98a5', width: 1, dash: 'dash' }
        }]
    };

    Plotly.newPlot('sentimentTimeChart', [timeTrace], timeLayout, {responsive: true});

    // Sentiment distribution
    const positive = articles.filter(a => (a.sentiment_score || 0) > 0.1).length;
    const neutral = articles.filter(a => Math.abs(a.sentiment_score || 0) <= 0.1).length;
    const negative = articles.filter(a => (a.sentiment_score || 0) < -0.1).length;

    const distTrace = {
        labels: ['Positive', 'Neutral', 'Negative'],
        values: [positive, neutral, negative],
        type: 'pie',
        marker: {
            colors: ['#17bf63', '#536471', '#dc3545']
        },
        hole: 0.4
    };

    const distLayout = {
        title: 'Sentiment Distribution',
        plot_bgcolor: '#0f1419',
        paper_bgcolor: '#16181c',
        font: { color: '#e7e9ea' }
    };

    Plotly.newPlot('sentimentDistChart', [distTrace], distLayout, {responsive: true});
}

function displayKeywordNetwork(articles) {
    // Extract keywords and build co-occurrence network
    const keywordCounts = {};
    const keywordCooccurrence = {};

    articles.forEach(article => {
        const words = article.text.toLowerCase().match(/\b[a-z]{4,}\b/g) || [];
        const uniqueWords = [...new Set(words)].slice(0, 10); // Top 10 words per article

        uniqueWords.forEach(word => {
            keywordCounts[word] = (keywordCounts[word] || 0) + 1;

            if (!keywordCooccurrence[word]) {
                keywordCooccurrence[word] = {};
            }

            uniqueWords.forEach(otherWord => {
                if (word !== otherWord) {
                    keywordCooccurrence[word][otherWord] =
                        (keywordCooccurrence[word][otherWord] || 0) + 1;
                }
            });
        });
    });

    // Get top keywords
    const topKeywords = Object.entries(keywordCounts)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 20)
        .map(([word]) => word);

    // Build network data
    const nodes = topKeywords.map(word => ({
        id: word,
        label: word,
        value: keywordCounts[word]
    }));

    const links = [];
    topKeywords.forEach(word1 => {
        topKeywords.forEach(word2 => {
            if (word1 < word2 && keywordCooccurrence[word1] && keywordCooccurrence[word1][word2]) {
                links.push({
                    source: word1,
                    target: word2,
                    value: keywordCooccurrence[word1][word2]
                });
            }
        });
    });

    // Create D3 force-directed graph
    createForceGraph('keywordNetworkChart', nodes, links);
}

function displaySourceAnalysis(articles) {
    // Count articles by source
    const sourceCounts = {};

    articles.forEach(article => {
        const source = article.user_handle || 'Unknown';
        sourceCounts[source] = (sourceCounts[source] || 0) + 1;
    });

    const sources = Object.keys(sourceCounts).sort((a, b) => sourceCounts[b] - sourceCounts[a]).slice(0, 15);
    const counts = sources.map(s => sourceCounts[s]);

    const trace = {
        x: counts,
        y: sources,
        type: 'bar',
        orientation: 'h',
        marker: { color: '#1da1f2' }
    };

    const layout = {
        title: 'Top Sources',
        xaxis: { title: 'Article Count' },
        yaxis: { title: 'Source' },
        plot_bgcolor: '#0f1419',
        paper_bgcolor: '#16181c',
        font: { color: '#e7e9ea' },
        margin: { l: 150 }
    };

    Plotly.newPlot('sourcesChart', [trace], layout, {responsive: true});
}

function createForceGraph(containerId, nodes, links) {
    const container = document.getElementById(containerId);
    const width = container.clientWidth;
    const height = 600;

    // Clear existing
    container.innerHTML = '';

    // Create SVG
    const svg = d3.select(`#${containerId}`)
        .append('svg')
        .attr('width', width)
        .attr('height', height);

    // Create simulation
    const simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(links).id(d => d.id).distance(100))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(d => Math.sqrt(d.value) * 5 + 20));

    // Create links
    const link = svg.append('g')
        .selectAll('line')
        .data(links)
        .enter()
        .append('line')
        .attr('stroke', '#2f3336')
        .attr('stroke-width', d => Math.sqrt(d.value));

    // Create nodes
    const node = svg.append('g')
        .selectAll('g')
        .data(nodes)
        .enter()
        .append('g')
        .call(d3.drag()
            .on('start', dragStarted)
            .on('drag', dragged)
            .on('end', dragEnded));

    node.append('circle')
        .attr('r', d => Math.sqrt(d.value) * 5 + 10)
        .attr('fill', '#1da1f2')
        .attr('class', 'keyword-network-node');

    node.append('text')
        .text(d => d.label)
        .attr('x', 0)
        .attr('y', 5)
        .attr('text-anchor', 'middle')
        .attr('fill', '#e7e9ea')
        .attr('font-size', '12px')
        .attr('font-weight', 'bold')
        .style('pointer-events', 'none');

    // Update positions
    simulation.on('tick', () => {
        link
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        node.attr('transform', d => `translate(${d.x},${d.y})`);
    });

    function dragStarted(event, d) {
        if (!event.active) simulation.alphaTarget(0.3).restart();
        d.fx = d.x;
        d.fy = d.y;
    }

    function dragged(event, d) {
        d.fx = event.x;
        d.fy = event.y;
    }

    function dragEnded(event, d) {
        if (!event.active) simulation.alphaTarget(0);
        d.fx = null;
        d.fy = null;
    }
}

function getSentimentClass(score) {
    if (score === null || score === undefined) return 'sentiment-neutral';
    if (score > 0.5) return 'sentiment-very-positive';
    if (score > 0.1) return 'sentiment-positive';
    if (score < -0.5) return 'sentiment-very-negative';
    if (score < -0.1) return 'sentiment-negative';
    return 'sentiment-neutral';
}

function showLoading() {
    document.getElementById('loadingSpinner').style.display = 'block';
}

function hideLoading() {
    document.getElementById('loadingSpinner').style.display = 'none';
}

function showNoResults() {
    document.getElementById('noResults').style.display = 'block';
}

function hideNoResults() {
    document.getElementById('noResults').style.display = 'none';
}

function hideResults() {
    document.getElementById('resultsSummary').style.display = 'none';
    document.getElementById('analysisContainer').style.display = 'none';
}
