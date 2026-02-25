/**
 * Shared Agent Listing component for project_show and persona_detail pages.
 *
 * Provides:
 * - Agent sorting (active-first, then by last_seen_at desc)
 * - State-to-CSS-class mapping
 * - Relative time and duration formatting
 * - Configurable agent row rendering
 * - Revive action for dead agents
 */
(function(global) {
    'use strict';

    var AgentListing = {

        /**
         * Sort agents: active (non-ended) first, then by last_seen_at descending.
         */
        sortAgents: function(agents) {
            if (!agents || agents.length <= 1) return agents;
            return agents.slice().sort(function(a, b) {
                var aEnded = !!a.ended_at;
                var bEnded = !!b.ended_at;
                if (aEnded !== bEnded) return aEnded ? 1 : -1;
                var aTime = a.last_seen_at ? new Date(a.last_seen_at).getTime() : 0;
                var bTime = b.last_seen_at ? new Date(b.last_seen_at).getTime() : 0;
                return bTime - aTime;
            });
        },

        /**
         * Map agent state to CSS class string for badge styling.
         */
        stateColorClass: function(state) {
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

        /**
         * Relative time display (e.g. "3 minutes ago").
         */
        timeAgo: function(dateString) {
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
        },

        /**
         * Duration between two timestamps (e.g. "2h 15m").
         */
        formatDuration: function(startStr, endStr) {
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

        /**
         * Render a single agent row HTML.
         *
         * Options:
         *   showAccordionArrow  - render expand arrow (project_show: true)
         *   onRowClick          - JS expression for row click, use AGENT_ID as placeholder
         *   showPersonaHero     - show persona name+role as hero (project_show: true)
         *   showClaudeSessionId - show truncated claude_session_id (project_show: true)
         *   showProjectName     - show project name column (persona_detail: true)
         *   showChatLink        - show Chat link (project_show: true)
         *   showReviveButton    - show Revive button for dead agents (both: true)
         *   thresholds          - { yellow, red } frustration thresholds
         */
        renderAgentRow: function(agent, options) {
            options = options || {};
            var thresholds = options.thresholds || { yellow: 4, red: 7 };
            var isEnded = !!agent.ended_at;
            var stateValue = agent.state || 'idle';
            if (isEnded) stateValue = 'ended';
            var uuid8 = agent.session_uuid ? agent.session_uuid.substring(0, 8) : '';
            var agentId = agent.id;
            var stateClass = AgentListing.stateColorClass(stateValue);

            var html = '';

            // Outer wrapper for accordion
            if (options.showAccordionArrow) {
                html += '<div class="accordion-agent-row">';
            }

            // Row div
            var rowClass = 'agent-metric-row';
            if (options.onRowClick) {
                rowClass += ' cursor-pointer hover:border-border-bright transition-colors';
            }
            var onclickAttr = options.onRowClick
                ? ' onclick="' + options.onRowClick.replace('AGENT_ID', agentId) + '"'
                : '';
            html += '<div class="' + rowClass + '"' + onclickAttr + '>';

            // Accordion arrow
            if (options.showAccordionArrow) {
                html += '<span class="accordion-arrow text-muted text-xs transition-transform duration-150" id="agent-arrow-' + agentId + '" style="flex-shrink:0">&#9654;</span>';
            }

            // ALIVE pill for active agents
            if (!isEnded) {
                html += '<span class="text-xs font-medium px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-400 border border-emerald-700/50" style="flex-shrink:0">ALIVE</span>';
            }

            // State badge
            html += '<span class="text-xs font-medium px-1.5 py-0.5 rounded ' + stateClass + '" style="flex-shrink:0">' + CHUtils.escapeHtml(stateValue.toUpperCase()) + '</span>';

            // DB ID
            html += '<span class="text-xs text-muted font-mono" style="flex-shrink:0">#' + agentId + '</span>';

            // Hero identity
            if (options.showPersonaHero) {
                var agentHeroHtml;
                if (agent.persona_name) {
                    agentHeroHtml = '<span class="agent-hero">' + CHUtils.escapeHtml(agent.persona_name) + '</span>' +
                        (agent.persona_role ? '<span class="agent-hero-trail"> \u2014 ' + CHUtils.escapeHtml(agent.persona_role) + '</span>' : '');
                } else if (uuid8) {
                    agentHeroHtml = '<span class="agent-hero">' + CHUtils.escapeHtml(uuid8.substring(0, 2)) + '</span><span class="agent-hero-trail">' + CHUtils.escapeHtml(uuid8.substring(2)) + '</span>';
                } else {
                    agentHeroHtml = 'Agent ' + agent.id;
                }
                html += '<span class="agent-metric-tag">' + agentHeroHtml + '</span>';
            } else {
                if (uuid8) {
                    html += '<span class="agent-metric-tag"><span class="font-mono text-xs text-secondary">' + CHUtils.escapeHtml(uuid8) + '</span></span>';
                }
            }

            // Claude session ID
            if (options.showClaudeSessionId && agent.claude_session_id) {
                html += '<span class="text-xs text-muted font-mono" style="flex-shrink:0;max-width:120px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + CHUtils.escapeHtml(agent.claude_session_id) + '">' + CHUtils.escapeHtml(agent.claude_session_id.substring(0, 12)) + '</span>';
            }

            // Project name
            if (options.showProjectName && agent.project_name) {
                html += '<span class="text-xs text-secondary" style="flex-shrink:0">' + CHUtils.escapeHtml(agent.project_name) + '</span>';
            }

            // Metric stats
            html += '<div class="agent-metric-stats">';
            html += '<span><span class="stat-value">' + (agent.turn_count || 0) + '</span><span class="stat-label">turns</span></span>';
            if (agent.avg_turn_time != null) {
                html += '<span><span class="stat-value">' + agent.avg_turn_time.toFixed(1) + 's</span><span class="stat-label">avg</span></span>';
            }
            if (agent.frustration_avg != null) {
                var frustLevel = agent.frustration_avg >= thresholds.red ? 'text-red' : (agent.frustration_avg >= thresholds.yellow ? 'text-amber' : 'text-green');
                html += '<span><span class="stat-value ' + frustLevel + '">' + agent.frustration_avg.toFixed(1) + '</span><span class="stat-label">frust</span></span>';
            }
            html += '</div>';

            // Chat link
            if (options.showChatLink) {
                html += '<a href="/voice?agent_id=' + agentId + '" class="text-xs text-cyan hover:underline" style="flex-shrink:0" title="Chat" onclick="event.stopPropagation()">Chat</a>';
            }

            // Last seen / ended badge
            if (isEnded) {
                html += '<span class="text-xs px-1.5 py-0.5 rounded bg-surface border border-border text-muted" style="flex-shrink:0">Ended</span>';
                if (agent.started_at && agent.ended_at) {
                    html += '<span class="text-xs text-muted" style="flex-shrink:0">' + AgentListing.formatDuration(agent.started_at, agent.ended_at) + '</span>';
                }
            } else if (agent.last_seen_at) {
                html += '<span class="text-xs text-muted" style="flex-shrink:0">' + AgentListing.timeAgo(agent.last_seen_at) + '</span>';
            }

            // Revive button (dead agents only)
            if (options.showReviveButton && isEnded) {
                html += '<button type="button" class="agent-revive-btn text-xs text-cyan hover:underline" style="flex-shrink:0" data-agent-id="' + agentId + '" onclick="event.stopPropagation(); AgentListing.reviveAgent(' + agentId + ')">Revive</button>';
            }

            html += '</div>'; // close agent-metric-row

            // Accordion body for commands
            if (options.showAccordionArrow) {
                html += '<div id="agent-commands-' + agentId + '" class="accordion-body ml-6 mt-1" style="display: none;"></div>';
                html += '</div>'; // close accordion-agent-row
            }

            return html;
        },

        /**
         * Render a full agents list into a container element.
         * Handles sorting and empty state.
         *
         * Options: same as renderAgentRow, plus:
         *   emptyMessage - text to show when no agents
         */
        renderAgentsList: function(container, agents, options) {
            options = options || {};
            agents = AgentListing.sortAgents(agents);

            if (!agents || agents.length === 0) {
                container.innerHTML = '<p class="text-muted italic text-sm">' + CHUtils.escapeHtml(options.emptyMessage || 'No agents.') + '</p>';
                return;
            }

            var html = '';
            for (var i = 0; i < agents.length; i++) {
                html += AgentListing.renderAgentRow(agents[i], options);
            }
            container.innerHTML = html;
        },

        /**
         * Revive a dead agent by creating a successor.
         */
        reviveAgent: function(agentId) {
            CHUtils.apiFetch('/api/agents/' + agentId + '/revive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({})
            }).then(function(res) {
                return res.json().then(function(data) {
                    if (res.ok) {
                        if (window.Toast) {
                            window.Toast.success('Revival initiated', data.message || 'Successor agent starting');
                        }
                    } else {
                        if (window.Toast) {
                            window.Toast.error('Revival failed', data.error || 'Unknown error');
                        }
                    }
                    return data;
                });
            });
        }
    };

    global.AgentListing = AgentListing;

})(typeof window !== 'undefined' ? window : this);
