/**
 * Agent Lifecycle controls for the Dashboard.
 *
 * Handles:
 * - Creating new agents via the "New Agent" control
 * - Shutting down agents via kill buttons on cards
 * - Checking context usage via ctx buttons on cards
 */

(function(global) {
    'use strict';

    var API_BASE = '/api/agents';

    /**
     * Create a new agent for a project.
     * @param {number} projectId - The project ID
     * @returns {Promise}
     */
    function createAgent(projectId) {
        return CHUtils.apiFetch(API_BASE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_id: projectId })
        }).then(function(res) {
            return res.json().then(function(data) {
                if (res.ok) {
                    if (global.Toast) {
                        global.Toast.success('Agent starting', data.message || 'Agent creation initiated');
                    }
                } else {
                    if (global.Toast) {
                        global.Toast.error('Create failed', data.error || 'Unknown error');
                    }
                }
                return data;
            });
        });
    }

    /**
     * Shut down an agent gracefully.
     * @param {number} agentId - The agent ID
     * @returns {Promise}
     */
    function shutdownAgent(agentId) {
        return CHUtils.apiFetch(API_BASE + '/' + agentId, {
            method: 'DELETE'
        }).then(function(res) {
            return res.json().then(function(data) {
                if (res.ok) {
                    if (global.Toast) {
                        global.Toast.success('Shutdown sent', data.message || 'Agent shutting down');
                    }
                } else {
                    if (global.Toast) {
                        global.Toast.error('Shutdown failed', data.error || 'Unknown error');
                    }
                }
                return data;
            });
        });
    }

    /**
     * Fetch context usage for an agent and display it.
     * @param {number} agentId - The agent ID
     */
    function checkContext(agentId) {
        var display = document.querySelector('.agent-ctx-display[data-agent-id="' + agentId + '"]');
        if (!display) return;

        display.classList.remove('hidden');
        display.textContent = 'Checking...';
        display.className = 'agent-ctx-display px-3 py-1 text-xs text-muted';

        fetch(API_BASE + '/' + agentId + '/context')
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (data.available) {
                    var pct = data.percent_used;
                    var colorClass = pct >= 80 ? 'text-red' : pct >= 60 ? 'text-amber' : 'text-green';
                    display.innerHTML = '<span class="' + colorClass + ' font-medium">' + pct + '% used</span>' +
                        ' <span class="text-muted">\u00B7</span> ' +
                        '<span class="text-secondary">' + data.remaining_tokens + ' remaining</span>';
                } else {
                    display.textContent = 'Context unavailable';
                    display.className = 'agent-ctx-display px-3 py-1 text-xs text-muted italic';
                }
            })
            .catch(function() {
                display.textContent = 'Error checking context';
                display.className = 'agent-ctx-display px-3 py-1 text-xs text-red italic';
            });
    }

    /**
     * Initialize event handlers.
     */
    function init() {
        // New Agent control
        var projectSelect = document.getElementById('new-agent-project');
        var createBtn = document.getElementById('new-agent-btn');

        if (projectSelect && createBtn) {
            // Enable button when project is selected
            projectSelect.addEventListener('change', function() {
                createBtn.disabled = !this.value;
            });

            createBtn.addEventListener('click', function() {
                var projectId = parseInt(projectSelect.value, 10);
                if (!projectId) return;

                createBtn.disabled = true;
                createBtn.textContent = 'Starting...';

                createAgent(projectId).then(function() {
                    projectSelect.value = '';
                    createBtn.textContent = '+ Agent';
                    createBtn.disabled = true;
                }).catch(function() {
                    createBtn.textContent = '+ Agent';
                    createBtn.disabled = false;
                });
            });
        }

        // Delegate click events for ctx and kill buttons on agent cards
        document.addEventListener('click', function(e) {
            // Context check button
            var ctxBtn = e.target.closest('.agent-ctx-btn');
            if (ctxBtn) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = parseInt(ctxBtn.getAttribute('data-agent-id'), 10);
                if (agentId) checkContext(agentId);
                return;
            }

            // Kill button
            var killBtn = e.target.closest('.agent-kill-btn');
            if (killBtn) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = parseInt(killBtn.getAttribute('data-agent-id'), 10);
                if (!agentId) return;

                if (typeof ConfirmDialog !== 'undefined') {
                    ConfirmDialog.show({
                        title: 'Shut down agent?',
                        message: 'This will send /exit to the agent. It will clean up and fire shutdown hooks.',
                        confirmText: 'Shut down',
                        cancelText: 'Cancel',
                        variant: 'danger',
                        onConfirm: function() {
                            shutdownAgent(agentId);
                        }
                    });
                } else if (confirm('Shut down this agent?')) {
                    shutdownAgent(agentId);
                }
                return;
            }
        });
    }

    // Export
    global.AgentLifecycle = {
        init: init,
        createAgent: createAgent,
        shutdownAgent: shutdownAgent,
        checkContext: checkContext
    };

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})(typeof window !== 'undefined' ? window : this);
