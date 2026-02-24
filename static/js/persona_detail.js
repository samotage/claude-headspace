/**
 * Persona detail page client for Claude Headspace.
 *
 * Handles skill editor (view/edit/preview), experience display,
 * and linked agents list.
 */

(function(global) {
    'use strict';

    var slug = global.PERSONA_SLUG;
    var API_BASE = '/api/personas/' + encodeURIComponent(slug);

    // Editor state
    var state = {
        originalContent: '',
        isDirty: false,
        mode: 'view',  // 'view' | 'edit' | 'preview'
        showEnded: false,
        activeAgentCount: 0
    };

    // Warn on navigation when skill editor has unsaved changes
    function _beforeUnloadHandler(e) {
        if (state.isDirty) {
            e.preventDefault();
            e.returnValue = '';
        }
    }

    var PersonaDetail = {

        /**
         * Initialize the detail page — load all sections.
         */
        init: function() {
            if (!slug) {
                console.error('PersonaDetail: No PERSONA_SLUG defined');
                return;
            }
            window.addEventListener('beforeunload', _beforeUnloadHandler);
            this.loadSkill();
            this.loadExperience();
            this.loadLinkedAgents();
        },

        // --- Skill ---

        /**
         * Fetch skill content and render in view mode.
         */
        loadSkill: async function() {
            try {
                var response = await fetch(API_BASE + '/skill');
                if (!response.ok) {
                    document.getElementById('skill-view').innerHTML =
                        '<p class="text-red italic">Failed to load skill.</p>';
                    return;
                }

                var data = await response.json();

                if (!data.exists || !data.content.trim()) {
                    document.getElementById('skill-view').innerHTML =
                        '<p class="text-muted italic">No skill file yet. Click Edit to create one.</p>';
                } else {
                    document.getElementById('skill-view').innerHTML =
                        DOMPurify.sanitize(marked.parse(data.content));
                }

                state.originalContent = data.content || '';
            } catch (error) {
                console.error('PersonaDetail: Failed to load skill', error);
                document.getElementById('skill-view').innerHTML =
                    '<p class="text-red italic">Error loading skill.</p>';
            }
        },

        /**
         * Switch to edit mode.
         */
        editSkill: function() {
            state.mode = 'edit';

            document.getElementById('skill-view').classList.add('hidden');
            document.getElementById('skill-edit-btn').classList.add('hidden');
            document.getElementById('skill-editor').classList.remove('hidden');

            var textarea = document.getElementById('skill-textarea');
            textarea.value = state.originalContent;
            textarea.focus();

            // Track changes
            textarea.oninput = function() {
                state.isDirty = textarea.value !== state.originalContent;
                PersonaDetail._updateDirtyIndicator();
            };

            this.switchEditorTab('edit');
            state.isDirty = false;
            this._updateDirtyIndicator();
        },

        /**
         * Switch between edit and preview tabs.
         */
        switchEditorTab: function(tab) {
            var textarea = document.getElementById('skill-textarea');
            var previewPane = document.getElementById('skill-preview-pane');
            var tabEdit = document.getElementById('skill-tab-edit');
            var tabPreview = document.getElementById('skill-tab-preview');

            if (tab === 'edit') {
                state.mode = 'edit';
                textarea.classList.remove('hidden');
                previewPane.classList.add('hidden');
                tabEdit.className = 'px-4 py-2 text-sm font-medium border-b-2 border-cyan text-cyan -mb-px';
                tabPreview.className = 'px-4 py-2 text-sm font-medium border-b-2 border-transparent text-muted hover:text-secondary -mb-px';
            } else {
                state.mode = 'preview';
                textarea.classList.add('hidden');
                previewPane.classList.remove('hidden');
                previewPane.innerHTML = DOMPurify.sanitize(marked.parse(textarea.value || ''));
                tabEdit.className = 'px-4 py-2 text-sm font-medium border-b-2 border-transparent text-muted hover:text-secondary -mb-px';
                tabPreview.className = 'px-4 py-2 text-sm font-medium border-b-2 border-cyan text-cyan -mb-px';
            }
        },

        /**
         * Save skill content.
         */
        saveSkill: async function() {
            var textarea = document.getElementById('skill-textarea');
            var content = textarea.value;

            try {
                var response = await CHUtils.apiFetch(API_BASE + '/skill', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: content })
                });

                if (!response.ok) {
                    var errData = await response.json();
                    if (window.Toast) {
                        window.Toast.error('Save failed', errData.error || 'Could not save skill.');
                    }
                    return;
                }

                state.originalContent = content;
                state.isDirty = false;
                this._updateDirtyIndicator();

                // Switch back to view mode
                this._exitEditor();

                // Re-render view
                if (!content.trim()) {
                    document.getElementById('skill-view').innerHTML =
                        '<p class="text-muted italic">No skill file yet. Click Edit to create one.</p>';
                } else {
                    document.getElementById('skill-view').innerHTML =
                        DOMPurify.sanitize(marked.parse(content));
                }

                if (window.Toast) {
                    window.Toast.success('Skill saved', 'Skill file updated successfully.');
                }
            } catch (error) {
                console.error('PersonaDetail: Failed to save skill', error);
                if (window.Toast) {
                    window.Toast.error('Save failed', 'Network error.');
                }
            }
        },

        /**
         * Cancel editing — discard changes and return to view mode.
         */
        cancelEdit: function() {
            state.isDirty = false;
            this._updateDirtyIndicator();
            this._exitEditor();
        },

        /**
         * Hide editor, show view mode.
         */
        _exitEditor: function() {
            state.mode = 'view';
            document.getElementById('skill-editor').classList.add('hidden');
            document.getElementById('skill-view').classList.remove('hidden');
            document.getElementById('skill-edit-btn').classList.remove('hidden');
        },

        /**
         * Update the unsaved-changes indicator.
         */
        _updateDirtyIndicator: function() {
            var indicator = document.getElementById('skill-dirty-indicator');
            if (indicator) {
                if (state.isDirty) {
                    indicator.classList.remove('hidden');
                } else {
                    indicator.classList.add('hidden');
                }
            }
        },

        // --- Experience ---

        /**
         * Fetch experience content and render as read-only markdown.
         */
        loadExperience: async function() {
            try {
                var response = await fetch(API_BASE + '/experience');
                if (!response.ok) {
                    document.getElementById('experience-content').innerHTML =
                        '<p class="text-red italic">Failed to load experience log.</p>';
                    return;
                }

                var data = await response.json();

                if (!data.exists || !data.content.trim()) {
                    document.getElementById('experience-content').innerHTML =
                        '<p class="text-muted italic">No experience log yet.</p>';
                } else {
                    document.getElementById('experience-content').innerHTML =
                        DOMPurify.sanitize(marked.parse(data.content));
                }

                // Display last-modified timestamp
                var mtimeEl = document.getElementById('experience-mtime');
                if (mtimeEl && data.last_modified) {
                    var d = new Date(data.last_modified);
                    mtimeEl.textContent = 'Last modified: ' + d.toLocaleString();
                } else if (mtimeEl) {
                    mtimeEl.textContent = '';
                }
            } catch (error) {
                console.error('PersonaDetail: Failed to load experience', error);
                document.getElementById('experience-content').innerHTML =
                    '<p class="text-red italic">Error loading experience log.</p>';
            }
        },

        // --- Linked Agents ---

        toggleShowEnded: function() {
            var btn = document.getElementById('btn-show-ended');
            if (state.showEnded) {
                state.showEnded = false;
                if (btn) {
                    btn.textContent = 'Show ended';
                    btn.className = 'px-2 py-1 text-xs rounded border border-border text-muted hover:text-secondary hover:border-border-bright transition-colors';
                }
            } else {
                state.showEnded = true;
                if (btn) {
                    btn.textContent = 'Hide ended';
                    btn.className = 'px-2 py-1 text-xs rounded border border-cyan/30 text-cyan hover:text-primary transition-colors';
                }
            }
            this.loadLinkedAgents();
        },

        /**
         * Fetch linked agents and render using agent-metric-row pattern.
         */
        loadLinkedAgents: async function() {
            var container = document.getElementById('agents-list');
            container.innerHTML = '<p class="text-muted italic text-sm"><span class="inline-block animate-pulse">Loading agents...</span></p>';

            try {
                var url = API_BASE + '/agents';
                if (state.showEnded) url += '?include_ended=true';
                var response = await fetch(url);
                if (!response.ok) {
                    container.innerHTML = '<p class="text-red italic">Failed to load agents.</p>';
                    return;
                }

                var data = await response.json();
                var agents = data.agents || [];
                state.activeAgentCount = data.active_agent_count || 0;
                this._updateAgentsBadge(agents.length);

                if (agents.length === 0) {
                    container.innerHTML = '<p class="text-muted italic text-sm">No agents linked to this persona.</p>';
                    return;
                }

                this._renderAgentsList(container, agents);
            } catch (error) {
                console.error('PersonaDetail: Failed to load agents', error);
                container.innerHTML = '<p class="text-red italic">Error loading agents.</p>';
            }
        },

        _updateAgentsBadge: function(totalCount) {
            var badge = document.getElementById('agents-count-badge');
            if (!badge) return;
            var active = state.activeAgentCount;
            if (state.showEnded && totalCount !== active) {
                badge.textContent = '(' + active + ' active / ' + totalCount + ' total)';
            } else {
                badge.textContent = '(' + active + ')';
            }
        },

        _renderAgentsList: function(container, agents) {
            // Sort: active first, then by last_seen_at descending
            if (agents.length > 1) {
                agents = agents.slice().sort(function(a, b) {
                    var aEnded = !!a.ended_at;
                    var bEnded = !!b.ended_at;
                    if (aEnded !== bEnded) return aEnded ? 1 : -1;
                    var aTime = a.last_seen_at ? new Date(a.last_seen_at).getTime() : 0;
                    var bTime = b.last_seen_at ? new Date(b.last_seen_at).getTime() : 0;
                    return bTime - aTime;
                });
            }

            var html = '';
            var self = this;
            agents.forEach(function(agent) {
                var isEnded = !!agent.ended_at;
                var stateValue = agent.state || 'idle';
                if (isEnded) stateValue = 'ended';
                var stateClass = self._stateColorClass(stateValue);
                var uuid8 = agent.session_uuid ? agent.session_uuid.substring(0, 8) : '';

                html += '<div class="agent-metric-row">';

                // Alive pill for active agents
                if (!isEnded) {
                    html += '<span class="text-xs font-medium px-1.5 py-0.5 rounded bg-emerald-900/40 text-emerald-400 border border-emerald-700/50" style="flex-shrink:0">ALIVE</span>';
                }
                // State badge
                html += '<span class="text-xs font-medium px-1.5 py-0.5 rounded ' + stateClass + '" style="flex-shrink:0">' + CHUtils.escapeHtml(stateValue.toUpperCase()) + '</span>';

                // Agent ID + UUID
                html += '<span class="text-xs text-muted font-mono" style="flex-shrink:0">#' + agent.id + '</span>';
                if (uuid8) {
                    html += '<span class="agent-metric-tag"><span class="font-mono text-xs text-secondary">' + CHUtils.escapeHtml(uuid8) + '</span></span>';
                }

                // Project name
                if (agent.project_name) {
                    html += '<span class="text-xs text-secondary" style="flex-shrink:0">' + CHUtils.escapeHtml(agent.project_name) + '</span>';
                }

                // Metrics
                html += '<div class="agent-metric-stats">';
                html += '<span><span class="stat-value">' + (agent.turn_count || 0) + '</span><span class="stat-label">turns</span></span>';
                if (agent.avg_turn_time != null) {
                    html += '<span><span class="stat-value">' + agent.avg_turn_time.toFixed(1) + 's</span><span class="stat-label">avg</span></span>';
                }
                if (agent.frustration_avg != null) {
                    var frustLevel = agent.frustration_avg >= 7 ? 'text-red' : (agent.frustration_avg >= 4 ? 'text-amber' : 'text-green');
                    html += '<span><span class="stat-value ' + frustLevel + '">' + agent.frustration_avg.toFixed(1) + '</span><span class="stat-label">frust</span></span>';
                }
                html += '</div>';

                // Last seen / ended badge
                if (isEnded) {
                    html += '<span class="text-xs px-1.5 py-0.5 rounded bg-surface border border-border text-muted" style="flex-shrink:0">Ended</span>';
                    if (agent.started_at && agent.ended_at) {
                        html += '<span class="text-xs text-muted" style="flex-shrink:0">' + self._formatDuration(agent.started_at, agent.ended_at) + '</span>';
                    }
                } else if (agent.last_seen_at) {
                    html += '<span class="text-xs text-muted" style="flex-shrink:0">' + self._timeAgo(agent.last_seen_at) + '</span>';
                }

                html += '</div>';
            });

            container.innerHTML = html;
        },

        // --- Agent display utilities ---

        _stateColorClass: function(s) {
            s = (s || '').toLowerCase();
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
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { PersonaDetail.init(); });
    } else {
        PersonaDetail.init();
    }

    global.PersonaDetail = PersonaDetail;

})(typeof window !== 'undefined' ? window : this);
