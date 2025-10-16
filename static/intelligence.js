/**
 * News Intelligence Page - JavaScript
 */

// Show loading spinner
function showLoading(containerId) {
    $(`#${containerId}`).html(`
        <div class="loading-spinner">
            <i class="bi bi-arrow-clockwise"></i>
            <p>Loading...</p>
        </div>
    `);
}

// Show error message
function showError(containerId, message) {
    $(`#${containerId}`).html(`
        <div class="alert alert-warning">
            <i class="bi bi-exclamation-triangle"></i> ${message}
        </div>
    `);
}

// Show empty state
function showEmpty(containerId, message) {
    $(`#${containerId}`).html(`
        <div class="empty-state">
            <i class="bi bi-inbox"></i>
            <p>${message}</p>
        </div>
    `);
}

// Load daily briefing
function loadBriefing(type) {
    showLoading('briefing-content');

    $.ajax({
        url: `/api/intelligence/briefing/${type}`,
        method: 'GET',
        timeout: 90000, // 90 second timeout for AI generation
        success: function(data) {
            const briefing = data.briefing;
            const stats = briefing.stats || {};
            const stories = briefing.top_stories || [];

            let html = `
                <div class="briefing-content">
                    <h5><i class="bi bi-chat-quote"></i> Summary</h5>
                    <p>${briefing.summary}</p>
                </div>

                <div class="briefing-stats">
                    <div class="stat-box">
                        <div class="stat-value">${stats.total_articles || 0}</div>
                        <div class="stat-label">Total Articles</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">${(stats.avg_sentiment || 0).toFixed(2)}</div>
                        <div class="stat-label">Avg Sentiment</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">${stats.trending_count || 0}</div>
                        <div class="stat-label">Trending Topics</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">${stats.top_category || 'N/A'}</div>
                        <div class="stat-label">Top Category</div>
                    </div>
                </div>
            `;

            if (stories.length > 0) {
                html += '<h5 class="mt-4"><i class="bi bi-list-stars"></i> Top Stories</h5>';
                stories.forEach((story, idx) => {
                    const sentimentEmoji = story.sentiment > 0.1 ? '🟢' : (story.sentiment < -0.1 ? '🔴' : '⚪');
                    html += `
                        <div class="story-item">
                            <div class="story-keyword">
                                ${idx + 1}. ${sentimentEmoji} ${story.keyword}
                                <span class="badge bg-secondary">${story.count} articles</span>
                            </div>
                            <div class="story-summary">${story.summary}</div>
                        </div>
                    `;
                });
            }

            $('#briefing-content').html(html);
        },
        error: function(xhr, status, error) {
            showError('briefing-content', 'Failed to load briefing. The AI model may be loading, please try again in a moment.');
        }
    });
}

// Load trending topics
function loadTrending() {
    const hours = $('#trending-hours').val();
    showLoading('trending-content');

    $.ajax({
        url: `/api/intelligence/trends`,
        method: 'GET',
        data: { hours: hours, min_articles: 2 },
        timeout: 60000,  // Increased timeout to 60 seconds
        success: function(data) {
            const trends = data.trends || [];

            if (trends.length === 0) {
                showEmpty('trending-content', 'No trending topics found in this time range.');
                return;
            }

            let html = '';
            trends.forEach(trend => {
                const momentumClass = trend.trend_status === 'skyrocketing' ? 'momentum-skyrocketing' :
                                     trend.trend_status === 'rising_fast' ? 'momentum-rising-fast' :
                                     'momentum-trending-up';

                const momentumEmoji = trend.momentum > 2 ? '🚀' :
                                     trend.momentum > 1.5 ? '📈' : '📊';

                const sentimentEmoji = trend.avg_sentiment > 0.1 ? '🟢' :
                                      trend.avg_sentiment < -0.1 ? '🔴' : '⚪';

                html += `
                    <div class="trend-item">
                        <div>
                            <span class="trend-keyword">${momentumEmoji} ${trend.keyword}</span>
                            <span class="trend-momentum ${momentumClass}">
                                ${trend.momentum}x momentum
                            </span>
                            <span class="badge bg-info">${trend.current_count} articles</span>
                        </div>
                        <div class="trend-meta">
                            ${sentimentEmoji} Sentiment: ${trend.avg_sentiment.toFixed(2)} |
                            Status: ${trend.trend_status.replace('_', ' ')} |
                            Categories: ${trend.categories.join(', ') || 'N/A'}
                        </div>
                    </div>
                `;
            });

            $('#trending-content').html(html);
        },
        error: function(xhr, status, error) {
            showError('trending-content', 'Failed to load trending topics.');
        }
    });
}

