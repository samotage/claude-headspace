/**
 * Project Show page client for Claude Headspace.
 *
 * Loads project data, waypoint, brain reboot, and progress summary.
 * Handles control actions: edit, delete, pause/resume, regenerate, export.
 * Accordion object tree: Agents -> Tasks -> Turns with lazy loading.
 * Activity metrics with day/week/month toggle and Chart.js visualization.
 * Archive history and inference usage summary.
 */

(function(global) {
    'use strict';

    var projectId = null;
    var projectSlug = null;
    var projectData = null;

    // Accordion state
    var agentsExpanded = false;
    var expandedAgents = {};   // agentId -> true
    var expandedTasks = {};    // taskId -> true

    // Client-side cache
    var cache = {
        agents: null,          // agents list from projectData
        agentsPagination: null, // pagination metadata
        agentTasks: {},        // agentId -> tasks array
        taskTurns: {}          // taskId -> turns array
    };

    // SSE debounce
    var sseDebounceTimer = null;
    var ssePendingUpdates = {};

    // Activity metrics state
    var metricsWindow = 'week';
    var metricsOffset = 0;
    var metricsChart = null;

    // Frustration thresholds
    var THRESHOLDS = global.FRUSTRATION_THRESHOLDS || { yellow: 4, red: 7 };

    var ProjectShow = {
        init: function() {
            var main = document.querySelector('main[data-project-id]');
            if (!main) return;

            projectId = main.getAttribute('data-project-id');
            projectSlug = main.getAttribute('data-project-slug');

            this._loadWaypoint();
            this._loadBrainReboot();
            this._loadProgressSummary();
            this._loadProjectData();
            this._loadArchives();
            this._loadInferenceSummary();
            this._loadActivityMetrics();
            this._initSSE();
            this._initFormModal();
        },

        _initFormModal: function() {
            // Override the form submission to use ProjectShow handler
            var form = document.getElementById('project-form');
            if (form) {
                form.onsubmit = function(e) {
                    e.preventDefault();
                    ProjectShow.submitProject();
                };
            }
        },

        // --- Data Loading ---

        _loadProjectData: async function() {
            try {
                var showEnded = projectData && projectData._showEnded;
                var url = '/api/projects/' + projectId;
                if (showEnded) url += '?include_ended=true';
                var response = await fetch(url);
                if (!response.ok) return;
                projectData = await response.json();
                projectData._showEnded = showEnded;
                this._updateAgentWarning();
                this._updateAgentsBadge();
                cache.agents = projectData.agents || [];
                cache.agentsPagination = projectData.agents_pagination || null;
                // Auto-expand agents accordion if there are agents
                if (cache.agents.length > 0 && !agentsExpanded) {
                    this.toggleAgentsAccordion();
                }
            } catch (e) {
                console.error('ProjectShow: Failed to load project data', e);
            }
        },

        _updateAgentWarning: function() {
            if (!projectData) return;
            var agents = projectData.agents || [];
            var activeCount = agents.filter(function(a) { return !a.ended_at; }).length;
            var warning = document.getElementById('delete-agent-warning');
            if (warning) {
                if (activeCount > 0) {
                    warning.textContent = 'This will also delete ' + activeCount + ' active agent(s) associated with this project.';
                } else {
                    warning.textContent = '';
                }
            }
        },

        _updateAgentsBadge: function() {
            var badge = document.getElementById('agents-count-badge');
            if (badge && projectData) {
                var activeCount = projectData.active_agent_count || 0;
                var total = (projectData.agents_pagination && projectData.agents_pagination.total) || (projectData.agents || []).length;
                if (projectData._showEnded && total !== activeCount) {
                    badge.textContent = '(' + activeCount + ' active / ' + total + ' total)';
                } else {
                    badge.textContent = '(' + activeCount + ')';
                }
            }
        },

        _loadWaypoint: async function() {
            var container = document.getElementById('waypoint-content');
            if (!container) return;

            try {
                var response = await fetch('/api/projects/' + projectId + '/waypoint');
                if (!response.ok) {
                    container.innerHTML = '<p class="text-muted italic">No waypoint set. Set a waypoint to track your project\'s roadmap.</p>';
                    return;
                }
                var data = await response.json();
                var content = data.content || data.waypoint || '';
                // Strip leading "# Waypoint" heading since the section already has one
                content = content.replace(/^\s*#\s+Waypoint\s*\n/, '');
                if (content.trim()) {
                    container.innerHTML = this._renderMarkdown(content);
                } else {
                    container.innerHTML = '<p class="text-muted italic">No waypoint set. Set a waypoint to track your project\'s roadmap.</p>';
                }
            } catch (e) {
                container.innerHTML = '<p class="text-muted italic">Failed to load waypoint.</p>';
            }
        },

        _loadBrainReboot: async function() {
            var container = document.getElementById('brain-reboot-content');
            var timestamp = document.getElementById('brain-reboot-timestamp');
            if (!container) return;

            try {
                var response = await fetch('/api/projects/' + projectId + '/brain-reboot');
                if (!response.ok) {
                    container.innerHTML = '<p class="text-muted italic">No brain reboot generated yet.</p>';
                    if (timestamp) timestamp.textContent = '';
                    var regenBtn = document.getElementById('btn-regen-brain-reboot');
                    if (regenBtn) regenBtn.textContent = 'Generate';
                    return;
                }
                var data = await response.json();
                var content = data.content || data.brain_reboot || '';
                if (content.trim()) {
                    container.innerHTML = this._renderMarkdown(content);
                    if (timestamp && data.generated_at) {
                        timestamp.textContent = 'Generated ' + this._timeAgo(data.generated_at);
                    }
                } else {
                    container.innerHTML = '<p class="text-muted italic">No brain reboot generated yet.</p>';
                    if (timestamp) timestamp.textContent = '';
                    var regenBtn2 = document.getElementById('btn-regen-brain-reboot');
                    if (regenBtn2) regenBtn2.textContent = 'Generate';
                }
            } catch (e) {
                container.innerHTML = '<p class="text-muted italic">Failed to load brain reboot.</p>';
            }
        },

        _loadProgressSummary: async function() {
            var container = document.getElementById('progress-summary-content');
            if (!container) return;

            try {
                var response = await fetch('/api/projects/' + projectId + '/progress-summary');
                if (!response.ok) {
                    container.innerHTML = '<p class="text-muted italic">No progress summary generated yet.</p>';
                    var regenBtn = document.getElementById('btn-regen-progress');
                    if (regenBtn) regenBtn.textContent = 'Generate';
                    return;
                }
                var data = await response.json();
                var content = data.content || data.summary || data.progress_summary || '';
                if (content.trim()) {
                    container.innerHTML = this._renderMarkdown(content);
                } else {
                    container.innerHTML = '<p class="text-muted italic">No progress summary generated yet.</p>';
                    var regenBtn2 = document.getElementById('btn-regen-progress');
                    if (regenBtn2) regenBtn2.textContent = 'Generate';
                }
            } catch (e) {
                container.innerHTML = '<p class="text-muted italic">Failed to load progress summary.</p>';
            }
        },

        // --- Accordion Object Tree ---

        toggleAgentsAccordion: function() {
            var body = document.getElementById('agents-accordion-body');
            var arrow = document.getElementById('agents-accordion-arrow');
            if (!body) return;

            if (agentsExpanded) {
                // Collapse
                body.style.display = 'none';
                if (arrow) arrow.style.transform = 'rotate(0deg)';
                agentsExpanded = false;
                // Collapse all children
                expandedAgents = {};
                expandedTasks = {};
            } else {
                // Expand
                body.style.display = 'block';
                if (arrow) arrow.style.transform = 'rotate(90deg)';
                agentsExpanded = true;
                // Fetch agents if not cached
                if (cache.agents) {
                    this._renderAgentsList(cache.agents);
                } else {
                    this._fetchAndRenderAgents();
                }
            }
        },

        toggleShowEnded: function() {
            var showEnded = projectData && projectData._showEnded;
            var btn = document.getElementById('btn-show-ended');
            if (showEnded) {
                // Switch back to active-only
                if (btn) {
                    btn.textContent = 'Show ended';
                    btn.className = 'px-2 py-1 text-xs rounded border border-border text-muted hover:text-secondary hover:border-border-bright transition-colors';
                }
                if (projectData) projectData._showEnded = false;
            } else {
                if (btn) {
                    btn.textContent = 'Hide ended';
                    btn.className = 'px-2 py-1 text-xs rounded border border-cyan/30 text-cyan hover:text-primary transition-colors';
                }
                if (projectData) projectData._showEnded = true;
            }
            cache.agents = null;
            this._fetchAndRenderAgents(1);
        },

        _fetchAndRenderAgents: async function(page) {
            var container = document.getElementById('agents-list');
            container.innerHTML = '<p class="text-muted italic text-sm"><span class="inline-block animate-pulse">Loading agents...</span></p>';

            page = page || 1;
            var showEnded = projectData && projectData._showEnded;
            var url = '/api/projects/' + projectId + '?agents_page=' + page;
            if (showEnded) url += '&include_ended=true';
            try {
                var response = await fetch(url);
                if (!response.ok) throw new Error('Failed to fetch');
                var data = await response.json();
                data._showEnded = showEnded;
                cache.agents = data.agents || [];
                cache.agentsPagination = data.agents_pagination || null;
                projectData = data;
                this._updateAgentsBadge();
                this._renderAgentsList(cache.agents);
            } catch (e) {
                container.innerHTML = '<div class="text-red text-sm">Failed to load agents. <button type="button" onclick="ProjectShow._fetchAndRenderAgents()" class="text-cyan hover:underline ml-1">Retry</button></div>';
            }
        },

        _renderAgentsList: function(agents) {
            var container = document.getElementById('agents-list');

            // Sort: active (non-ended) first, then by last_seen_at descending
            if (agents && agents.length > 1) {
                agents = agents.slice().sort(function(a, b) {
                    var aEnded = !!a.ended_at;
                    var bEnded = !!b.ended_at;
                    if (aEnded !== bEnded) return aEnded ? 1 : -1;
                    var aTime = a.last_seen_at ? new Date(a.last_seen_at).getTime() : 0;
                    var bTime = b.last_seen_at ? new Date(b.last_seen_at).getTime() : 0;
                    return bTime - aTime;
                });
            }

            if (!agents || agents.length === 0) {
                var pagination = cache.agentsPagination;
                if (pagination && pagination.page > 1) {
                    container.innerHTML = '<p class="text-muted italic text-sm">No agents on this page.</p>';
                } else {
                    container.innerHTML = '<p class="text-muted italic text-sm">No agents.</p>';
                }
                return;
            }

            var html = '';
            agents.forEach(function(agent) {
                var isEnded = !!agent.ended_at;
                var stateValue = agent.state || 'idle';
                if (isEnded) stateValue = 'ended';
                var uuid8 = agent.session_uuid ? agent.session_uuid.substring(0, 8) : '';
                var agentId = agent.id;

                var rowClass = isEnded ? 'opacity-50' : '';
                var stateClass = ProjectShow._stateColorClass(stateValue);

                var agentHeroHtml = uuid8
                    ? '<span class="agent-hero">' + CHUtils.escapeHtml(uuid8.substring(0, 2)) + '</span><span class="agent-hero-trail">' + CHUtils.escapeHtml(uuid8.substring(2)) + '</span>'
                    : 'Agent ' + agent.id;

                html += '<div class="accordion-agent-row ' + rowClass + '">';
                html += '<div class="agent-metric-row cursor-pointer hover:border-border-bright transition-colors" onclick="ProjectShow.toggleAgentTasks(' + agentId + ')">';

                // Arrow + state badge
                html += '<span class="accordion-arrow text-muted text-xs transition-transform duration-150" id="agent-arrow-' + agentId + '" style="flex-shrink:0">&#9654;</span>';
                html += '<span class="text-xs font-medium px-1.5 py-0.5 rounded ' + stateClass + '" style="flex-shrink:0">' + CHUtils.escapeHtml(stateValue.toUpperCase()) + '</span>';

                // UUID hero/trail
                html += '<span class="agent-metric-tag">' + agentHeroHtml + '</span>';

                // Metric stats
                html += '<div class="agent-metric-stats">';
                html += '<span><span class="stat-value">' + (agent.turn_count || 0) + '</span><span class="stat-label">turns</span></span>';
                if (agent.avg_turn_time != null) {
                    html += '<span><span class="stat-value">' + agent.avg_turn_time.toFixed(1) + 's</span><span class="stat-label">avg</span></span>';
                }
                if (agent.frustration_avg != null) {
                    var frustLevel = agent.frustration_avg >= THRESHOLDS.red ? 'text-red' : (agent.frustration_avg >= THRESHOLDS.yellow ? 'text-amber' : 'text-green');
                    html += '<span><span class="stat-value ' + frustLevel + '">' + agent.frustration_avg.toFixed(1) + '</span><span class="stat-label">frust</span></span>';
                }
                html += '</div>';

                // Last seen / ended badge
                if (isEnded) {
                    html += '<span class="text-xs px-1.5 py-0.5 rounded bg-surface border border-border text-muted" style="flex-shrink:0">Ended</span>';
                    if (agent.started_at && agent.ended_at) {
                        html += '<span class="text-xs text-muted" style="flex-shrink:0">' + ProjectShow._formatDuration(agent.started_at, agent.ended_at) + '</span>';
                    }
                } else if (agent.last_seen_at) {
                    html += '<span class="text-xs text-muted" style="flex-shrink:0">' + ProjectShow._timeAgo(agent.last_seen_at) + '</span>';
                }

                html += '</div>';
                html += '<div id="agent-tasks-' + agentId + '" class="accordion-body ml-6 mt-1" style="display: none;"></div>';
                html += '</div>';
            });

            // Pagination controls
            var pagination = cache.agentsPagination;
            if (pagination && pagination.total_pages > 1) {
                html += '<div class="flex items-center justify-between mt-3 pt-3 border-t border-border">';
                html += '<span class="text-xs text-muted">Page ' + pagination.page + ' of ' + pagination.total_pages + ' (' + pagination.total + ' agents)</span>';
                html += '<div class="flex gap-2">';
                if (pagination.page > 1) {
                    html += '<button type="button" onclick="ProjectShow._fetchAndRenderAgents(' + (pagination.page - 1) + ')" class="px-3 py-1 text-xs rounded border border-border text-secondary hover:text-primary hover:border-cyan/30 transition-colors">&laquo; Prev</button>';
                }
                if (pagination.page < pagination.total_pages) {
                    html += '<button type="button" onclick="ProjectShow._fetchAndRenderAgents(' + (pagination.page + 1) + ')" class="px-3 py-1 text-xs rounded border border-border text-secondary hover:text-primary hover:border-cyan/30 transition-colors">Next &raquo;</button>';
                }
                html += '</div>';
                html += '</div>';
            }

            container.innerHTML = html;
        },

        toggleAgentTasks: async function(agentId) {
            var body = document.getElementById('agent-tasks-' + agentId);
            var arrow = document.getElementById('agent-arrow-' + agentId);
            if (!body) return;

            if (expandedAgents[agentId]) {
                // Collapse
                body.style.display = 'none';
                if (arrow) arrow.style.transform = 'rotate(0deg)';
                delete expandedAgents[agentId];
                // Collapse children
                var taskKeys = Object.keys(expandedTasks);
                taskKeys.forEach(function(key) {
                    if (expandedTasks[key] === agentId) {
                        delete expandedTasks[key];
                    }
                });
            } else {
                // Expand
                body.style.display = 'block';
                if (arrow) arrow.style.transform = 'rotate(90deg)';
                expandedAgents[agentId] = true;

                if (cache.agentTasks[agentId]) {
                    this._renderTasksList(agentId, cache.agentTasks[agentId]);
                } else {
                    this._fetchAndRenderTasks(agentId);
                }
            }
        },

        _fetchAndRenderTasks: async function(agentId) {
            var container = document.getElementById('agent-tasks-' + agentId);
            container.innerHTML = '<p class="text-muted italic text-sm"><span class="inline-block animate-pulse">Loading tasks...</span></p>';

            try {
                var response = await fetch('/api/agents/' + agentId + '/tasks');
                if (!response.ok) throw new Error('Failed to fetch');
                var tasks = await response.json();
                cache.agentTasks[agentId] = tasks;
                this._renderTasksList(agentId, tasks);
            } catch (e) {
                container.innerHTML = '<div class="text-red text-sm">Failed to load tasks. <button type="button" onclick="ProjectShow._fetchAndRenderTasks(' + agentId + ')" class="text-cyan hover:underline ml-1">Retry</button></div>';
            }
        },

        _renderTasksList: function(agentId, tasks) {
            var container = document.getElementById('agent-tasks-' + agentId);
            if (!tasks || tasks.length === 0) {
                container.innerHTML = '<p class="text-muted italic text-sm">No tasks.</p>';
                return;
            }

            var html = '<div class="space-y-2">';
            tasks.forEach(function(task) {
                var stateValue = task.state || 'idle';
                var stateClass = ProjectShow._stateColorClass(stateValue);
                var instruction = task.instruction || '';
                var summary = task.completion_summary || '';
                var displayText = instruction.length > 60 ? instruction.substring(0, 60) + '...' : instruction;
                var taskId = task.id;
                var isComplete = stateValue.toLowerCase() === 'complete';
                var borderColor = isComplete ? 'border-green/20' : 'border-border';

                html += '<div class="accordion-task-row">';
                // Header row (clickable, expands turns)
                html += '<div class="flex items-center gap-2 px-3 py-2 bg-elevated rounded-t-lg border ' + borderColor + ' cursor-pointer hover:border-border-bright transition-colors" onclick="ProjectShow.toggleTaskTurns(' + taskId + ', ' + agentId + ')">';
                html += '<span class="accordion-arrow text-muted text-xs transition-transform duration-150" id="task-arrow-' + taskId + '">&#9654;</span>';
                html += '<span class="text-xs font-medium px-1.5 py-0.5 rounded ' + stateClass + '">' + CHUtils.escapeHtml(stateValue.toUpperCase()) + '</span>';
                if (displayText) {
                    html += '<span class="text-sm text-primary font-medium truncate flex-1">' + CHUtils.escapeHtml(displayText) + '</span>';
                }
                html += '</div>';

                // Card-editor body
                html += '<div class="card-editor border-t-0 rounded-t-none border ' + borderColor + ' border-t-0 rounded-b-lg">';
                // Line 01: Full instruction
                html += '<div class="card-line"><span class="line-num">01</span><div class="line-content">';
                html += '<p class="task-instruction text-primary text-sm font-medium">' + CHUtils.escapeHtml(instruction || 'No instruction') + '</p>';
                html += '</div></div>';
                // Line 02: Completion summary or in-progress indicator
                html += '<div class="card-line"><span class="line-num">02</span><div class="line-content">';
                if (isComplete && summary) {
                    html += '<p class="task-summary text-green text-sm italic">' + CHUtils.escapeHtml(summary) + '</p>';
                } else if (isComplete) {
                    html += '<p class="text-green text-sm italic">Completed</p>';
                } else {
                    html += '<p class="text-amber text-sm italic">In progress...</p>';
                }
                html += '</div></div>';
                // Line 03: Turn count + duration (completed only)
                if (isComplete) {
                    html += '<div class="card-line"><span class="line-num">03</span><div class="line-content flex items-baseline justify-between gap-2">';
                    var turnLabel = (task.turn_count || 0) + ' turn' + ((task.turn_count || 0) !== 1 ? 's' : '');
                    if (task.started_at && task.completed_at) {
                        turnLabel += ' \u00B7 ' + ProjectShow._formatDuration(task.started_at, task.completed_at);
                    }
                    html += '<span class="text-muted text-xs">' + turnLabel + '</span>';
                    html += '<button type="button" class="full-text-btn text-muted hover:text-cyan text-xs whitespace-nowrap transition-colors" onclick="ProjectShow.toggleFullOutput(' + taskId + ')" title="View full output">View full</button>';
                    html += '</div></div>';
                }
                // Full output expandable section (hidden by default)
                html += '<div id="task-full-output-' + taskId + '" class="card-line" style="display:none;"><span class="line-num">&nbsp;</span><div class="line-content"><pre class="full-text-modal-text" style="max-height:300px;overflow-y:auto;"></pre></div></div>';
                html += '</div>';

                html += '<div id="task-turns-' + taskId + '" class="accordion-body ml-6 mt-1" style="display: none;"></div>';
                html += '</div>';
            });
            html += '</div>';

            container.innerHTML = html;
        },

        toggleFullOutput: async function(taskId) {
            var container = document.getElementById('task-full-output-' + taskId);
            if (!container) return;

            if (container.style.display !== 'none') {
                container.style.display = 'none';
                return;
            }

            container.style.display = '';
            var pre = container.querySelector('pre');
            if (!pre) return;

            // Check cache
            if (cache._fullText && cache._fullText[taskId]) {
                pre.textContent = cache._fullText[taskId].full_output || 'No full output available';
                return;
            }

            pre.textContent = 'Loading...';
            try {
                var response = await fetch('/api/tasks/' + taskId + '/full-text');
                if (!response.ok) throw new Error('Failed to fetch');
                var data = await response.json();
                if (!cache._fullText) cache._fullText = {};
                cache._fullText[taskId] = data;
                pre.textContent = data.full_output || 'No full output available';
            } catch (e) {
                pre.textContent = 'Failed to load full output.';
            }
        },

        toggleTaskTurns: async function(taskId, agentId) {
            var body = document.getElementById('task-turns-' + taskId);
            var arrow = document.getElementById('task-arrow-' + taskId);
            if (!body) return;

            if (expandedTasks[taskId]) {
                // Collapse
                body.style.display = 'none';
                if (arrow) arrow.style.transform = 'rotate(0deg)';
                delete expandedTasks[taskId];
            } else {
                // Expand
                body.style.display = 'block';
                if (arrow) arrow.style.transform = 'rotate(90deg)';
                expandedTasks[taskId] = agentId;

                if (cache.taskTurns[taskId]) {
                    this._renderTurnsList(taskId, cache.taskTurns[taskId]);
                } else {
                    this._fetchAndRenderTurns(taskId);
                }
            }
        },

        _fetchAndRenderTurns: async function(taskId) {
            var container = document.getElementById('task-turns-' + taskId);
            container.innerHTML = '<p class="text-muted italic text-sm"><span class="inline-block animate-pulse">Loading turns...</span></p>';

            try {
                var response = await fetch('/api/tasks/' + taskId + '/turns');
                if (!response.ok) throw new Error('Failed to fetch');
                var turns = await response.json();
                cache.taskTurns[taskId] = turns;
                this._renderTurnsList(taskId, turns);
            } catch (e) {
                container.innerHTML = '<div class="text-red text-sm">Failed to load turns. <button type="button" onclick="ProjectShow._fetchAndRenderTurns(' + taskId + ')" class="text-cyan hover:underline ml-1">Retry</button></div>';
            }
        },

        _renderTurnsList: function(taskId, turns) {
            var container = document.getElementById('task-turns-' + taskId);
            if (!turns || turns.length === 0) {
                container.innerHTML = '<p class="text-muted italic text-sm">No turns.</p>';
                return;
            }

            var html = '<div class="space-y-1">';
            turns.forEach(function(turn) {
                var actorValue = turn.actor || 'agent';
                var intentValue = turn.intent || '';
                var summary = turn.summary || '';
                var frustration = turn.frustration_score;

                // Frustration highlighting
                var rowClass = 'p-2 rounded border border-border text-sm';
                if (frustration != null && frustration >= THRESHOLDS.red) {
                    rowClass += ' bg-red/10 border-red/30';
                } else if (frustration != null && frustration >= THRESHOLDS.yellow) {
                    rowClass += ' bg-amber/10 border-amber/30';
                } else {
                    rowClass += ' bg-void';
                }

                var actorClass = actorValue === 'user' ? 'text-amber' : 'text-cyan';

                html += '<div class="' + rowClass + '">';
                html += '<div class="flex items-center gap-2">';
                html += '<span class="text-xs font-medium px-1.5 py-0.5 rounded ' + actorClass + ' bg-surface">' + CHUtils.escapeHtml(actorValue.toUpperCase()) + '</span>';
                if (intentValue) {
                    html += '<span class="text-xs text-muted">' + CHUtils.escapeHtml(intentValue) + '</span>';
                }
                if (frustration != null) {
                    var frustClass = frustration >= THRESHOLDS.red ? 'text-red' : (frustration >= THRESHOLDS.yellow ? 'text-amber' : 'text-green');
                    html += '<span class="text-xs ' + frustClass + '">F:' + frustration + '</span>';
                }
                if (turn.created_at) {
                    html += '<span class="text-xs text-muted ml-auto">' + ProjectShow._formatDate(turn.created_at) + '</span>';
                }
                html += '</div>';
                if (summary) {
                    html += '<p class="text-xs text-secondary mt-1">' + CHUtils.escapeHtml(summary) + '</p>';
                }
                html += '</div>';
            });
            html += '</div>';

            container.innerHTML = html;
        },

        // --- Activity Metrics ---

        setMetricsWindow: function(w) {
            metricsWindow = w;
            metricsOffset = 0;
            document.querySelectorAll('#ps-window-toggles button').forEach(function(btn) {
                if (btn.dataset.window === w) {
                    btn.className = 'px-3 py-1 text-sm rounded border border-cyan/30 bg-cyan/20 text-cyan font-medium';
                } else {
                    btn.className = 'px-3 py-1 text-sm rounded border border-border text-secondary hover:text-primary hover:border-cyan/30 transition-colors';
                }
            });
            this._updateMetricsNav();
            this._loadActivityMetrics();
        },

        metricsGoBack: function() {
            metricsOffset--;
            this._updateMetricsNav();
            this._loadActivityMetrics();
        },

        metricsGoForward: function() {
            if (metricsOffset < 0) {
                metricsOffset++;
                this._updateMetricsNav();
                this._loadActivityMetrics();
            }
        },

        _metricsPeriodStart: function(offset) {
            var now = new Date();
            if (metricsWindow === 'day') {
                return new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset);
            } else if (metricsWindow === 'week') {
                var dow = now.getDay();
                var diffToMon = (dow === 0 ? 6 : dow - 1);
                var thisMon = new Date(now.getFullYear(), now.getMonth(), now.getDate() - diffToMon);
                return new Date(thisMon.getFullYear(), thisMon.getMonth(), thisMon.getDate() + (offset * 7));
            } else {
                return new Date(now.getFullYear(), now.getMonth() + offset, 1);
            }
        },

        _metricsPeriodTitle: function() {
            var start = this._metricsPeriodStart(metricsOffset);
            if (metricsWindow === 'day') {
                if (metricsOffset === 0) return 'Today';
                if (metricsOffset === -1) return 'Yesterday';
                return start.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short' });
            } else if (metricsWindow === 'week') {
                var end = new Date(start);
                end.setDate(end.getDate() + 6);
                if (metricsOffset === 0) return 'This Week';
                return start.toLocaleDateString([], { day: 'numeric', month: 'short' }) +
                    ' \u2013 ' + end.toLocaleDateString([], { day: 'numeric', month: 'short' });
            } else {
                if (metricsOffset === 0) return 'This Month';
                return start.toLocaleDateString([], { month: 'long', year: 'numeric' });
            }
        },

        _updateMetricsNav: function() {
            var title = document.getElementById('ps-period-title');
            if (title) title.textContent = this._metricsPeriodTitle();
            var fwd = document.getElementById('ps-nav-forward');
            if (fwd) {
                if (metricsOffset >= 0) {
                    fwd.disabled = true;
                    fwd.className = 'w-7 h-7 flex items-center justify-center rounded border border-border text-muted cursor-not-allowed text-sm';
                } else {
                    fwd.disabled = false;
                    fwd.className = 'w-7 h-7 flex items-center justify-center rounded border border-border text-secondary hover:text-primary hover:border-cyan/30 transition-colors text-sm';
                }
            }
        },

        _metricsApiParams: function() {
            var since = this._metricsPeriodStart(metricsOffset).toISOString();
            var until = this._metricsPeriodStart(metricsOffset + 1).toISOString();
            return 'window=' + metricsWindow +
                '&since=' + encodeURIComponent(since) +
                '&until=' + encodeURIComponent(until);
        },

        _loadActivityMetrics: async function() {
            try {
                var response = await fetch('/api/metrics/projects/' + projectId + '?' + this._metricsApiParams());
                if (!response.ok) return;
                var data = await response.json();
                var history = data.history || [];

                // Update summary cards
                var totalTurns = this._sumTurns(history);
                var avgTime = this._weightedAvgTime(history);
                var activeAgents = projectData ? (projectData.active_agent_count || 0) : 0;
                var frustStats = this._sumFrustrationHistory(history);

                var turnEl = document.getElementById('ps-turn-count');
                if (turnEl) turnEl.textContent = totalTurns;

                var avgEl = document.getElementById('ps-avg-time');
                if (avgEl) avgEl.textContent = avgTime != null ? avgTime.toFixed(1) + 's' : '--';

                var agentsEl = document.getElementById('ps-active-agents');
                if (agentsEl) agentsEl.textContent = activeAgents;

                var frustEl = document.getElementById('ps-frustration-count');
                if (frustEl) {
                    frustEl.textContent = frustStats.turns > 0 ? frustStats.turns : 0;
                    var level = this._frustrationLevel(frustStats.total, frustStats.turns);
                    var colorMap = { green: 'text-green', yellow: 'text-amber', red: 'text-red' };
                    frustEl.className = 'metric-card-value ' + (colorMap[level] || 'text-muted');
                }

                this._renderMetricsChart(history);
            } catch (e) {
                console.error('ProjectShow: Failed to load activity metrics', e);
            }
        },

        _sumTurns: function(history) {
            return CHUtils.sumTurns(history);
        },

        _weightedAvgTime: function(history) {
            return CHUtils.weightedAvgTime(history);
        },

        _sumFrustrationHistory: function(history) {
            return CHUtils.sumFrustrationHistory(history);
        },

        _frustrationLevel: function(totalFrustration, turnCount) {
            if (!totalFrustration || !turnCount || turnCount === 0) return 'green';
            var avg = totalFrustration / turnCount;
            if (avg >= THRESHOLDS.red) return 'red';
            if (avg >= THRESHOLDS.yellow) return 'yellow';
            return 'green';
        },

        _aggregateByDay: function(history) {
            return CHUtils.aggregateByDay(history);
        },

        _fillHourlyGaps: function(history) {
            return CHUtils.fillHourlyGaps(history);
        },

        _renderMetricsChart: function(history) {
            var canvas = document.getElementById('ps-activity-chart');
            var chartEmpty = document.getElementById('ps-chart-empty');
            if (!canvas) return;

            if (!history || history.length === 0 || !history.some(function(h) { return h.turn_count > 0; })) {
                if (metricsChart) { metricsChart.destroy(); metricsChart = null; }
                canvas.style.display = 'none';
                if (chartEmpty) chartEmpty.classList.remove('hidden');
                return;
            }

            var isAggregated = (metricsWindow === 'week' || metricsWindow === 'month');
            if (isAggregated) {
                history = history.filter(function(h) { return h.turn_count > 0; });
                history = this._aggregateByDay(history);
            } else {
                history = this._fillHourlyGaps(history);
            }

            canvas.style.display = 'block';
            if (chartEmpty) chartEmpty.classList.add('hidden');

            var labels = history.map(function(h) {
                var d = new Date(h.bucket_start);
                if (metricsWindow === 'day') {
                    return d.getHours().toString().padStart(2, '0') + ':00';
                } else if (metricsWindow === 'week') {
                    return d.toLocaleDateString([], { weekday: 'long' });
                } else {
                    return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
                }
            });

            var turnData = history.map(function(h) { return h.turn_count > 0 ? h.turn_count : null; });
            // Chart frustration line: max frustration per bucket (peak score)
            var frustrationData = history.map(function(h) {
                if (h.max_frustration != null) return h.max_frustration;
                // Fallback for historical data without max tracked
                if (h.total_frustration != null && h.frustration_turn_count && h.frustration_turn_count > 0) {
                    return h.total_frustration / h.frustration_turn_count;
                }
                return null;
            });

            var FRUST_COLORS = {
                green: { rgb: '76, 175, 80' },
                yellow: { rgb: '255, 193, 7' },
                red: { rgb: '255, 85, 85' }
            };

            var pointColors = frustrationData.map(function(val) {
                if (val == null) return 'rgba(' + FRUST_COLORS.green.rgb + ', 1)';
                var lvl = val >= THRESHOLDS.red ? 'red' : (val >= THRESHOLDS.yellow ? 'yellow' : 'green');
                return 'rgba(' + FRUST_COLORS[lvl].rgb + ', 1)';
            });

            if (metricsChart) metricsChart.destroy();

            var chartHistory = history;

            metricsChart = new Chart(canvas, {
                type: 'bar',
                data: {
                    labels: labels,
                    datasets: [{
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
                    }]
                },
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
                                        return item.raw != null ? 'Frustration Peak: ' + item.raw : null;
                                    }
                                    var idx = item.dataIndex;
                                    var h = chartHistory[idx];
                                    var lines = ['Turns: ' + h.turn_count];
                                    if (h.max_frustration != null) {
                                        lines.push('Frustration Peak: ' + h.max_frustration);
                                    } else if (h.total_frustration != null) {
                                        lines.push('Frustration: ' + h.total_frustration);
                                    }
                                    return lines;
                                }
                            }
                        },
                        legend: { labels: { color: 'rgba(255,255,255,0.6)' } }
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
                    }
                }
            });
        },

        // --- Archive History ---

        _loadArchives: async function() {
            var container = document.getElementById('archive-list');
            if (!container) return;

            try {
                var response = await fetch('/api/projects/' + projectId + '/archives');
                if (!response.ok) {
                    container.innerHTML = '<p class="text-muted italic text-sm">No archives available.</p>';
                    return;
                }
                var data = await response.json();
                // Flatten grouped archives dict into flat array
                var archivesByType = data.archives || {};
                var archives = [];
                if (Array.isArray(archivesByType)) {
                    // Handle if backend ever returns flat array
                    archives = archivesByType;
                } else {
                    Object.keys(archivesByType).forEach(function(artifactType) {
                        (archivesByType[artifactType] || []).forEach(function(item) {
                            archives.push({
                                artifact: artifactType,
                                filename: item.filename,
                                timestamp: item.timestamp
                            });
                        });
                    });
                }
                // Sort by timestamp descending
                archives.sort(function(a, b) {
                    return (b.timestamp || '').localeCompare(a.timestamp || '');
                });
                if (archives.length === 0) {
                    container.innerHTML = '<p class="text-muted italic text-sm">No archived artifacts yet.</p>';
                    return;
                }

                var html = '<div class="space-y-2">';
                archives.forEach(function(archive) {
                    html += '<div class="flex items-center gap-3 p-3 bg-surface rounded border border-border">';
                    html += '<span class="text-xs font-medium px-1.5 py-0.5 rounded bg-cyan/10 text-cyan">' + CHUtils.escapeHtml(archive.artifact || archive.type || 'artifact') + '</span>';
                    html += '<span class="text-sm text-secondary flex-1">' + CHUtils.escapeHtml(archive.timestamp || '') + '</span>';
                    if (archive.artifact && archive.timestamp) {
                        html += '<a href="/api/projects/' + projectId + '/archives/' +
                            encodeURIComponent(archive.artifact) + '/' +
                            encodeURIComponent(archive.timestamp) +
                            '" target="_blank" class="text-xs text-cyan hover:underline">View</a>';
                    }
                    html += '</div>';
                });
                html += '</div>';

                container.innerHTML = html;
            } catch (e) {
                container.innerHTML = '<p class="text-muted italic text-sm">Failed to load archives.</p>';
            }
        },

        // --- Inference Usage ---

        _loadInferenceSummary: async function() {
            try {
                var response = await fetch('/api/projects/' + projectId + '/inference-summary');
                if (!response.ok) return;
                var data = await response.json();

                var callsEl = document.getElementById('inf-total-calls');
                if (callsEl) callsEl.textContent = data.total_calls || 0;

                var tokensEl = document.getElementById('inf-total-tokens');
                if (tokensEl) tokensEl.textContent = this._formatNumber((data.total_input_tokens || 0) + (data.total_output_tokens || 0));

                var inputEl = document.getElementById('inf-input-tokens');
                if (inputEl) inputEl.textContent = this._formatNumber(data.total_input_tokens || 0);

                var costEl = document.getElementById('inf-total-cost');
                if (costEl) costEl.textContent = '$' + (data.total_cost || 0).toFixed(4);
            } catch (e) {
                console.error('ProjectShow: Failed to load inference summary', e);
            }
        },

        // --- Control Actions ---

        openEditModal: function() {
            document.getElementById('project-form-title').textContent = 'Edit Project';
            document.getElementById('project-form-submit').textContent = 'Update Project';
            document.getElementById('project-form-id').value = projectId;

            var errEl = document.getElementById('project-form-error');
            if (errEl) { errEl.textContent = ''; errEl.classList.add('hidden'); }

            // Populate from server
            fetch('/api/projects/' + projectId)
                .then(function(r) { return r.json(); })
                .then(function(p) {
                    document.getElementById('project-form-name').value = p.name || '';
                    document.getElementById('project-form-path').value = p.path || '';
                    document.getElementById('project-form-github').value = p.github_repo || '';
                    document.getElementById('project-form-description').value = p.description || '';
                    document.getElementById('project-form-modal').classList.remove('hidden');
                    document.getElementById('project-form-name').focus();
                })
                .catch(function(err) { console.warn('ProjectShow: Failed to load project for edit', err); });
        },

        closeFormModal: function() {
            document.getElementById('project-form-modal').classList.add('hidden');
        },

        submitProject: async function() {
            var payload = {
                name: document.getElementById('project-form-name').value.trim(),
                path: document.getElementById('project-form-path').value.trim(),
                github_repo: document.getElementById('project-form-github').value.trim() || null,
                description: document.getElementById('project-form-description').value.trim() || null
            };

            if (!payload.name || !payload.path) {
                var errEl = document.getElementById('project-form-error');
                if (errEl) {
                    errEl.textContent = 'Name and Path are required.';
                    errEl.classList.remove('hidden');
                }
                return;
            }

            try {
                var response = await CHUtils.apiFetch('/api/projects/' + projectId, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                var data = await response.json();

                if (!response.ok) {
                    var errEl2 = document.getElementById('project-form-error');
                    if (errEl2) {
                        errEl2.textContent = data.error || 'Failed to save project.';
                        errEl2.classList.remove('hidden');
                    }
                    return;
                }

                document.getElementById('project-form-modal').classList.add('hidden');

                // Update display
                this._updateMetadataDisplay(data);

                // If slug changed, update URL
                if (data.slug && data.slug !== projectSlug) {
                    projectSlug = data.slug;
                    window.history.replaceState(null, '', '/projects/' + data.slug);
                }
            } catch (e) {
                console.error('ProjectShow: Submit failed', e);
            }
        },

        _updateMetadataDisplay: function(data) {
            var nameEl = document.getElementById('project-name');
            if (nameEl) nameEl.textContent = data.name || '';

            var pathEl = document.getElementById('project-path');
            if (pathEl) pathEl.textContent = data.path || '';

            var githubEl = document.getElementById('project-github');
            if (githubEl) {
                if (data.github_repo) {
                    githubEl.innerHTML = 'GitHub: <a href="https://github.com/' +
                        CHUtils.escapeHtml(data.github_repo) + '" target="_blank" rel="noopener" class="text-cyan hover:underline">' +
                        CHUtils.escapeHtml(data.github_repo) + '</a>';
                } else {
                    githubEl.innerHTML = 'GitHub: <span class="text-muted">Not set</span>';
                }
            }

            var descEl = document.getElementById('project-description');
            if (descEl) {
                if (data.description) {
                    descEl.textContent = data.description;
                    descEl.className = 'text-secondary text-sm mb-4';
                } else {
                    descEl.innerHTML = '<span class="text-muted italic">No description</span>';
                }
            }

            // Update page title
            document.title = (data.name || 'Project') + ' - Claude Headspace';

            // Update delete dialog name
            var deleteNameEl = document.getElementById('delete-project-name');
            if (deleteNameEl) deleteNameEl.textContent = data.name || '';
        },

        openDeleteDialog: function() {
            this._updateAgentWarning();
            document.getElementById('delete-dialog').classList.remove('hidden');
        },

        closeDeleteDialog: function() {
            document.getElementById('delete-dialog').classList.add('hidden');
        },

        confirmDelete: async function() {
            try {
                var response = await CHUtils.apiFetch('/api/projects/' + projectId, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    window.location.href = '/projects';
                } else {
                    var data = await response.json();
                    console.error('ProjectShow: Delete failed', data.error);
                }
            } catch (e) {
                console.error('ProjectShow: Delete failed', e);
            }
        },

        togglePause: async function() {
            var btn = document.getElementById('btn-pause');
            var statusEl = document.getElementById('inference-status');
            var isPaused = btn && btn.textContent.trim().startsWith('Resume');

            try {
                var response = await CHUtils.apiFetch('/api/projects/' + projectId + '/settings', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ inference_paused: !isPaused })
                });

                if (!response.ok) return;
                var data = await response.json();

                // Update button
                if (btn) {
                    if (data.inference_paused) {
                        btn.textContent = 'Resume Inference';
                        btn.className = 'px-3 py-1.5 text-xs font-medium rounded border transition-colors border-green/30 text-green hover:bg-green/10';
                    } else {
                        btn.textContent = 'Pause Inference';
                        btn.className = 'px-3 py-1.5 text-xs font-medium rounded border transition-colors border-amber/30 text-amber hover:bg-amber/10';
                    }
                }

                // Update status display
                if (statusEl) {
                    if (data.inference_paused) {
                        var statusText = '<span class="text-amber">Inference Paused</span>';
                        if (data.inference_paused_at) {
                            statusText += '<span class="text-muted"> since ' + new Date(data.inference_paused_at).toLocaleDateString('en-AU', { day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit' }) + '</span>';
                        }
                        statusEl.innerHTML = statusText;
                    } else {
                        statusEl.innerHTML = '<span class="text-green">Inference Active</span>';
                    }
                }
            } catch (e) {
                console.error('ProjectShow: Toggle pause failed', e);
            }
        },

        regenerateDescription: async function() {
            var btn = document.getElementById('btn-regen-desc');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Detecting...';
            }

            try {
                var response = await CHUtils.apiFetch('/api/projects/' + projectId + '/detect-metadata', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (!response.ok) return;

                // Reload project data to get updated fields
                var projResponse = await fetch('/api/projects/' + projectId);
                if (projResponse.ok) {
                    var data = await projResponse.json();
                    this._updateMetadataDisplay(data);
                }
            } catch (e) {
                console.error('ProjectShow: Regenerate description failed', e);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = 'Regen Description';
                }
            }
        },

        refetchGitInfo: async function() {
            var btn = document.getElementById('btn-refetch-git');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Fetching...';
            }

            try {
                var response = await CHUtils.apiFetch('/api/projects/' + projectId + '/detect-metadata', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (!response.ok) return;

                // Reload project data to get updated fields
                var projResponse = await fetch('/api/projects/' + projectId);
                if (projResponse.ok) {
                    var data = await projResponse.json();
                    this._updateMetadataDisplay(data);

                    // Update branch
                    var branchEl = document.getElementById('project-branch');
                    if (branchEl) {
                        branchEl.innerHTML = 'Branch: <span class="text-primary">' + CHUtils.escapeHtml(data.current_branch || 'Unknown') + '</span>';
                    }
                }
            } catch (e) {
                console.error('ProjectShow: Refetch git info failed', e);
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = 'Refetch Git Info';
                }
            }
        },

        regenerateBrainReboot: async function() {
            var btn = document.getElementById('btn-regen-brain-reboot');
            var container = document.getElementById('brain-reboot-content');

            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Generating...';
            }
            if (container) {
                container.innerHTML = '<p class="text-muted italic">Generating brain reboot...</p>';
            }

            try {
                var response = await CHUtils.apiFetch('/api/projects/' + projectId + '/brain-reboot', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (response.ok) {
                    this._loadBrainReboot();
                } else {
                    if (container) container.innerHTML = '<p class="text-red italic">Failed to generate brain reboot.</p>';
                }
            } catch (e) {
                console.error('ProjectShow: Regenerate brain reboot failed', e);
                if (container) container.innerHTML = '<p class="text-red italic">Failed to generate brain reboot.</p>';
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = 'Regenerate';
                }
            }
        },

        exportBrainReboot: async function() {
            var btn = document.getElementById('btn-export-brain-reboot');
            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Exporting...';
            }

            try {
                var response = await CHUtils.apiFetch('/api/projects/' + projectId + '/brain-reboot/export', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (response.ok) {
                    var data = await response.json();
                    if (btn) btn.textContent = 'Exported!';
                    setTimeout(function() {
                        if (btn) {
                            btn.textContent = 'Export';
                            btn.disabled = false;
                        }
                    }, 2000);
                } else {
                    if (btn) btn.textContent = 'Export Failed';
                    setTimeout(function() {
                        if (btn) {
                            btn.textContent = 'Export';
                            btn.disabled = false;
                        }
                    }, 2000);
                }
            } catch (e) {
                console.error('ProjectShow: Export brain reboot failed', e);
                if (btn) {
                    btn.textContent = 'Export';
                    btn.disabled = false;
                }
            }
        },

        regenerateProgressSummary: async function() {
            var btn = document.getElementById('btn-regen-progress');
            var container = document.getElementById('progress-summary-content');

            if (btn) {
                btn.disabled = true;
                btn.textContent = 'Generating...';
            }
            if (container) {
                container.innerHTML = '<p class="text-muted italic">Generating progress summary...</p>';
            }

            try {
                var response = await CHUtils.apiFetch('/api/projects/' + projectId + '/progress-summary', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (response.ok) {
                    this._loadProgressSummary();
                } else {
                    if (container) container.innerHTML = '<p class="text-red italic">Failed to generate progress summary.</p>';
                }
            } catch (e) {
                console.error('ProjectShow: Regenerate progress summary failed', e);
                if (container) container.innerHTML = '<p class="text-red italic">Failed to generate progress summary.</p>';
            } finally {
                if (btn) {
                    btn.disabled = false;
                    btn.textContent = 'Regenerate';
                }
            }
        },

        editWaypoint: async function() {
            var content = document.getElementById('waypoint-content');
            var editor = document.getElementById('waypoint-editor');
            var textarea = document.getElementById('waypoint-editor-textarea');
            var actions = document.getElementById('waypoint-actions');
            if (!content || !editor || !textarea) return;

            // Load raw markdown content into textarea
            try {
                var response = await fetch('/api/projects/' + projectId + '/waypoint');
                if (response.ok) {
                    var data = await response.json();
                    textarea.value = data.content || '';
                    // Store last_modified for conflict detection
                    textarea.dataset.lastModified = data.last_modified || '';
                } else {
                    textarea.value = '';
                    textarea.dataset.lastModified = '';
                }
            } catch (e) {
                textarea.value = '';
                textarea.dataset.lastModified = '';
            }

            // Toggle visibility
            content.classList.add('hidden');
            editor.classList.remove('hidden');
            if (actions) actions.classList.add('hidden');
            textarea.focus();
        },

        cancelWaypointEdit: function() {
            var content = document.getElementById('waypoint-content');
            var editor = document.getElementById('waypoint-editor');
            var actions = document.getElementById('waypoint-actions');
            if (content) content.classList.remove('hidden');
            if (editor) editor.classList.add('hidden');
            if (actions) actions.classList.remove('hidden');
        },

        saveWaypoint: async function() {
            var textarea = document.getElementById('waypoint-editor-textarea');
            var saveBtn = document.getElementById('waypoint-save-btn');
            if (!textarea) return;

            var payload = { content: textarea.value };
            if (textarea.dataset.lastModified) {
                payload.expected_mtime = textarea.dataset.lastModified;
            }

            if (saveBtn) {
                saveBtn.disabled = true;
                saveBtn.textContent = 'Saving...';
            }

            try {
                var response = await CHUtils.apiFetch('/api/projects/' + projectId + '/waypoint', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                if (response.ok) {
                    // Switch back to view mode and reload rendered content
                    this.cancelWaypointEdit();
                    this._loadWaypoint();
                } else {
                    var data = await response.json();
                    if (response.status === 409) {
                        // Conflict - file was modified externally, reload and re-enter edit
                        alert('Waypoint was modified externally. Your content has been preserved. The latest version will be reloaded.');
                        var savedContent = textarea.value;
                        await this.editWaypoint();
                        // Restore user's edits so they can merge manually
                        textarea.value = savedContent;
                    } else {
                        alert('Failed to save waypoint: ' + (data.message || data.error || 'Unknown error'));
                    }
                }
            } catch (e) {
                console.error('ProjectShow: Save waypoint failed', e);
                alert('Failed to save waypoint. Check the console for details.');
            } finally {
                if (saveBtn) {
                    saveBtn.disabled = false;
                    saveBtn.textContent = 'Save';
                }
            }
        },

        // --- SSE ---

        _initSSE: function() {
            var client = window.headerSSEClient;
            if (!client) return;

            var self = this;

            client.on('project_changed', function(data) {
                if (data && data.project_id == projectId) {
                    self._loadProjectData();
                    // Reload page data if project was updated
                    if (data.action === 'updated') {
                        fetch('/api/projects/' + projectId)
                            .then(function(r) { return r.json(); })
                            .then(function(p) { self._updateMetadataDisplay(p); })
                            .catch(function(err) { console.warn('ProjectShow: SSE project refresh failed', err); });
                    } else if (data.action === 'deleted') {
                        window.location.href = '/projects';
                    }
                }
            });

            client.on('project_settings_changed', function(data) {
                if (data && data.project_id == projectId) {
                    // Refresh the page to get updated inference status
                    window.location.reload();
                }
            });

            // Enhanced SSE: update accordion on card_refresh events
            client.on('card_refresh', function(data) {
                if (!data) return;
                // Check if this agent belongs to our project
                self._scheduleAccordionUpdate('agents', data);
            });

            client.on('state_transition', function(data) {
                if (!data) return;
                self._scheduleAccordionUpdate('tasks', data);
            });
        },

        _scheduleAccordionUpdate: function(type, data) {
            ssePendingUpdates[type] = data;
            if (sseDebounceTimer) return;

            var self = this;
            sseDebounceTimer = setTimeout(function() {
                sseDebounceTimer = null;
                var pending = ssePendingUpdates;
                ssePendingUpdates = {};
                self._processAccordionUpdates(pending);
            }, 2000);
        },

        _processAccordionUpdates: function(pending) {
            // Refresh agents list if accordion is expanded
            if (agentsExpanded && pending.agents) {
                // Invalidate cache and re-fetch, preserving current page
                cache.agents = null;
                var currentPage = (cache.agentsPagination && cache.agentsPagination.page) || 1;
                var showEnded = projectData && projectData._showEnded;
                var sseUrl = '/api/projects/' + projectId + '?agents_page=' + currentPage;
                if (showEnded) sseUrl += '&include_ended=true';
                var self = this;
                fetch(sseUrl)
                    .then(function(r) { return r.json(); })
                    .then(function(data) {
                        data._showEnded = showEnded;
                        projectData = data;
                        cache.agents = data.agents || [];
                        cache.agentsPagination = data.agents_pagination || null;
                        self._updateAgentsBadge();
                        self._renderAgentsList(cache.agents);
                        // Re-expand agents that were expanded
                        Object.keys(expandedAgents).forEach(function(agentId) {
                            var body = document.getElementById('agent-tasks-' + agentId);
                            var arrow = document.getElementById('agent-arrow-' + agentId);
                            if (body) {
                                body.style.display = 'block';
                                if (arrow) arrow.style.transform = 'rotate(90deg)';
                                // Invalidate task cache and re-fetch
                                delete cache.agentTasks[agentId];
                                self._fetchAndRenderTasks(parseInt(agentId));
                            }
                        });
                    })
                    .catch(function(err) { console.warn('ProjectShow: accordion refresh failed', err); });
            }

            // Refresh task accordions if expanded
            if (pending.tasks) {
                Object.keys(expandedTasks).forEach(function(taskId) {
                    delete cache.taskTurns[taskId];
                    var container = document.getElementById('task-turns-' + taskId);
                    if (container && container.style.display !== 'none') {
                        ProjectShow._fetchAndRenderTurns(parseInt(taskId));
                    }
                });
            }
        },

        // --- Utilities ---

        _stateColorClass: function(state) {
            var s = (state || '').toLowerCase();
            var map = {
                idle: 'bg-surface text-muted',
                commanded: 'bg-amber/15 text-amber',
                processing: 'bg-blue/15 text-blue',
                awaiting_input: 'bg-amber/15 text-amber',
                complete: 'bg-green/15 text-green',
                ended: 'bg-surface text-muted opacity-60'
            };
            return map[s] || 'bg-surface text-muted';
        },

        _formatDate: function(dateStr) {
            if (!dateStr) return '';
            var d = new Date(dateStr);
            return d.toLocaleDateString([], { day: 'numeric', month: 'short' }) + ' ' +
                d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        },

        _formatDuration: function(startStr, endStr) {
            var start = new Date(startStr);
            var end = new Date(endStr);
            var seconds = Math.floor((end - start) / 1000);
            if (seconds < 60) return seconds + 's';
            var minutes = Math.floor(seconds / 60);
            if (minutes < 60) return minutes + 'm';
            var hours = Math.floor(minutes / 60);
            var mins = minutes % 60;
            return hours + 'h ' + mins + 'm';
        },

        _formatNumber: function(n) {
            if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M';
            if (n >= 1000) return (n / 1000).toFixed(1) + 'K';
            return n.toString();
        },

        _renderMarkdown: function(text) {
            return CHUtils.renderMarkdown(text);
        },

        _timeAgo: function(dateString) {
            var date = new Date(dateString);
            var now = new Date();
            var seconds = Math.floor((now - date) / 1000);

            if (seconds < 60) return 'just now';
            var minutes = Math.floor(seconds / 60);
            if (minutes < 60) return minutes + ' minute' + (minutes !== 1 ? 's' : '') + ' ago';
            var hours = Math.floor(minutes / 60);
            if (hours < 24) return hours + ' hour' + (hours !== 1 ? 's' : '') + ' ago';
            var days = Math.floor(hours / 24);
            if (days < 30) return days + ' day' + (days !== 1 ? 's' : '') + ' ago';
            var months = Math.floor(days / 30);
            return months + ' month' + (months !== 1 ? 's' : '') + ' ago';
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { ProjectShow.init(); });
    } else {
        ProjectShow.init();
    }

    global.ProjectShow = ProjectShow;

    // Provide ProjectsPage shim so the shared form modal works on this page
    if (!global.ProjectsPage) {
        global.ProjectsPage = {
            closeFormModal: function() { ProjectShow.closeFormModal(); },
            submitProject: function() { ProjectShow.submitProject(); }
        };
    }

})(typeof window !== 'undefined' ? window : this);
