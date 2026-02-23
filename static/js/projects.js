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
                var slug = p.slug || '';

                return '<tr class="border-b border-border">' +
                    '<td class="py-3 pr-4 font-medium"><a href="/projects/' + CHUtils.escapeHtml(slug) + '" class="text-cyan hover:underline">' + CHUtils.escapeHtml(p.name) + '</a></td>' +
                    '<td class="py-3 pr-4 text-secondary text-sm font-mono truncate max-w-[200px]" title="' + CHUtils.escapeHtml(p.path) + '">' + CHUtils.escapeHtml(p.path) + '</td>' +
                    '<td class="py-3 pr-4 text-center text-secondary">' + p.agent_count + '</td>' +
                    '<td class="py-3 pr-4"><span class="' + pausedClass + ' text-sm font-medium">' + pausedLabel + '</span></td>' +
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
                this._autoResizeDescription();

                // Auto-detect empty fields
                var needsGithub = !project.github_repo;
                var needsDescription = !project.description;
                if (needsGithub || needsDescription) {
                    this._detectMetadata(project.id, needsGithub, needsDescription);
                }
            } catch (error) {
                console.error('ProjectsPage: Failed to open edit modal', error);
            }
        },

        /**
         * Auto-detect metadata for empty fields
         */
        _detectMetadata: async function(projectId, needsGithub, needsDescription) {
            var githubField = document.getElementById('project-form-github');
            var descField = document.getElementById('project-form-description');

            // Set loading placeholders
            var originalGithubPlaceholder = githubField ? githubField.placeholder : '';
            var originalDescPlaceholder = descField ? descField.placeholder : '';

            if (needsGithub && githubField) {
                githubField.placeholder = 'Detecting from git remote...';
            }
            if (needsDescription && descField) {
                descField.placeholder = 'Generating from CLAUDE.md...';
            }

            try {
                var response = await CHUtils.apiFetch(API_ENDPOINT + '/' + projectId + '/detect-metadata', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (!response.ok) return;

                var data = await response.json();

                // Only fill if field is still empty (user may have typed meanwhile)
                if (needsGithub && githubField && !githubField.value && data.github_repo) {
                    githubField.value = data.github_repo;
                }
                if (needsDescription && descField && !descField.value && data.description) {
                    descField.value = data.description;
                    ProjectsPage._autoResizeDescription();
                }
            } catch (error) {
                // Silently ignore — auto-detection is best-effort
            } finally {
                if (githubField) githubField.placeholder = originalGithubPlaceholder;
                if (descField) descField.placeholder = originalDescPlaceholder;
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

                var response = await CHUtils.apiFetch(url, {
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
                var response = await CHUtils.apiFetch(API_ENDPOINT + '/' + deleteTargetId, {
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
                var response = await CHUtils.apiFetch(API_ENDPOINT + '/' + projectId + '/settings', {
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

        /**
         * Auto-resize description textarea to fit content (min 4 rows)
         */
        _autoResizeDescription: function() {
            var el = document.getElementById('project-form-description');
            if (!el) return;
            el.style.height = 'auto';
            var lineHeight = parseFloat(getComputedStyle(el).lineHeight);
            if (isNaN(lineHeight)) lineHeight = 20;
            var minHeight = lineHeight * 4 + parseFloat(getComputedStyle(el).paddingTop) + parseFloat(getComputedStyle(el).paddingBottom);
            el.style.height = Math.max(el.scrollHeight, minHeight) + 'px';
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