// Check what changed
function checkChanges() {
    const hoursAway = $('#time-away').val();
    showLoading('changes-content');

    // Calculate last visit time
    const lastVisit = new Date();
    lastVisit.setHours(lastVisit.getHours() - hoursAway);

    $.ajax({
        url: '/api/intelligence/what-changed',
        method: 'GET',
        data: { last_visit: lastVisit.toISOString() },
        timeout: 30000,
        success: function(data) {
            const changes = data.changes;

            let html = `
                <div class="briefing-content">
                    <h5><i class="bi bi-info-circle"></i> Summary</h5>
                    <p>${changes.summary}</p>
                </div>

                <div class="briefing-stats">
                    <div class="stat-box">
                        <div class="stat-value">${changes.new_articles}</div>
                        <div class="stat-label">New Articles</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">${changes.new_trends}</div>
                        <div class="stat-label">New Trends</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">${changes.time_away}</div>
                        <div class="stat-label">Time Away</div>
                    </div>
                    <div class="stat-box">
                        <div class="stat-value">${changes.sentiment_changes}</div>
                        <div class="stat-label">Sentiment Shifts</div>
                    </div>
                </div>
            `;

            if (changes.new_trending_topics && changes.new_trending_topics.length > 0) {
                html += '<h5 class="mt-4"><i class="bi bi-fire"></i> New Trending Topics</h5>';
                html += '<div class="row">';
                changes.new_trending_topics.forEach(topic => {
                    html += `
                        <div class="col-md-4 mb-3">
                            <div class="trend-item">
                                <span class="trend-keyword">${topic}</span>
                            </div>
                        </div>
                    `;
                });
                html += '</div>';
            }

            $('#changes-content').html(html);
        },
        error: function(xhr, status, error) {
            showError('changes-content', 'Failed to calculate changes.');
        }
    });
}

// Analyze keyword
function analyzeKeyword() {
    const keyword = $('#keyword-input').val().trim();

    if (!keyword) {
        alert('Please enter a keyword to analyze');
        return;
    }

    // Get selected time range
    const selectedHours = $('.analysis-timerange-btn.active').data('hours') || 24;

    // Load TL;DR
    showLoading('tldr-content');
    $.ajax({
        url: `/api/intelligence/tldr/${encodeURIComponent(keyword)}`,
        method: 'GET',
        data: { hours: selectedHours },
        timeout: 60000,
        success: function(data) {
            let html = `
                <div class="briefing-content">
                    <p><strong>${data.tldr}</strong></p>
                    <small class="text-muted">Based on ${data.article_count} articles</small>
                </div>
            `;
            $('#tldr-content').html(html);
        },
        error: function() {
            showError('tldr-content', 'Failed to generate TL;DR');
        }
    });

    // Load momentum
    showLoading('momentum-content');
    $.ajax({
        url: `/api/intelligence/trend-momentum/${encodeURIComponent(keyword)}`,
        method: 'GET',
        data: { hours: selectedHours },
        timeout: 30000,
        success: function(data) {
            const momentum = data.momentum;
            const momentumClass = momentum.trend_status === 'skyrocketing' ? 'momentum-skyrocketing' :
                                 momentum.trend_status === 'rising_fast' ? 'momentum-rising-fast' :
                                 'momentum-trending-up';

            let html = `
                <div class="briefing-content">
                    <div class="mb-3">
                        <span class="trend-momentum ${momentumClass}">
                            ${momentum.momentum}x momentum
                        </span>
                    </div>
                    <p><strong>Status:</strong> ${momentum.trend_status.replace('_', ' ')}</p>
                    <p><strong>Velocity:</strong> ${momentum.velocity}</p>
                    <p><strong>Articles:</strong> ${momentum.current_count} (previous: ${momentum.previous_count})</p>
                    <p><strong>Sentiment:</strong> ${momentum.avg_sentiment.toFixed(2)}</p>
                    <p><strong>Categories:</strong> ${momentum.categories.join(', ')}</p>
                </div>
            `;
            $('#momentum-content').html(html);
        },
        error: function() {
            showError('momentum-content', 'Failed to calculate momentum');
        }
    });

    // Load source comparison
    showLoading('sources-content');
    $.ajax({
        url: `/api/intelligence/sources/${encodeURIComponent(keyword)}`,
        method: 'GET',
        data: { hours: selectedHours },
        timeout: 60000,
        success: function(data) {
            const comparison = data.comparison;

            if (comparison.source_count === 0) {
                showEmpty('sources-content', 'No sources found covering this topic.');
                return;
            }

            let html = `<p class="text-muted mb-3">${comparison.source_count} sources covering "${comparison.keyword}"</p>`;

            Object.entries(comparison.sources).forEach(([source, data]) => {
                const sentimentClass = data.sentiment_label === 'positive' ? 'sentiment-positive' :
                                      data.sentiment_label === 'negative' ? 'sentiment-negative' :
                                      'sentiment-neutral';

                html += `
                    <div class="source-item">
                        <div class="source-name">
                            ${source}
                            <span class="source-sentiment ${sentimentClass}">${data.sentiment_label}</span>
                            <span class="badge bg-secondary">${data.article_count} articles</span>
                        </div>
                        <div class="text-muted">${data.perspective}</div>
                    </div>
                `;
            });

            $('#sources-content').html(html);
        },
        error: function() {
            showError('sources-content', 'Failed to compare sources');
        }
    });

    // Load story timeline (use double the hours for better context)
    showLoading('timeline-content');
    const timelineHours = Math.min(selectedHours * 2, 168); // Cap at 1 week
    $.ajax({
        url: `/api/intelligence/story-thread/${encodeURIComponent(keyword)}`,
        method: 'GET',
        data: { hours: timelineHours },
        timeout: 60000,
        success: function(data) {
            const thread = data.thread;

            if (!thread.is_story_thread) {
                $('#timeline-content').html(`
                    <div class="alert alert-info">
                        <i class="bi bi-info-circle"></i> ${thread.analysis}
                    </div>
                `);
                return;
            }

            let html = `
                <div class="mb-3">
                    <p><strong>${thread.analysis}</strong></p>
                </div>
            `;

            if (thread.timeline && thread.timeline.length > 0) {
                thread.timeline.forEach((item, idx) => {
                    const time = new Date(item.timestamp).toLocaleString();
                    const sentimentEmoji = item.sentiment > 0.1 ? '🟢' : (item.sentiment < -0.1 ? '🔴' : '⚪');

                    html += `
                        <div class="timeline-item">
                            <div class="timeline-dot"></div>
                            <div class="timeline-time">${time} - ${item.source}</div>
                            <div class="timeline-content">
                                ${sentimentEmoji} ${item.text}
                            </div>
                        </div>
                    `;
                });
            }

            $('#timeline-content').html(html);
        },
        error: function() {
            showError('timeline-content', 'Failed to analyze story thread');
        }
    });
}

