(function(global) {
    'use strict';

    let chart = null;
    let currentWindow = 'day';

    // Frustration thresholds from config (injected by template)
    var THRESHOLDS = global.FRUSTRATION_THRESHOLDS || { yellow: 4, red: 7 };

    // Color constants for frustration states
    var FRUST_COLORS = {
        green:  { text: 'text-green',  rgb: '76, 175, 80',  hex: '#4caf50' },
        yellow: { text: 'text-amber',  rgb: '255, 193, 7',  hex: '#ffc107' },
        red:    { text: 'text-red',    rgb: '255, 85, 85',   hex: '#ff5555' }
    };

    const ActivityPage = {
        init: function() {
            this.loadOverallMetrics();
            this.loadProjectMetrics();
        },

        setWindow: function(window) {
            currentWindow = window;
            // Update toggle button styles
            document.querySelectorAll('#window-toggles button').forEach(function(btn) {
                if (btn.dataset.window === window) {
                    btn.className = 'px-3 py-1 text-sm rounded border border-cyan/30 bg-cyan/20 text-cyan font-medium';
                } else {
                    btn.className = 'px-3 py-1 text-sm rounded border border-border text-secondary hover:text-primary hover:border-cyan/30 transition-colors';
                }
            });
            this.loadOverallMetrics();
            this.loadProjectMetrics();
        },

        loadOverallMetrics: function() {
            fetch('/api/metrics/overall?window=' + currentWindow)
                .then(function(res) { return res.json(); })
                .then(function(data) {
                    var overallEmpty = document.getElementById('overall-empty');
                    var overallMetrics = document.getElementById('overall-metrics');

                    if (!data.current) {
                        overallEmpty.classList.remove('hidden');
                        overallMetrics.classList.add('hidden');
                        ActivityPage._renderChart([]);
                        return;
                    }

                    overallEmpty.classList.add('hidden');
                    overallMetrics.classList.remove('hidden');

                    document.getElementById('overall-turn-rate').textContent =
                        data.current.turn_count || 0;
                    document.getElementById('overall-avg-time').textContent =
                        data.current.avg_turn_time_seconds != null
                            ? data.current.avg_turn_time_seconds.toFixed(1) + 's'
                            : '--';
                    document.getElementById('overall-active-agents').textContent =
                        data.current.active_agents || 0;

                    // Sum total frustration across all history entries for window total
                    var frustStats = ActivityPage._sumFrustrationHistory(data.history);
                    var frustEl = document.getElementById('overall-frustration');
                    frustEl.textContent = frustStats.total > 0 ? frustStats.total : 0;
                    // Apply threshold-based color
                    var level = ActivityPage._frustrationLevel(frustStats.total, frustStats.turns);
                    var colors = FRUST_COLORS[level];
                    frustEl.className = 'metric-card-value ' + colors.text;

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
                        return fetch('/api/metrics/projects/' + p.id + '?window=' + currentWindow)
                            .then(function(res) { return res.json(); })
                            .then(function(metrics) {
                                return { project: p, metrics: metrics };
                            });
                    });

                    // Also fetch agent metrics for each project's agents
                    Promise.all(promises).then(function(results) {
                        var agentPromises = [];
                        results.forEach(function(r) {
                            var agents = r.project.agents || [];
                            // Use the project's active agent list from the project API
                            if (r.project.agent_count > 0) {
                                agentPromises.push(
                                    fetch('/api/projects/' + r.project.id)
                                        .then(function(res) { return res.json(); })
                                        .then(function(detail) {
                                            var aPromises = (detail.agents || [])
                                                .filter(function(a) { return !a.ended_at; })
                                                .map(function(a) {
                                                    return fetch('/api/metrics/agents/' + a.id + '?window=' + currentWindow)
                                                        .then(function(res) { return res.json(); })
                                                        .then(function(metrics) {
                                                            return { agent: a, metrics: metrics };
                                                        });
                                                });
                                            return Promise.all(aPromises);
                                        })
                                        .then(function(agentData) {
                                            r.agents = agentData;
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
            // Round to hour boundaries
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
                cursor = new Date(cursor.getTime() + 3600000); // +1 hour
            }
            return result;
        },

        _aggregateByDay: function(history) {
            var dayMap = {};
            history.forEach(function(h) {
                var d = new Date(h.bucket_start);
                var key = d.toLocaleDateString('en-CA'); // YYYY-MM-DD
                if (!dayMap[key]) {
                    dayMap[key] = { date: d, turn_count: 0, total_frustration: 0, frustration_turn_count: 0, bucket_start: h.bucket_start };
                }
                dayMap[key].turn_count += h.turn_count;
                if (h.total_frustration != null) {
                    dayMap[key].total_frustration += h.total_frustration;
                }
                if (h.frustration_turn_count != null) {
                    dayMap[key].frustration_turn_count += h.frustration_turn_count;
                }
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

            // Check if any turns exist at all
            var hasAnyTurns = history.some(function(h) { return h.turn_count > 0; });
            if (!hasAnyTurns) {
                if (chart) { chart.destroy(); chart = null; }
                canvas.style.display = 'none';
                chartEmpty.classList.remove('hidden');
                return;
            }

            // Aggregate by day for week/month views, fill hourly gaps for day view
            var isAggregated = (currentWindow === 'week' || currentWindow === 'month');
            if (isAggregated) {
                // Filter zeros before aggregation for week/month (no timeline continuity needed)
                history = history.filter(function(h) { return h.turn_count > 0; });
                history = this._aggregateByDay(history);
            } else {
                // Day view: fill in missing hours so x-axis is continuous
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

            // For day view, use null for zero-turn hours so bars don't render but axis stays continuous
            var turnData = history.map(function(h) {
                return h.turn_count > 0 ? h.turn_count : null;
            });

            // Frustration data for line overlay (always present)
            var frustrationData = history.map(function(h) {
                return h.total_frustration != null ? h.total_frustration : null;
            });

            // Compute per-point frustration level color for chart segments
            var pointColors = history.map(function(h) {
                var lvl = ActivityPage._frustrationLevel(h.total_frustration, h.frustration_turn_count);
                return 'rgba(' + FRUST_COLORS[lvl].rgb + ', 1)';
            });

            // Capture reference for tooltip closure
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
                // Per-segment coloring based on frustration level
                segment: {
                    borderColor: function(ctx) {
                        // Color segment by the destination point's frustration level
                        return pointColors[ctx.p1DataIndex] || 'rgba(' + FRUST_COLORS.green.rgb + ', 1)';
                    }
                },
                pointBackgroundColor: pointColors,
                pointBorderColor: pointColors,
                borderColor: pointColors[0] || 'rgba(' + FRUST_COLORS.green.rgb + ', 1)',
            }];

            // Compute overall frustration level for y1 axis tick color
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
                data: {
                    labels: labels,
                    datasets: datasets
                },
                options: {
                    responsive: true,
                    maintainAspectRatio: false,
                    interaction: {
                        intersect: false,
                        mode: 'index'
                    },
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
                        legend: {
                            labels: { color: 'rgba(255,255,255,0.6)' }
                        }
                    },
                    scales: scales
                }
            });
        },

        _renderProjectPanels: function(results) {
            var container = document.getElementById('project-metrics-container');
            var empty = document.getElementById('projects-empty');

            var hasAnyData = results.some(function(r) {
                return r.metrics.current != null || (r.agents && r.agents.length > 0);
            });

            if (!hasAnyData && results.length > 0) {
                // Projects exist but no metrics
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

            // Sort: projects with data first, no-data projects at the end
            results.sort(function(a, b) {
                var aHasData = a.metrics.current != null || (a.agents && a.agents.length > 0) ? 1 : 0;
                var bHasData = b.metrics.current != null || (b.agents && b.agents.length > 0) ? 1 : 0;
                return bHasData - aHasData;
            });

            results.forEach(function(r) {
                var section = document.createElement('div');
                section.className = 'py-4 border-b border-border last:border-0';

                var current = r.metrics.current;
                var html = '<h3 class="text-xs font-semibold text-secondary uppercase tracking-wider mb-3">' +
                    ActivityPage._escapeHtml(r.project.name) + '</h3>';

                if (current) {
                    var projFrust = ActivityPage._sumFrustrationHistory(r.metrics.history);
                    var projLevel = ActivityPage._frustrationLevel(projFrust.total, projFrust.turns);
                    var projColor = FRUST_COLORS[projLevel].text;
                    html += '<div class="grid grid-cols-4 gap-3 mb-3">' +
                        '<div class="metric-card-sm">' +
                        '<div class="metric-card-value text-cyan">' + (current.turn_count || 0) + '</div>' +
                        '<div class="metric-card-label">Turns</div></div>' +
                        '<div class="metric-card-sm">' +
                        '<div class="metric-card-value text-amber">' +
                        (current.avg_turn_time_seconds != null ? current.avg_turn_time_seconds.toFixed(1) + 's' : '--') +
                        '</div><div class="metric-card-label">Avg Time</div></div>' +
                        '<div class="metric-card-sm">' +
                        '<div class="metric-card-value text-green">' + (current.active_agents || 0) + '</div>' +
                        '<div class="metric-card-label">Agents</div></div>' +
                        '<div class="metric-card-sm">' +
                        '<div class="metric-card-value ' + projColor + '">' + projFrust.total + '</div>' +
                        '<div class="metric-card-label">Frustration</div></div></div>';
                } else {
                    html += '<p class="text-muted text-sm mb-3">No activity data for this project.</p>';
                }

                // Agent rows
                if (r.agents && r.agents.length > 0) {
                    html += '<div class="space-y-2">';
                    r.agents.forEach(function(ad) {
                        var ac = ad.metrics.current;
                        var agentLabel = ad.agent.session_uuid
                            ? ad.agent.session_uuid.substring(0, 8)
                            : 'Agent ' + ad.agent.id;
                        html += '<div class="agent-metric-row">' +
                            '<span class="agent-metric-tag">' + ActivityPage._escapeHtml(agentLabel) + '</span>';
                        if (ac) {
                            var agentFrust = ActivityPage._sumFrustrationHistory(ad.metrics.history);
                            var agentLevel = ActivityPage._frustrationLevel(agentFrust.total, agentFrust.turns);
                            var agentFrustColor = FRUST_COLORS[agentLevel].text;
                            html += '<div class="agent-metric-stats">' +
                                '<span><span class="stat-value">' + ac.turn_count + '</span><span class="stat-label">turns</span></span>';
                            if (ac.avg_turn_time_seconds != null) {
                                html += '<span><span class="stat-value">' + ac.avg_turn_time_seconds.toFixed(1) + 's</span><span class="stat-label">avg</span></span>';
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
                    html += '</div>';
                }

                section.innerHTML = html;
                container.appendChild(section);
            });
        },

        /**
         * Compute frustration color based on average frustration per USER turn.
         * Uses PRD thresholds: green (< yellow), yellow (>= yellow, < red), red (>= red).
         * @param {number} totalFrustration - sum of frustration scores
         * @param {number} turnCount - number of USER turns with frustration scores
         * @returns {string} 'green', 'yellow', or 'red'
         */
        _frustrationLevel: function(totalFrustration, turnCount) {
            if (!totalFrustration || !turnCount || turnCount === 0) return 'green';
            var avg = totalFrustration / turnCount;
            if (avg >= THRESHOLDS.red) return 'red';
            if (avg >= THRESHOLDS.yellow) return 'yellow';
            return 'green';
        },

        /**
         * Compute frustration stats from a history array.
         * Sums total_frustration and frustration_turn_count across all entries.
         */
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

    // Initialize on DOM ready
    document.addEventListener('DOMContentLoaded', function() {
        ActivityPage.init();
    });

    global.ActivityPage = ActivityPage;
})(window);
