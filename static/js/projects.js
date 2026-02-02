/**
 * Projects page client for Claude Headspace.
 *
 * Handles project CRUD operations, pause/resume toggle,
 * and real-time SSE updates.
 */

(function(global) {
    'use strict';

    const API_ENDPOINT = '/api/projects';

    let deleteTargetId = null;

    const ProjectsPage = {
        /**
         * Initialize the projects page
         */
        init: function() {
            this.tbody = document.getElementById('projects-tbody');
            this.tableContainer = document.getElementById('projects-table-container');
            this.emptyState = document.getElementById('projects-empty');
            this.loadingState = document.getElementById('projects-loading');

            this.loadProjects();
            this._initSSE();
        },

        /**
         * Fetch and render project list
         */
        loadProjects: async function() {
            try {
                const response = await fetch(API_ENDPOINT);
                const projects = await response.json();

                if (this.loadingState) this.loadingState.classList.add('hidden');

                if (!response.ok) {
                    console.error('ProjectsPage: Failed to load projects', projects.error);
                    return;
                }

                if (projects.length === 0) {
                    if (this.tableContainer) this.tableContainer.classList.add('hidden');
                    if (this.emptyState) this.emptyState.classList.remove('hidden');
                    return;
                }

                if (this.tableContainer) this.tableContainer.classList.remove('hidden');
                if (this.emptyState) this.emptyState.classList.add('hidden');

                this._renderTable(projects);
            } catch (error) {
                console.error('ProjectsPage: Failed to load projects', error);
                if (this.loadingState) this.loadingState.textContent = 'Failed to load projects.';
            }
        },

        /**
         * Render project rows
         */
        _renderTable: function(projects) {
            if (!this.tbody) return;

            this.tbody.innerHTML = projects.map(function(p) {
                var pausedClass = p.inference_paused ? 'text-amber' : 'text-green';
                var pausedLabel = p.inference_paused ? 'Paused' : 'Active';
                var pauseBtnLabel = p.inference_paused ? 'Resume' : 'Pause';
                var pauseBtnClass = p.inference_paused
                    ? 'text-green hover:text-green'
                    : 'text-amber hover:text-amber';

                return '<tr class="border-b border-border">' +
                    '<td class="py-3 pr-4 text-primary font-medium">' + ProjectsPage._escapeHtml(p.name) + '</td>' +
                    '<td class="py-3 pr-4 text-secondary text-xs font-mono truncate max-w-[200px]" title="' + ProjectsPage._escapeHtml(p.path) + '">' + ProjectsPage._escapeHtml(p.path) + '</td>' +
                    '<td class="py-3 pr-4 text-center text-secondary">' + p.agent_count + '</td>' +
                    '<td class="py-3 pr-4"><span class="' + pausedClass + ' text-xs font-medium">' + pausedLabel + '</span></td>' +
                    '<td class="py-3 text-right space-x-2 whitespace-nowrap">' +
                        '<button onclick="ProjectsPage.togglePause(' + p.id + ', ' + p.inference_paused + ')" class="text-xs ' + pauseBtnClass + ' hover:underline">' + pauseBtnLabel + '</button>' +
                        '<button onclick="ProjectsPage.openEditModal(' + p.id + ')" class="text-xs text-cyan hover:underline">Edit</button>' +
                        '<button onclick="ProjectsPage.openDeleteDialog(' + p.id + ', \'' + ProjectsPage._escapeHtml(p.name).replace(/'/g, "\\'") + '\', ' + p.agent_count + ')" class="text-xs text-red hover:underline">Delete</button>' +
                    '</td>' +
                '</tr>';
            }).join('');
        },

        // --- Modal ---

        /**
         * Open modal in Add mode
         */
        openAddModal: function() {
            document.getElementById('project-form-title').textContent = 'Add Project';
            document.getElementById('project-form-submit').textContent = 'Save Project';
            document.getElementById('project-form-id').value = '';
            document.getElementById('project-form').reset();
            this._hideFormError();
            document.getElementById('project-form-modal').classList.remove('hidden');
            document.addEventListener('keydown', ProjectsPage._formModalEscHandler);
            document.getElementById('project-form-name').focus();
        },

        /**
         * Open modal in Edit mode (pre-populated)
         */
        openEditModal: async function(projectId) {
            try {
                var response = await fetch(API_ENDPOINT + '/' + projectId);
                var project = await response.json();

                if (!response.ok) {
                    console.error('ProjectsPage: Failed to fetch project', project.error);
                    return;
                }

                document.getElementById('project-form-title').textContent = 'Edit Project';
                document.getElementById('project-form-submit').textContent = 'Update Project';
                document.getElementById('project-form-id').value = project.id;
                document.getElementById('project-form-name').value = project.name || '';
                document.getElementById('project-form-path').value = project.path || '';
                document.getElementById('project-form-github').value = project.github_repo || '';
                document.getElementById('project-form-description').value = project.description || '';
                this._hideFormError();
                document.getElementById('project-form-modal').classList.remove('hidden');
                document.addEventListener('keydown', ProjectsPage._formModalEscHandler);
                document.getElementById('project-form-name').focus();
            } catch (error) {
                console.error('ProjectsPage: Failed to open edit modal', error);
            }
        },

        /**
         * Close the form modal
         */
        closeFormModal: function() {
            document.getElementById('project-form-modal').classList.add('hidden');
            document.removeEventListener('keydown', ProjectsPage._formModalEscHandler);
        },

        /**
         * Esc key handler for form modal
         */
        _formModalEscHandler: function(e) {
            if (e.key === 'Escape') {
                ProjectsPage.closeFormModal();
            }
        },

        /**
         * Submit the project form (create or update)
         */
        submitProject: async function() {
            var projectId = document.getElementById('project-form-id').value;
            var isEdit = !!projectId;

            var payload = {
                name: document.getElementById('project-form-name').value.trim(),
                path: document.getElementById('project-form-path').value.trim(),
                github_repo: document.getElementById('project-form-github').value.trim() || null,
                description: document.getElementById('project-form-description').value.trim() || null
            };

            if (!payload.name || !payload.path) {
                this._showFormError('Name and Path are required.');
                return;
            }

            try {
                var url = isEdit ? API_ENDPOINT + '/' + projectId : API_ENDPOINT;
                var method = isEdit ? 'PUT' : 'POST';

                var response = await fetch(url, {
                    method: method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                var data = await response.json();

                if (!response.ok) {
                    this._showFormError(data.error || 'Failed to save project.');
                    return;
                }

                this.closeFormModal();
                this.loadProjects();
            } catch (error) {
                console.error('ProjectsPage: Submit failed', error);
                this._showFormError('Network error. Please try again.');
            }
        },

        _showFormError: function(message) {
            var el = document.getElementById('project-form-error');
            if (el) {
                el.textContent = message;
                el.classList.remove('hidden');
            }
        },

        _hideFormError: function() {
            var el = document.getElementById('project-form-error');
            if (el) {
                el.textContent = '';
                el.classList.add('hidden');
            }
        },

        // --- Delete ---

        /**
         * Open delete confirmation dialog
         */
        openDeleteDialog: function(projectId, projectName, agentCount) {
            deleteTargetId = projectId;
            document.getElementById('delete-project-name').textContent = projectName;

            var warning = document.getElementById('delete-agent-warning');
            if (warning) {
                if (agentCount > 0) {
                    warning.textContent = 'This will also delete ' + agentCount + ' agent(s) associated with this project.';
                } else {
                    warning.textContent = '';
                }
            }

            document.getElementById('delete-dialog').classList.remove('hidden');
        },

        /**
         * Close delete confirmation dialog
         */
        closeDeleteDialog: function() {
            deleteTargetId = null;
            document.getElementById('delete-dialog').classList.add('hidden');
        },

        /**
         * Confirm and execute deletion
         */
        confirmDelete: async function() {
            if (!deleteTargetId) return;

            try {
                var response = await fetch(API_ENDPOINT + '/' + deleteTargetId, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    this.closeDeleteDialog();
                    this.loadProjects();
                } else {
                    var data = await response.json();
                    console.error('ProjectsPage: Delete failed', data.error);
                }
            } catch (error) {
                console.error('ProjectsPage: Delete failed', error);
            }
        },

        // --- Pause/Resume ---

        /**
         * Toggle inference pause state
         */
        togglePause: async function(projectId, currentPaused) {
            try {
                var response = await fetch(API_ENDPOINT + '/' + projectId + '/settings', {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ inference_paused: !currentPaused })
                });

                if (response.ok) {
                    this.loadProjects();
                } else {
                    var data = await response.json();
                    console.error('ProjectsPage: Toggle pause failed', data.error);
                }
            } catch (error) {
                console.error('ProjectsPage: Toggle pause failed', error);
            }
        },

        // --- SSE ---

        /**
         * Initialize SSE listeners for real-time updates
         */
        _initSSE: function() {
            var client = window.headerSSEClient;
            if (!client) return;

            var self = this;

            client.on('project_changed', function() {
                self.loadProjects();
            });

            client.on('project_settings_changed', function() {
                self.loadProjects();
            });
        },

        // --- Utility ---

        _escapeHtml: function(text) {
            var div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { ProjectsPage.init(); });
    } else {
        ProjectsPage.init();
    }

    global.ProjectsPage = ProjectsPage;

})(typeof window !== 'undefined' ? window : this);
