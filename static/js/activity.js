(function(global) {
    'use strict';

    let chart = null;
    let currentWindow = 'day';
    let windowOffset = 0;  // 0 = current period, -1 = previous, etc.

    // Frustration thresholds from config (injected by template)
    var THRESHOLDS = global.FRUSTRATION_THRESHOLDS || { yellow: 4, red: 7 };

    // Color constants for frustration states
    var FRUST_COLORS = {
        green:  { text: 'text-green',  rgb: '76, 175, 80',  hex: '#4caf50' },
        yellow: { text: 'text-amber',  rgb: '255, 193, 7',  hex: '#ffc107' },
        red:    { text: 'text-red',    rgb: '255, 85, 85',   hex: '#ff5555' }
    };

    // Rate label by window
    var RATE_LABELS = { day: 'Turns / Hour', week: 'Turns / Day', month: 'Turns / Day' };

    const ActivityPage = {
        init: function() {
            this.loadOverallMetrics();
            this.loadProjectMetrics();
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
         * Day: turns/hour, Week/Month: turns/day.
         */
        _computeRate: function(totalTurns) {
            if (currentWindow === 'day') {
                return totalTurns / 24;
            }
            // week/month: turns per day
            var days = currentWindow === 'week' ? 7 : 30;
            return totalTurns / days;
        },

        _formatRate: function(rate) {
            if (rate === 0) return '0';
            if (rate >= 10) return Math.round(rate).toString();
            return rate.toFixed(1);
        },

        /**
         * Sum all turns across a history array.
         */
        _sumTurns: function(history) {
            var total = 0;
            if (history) {
                history.forEach(function(h) { total += (h.turn_count || 0); });
            }
            return total;
        },

        /**
         * Compute weighted average turn time across history.
         */
        _weightedAvgTime: function(history) {
            var totalTime = 0, totalPairs = 0;
            if (history) {
                history.forEach(function(h) {
                    if (h.avg_turn_time_seconds != null && h.turn_count >= 2) {
                        var pairs = h.turn_count - 1;
                        totalTime += h.avg_turn_time_seconds * pairs;
                        totalPairs += pairs;
                    }
                });
            }
            return totalPairs > 0 ? totalTime / totalPairs : null;
        },

        loadOverallMetrics: function() {
            fetch('/api/metrics/overall?' + this._apiParams())
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    var overallEmpty = document.getElementById('overall-empty');
                    var overallMetrics = document.getElementById('overall-metrics');

                    if (!data.history || data.history.length === 0) {
                        overallEmpty.classList.remove('hidden');
                        overallMetrics.classList.add('hidden');
                        ActivityPage._renderChart([]);
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
                        data.current ? (data.current.active_agents || 0) : 0;

                    // Frustration with threshold-based color
                    var frustStats = ActivityPage._sumFrustrationHistory(data.history);
                    var frustEl = document.getElementById('overall-frustration');
                    frustEl.textContent = frustStats.total > 0 ? frustStats.total : 0;
                    var level = ActivityPage._frustrationLevel(frustStats.total, frustStats.turns);
                    frustEl.className = 'metric-card-value ' + FRUST_COLORS[level].text;

                    ActivityPage._renderChart(data.history);
                })
                .catch(function(err) {
                    console.error('Failed to load overall metrics:', err);
                });
        },

        loadProjectMetrics: function() {
            // First fetch list of projects, then fetch metrics for each
            fetch('/api/projects')
                .then(function(res) { return res.json(); })
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

                    var promises = projects.map(function(p) {
                        return fetch('/api/metrics/projects/' + p.id + '?' + ActivityPage._apiParams())
                            .then(function(res) { return res.json(); })
                            .then(function(metrics) {
                                return { project: p, metrics: metrics };
                            });
                    });

                    // Also fetch agent metrics for each project's agents
                    Promise.all(promises).then(function(results) {
                        var agentPromises = [];
                        results.forEach(function(r) {
                            if (r.metrics.history && r.metrics.history.length > 0) {
                                agentPromises.push(
                                    fetch('/api/projects/' + r.project.id)
                                        .then(function(res) { return res.json(); })
                                        .then(function(detail) {
                                            var activeAgents = (detail.agents || [])
                                                .filter(function(a) { return !a.ended_at; });
                                            var aPromises = activeAgents
                                                .map(function(a) {
                                                    return fetch('/api/metrics/agents/' + a.id + '?' + ActivityPage._apiParams())
                                                        .then(function(res) { return res.json(); })
                                                        .then(function(metrics) {
                                                            return { agent: a, metrics: metrics };
                                                        });
                                                });
                                            return Promise.all(aPromises);
                                        })
                                        .then(function(agentData) {
                                            // Filter out agents with no metrics in the selected period
                                            r.agents = agentData.filter(function(ad) {
                                                return ad.metrics.history && ad.metrics.history.length > 0;
                                            });
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
                })
                .catch(function(err) {
                    console.error('Failed to load project metrics:', err);
                    document.getElementById('projects-loading').classList.add('hidden');
                });
        },

        _fillHourlyGaps: function(history) {
            if (history.length < 2) return history;
            var bucketMap = {};
            history.forEach(function(h) {
                var d = new Date(h.bucket_start);
                var key = d.getFullYear() + '-' +
                    String(d.getMonth() + 1).padStart(2, '0') + '-' +
                    String(d.getDate()).padStart(2, '0') + 'T' +
                    String(d.getHours()).padStart(2, '0');
                bucketMap[key] = h;
            });
            var first = new Date(history[0].bucket_start);
            var last = new Date(history[history.length - 1].bucket_start);
            first.setMinutes(0, 0, 0);
            last.setMinutes(0, 0, 0);
            var result = [];
            var cursor = new Date(first);
            while (cursor <= last) {
                var key = cursor.getFullYear() + '-' +
                    String(cursor.getMonth() + 1).padStart(2, '0') + '-' +
                    String(cursor.getDate()).padStart(2, '0') + 'T' +
                    String(cursor.getHours()).padStart(2, '0');
                if (bucketMap[key]) {
                    result.push(bucketMap[key]);
                } else {
                    result.push({
                        bucket_start: cursor.toISOString(),
                        turn_count: 0,
                        avg_turn_time_seconds: null,
                        active_agents: null,
                        total_frustration: null,
                        frustration_turn_count: null
                    });
                }
                cursor = new Date(cursor.getTime() + 3600000);
            }
            return result;
        },

        _aggregateByDay: function(history) {
            var dayMap = {};
            history.forEach(function(h) {
                var d = new Date(h.bucket_start);
                var key = d.toLocaleDateString('en-CA');
                if (!dayMap[key]) {
                    dayMap[key] = { date: d, turn_count: 0, total_frustration: 0, frustration_turn_count: 0, bucket_start: h.bucket_start };
                }
                dayMap[key].turn_count += h.turn_count;
                if (h.total_frustration != null) dayMap[key].total_frustration += h.total_frustration;
                if (h.frustration_turn_count != null) dayMap[key].frustration_turn_count += h.frustration_turn_count;
            });
            return Object.keys(dayMap).sort().map(function(k) {
                var entry = dayMap[k];
                if (entry.total_frustration === 0) entry.total_frustration = null;
                if (entry.frustration_turn_count === 0) entry.frustration_turn_count = null;
                return entry;
            });
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

            var frustrationData = history.map(function(h) {
                return h.total_frustration != null ? h.total_frustration : null;
            });

            var pointColors = history.map(function(h) {
                var lvl = ActivityPage._frustrationLevel(h.total_frustration, h.frustration_turn_count);
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

            var overallFrust = ActivityPage._sumFrustrationHistory(history);
            var overallLevel = ActivityPage._frustrationLevel(overallFrust.total, overallFrust.turns);
            var axisColor = FRUST_COLORS[overallLevel].rgb;

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
                    ticks: { color: 'rgba(' + axisColor + ', 0.6)', precision: 0 },
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
                                        return item.raw != null ? 'Frustration: ' + item.raw : null;
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
                                    if (h.total_frustration != null) {
                                        lines.push('Frustration: ' + h.total_frustration);
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
                        '<h3 class="text-xs font-semibold text-secondary uppercase tracking-wider mb-2">' +
                        ActivityPage._escapeHtml(r.project.name) + '</h3>' +
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
                var html = '<h3 class="text-xs font-semibold text-secondary uppercase tracking-wider mb-3">' +
                    ActivityPage._escapeHtml(r.project.name) + '</h3>';

                if (history.length > 0) {
                    var totalTurns = ActivityPage._sumTurns(history);
                    var rate = ActivityPage._computeRate(totalTurns);
                    var avgTime = ActivityPage._weightedAvgTime(history);
                    var projFrust = ActivityPage._sumFrustrationHistory(history);
                    var projLevel = ActivityPage._frustrationLevel(projFrust.total, projFrust.turns);
                    var projColor = FRUST_COLORS[projLevel].text;

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
                        '<div class="metric-card-value text-green">' + (r.metrics.current ? (r.metrics.current.active_agents || 0) : 0) + '</div>' +
                        '<div class="metric-card-label">Agents</div></div>' +
                        '<div class="metric-card-sm">' +
                        '<div class="metric-card-value ' + projColor + '">' + projFrust.total + '</div>' +
                        '<div class="metric-card-label">Frustration</div></div></div>';
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
                        var agentLabel = ad.agent.session_uuid
                            ? ad.agent.session_uuid.substring(0, 8)
                            : 'Agent ' + ad.agent.id;
                        html += '<div class="agent-metric-row">' +
                            '<span class="agent-metric-tag">' + ActivityPage._escapeHtml(agentLabel) + '</span>';
                        if (agentHistory.length > 0) {
                            var agentTurns = ActivityPage._sumTurns(agentHistory);
                            var agentAvg = ActivityPage._weightedAvgTime(agentHistory);
                            var agentFrust = ActivityPage._sumFrustrationHistory(agentHistory);
                            var agentLevel = ActivityPage._frustrationLevel(agentFrust.total, agentFrust.turns);
                            var agentFrustColor = FRUST_COLORS[agentLevel].text;
                            html += '<div class="agent-metric-stats">' +
                                '<span><span class="stat-value">' + agentTurns + '</span><span class="stat-label">turns</span></span>';
                            if (agentAvg != null) {
                                html += '<span><span class="stat-value">' + agentAvg.toFixed(1) + 's</span><span class="stat-label">avg</span></span>';
                            }
                            if (agentFrust.total > 0) {
                                html += '<span><span class="stat-value ' + agentFrustColor + '">' + agentFrust.total + '</span><span class="stat-label">frust</span></span>';
                            }
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

        _frustrationLevel: function(totalFrustration, turnCount) {
            if (!totalFrustration || !turnCount || turnCount === 0) return 'green';
            var avg = totalFrustration / turnCount;
            if (avg >= THRESHOLDS.red) return 'red';
            if (avg >= THRESHOLDS.yellow) return 'yellow';
            return 'green';
        },

        _sumFrustrationHistory: function(history) {
            var total = 0, turns = 0;
            if (history) {
                history.forEach(function(h) {
                    if (h.total_frustration != null) total += h.total_frustration;
                    if (h.frustration_turn_count != null) turns += h.frustration_turn_count;
                });
            }
            return { total: total, turns: turns };
        },

        _escapeHtml: function(str) {
            var div = document.createElement('div');
            div.appendChild(document.createTextNode(str || ''));
            return div.innerHTML;
        }
    };

    document.addEventListener('DOMContentLoaded', function() {
        ActivityPage.init();
    });

    global.ActivityPage = ActivityPage;
})(window);
