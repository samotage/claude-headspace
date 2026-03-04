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

    // Accordion state for agent commands
    var expandedAgents = {};
    var expandedCommands = {};
    var cache = {
        agentCommands: {},
        commandTurns: {}
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
            AgentListing.renderAgentsList(container, agents, {
                showAccordionArrow: true,
                onRowClick: 'PersonaDetail.toggleAgentCommands(AGENT_ID)',
                showProjectName: true,
                showClaudeSessionId: true,
                showChatLink: true,
                showReviveButton: true,
                showContext: true,
                showContextProject: true,
                thresholds: { yellow: 4, red: 7 },
                emptyMessage: 'No agents linked to this persona.'
            });
        },

        // --- Agent Accordion ---

        toggleAgentCommands: async function(agentId) {
            var body = document.getElementById('agent-commands-' + agentId);
            var arrow = document.getElementById('agent-arrow-' + agentId);
            if (!body) return;

            if (expandedAgents[agentId]) {
                body.style.display = 'none';
                if (arrow) arrow.style.transform = 'rotate(0deg)';
                delete expandedAgents[agentId];
                var commandKeys = Object.keys(expandedCommands);
                commandKeys.forEach(function(key) {
                    if (expandedCommands[key] === agentId) {
                        delete expandedCommands[key];
                    }
                });
            } else {
                body.style.display = 'block';
                if (arrow) arrow.style.transform = 'rotate(90deg)';
                expandedAgents[agentId] = true;

                if (cache.agentCommands[agentId]) {
                    this._renderCommandsList(agentId, cache.agentCommands[agentId]);
                } else {
                    this._fetchAndRenderCommands(agentId);
                }
            }
        },

        _fetchAndRenderCommands: async function(agentId) {
            var container = document.getElementById('agent-commands-' + agentId);
            container.innerHTML = '<p class="text-muted italic text-sm"><span class="inline-block animate-pulse">Loading commands...</span></p>';

            try {
                var response = await fetch('/api/agents/' + agentId + '/commands');
                if (!response.ok) throw new Error('Failed to fetch');
                var commands = await response.json();
                cache.agentCommands[agentId] = commands;
                this._renderCommandsList(agentId, commands);
            } catch (e) {
                container.innerHTML = '<div class="text-red text-sm">Failed to load commands. <button type="button" onclick="PersonaDetail._fetchAndRenderCommands(' + agentId + ')" class="text-cyan hover:underline ml-1">Retry</button></div>';
            }
        },

        _renderCommandsList: function(agentId, commands) {
            var container = document.getElementById('agent-commands-' + agentId);
            if (!commands || commands.length === 0) {
                container.innerHTML = '<p class="text-muted italic text-sm">No commands.</p>';
                return;
            }

            var html = '<div class="space-y-2">';
            commands.forEach(function(command) {
                var stateValue = command.state || 'idle';
                var stateClass = AgentListing.stateColorClass(stateValue);
                var instruction = command.instruction || '';
                var summary = command.completion_summary || '';
                var displayText = instruction.length > 60 ? instruction.substring(0, 60) + '...' : instruction;
                var commandId = command.id;
                var isComplete = stateValue.toLowerCase() === 'complete';
                var borderColor = isComplete ? 'border-green/20' : 'border-border';

                html += '<div class="accordion-command-row">';
                html += '<div class="flex items-center gap-2 px-3 py-2 bg-elevated rounded-t-lg border ' + borderColor + ' cursor-pointer hover:border-border-bright transition-colors" onclick="PersonaDetail.toggleCommandTurns(' + commandId + ', ' + agentId + ')">';
                html += '<span class="accordion-arrow text-muted text-xs transition-transform duration-150" id="command-arrow-' + commandId + '">&#9654;</span>';
                html += '<span class="text-xs font-medium px-1.5 py-0.5 rounded ' + stateClass + '">' + CHUtils.escapeHtml(stateValue.toUpperCase()) + '</span>';
                if (displayText) {
                    html += '<span class="text-sm text-primary font-medium truncate flex-1">' + CHUtils.escapeHtml(displayText) + '</span>';
                }
                html += '</div>';

                html += '<div class="card-editor border-t-0 rounded-t-none border ' + borderColor + ' border-t-0 rounded-b-lg">';
                html += '<div class="card-line"><span class="line-num">01</span><div class="line-content">';
                html += '<p class="command-instruction text-primary text-sm font-medium">' + CHUtils.escapeHtml(instruction || 'No instruction') + '</p>';
                html += '</div></div>';
                html += '<div class="card-line"><span class="line-num">02</span><div class="line-content">';
                if (isComplete && summary) {
                    html += '<p class="command-summary text-green text-sm italic">' + CHUtils.escapeHtml(summary) + '</p>';
                } else if (isComplete) {
                    html += '<p class="text-green text-sm italic">Completed</p>';
                } else {
                    html += '<p class="text-amber text-sm italic">In progress...</p>';
                }
                html += '</div></div>';
                html += '<div class="card-line"><span class="line-num">03</span><div class="line-content flex items-baseline justify-between gap-2">';
                var turnLabel = (command.turn_count || 0) + ' turn' + ((command.turn_count || 0) !== 1 ? 's' : '');
                if (isComplete && command.started_at && command.completed_at) {
                    turnLabel += ' \u00B7 ' + AgentListing.formatDuration(command.started_at, command.completed_at);
                }
                html += '<span class="text-muted text-xs">' + turnLabel + '</span>';
                html += '<button type="button" class="full-text-btn text-muted hover:text-cyan text-xs whitespace-nowrap transition-colors" onclick="PersonaDetail.toggleCommandTurns(' + commandId + ', ' + agentId + ')" id="command-view-full-btn-' + commandId + '" title="View conversation">View full</button>';
                html += '</div></div>';
                html += '<div id="command-turns-' + commandId + '" class="card-line" style="display: none;"><span class="line-num">&nbsp;</span><div class="line-content"></div></div>';
                html += '</div>';
                html += '</div>';
            });
            html += '</div>';

            container.innerHTML = html;
        },

        toggleCommandTurns: async function(commandId, agentId) {
            var wrapper = document.getElementById('command-turns-' + commandId);
            var arrow = document.getElementById('command-arrow-' + commandId);
            var viewBtn = document.getElementById('command-view-full-btn-' + commandId);
            if (!wrapper) return;

            if (expandedCommands[commandId]) {
                wrapper.style.display = 'none';
                if (arrow) arrow.style.transform = 'rotate(0deg)';
                if (viewBtn) viewBtn.textContent = 'View full';
                delete expandedCommands[commandId];
            } else {
                wrapper.style.display = 'block';
                if (arrow) arrow.style.transform = 'rotate(90deg)';
                if (viewBtn) viewBtn.textContent = 'Collapse';
                expandedCommands[commandId] = agentId;

                if (cache.commandTurns[commandId]) {
                    this._renderTurnsList(commandId, cache.commandTurns[commandId]);
                } else {
                    this._fetchAndRenderTurns(commandId);
                }
            }
        },

        _fetchAndRenderTurns: async function(commandId) {
            var contentEl = document.querySelector('#command-turns-' + commandId + ' .line-content');
            if (contentEl) contentEl.innerHTML = '<span class="text-muted italic text-sm inline-block animate-pulse">Loading turns...</span>';

            try {
                var response = await fetch('/api/commands/' + commandId + '/turns');
                if (!response.ok) throw new Error('Failed to fetch');
                var turns = await response.json();
                cache.commandTurns[commandId] = turns;
                this._renderTurnsList(commandId, turns);
            } catch (e) {
                if (contentEl) contentEl.innerHTML = '<span class="text-red text-sm">Failed to load turns. <button type="button" onclick="PersonaDetail._fetchAndRenderTurns(' + commandId + ')" class="text-cyan hover:underline ml-1">Retry</button></span>';
            }
        },

        _renderTurnsList: function(commandId, turns) {
            var contentEl = document.querySelector('#command-turns-' + commandId + ' .line-content');
            if (!contentEl) return;

            if (!turns || turns.length === 0) {
                contentEl.innerHTML = '<span class="text-muted italic text-sm">No turns.</span>';
                return;
            }

            var html = '<div class="space-y-1 py-1">';
            turns.forEach(function(turn) {
                var actorClass = turn.actor === 'USER' ? 'text-cyan' : 'text-green';
                var actorLabel = turn.actor === 'USER' ? 'USER' : 'AGENT';
                var text = turn.summary || turn.text || '';
                if (text.length > 200) text = text.substring(0, 200) + '...';
                html += '<div class="flex gap-2 text-xs leading-relaxed">';
                html += '<span class="' + actorClass + ' font-medium shrink-0 w-12">' + actorLabel + '</span>';
                html += '<span class="text-secondary">' + CHUtils.escapeHtml(text) + '</span>';
                html += '</div>';
            });
            html += '</div>';

            contentEl.innerHTML = html;
        },

        // --- Delete ---

        /**
         * Delete this persona with confirmation dialog.
         * Cascade-deletes all linked agents/commands/turns from DB.
         * Filesystem assets (skill.md, experience.md) are retained.
         */
        deletePersona: async function() {
            var name = global.PERSONA_NAME || slug;
            var agentCount = state.activeAgentCount || 0;

            var message = 'Are you sure you want to permanently delete "' + name + '"?';
            if (agentCount > 0) {
                message += ' ' + agentCount + ' linked agent(s) will be unlinked but preserved.';
            }
            message += ' Filesystem assets (skill & experience files) will be retained. This action cannot be undone.';

            var ok = await ConfirmDialog.show(
                'Delete Persona',
                message,
                {
                    confirmText: 'Delete',
                    confirmClass: 'bg-red hover:bg-red/90'
                }
            );

            if (!ok) return;

            try {
                var response = await CHUtils.apiFetch(API_BASE, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    var data = await response.json();
                    var toast = '"' + name + '" has been permanently deleted.';
                    if (data.agents_unlinked > 0) {
                        toast += ' ' + data.agents_unlinked + ' agent(s) unlinked.';
                    }
                    if (window.Toast) {
                        window.Toast.success('Persona deleted', toast);
                    }
                    // Redirect back to personas list
                    setTimeout(function() {
                        window.location.href = '/personas';
                    }, 1000);
                } else {
                    var errData = await response.json();
                    if (window.Toast) {
                        window.Toast.error('Delete failed', errData.error || 'Could not delete persona.');
                    }
                }
            } catch (error) {
                console.error('PersonaDetail: Delete failed', error);
                if (window.Toast) {
                    window.Toast.error('Delete failed', 'Network error.');
                }
            }
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
