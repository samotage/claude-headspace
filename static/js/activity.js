(function(global) {
    'use strict';

    let chart = null;
    let currentWindow = 'day';
    let windowOffset = 0;  // 0 = current period, -1 = previous, etc.
    var _refreshDebounce = null;

    // Frustration thresholds from config (injected by template)
    var THRESHOLDS = global.FRUSTRATION_THRESHOLDS || { yellow: 4, red: 7 };
    var HEADSPACE_ENABLED = global.HEADSPACE_ENABLED || false;

    // Color constants for frustration states
    var FRUST_COLORS = {
        green:  { text: 'text-green',  rgb: '76, 175, 80',  hex: '#4caf50' },
        yellow: { text: 'text-amber',  rgb: '255, 193, 7',  hex: '#ffc107' },
        red:    { text: 'text-red',    rgb: '255, 85, 85',   hex: '#ff5555' }
    };

    // Rate label by window
    var RATE_LABELS = { day: 'Turns / Hour', week: 'Turns / Day', month: 'Turns / Day' };

    /**
     * Fetch with retry and exponential backoff.
     * Returns the parsed JSON response, or null after all retries fail.
     */
    function _fetchWithRetry(url, maxRetries, baseDelayMs) {
        maxRetries = maxRetries || 3;
        baseDelayMs = baseDelayMs || 1000;
        var attempt = 0;

        function doFetch() {
            return fetch(url).then(function(res) {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            }).catch(function(err) {
                attempt++;
                if (attempt >= maxRetries) {
                    console.error('Fetch failed after ' + maxRetries + ' attempts: ' + url, err);
                    return null;
                }
                var delay = baseDelayMs * Math.pow(2, attempt - 1);
                return new Promise(function(resolve) {
                    setTimeout(function() { resolve(doFetch()); }, delay);
                });
            });
        }

        return doFetch();
    }

    /**
     * Compute frustration level (green/yellow/red) from a numeric average.
     */
    function _levelFromAvg(avg) {
        if (avg == null) return 'green';
        if (avg >= THRESHOLDS.red) return 'red';
        if (avg >= THRESHOLDS.yellow) return 'yellow';
        return 'green';
    }

    const ActivityPage = {
        init: function() {
            this.loadOverallMetrics();
            this.loadProjectMetrics();
            this._initSSE();
            if (HEADSPACE_ENABLED) {
                this._initFrustrationWidget();
            }
        },

        setWindow: function(w) {
            currentWindow = w;
            windowOffset = 0;
            document.querySelectorAll('#window-toggles button').forEach(function(btn) {
                if (btn.dataset.window === w) {
                    btn.className = 'px-3 py-1 text-sm rounded border border-cyan/30 bg-cyan/20 text-cyan font-medium';
                } else {
                    btn.className = 'px-3 py-1 text-sm rounded border border-border text-secondary hover:text-primary hover:border-cyan/30 transition-colors';
                }
            });
            this._refresh();
        },

        goBack: function() {
            windowOffset--;
            this._refresh();
        },

        goForward: function() {
            if (windowOffset < 0) {
                windowOffset++;
                this._refresh();
            }
        },

        _refresh: function() {
            this._updateNav();
            this.loadOverallMetrics();
            this.loadProjectMetrics();
            if (HEADSPACE_ENABLED) {
                if (currentWindow === 'day' && windowOffset === 0) {
                    this._initFrustrationWidget();
                }
                // Historical frustration is updated inside loadOverallMetrics callback
            }
        },

        /**
         * Compute the start of a period given an offset from the current period.
         * offset=0 is the current period, -1 is the previous, etc.
         */
        _periodStart: function(offset) {
            var now = new Date();
            if (currentWindow === 'day') {
                return new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset);
            } else if (currentWindow === 'week') {
                var dow = now.getDay();
                var diffToMon = (dow === 0 ? 6 : dow - 1);
                var thisMon = new Date(now.getFullYear(), now.getMonth(), now.getDate() - diffToMon);
                return new Date(thisMon.getFullYear(), thisMon.getMonth(), thisMon.getDate() + (offset * 7));
            } else {
                return new Date(now.getFullYear(), now.getMonth() + offset, 1);
            }
        },

        _periodTitle: function() {
            var start = this._periodStart(windowOffset);
            if (currentWindow === 'day') {
                if (windowOffset === 0) return 'Today';
                if (windowOffset === -1) return 'Yesterday';
                return start.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' });
            } else if (currentWindow === 'week') {
                var end = new Date(start);
                end.setDate(end.getDate() + 6);
                if (windowOffset === 0) {
                    return 'This Week';
                }
                return start.toLocaleDateString([], { day: 'numeric', month: 'short' }) +
                    ' \u2013 ' + end.toLocaleDateString([], { day: 'numeric', month: 'short' });
            } else {
                if (windowOffset === 0) return 'This Month';
                return start.toLocaleDateString([], { month: 'long', year: 'numeric' });
            }
        },

        _updateNav: function() {
            document.getElementById('period-title').textContent = this._periodTitle();
            var fwdBtn = document.getElementById('nav-forward');
            if (windowOffset >= 0) {
                fwdBtn.disabled = true;
                fwdBtn.className = 'w-7 h-7 flex items-center justify-center rounded border border-border text-muted cursor-not-allowed text-sm';
            } else {
                fwdBtn.disabled = false;
                fwdBtn.className = 'w-7 h-7 flex items-center justify-center rounded border border-border text-secondary hover:text-primary hover:border-cyan/30 transition-colors text-sm';
            }
        },

        _apiParams: function() {
            var since = this._periodStart(windowOffset).toISOString();
            var until = this._periodStart(windowOffset + 1).toISOString();
            return 'window=' + currentWindow +
                '&since=' + encodeURIComponent(since) +
                '&until=' + encodeURIComponent(until);
        },

        /**
         * Compute turn rate from total turns based on window.
         * Day: turns/hour (elapsed hours), Week/Month: turns/day (elapsed days).
         * Uses actual elapsed time so incomplete periods are accurate.
         */
        _computeRate: function(totalTurns) {
            var periodStart = this._periodStart(windowOffset);
            var periodEnd = this._periodStart(windowOffset + 1);
            var now = new Date();
            var effectiveEnd = now < periodEnd ? now : periodEnd;

            if (currentWindow === 'day') {
                var hoursElapsed = Math.max((effectiveEnd - periodStart) / (1000 * 60 * 60), 1);
                return totalTurns / hoursElapsed;
            }
            // week/month: turns per day
            var daysElapsed = Math.max((effectiveEnd - periodStart) / (1000 * 60 * 60 * 24), 1);
            return totalTurns / daysElapsed;
        },

        _formatRate: function(rate) {
            if (rate === 0) return '0';
            if (rate >= 10) return Math.round(rate).toString();
            return rate.toFixed(1);
        },

        /**
         * Sum all turns across a history array.
         * Delegates to CHUtils.sumTurns.
         */
        _sumTurns: function(history) {
            return CHUtils.sumTurns(history);
        },

        /**
         * Compute weighted average turn time across history.
         * Delegates to CHUtils.weightedAvgTime.
         */
        _weightedAvgTime: function(history) {
            return CHUtils.weightedAvgTime(history);
        },

        /**
         * Compute frustration average from history (total_frustration / frustration_turn_count).
         */
        _computeFrustrationAvg: function(history) {
            var totalFrust = 0, totalTurns = 0;
            if (history) {
                history.forEach(function(h) {
                    if (h.total_frustration != null) totalFrust += h.total_frustration;
                    if (h.frustration_turn_count != null) totalTurns += h.frustration_turn_count;
                });
            }
            if (totalTurns === 0) return null;
            return totalFrust / totalTurns;
        },

        /**
         * Compute peak frustration from history (max of all bucket max_frustration values).
         */
        _computePeakFrustration: function(history) {
            var peak = null;
            if (history) {
                history.forEach(function(h) {
                    if (h.max_frustration != null) {
                        peak = peak != null ? Math.max(peak, h.max_frustration) : h.max_frustration;
                    }
                });
            }
            return peak;
        },

        /**
         * Format a frustration average for display (1 decimal place).
         */
        _formatFrustAvg: function(avg) {
            if (avg == null) return '\u2014';
            return avg.toFixed(1);
        },

        loadOverallMetrics: function() {
            _fetchWithRetry('/api/metrics/overall?' + this._apiParams())
                .then(function(data) {
                    var overallEmpty = document.getElementById('overall-empty');
                    var overallMetrics = document.getElementById('overall-metrics');

                    if (!data || !data.history || data.history.length === 0) {
                        overallEmpty.classList.remove('hidden');
                        overallMetrics.classList.add('hidden');
                        ActivityPage._renderChart([]);
                        if (HEADSPACE_ENABLED && !(currentWindow === 'day' && windowOffset === 0)) {
                            ActivityPage._updateFrustrationFromHistory([]);
                        }
                        return;
                    }

                    overallEmpty.classList.add('hidden');
                    overallMetrics.classList.remove('hidden');

                    // Compute window totals from history
                    var totalTurns = ActivityPage._sumTurns(data.history);
                    var rate = ActivityPage._computeRate(totalTurns);
                    var avgTime = ActivityPage._weightedAvgTime(data.history);

                    document.getElementById('overall-total-turns').textContent = totalTurns;
                    document.getElementById('overall-total-turns-label').textContent = 'Total Turns';
                    document.getElementById('overall-turn-rate').textContent = ActivityPage._formatRate(rate);
                    document.getElementById('overall-turn-rate-label').textContent = RATE_LABELS[currentWindow];
                    document.getElementById('overall-avg-time').textContent =
                        avgTime != null ? avgTime.toFixed(1) + 's' : '--';
                    document.getElementById('overall-active-agents').textContent =
                        data.daily_totals ? (data.daily_totals.active_agents || 0) : 0;

                    ActivityPage._renderChart(data.history);

                    if (HEADSPACE_ENABLED && !(currentWindow === 'day' && windowOffset === 0)) {
                        ActivityPage._updateFrustrationFromHistory(data.history);
                    }
                });
        },

        loadProjectMetrics: function() {
            _fetchWithRetry('/api/projects')
                .then(function(projects) {
                    var container = document.getElementById('project-metrics-container');
                    var loading = document.getElementById('projects-loading');
                    var empty = document.getElementById('projects-empty');
                    loading.classList.add('hidden');

                    if (!projects || projects.length === 0) {
                        container.innerHTML = '';
                        empty.classList.remove('hidden');
                        return;
                    }

                    empty.classList.add('hidden');

                    // Update overall active agents from live project data
                    var liveAgentTotal = 0;
                    projects.forEach(function(p) { liveAgentTotal += (p.agent_count || 0); });
                    var overallAgentsEl = document.getElementById('overall-active-agents');
                    if (overallAgentsEl) overallAgentsEl.textContent = liveAgentTotal;

                    var promises = projects.map(function(p) {
                        return _fetchWithRetry('/api/metrics/projects/' + p.id + '?' + ActivityPage._apiParams())
                            .then(function(metrics) {
                                return { project: p, metrics: metrics || { history: [] } };
                            });
                    });

                    // Also fetch agent metrics for each project's agents
                    Promise.all(promises).then(function(results) {
                        var agentPromises = [];
                        results.forEach(function(r) {
                            if ((r.metrics.history && r.metrics.history.length > 0) || (r.project.agent_count > 0)) {
                                agentPromises.push(
                                    _fetchWithRetry('/api/projects/' + r.project.id)
                                        .then(function(detail) {
                                            if (!detail) { r.agents = []; return; }
                                            var activeAgents = (detail.agents || [])
                                                .filter(function(a) { return !a.ended_at; });
                                            var aPromises = activeAgents
                                                .map(function(a) {
                                                    return _fetchWithRetry('/api/metrics/agents/' + a.id + '?' + ActivityPage._apiParams())
                                                        .then(function(metrics) {
                                                            return { agent: a, metrics: metrics || { history: [] } };
                                                        });
                                                });
                                            return Promise.all(aPromises);
                                        })
                                        .then(function(agentData) {
                                            if (agentData) r.agents = agentData;
                                        })
                                );
                            } else {
                                r.agents = [];
                            }
                        });

                        return Promise.all(agentPromises).then(function() {
                            return results;
                        });
                    }).then(function(results) {
                        ActivityPage._renderProjectPanels(results);
                    });
                });
        },

        /**
         * Fill hourly gaps in history. Delegates to CHUtils.fillHourlyGaps.
         */
        _fillHourlyGaps: function(history) {
            return CHUtils.fillHourlyGaps(history);
        },

        /**
         * Aggregate history by day. Delegates to CHUtils.aggregateByDay.
         */
        _aggregateByDay: function(history) {
            return CHUtils.aggregateByDay(history);
        },

        /**
         * Get per-bucket average frustration (total / count).
         * Returns null for buckets with no scored turns.
         */
        _bucketFrustrationAvg: function(h) {
            if (h.total_frustration == null || !h.frustration_turn_count || h.frustration_turn_count === 0) {
                return null;
            }
            return h.total_frustration / h.frustration_turn_count;
        },

        _bucketFrustration: function(h) {
            if (h.max_frustration != null) return h.max_frustration;
            if (h.total_frustration == null || !h.frustration_turn_count || h.frustration_turn_count === 0) {
                return null;
            }
            return h.total_frustration / h.frustration_turn_count;
        },

        _renderChart: function(history) {
            var canvas = document.getElementById('activity-chart');
            var chartEmpty = document.getElementById('chart-empty');

            if (!history || history.length === 0) {
                if (chart) { chart.destroy(); chart = null; }
                canvas.style.display = 'none';
                chartEmpty.classList.remove('hidden');
                return;
            }

            var hasAnyTurns = history.some(function(h) { return h.turn_count > 0; });
            if (!hasAnyTurns) {
                if (chart) { chart.destroy(); chart = null; }
                canvas.style.display = 'none';
                chartEmpty.classList.remove('hidden');
                return;
            }

            var isAggregated = (currentWindow === 'week' || currentWindow === 'month');
            if (isAggregated) {
                history = history.filter(function(h) { return h.turn_count > 0; });
                history = this._aggregateByDay(history);
            } else {
                history = this._fillHourlyGaps(history);
            }

            canvas.style.display = 'block';
            chartEmpty.classList.add('hidden');

            var labels = history.map(function(h) {
                var d = new Date(h.bucket_start);
                if (currentWindow === 'day') {
                    return d.getHours().toString().padStart(2, '0') + ':00';
                } else if (currentWindow === 'week') {
                    return d.toLocaleDateString([], { weekday: 'long' });
                } else {
                    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
                }
            });

            var turnData = history.map(function(h) {
                return h.turn_count > 0 ? h.turn_count : null;
            });

            // Chart frustration line: max frustration per bucket (peak score)
            var frustrationData = history.map(function(h) {
                return ActivityPage._bucketFrustration(h);
            });

            // Threshold-based point colors (using peak value)
            var pointColors = frustrationData.map(function(val) {
                var lvl = _levelFromAvg(val);
                return 'rgba(' + FRUST_COLORS[lvl].rgb + ', 1)';
            });

            var chartHistory = history;

            if (chart) { chart.destroy(); }

            var datasets = [{
                label: 'Turns',
                data: turnData,
                backgroundColor: 'rgba(86, 212, 221, 0.7)',
                borderColor: 'rgba(86, 212, 221, 1)',
                borderWidth: 1,
                borderRadius: 3,
                yAxisID: 'y',
            }, {
                label: 'Frustration',
                type: 'line',
                data: frustrationData,
                borderWidth: 2,
                pointRadius: 3,
                tension: 0.3,
                fill: false,
                spanGaps: false,
                yAxisID: 'y1',
                segment: {
                    borderColor: function(ctx) {
                        return pointColors[ctx.p1DataIndex] || 'rgba(' + FRUST_COLORS.green.rgb + ', 1)';
                    }
                },
                pointBackgroundColor: pointColors,
                pointBorderColor: pointColors,
                borderColor: pointColors[0] || 'rgba(' + FRUST_COLORS.green.rgb + ', 1)',
            }];

            var scales = {
                x: {
                    ticks: { color: 'rgba(255,255,255,0.4)', maxTicksLimit: 12 },
                    grid: { color: 'rgba(255,255,255,0.06)' }
                },
                y: {
                    beginAtZero: true,
                    ticks: { color: 'rgba(255,255,255,0.4)', precision: 0 },
                    grid: { color: 'rgba(255,255,255,0.06)' }
                },
                y1: {
                    position: 'right',
                    beginAtZero: true,
                    min: 0,
                    max: 10,
                    ticks: {
                        color: 'rgba(255, 193, 7, 0.6)',
                        precision: 0,
                        stepSize: 2,
                    },
                    grid: { drawOnChartArea: false }
                }
            };

            chart = new Chart(canvas, {
                type: 'bar',
                data: { labels: labels, datasets: datasets },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: { intersect: false, mode: 'index' },
                    plugins: {
                        tooltip: {
                            titleFont: { size: 16 },
                            bodyFont: { size: 15 },
                            boxWidth: 15,
                            boxHeight: 15,
                            boxPadding: 8,
                            padding: 12,
                            callbacks: {
                                title: function(items) {
                                    if (!items.length) return '';
                                    var idx = items[0].dataIndex;
                                    var h = chartHistory[idx];
                                    var d = new Date(h.bucket_start);
                                    if (isAggregated) {
                                        return d.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' });
                                    }
                                    return d.toLocaleString();
                                },
                                label: function(item) {
                                    if (item.dataset.label === 'Frustration') {
                                        if (item.raw == null) return null;
                                        return 'Frustration Peak: ' + item.raw.toFixed(1);
                                    }
                                    var idx = item.dataIndex;
                                    var h = chartHistory[idx];
                                    var lines = ['Turns: ' + h.turn_count];
                                    if (!isAggregated) {
                                        if (h.avg_turn_time_seconds != null) {
                                            lines.push('Avg time: ' + h.avg_turn_time_seconds.toFixed(1) + 's');
                                        }
                                        if (h.active_agents != null) {
                                            lines.push('Active agents: ' + h.active_agents);
                                        }
                                    }
                                    var avg = ActivityPage._bucketFrustrationAvg(h);
                                    if (avg != null) {
                                        lines.push('Frustration Avg: ' + avg.toFixed(1));
                                    }
                                    return lines;
                                }
                            }
                        },
                        legend: { labels: { color: 'rgba(255,255,255,0.6)' } }
                    },
                    scales: scales
                }
            });
        },

        _renderProjectPanels: function(results) {
            var container = document.getElementById('project-metrics-container');
            var empty = document.getElementById('projects-empty');

            var hasAnyData = results.some(function(r) {
                return (r.metrics.history && r.metrics.history.length > 0) || (r.agents && r.agents.length > 0);
            });

            if (!hasAnyData && results.length > 0) {
                container.innerHTML = '';
                results.forEach(function(r) {
                    container.innerHTML += '<div class="border-b border-border py-4 last:border-0">' +
                        '<h3 class="text-xs font-semibold uppercase tracking-wider mb-2">' +
                        '<a href="/projects/' + CHUtils.escapeHtml(r.project.slug) + '" class="text-cyan hover:text-primary text-glow-cyan transition-colors">' +
                        CHUtils.escapeHtml(r.project.name) + '</a></h3>' +
                        '<p class="text-muted text-sm">No activity data yet.</p></div>';
                });
                empty.classList.add('hidden');
                return;
            }

            container.innerHTML = '';
            empty.classList.add('hidden');

            results.sort(function(a, b) {
                var aHas = (a.metrics.history && a.metrics.history.length > 0) || (a.agents && a.agents.length > 0) ? 1 : 0;
                var bHas = (b.metrics.history && b.metrics.history.length > 0) || (b.agents && b.agents.length > 0) ? 1 : 0;
                return bHas - aHas;
            });

            results.forEach(function(r) {
                var section = document.createElement('div');
                section.className = 'py-4 border-b border-border last:border-0';

                var history = r.metrics.history || [];
                var html = '<h3 class="text-xs font-semibold uppercase tracking-wider mb-3">' +
                    '<a href="/projects/' + CHUtils.escapeHtml(r.project.slug) + '" class="text-cyan hover:text-primary text-glow-cyan transition-colors">' +
                    CHUtils.escapeHtml(r.project.name) + '</a></h3>';

                if (history.length > 0) {
                    var totalTurns = ActivityPage._sumTurns(history);
                    var rate = ActivityPage._computeRate(totalTurns);
                    var avgTime = ActivityPage._weightedAvgTime(history);
                    var projPeak = ActivityPage._computePeakFrustration(history);
                    var projLevel = _levelFromAvg(projPeak);
                    var projColor = projPeak != null ? FRUST_COLORS[projLevel].text : 'text-muted';

                    html += '<div class="grid grid-cols-2 sm:grid-cols-5 gap-3 mb-3">' +
                        '<div class="metric-card-sm">' +
                        '<div class="metric-card-value text-cyan">' + totalTurns + '</div>' +
                        '<div class="metric-card-label">Turns</div></div>' +
                        '<div class="metric-card-sm">' +
                        '<div class="metric-card-value text-cyan">' + ActivityPage._formatRate(rate) + '</div>' +
                        '<div class="metric-card-label">' + RATE_LABELS[currentWindow] + '</div></div>' +
                        '<div class="metric-card-sm">' +
                        '<div class="metric-card-value text-amber">' +
                        (avgTime != null ? avgTime.toFixed(1) + 's' : '--') +
                        '</div><div class="metric-card-label">Avg Time</div></div>' +
                        '<div class="metric-card-sm">' +
                        '<div class="metric-card-value text-green">' + (r.project.agent_count || 0) + '</div>' +
                        '<div class="metric-card-label">Agents</div></div>' +
                        '<div class="metric-card-sm">' +
                        '<div class="metric-card-value ' + projColor + '">' + ActivityPage._formatFrustAvg(projPeak) + '</div>' +
                        '<div class="metric-card-label">Peak Frust.</div></div></div>';
                } else {
                    html += '<p class="text-muted text-sm mb-3">No activity data for this project.</p>';
                }

                // Agent rows (active only, in accordion)
                if (r.agents && r.agents.length > 0) {
                    html += '<details class="activity-agents-accordion">' +
                        '<summary class="activity-agents-toggle">' +
                        '<span class="toggle-arrow">&#9654;</span> Active Agents (' + r.agents.length + ')' +
                        '</summary>';
                    html += '<div class="space-y-2 mt-2">';
                    r.agents.forEach(function(ad) {
                        var agentHistory = ad.metrics.history || [];
                        var agentUuid8 = ad.agent.session_uuid
                            ? ad.agent.session_uuid.substring(0, 8)
                            : '';
                        var agentHeroHtml = agentUuid8
                            ? '<span class="agent-hero">' + CHUtils.escapeHtml(agentUuid8.substring(0, 2)) + '</span><span class="agent-hero-trail">' + CHUtils.escapeHtml(agentUuid8.substring(2)) + '</span>'
                            : 'Agent ' + ad.agent.id;
                        html += '<div class="agent-metric-row">' +
                            '<span class="agent-metric-tag">' + agentHeroHtml + '</span>';
                        if (agentHistory.length > 0) {
                            var agentTurns = ActivityPage._sumTurns(agentHistory);
                            var agentAvg = ActivityPage._weightedAvgTime(agentHistory);
                            var agentPeak = ActivityPage._computePeakFrustration(agentHistory);
                            var agentLevel = _levelFromAvg(agentPeak);
                            var agentFrustColor = agentPeak != null ? FRUST_COLORS[agentLevel].text : 'text-muted';
                            html += '<div class="agent-metric-stats">' +
                                '<span><span class="stat-value">' + agentTurns + '</span><span class="stat-label">turns</span></span>';
                            if (agentAvg != null) {
                                html += '<span><span class="stat-value">' + agentAvg.toFixed(1) + 's</span><span class="stat-label">avg</span></span>';
                            }
                            html += '<span><span class="stat-value ' + agentFrustColor + '">' + ActivityPage._formatFrustAvg(agentPeak) + '</span><span class="stat-label">peak frust</span></span>';
                            html += '</div>';
                        } else {
                            html += '<div class="agent-metric-stats"><span class="stat-label">No data</span></div>';
                        }
                        html += '</div>';
                    });
                    html += '</div></details>';
                }

                section.innerHTML = html;
                container.appendChild(section);
            });
        },

        // ---- Frustration State Widget ----

        _initFrustrationWidget: function() {
            fetch('/api/headspace/current')
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    if (!data.enabled || !data.current) return;
                    ActivityPage._updateWidgetValues(data.current);
                    // Restore live labels
                    ActivityPage._setLabel('frust-peak-today-label', 'Max Today');
                    ActivityPage._setLabel('frust-peak-today-sublabel',
                        ActivityPage._formatPeakTime(data.current.peak_frustration_today_at));
                    ActivityPage._setLabel('frust-immediate-label', 'Immediate');
                    ActivityPage._setLabel('frust-immediate-sublabel', 'Last 10 turns');
                    ActivityPage._setLabel('frust-shortterm-label', 'Short-term');
                    ActivityPage._setLabel('frust-shortterm-sublabel', 'Last 30 min');
                    ActivityPage._setLabel('frust-session-label', 'Session');
                    ActivityPage._setLabel('frust-session-sublabel', 'Last ' + (data.current.session_window_minutes || 180) + ' min');
                })
                .catch(function(err) {
                    console.error('Failed to load headspace state:', err);
                });
        },

        _updateFrustrationFromHistory: function(history) {
            if (!history || history.length === 0) {
                // No data — show dashes for all
                this._setIndicator('frust-peak-today-value', null);
                this._setIndicator('frust-immediate-value', null);
                this._setIndicator('frust-shortterm-value', null);
                this._setIndicator('frust-session-value', null);
                this._setLabel('frust-peak-today-label', 'Peak');
                this._setLabel('frust-peak-today-sublabel', 'No data');
                this._setLabel('frust-immediate-label', 'Average');
                this._setLabel('frust-immediate-sublabel', 'No data');
                this._setLabel('frust-shortterm-label', 'Short-term');
                this._setLabel('frust-shortterm-sublabel', 'N/A (historical)');
                this._setLabel('frust-session-label', 'Session');
                this._setLabel('frust-session-sublabel', 'N/A (historical)');
                return;
            }

            // Peak: max of all bucket max_frustration values, tracking timestamp
            var peak = null;
            var peakAt = null;
            history.forEach(function(h) {
                if (h.max_frustration != null) {
                    if (peak == null || h.max_frustration > peak) {
                        peak = h.max_frustration;
                        peakAt = h.max_frustration_at;
                    }
                }
            });

            // Average: total_frustration / frustration_turn_count across all buckets
            var avg = this._computeFrustrationAvg(history);

            // Update values
            this._setIndicator('frust-peak-today-value', peak);
            this._setIndicator('frust-immediate-value', avg);
            this._setIndicator('frust-shortterm-value', null);
            this._setIndicator('frust-session-value', null);

            // Update labels for historical view
            this._setLabel('frust-peak-today-label', 'Peak');
            this._setLabel('frust-peak-today-sublabel', this._formatPeakTime(peakAt));
            this._setLabel('frust-immediate-label', 'Average');
            this._setLabel('frust-immediate-sublabel', 'Period average');
            this._setLabel('frust-shortterm-label', 'Short-term');
            this._setLabel('frust-shortterm-sublabel', 'N/A (historical)');
            this._setLabel('frust-session-label', 'Session');
            this._setLabel('frust-session-sublabel', 'N/A (historical)');
        },

        _setLabel: function(elementId, text) {
            var el = document.getElementById(elementId);
            if (el) el.textContent = text;
        },

        /**
         * Format an ISO timestamp into "HH:MM, X ago" for the peak frustration sublabel.
         * For dates beyond today, prefixes with short day name: "Wed 14:15, 3 days ago".
         * Returns "Peak score" as fallback when no timestamp is available.
         */
        _formatPeakTime: function(isoString) {
            if (!isoString) return 'Peak score';
            var d = new Date(isoString);
            if (isNaN(d.getTime())) return 'Peak score';

            var time = String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0');

            // Check if the date is today
            var now = new Date();
            var isToday = d.getFullYear() === now.getFullYear() &&
                          d.getMonth() === now.getMonth() &&
                          d.getDate() === now.getDate();

            // Prefix with short day name if not today
            var dayNames = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
            var prefix = isToday ? '' : dayNames[d.getDay()] + ' ';

            var diffMs = Date.now() - d.getTime();
            var diffMin = Math.floor(diffMs / 60000);
            var ago;
            if (diffMin < 1) {
                ago = 'just now';
            } else if (diffMin < 60) {
                ago = diffMin + (diffMin === 1 ? ' minute ago' : ' minutes ago');
            } else if (diffMin < 1440) {
                var hours = Math.round(diffMin / 60);
                ago = hours + (hours === 1 ? ' hour ago' : ' hours ago');
            } else {
                var days = Math.floor(diffMin / 1440);
                if (days === 1) {
                    ago = 'yesterday';
                } else if (days < 7) {
                    ago = days + ' days ago';
                } else if (days < 28) {
                    var weeks = Math.round(days / 7);
                    ago = weeks + (weeks === 1 ? ' week ago' : ' weeks ago');
                } else {
                    var months = Math.round(days / 30);
                    ago = months + (months === 1 ? ' month ago' : ' months ago');
                }
            }
            return prefix + time + ', ' + ago;
        },

        /**
         * Debounced refresh of all activity data.
         * Coalesces rapid SSE events into a single re-fetch.
         */
        _debouncedRefresh: function() {
            if (_refreshDebounce) return;
            _refreshDebounce = setTimeout(function() {
                _refreshDebounce = null;
                // Only refresh if viewing the current period (not historical)
                if (windowOffset === 0) {
                    ActivityPage.loadOverallMetrics();
                    ActivityPage.loadProjectMetrics();
                }
            }, 3000);
        },

        _initSSE: function() {
            // Use the shared SSE connection from header-sse.js
            var client = window.headerSSEClient;
            if (!client) {
                console.warn('Shared SSE client not available (headerSSEClient)');
                return;
            }

            // Real-time activity updates: debounce-refresh on new turns or aggregation
            client.on('turn_detected', function() {
                ActivityPage._debouncedRefresh();
            });
            client.on('turn_created', function() {
                ActivityPage._debouncedRefresh();
            });
            client.on('activity_update', function() {
                ActivityPage._debouncedRefresh();
            });

            if (HEADSPACE_ENABLED) {
                client.on('headspace_update', function(data) {
                    // Only update frustration widget from SSE when viewing today
                    if (currentWindow === 'day' && windowOffset === 0) {
                        ActivityPage._updateWidgetValues(data);
                    }
                });
            }
        },

        _updateWidgetValues: function(state) {
            this._setIndicator('frust-immediate-value', state.frustration_rolling_10);
            this._setIndicator('frust-shortterm-value', state.frustration_rolling_30min);
            this._setIndicator('frust-session-value', state.frustration_rolling_3hr);
            this._setIndicator('frust-peak-today-value', state.peak_frustration_today);
            this._setLabel('frust-peak-today-sublabel',
                this._formatPeakTime(state.peak_frustration_today_at));
        },

        _setIndicator: function(elementId, value) {
            var el = document.getElementById(elementId);
            if (!el) return;
            if (value == null) {
                el.textContent = '\u2014';
                el.className = 'frustration-indicator-value text-muted';
            } else {
                el.textContent = value.toFixed(1);
                var level = _levelFromAvg(value);
                el.className = 'frustration-indicator-value ' + FRUST_COLORS[level].text;
            }
        },

        // ---- Utilities ----

        _frustrationLevel: function(totalFrustration, turnCount) {
            if (!totalFrustration || !turnCount || turnCount === 0) return 'green';
            var avg = totalFrustration / turnCount;
            return _levelFromAvg(avg);
        },

        /**
         * Sum frustration history. Delegates to CHUtils.sumFrustrationHistory.
         */
        _sumFrustrationHistory: function(history) {
            return CHUtils.sumFrustrationHistory(history);
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        ActivityPage.init();
    });

    global.ActivityPage = ActivityPage;
})(window);
