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
        mode: 'view'  // 'view' | 'edit' | 'preview'
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

        /**
         * Fetch linked agents and render a table.
         */
        loadLinkedAgents: async function() {
            try {
                var response = await fetch(API_BASE + '/agents');
                if (!response.ok) {
                    document.getElementById('agents-list').innerHTML =
                        '<p class="text-red italic">Failed to load agents.</p>';
                    return;
                }

                var agents = await response.json();

                if (agents.length === 0) {
                    document.getElementById('agents-list').innerHTML =
                        '<p class="text-muted italic">No agents linked to this persona.</p>';
                    return;
                }

                var html = '<table class="w-full text-sm">' +
                    '<thead>' +
                    '<tr class="border-b border-border text-left text-muted text-xs uppercase tracking-wider">' +
                    '<th class="pb-2 pr-4">Session</th>' +
                    '<th class="pb-2 pr-4">Project</th>' +
                    '<th class="pb-2 pr-4">State</th>' +
                    '<th class="pb-2 pr-4">Last Seen</th>' +
                    '</tr>' +
                    '</thead><tbody>';

                agents.forEach(function(a) {
                    var sessionShort = a.session_uuid ? a.session_uuid.substring(0, 8) : 'N/A';
                    var project = a.project_name || 'Unknown';
                    var agentState = a.state || 'unknown';
                    var lastSeen = a.last_seen_at ? new Date(a.last_seen_at).toLocaleString() : 'N/A';

                    html += '<tr class="border-b border-border/50">' +
                        '<td class="py-2 pr-4 font-mono text-primary">' + CHUtils.escapeHtml(sessionShort) + '</td>' +
                        '<td class="py-2 pr-4 text-secondary">' + CHUtils.escapeHtml(project) + '</td>' +
                        '<td class="py-2 pr-4 text-secondary">' + CHUtils.escapeHtml(agentState) + '</td>' +
                        '<td class="py-2 pr-4 text-muted">' + CHUtils.escapeHtml(lastSeen) + '</td>' +
                        '</tr>';
                });

                html += '</tbody></table>';
                document.getElementById('agents-list').innerHTML = html;
            } catch (error) {
                console.error('PersonaDetail: Failed to load agents', error);
                document.getElementById('agents-list').innerHTML =
                    '<p class="text-red italic">Error loading agents.</p>';
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
