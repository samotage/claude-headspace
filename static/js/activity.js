(function(global) {
    'use strict';

    let chart = null;
    let currentWindow = 'day';

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

        _renderChart: function(history) {
            var canvas = document.getElementById('activity-chart');
            var chartEmpty = document.getElementById('chart-empty');

            if (!history || history.length === 0) {
                if (chart) { chart.destroy(); chart = null; }
                canvas.style.display = 'none';
                chartEmpty.classList.remove('hidden');
                return;
            }

            canvas.style.display = 'block';
            chartEmpty.classList.add('hidden');

            var labels = history.map(function(h) {
                var d = new Date(h.bucket_start);
                if (currentWindow === 'day') {
                    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                } else if (currentWindow === 'week') {
                    return d.toLocaleDateString([], { weekday: 'short', hour: '2-digit' });
                } else {
                    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
                }
            });

            var turnData = history.map(function(h) { return h.turn_count; });

            if (chart) { chart.destroy(); }

            chart = new Chart(canvas, {
                type: 'line',
                data: {
                    labels: labels,
                    datasets: [{
                        label: 'Turns',
                        data: turnData,
                        borderColor: 'rgba(86, 212, 221, 1)',
                        backgroundColor: 'rgba(86, 212, 221, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.3,
                        pointRadius: 3,
                        pointHoverRadius: 6,
                    }]
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
                                    var h = history[idx];
                                    var d = new Date(h.bucket_start);
                                    return d.toLocaleString();
                                },
                                label: function(item) {
                                    var idx = item.dataIndex;
                                    var h = history[idx];
                                    var lines = ['Turns: ' + h.turn_count];
                                    if (h.avg_turn_time_seconds != null) {
                                        lines.push('Avg time: ' + h.avg_turn_time_seconds.toFixed(1) + 's');
                                    }
                                    if (h.active_agents != null) {
                                        lines.push('Active agents: ' + h.active_agents);
                                    }
                                    return lines;
                                }
                            }
                        },
                        legend: {
                            labels: { color: 'rgba(255,255,255,0.6)' }
                        }
                    },
                    scales: {
                        x: {
                            ticks: { color: 'rgba(255,255,255,0.4)', maxTicksLimit: 12 },
                            grid: { color: 'rgba(255,255,255,0.06)' }
                        },
                        y: {
                            beginAtZero: true,
                            ticks: { color: 'rgba(255,255,255,0.4)', precision: 0 },
                            grid: { color: 'rgba(255,255,255,0.06)' }
                        }
                    }
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
                        '<h3 class="text-sm font-semibold text-primary mb-2">' +
                        ActivityPage._escapeHtml(r.project.name) + '</h3>' +
                        '<p class="text-muted text-sm">No activity data yet.</p></div>';
                });
                empty.classList.add('hidden');
                return;
            }

            container.innerHTML = '';
            empty.classList.add('hidden');

            results.forEach(function(r) {
                var section = document.createElement('div');
                section.className = 'border-b border-border py-4 last:border-0';

                var current = r.metrics.current;
                var html = '<h3 class="text-sm font-semibold text-primary mb-3">' +
                    ActivityPage._escapeHtml(r.project.name) + '</h3>';

                if (current) {
                    html += '<div class="grid grid-cols-3 gap-4 mb-3">' +
                        '<div class="text-center">' +
                        '<div class="text-lg font-bold text-cyan">' + (current.turn_count || 0) + '</div>' +
                        '<div class="text-xs text-muted">Turns</div></div>' +
                        '<div class="text-center">' +
                        '<div class="text-lg font-bold text-cyan">' +
                        (current.avg_turn_time_seconds != null ? current.avg_turn_time_seconds.toFixed(1) + 's' : '--') +
                        '</div><div class="text-xs text-muted">Avg Time</div></div>' +
                        '<div class="text-center">' +
                        '<div class="text-lg font-bold text-cyan">' + (current.active_agents || 0) + '</div>' +
                        '<div class="text-xs text-muted">Agents</div></div></div>';
                } else {
                    html += '<p class="text-muted text-sm mb-3">No activity data for this project.</p>';
                }

                // Agent rows
                if (r.agents && r.agents.length > 0) {
                    html += '<div class="ml-4 space-y-2">';
                    r.agents.forEach(function(ad) {
                        var ac = ad.metrics.current;
                        var agentLabel = ad.agent.session_uuid
                            ? ad.agent.session_uuid.substring(0, 8)
                            : 'Agent ' + ad.agent.id;
                        html += '<div class="flex items-center justify-between text-sm py-1">' +
                            '<span class="text-secondary font-mono">' + ActivityPage._escapeHtml(agentLabel) + '</span>' +
                            '<span class="text-muted">';
                        if (ac) {
                            html += ac.turn_count + ' turns';
                            if (ac.avg_turn_time_seconds != null) {
                                html += ' | ' + ac.avg_turn_time_seconds.toFixed(1) + 's avg';
                            }
                        } else {
                            html += 'No data';
                        }
                        html += '</span></div>';
                    });
                    html += '</div>';
                }

                section.innerHTML = html;
                container.appendChild(section);
            });
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