// Load top stories with TL;DR
function loadTopStories() {
    showLoading('top-stories-content');

    // Get top keywords and generate TL;DR for each
    $.ajax({
        url: '/api/wordcloud',
        method: 'GET',
        data: { hours: 24, limit: 10 },
        success: function(keywords) {
            if (keywords.length === 0) {
                showEmpty('top-stories-content', 'No stories available yet.');
                return;
            }

            let html = '';
            let loadedCount = 0;

            keywords.slice(0, 5).forEach((kw, idx) => {
                // Get TL;DR for each keyword
                $.ajax({
                    url: `/api/intelligence/tldr/${encodeURIComponent(kw.word)}`,
                    method: 'GET',
                    data: { hours: 24 },
                    timeout: 60000,
                    success: function(data) {
                        $(`#story-${idx}`).html(`
                            <div class="story-item">
                                <div class="story-keyword">
                                    ${idx + 1}. ${kw.word}
                                    <span class="badge bg-secondary">${data.article_count} articles</span>
                                </div>
                                <div class="story-summary">${data.tldr}</div>
                            </div>
                        `);
                    },
                    error: function() {
                        $(`#story-${idx}`).html(`
                            <div class="story-item">
                                <div class="story-keyword">${idx + 1}. ${kw.word}</div>
                                <div class="story-summary text-muted">Summary not available</div>
                            </div>
                        `);
                    }
                });

                html += `<div id="story-${idx}">
                    <div class="loading-spinner" style="padding: 20px;">
                        <i class="bi bi-arrow-clockwise"></i>
                    </div>
                </div>`;
            });

            $('#top-stories-content').html(html);
        },
        error: function() {
            showError('top-stories-content', 'Failed to load top stories');
        }
    });
}

// Event handlers
$(document).ready(function() {
    // Briefing buttons
    $('.briefing-btn').on('click', function() {
        $('.briefing-btn').removeClass('btn-primary').addClass('btn-outline-primary');
        $(this).removeClass('btn-outline-primary').addClass('btn-primary');

        const type = $(this).data('type');
        loadBriefing(type);
    });

    // Refresh trends
    $('#refresh-trends').on('click', loadTrending);
    $('#trending-hours').on('change', loadTrending);

    // Check changes
    $('#check-changes').on('click', checkChanges);

    // Analyze keyword
    $('#analyze-keyword').on('click', analyzeKeyword);
    $('#keyword-input').on('keypress', function(e) {
        if (e.which === 13) { // Enter key
            analyzeKeyword();
        }
    });

    // Analysis time range buttons
    $('.analysis-timerange-btn').on('click', function() {
        $('.analysis-timerange-btn').removeClass('active');
        $(this).addClass('active');

        // If keyword is already entered, re-analyze with new time range
        const keyword = $('#keyword-input').val().trim();
        if (keyword) {
            analyzeKeyword();
        }
    });

    // Load initial data
    loadTrending();
    loadTopStories();

    // Auto-load morning briefing
    setTimeout(() => {
        $('.briefing-btn[data-type="morning"]').click();
    }, 500);
});
