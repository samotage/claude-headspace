/**
 * Project Show page client for Claude Headspace.
 *
 * Loads project data, waypoint, brain reboot, and progress summary.
 * Handles control actions: edit, delete, pause/resume, regenerate, export.
 */

(function(global) {
    'use strict';

    var projectId = null;
    var projectSlug = null;
    var projectData = null;

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
                var response = await fetch('/api/projects/' + projectId);
                if (!response.ok) return;
                projectData = await response.json();
                this._updateAgentWarning();
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
                });
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
                var response = await fetch('/api/projects/' + projectId, {
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
                        this._escapeHtml(data.github_repo) + '" target="_blank" rel="noopener" class="text-cyan hover:underline">' +
                        this._escapeHtml(data.github_repo) + '</a>';
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
                var response = await fetch('/api/projects/' + projectId, {
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
                var response = await fetch('/api/projects/' + projectId + '/settings', {
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
                var response = await fetch('/api/projects/' + projectId + '/detect-metadata', {
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
                var response = await fetch('/api/projects/' + projectId + '/detect-metadata', {
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
                        branchEl.innerHTML = 'Branch: <span class="text-primary">' + this._escapeHtml(data.current_branch || 'Unknown') + '</span>';
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
                var response = await fetch('/api/projects/' + projectId + '/brain-reboot', {
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
                var response = await fetch('/api/projects/' + projectId + '/brain-reboot/export', {
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
                var response = await fetch('/api/projects/' + projectId + '/progress-summary', {
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

        editWaypoint: function() {
            // Open the waypoint editor modal if available, or navigate
            if (typeof openWaypointEditor === 'function') {
                openWaypointEditor(projectId);
            } else {
                // Fallback: navigate to dashboard where waypoint editor is
                window.location.href = '/?waypoint=' + projectId;
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
                            .then(function(p) { self._updateMetadataDisplay(p); });
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
        },

        // --- Utilities ---

        _renderMarkdown: function(text) {
            // Basic markdown rendering: headers, bold, italic, code blocks, lists, links
            var html = this._escapeHtml(text);

            // Code blocks (triple backtick)
            html = html.replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-surface rounded p-3 text-xs overflow-x-auto"><code>$2</code></pre>');

            // Inline code
            html = html.replace(/`([^`]+)`/g, '<code class="bg-surface px-1 rounded text-xs">$1</code>');

            // Headers
            html = html.replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold text-primary mt-4 mb-2">$1</h3>');
            html = html.replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold text-primary mt-4 mb-2">$1</h2>');
            html = html.replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-primary mt-4 mb-2">$1</h1>');

            // Bold and italic
            html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
            html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

            // Unordered lists
            html = html.replace(/^- (.+)$/gm, '<li class="ml-4">$1</li>');
            html = html.replace(/(<li.*<\/li>\n?)+/g, '<ul class="list-disc mb-2">$&</ul>');

            // Links
            html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-cyan hover:underline" target="_blank" rel="noopener">$1</a>');

            // Line breaks (double newline -> paragraph)
            html = html.replace(/\n\n/g, '</p><p class="mb-2">');
            html = '<p class="mb-2">' + html + '</p>';

            // Clean up empty paragraphs
            html = html.replace(/<p class="mb-2"><\/p>/g, '');

            return html;
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

        _escapeHtml: function(text) {
            var div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
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
