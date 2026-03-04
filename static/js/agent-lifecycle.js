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
     * Create a new agent for a project, optionally with a persona.
     * @param {number} projectId - The project ID
     * @param {string|null} personaSlug - Optional persona slug
     * @returns {Promise}
     */
    function createAgent(projectId, personaSlug) {
        var body = { project_id: projectId };
        if (personaSlug) {
            body.persona_slug = personaSlug;
        }
        return CHUtils.apiFetch(API_BASE, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
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
     * Fetch context usage for an agent.
     * The API persists the result and broadcasts a card_refresh via SSE,
     * so the persistent footer display updates automatically.
     * @param {number} agentId - The agent ID
     */
    function checkContext(agentId) {
        fetch(API_BASE + '/' + agentId + '/context')
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (!data.available && global.Toast) {
                    global.Toast.error('Context unavailable', data.reason || 'Unknown');
                }
            })
            .catch(function() {
                if (global.Toast) {
                    global.Toast.error('Context check failed', 'Could not reach server');
                }
            });
    }

    /**
     * Revive a dead agent by creating a successor.
     * @param {number} agentId - The agent ID to revive
     * @returns {Promise}
     */
    function reviveAgent(agentId) {
        return CHUtils.apiFetch(API_BASE + '/' + agentId + '/revive', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        }).then(function(res) {
            return res.json().then(function(data) {
                if (res.ok) {
                    if (global.Toast) {
                        global.Toast.success('Revival initiated', data.message || 'Successor agent starting');
                    }
                } else {
                    if (global.Toast) {
                        global.Toast.error('Revival failed', data.error || 'Unknown error');
                    }
                }
                return data;
            });
        });
    }

    /**
     * Initiate a handoff for an agent via the API.
     * @param {number} agentId - The agent ID
     */
    function _doHandoff(agentId) {
        CHUtils.apiFetch(API_BASE + '/' + agentId + '/handoff', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: 'manual' })
        }).then(function(res) {
            return res.json().then(function(data) {
                if (res.ok) {
                    if (global.Toast) {
                        global.Toast.success('Handoff', data.message || 'Handoff initiated — agent writing handoff document');
                    }
                } else {
                    if (global.Toast) {
                        global.Toast.error('Handoff', data.error || 'Handoff failed');
                    }
                }
                return data;
            });
        }).catch(function() {
            if (global.Toast) {
                global.Toast.error('Handoff', 'Could not reach server');
            }
        });
    }

    /**
     * Dismiss an agent via the API without touching the DOM.
     * Used as a fallback when shutdownAgent fails — the card is already gone.
     */
    function _silentDismiss(agentId) {
        return CHUtils.apiFetch('/api/agents/' + agentId + '/dismiss', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        }).catch(function(err) {
            console.error('Silent dismiss failed for agent ' + agentId, err);
        });
    }

    /**
     * Build the action list for a dashboard agent card kebab menu.
     * Reads data attributes from the trigger button to determine available actions.
     */
    function buildDashboardActions(btn) {
        var I = (typeof PortalKebabMenu !== 'undefined') ? PortalKebabMenu.ICONS : {};
        var actions = [
            { id: 'chat', label: 'Chat', icon: I.chat || '' },
            { id: 'dismiss', label: 'Dismiss agent', icon: I.dismiss || '', className: 'kill-action' },
            'divider',
            { id: 'download-transcript', label: 'Download Transcript', icon: I.download || '' },
        ];
        if (btn.getAttribute('data-tmux-session')) {
            actions.push({ id: 'attach', label: 'Attach', icon: I.attach || '' });
        }
        actions.push({ id: 'context', label: 'Fetch context', icon: I.context || '' });
        actions.push({ id: 'info', label: 'Agent info', icon: I.info || '' });
        actions.push({ id: 'reconcile', label: 'Reconcile', icon: I.reconcile || '' });
        if (btn.getAttribute('data-persona-name')) {
            actions.push({ id: 'handoff', label: 'Handoff', icon: I.handoff || '', className: 'handoff-action' });
        }
        return actions;
    }

    /**
     * Handle a dashboard kebab menu action.
     */
    function handleDashboardAction(actionId, agentId) {
        switch (actionId) {
            case 'chat':
                window.location.href = '/voice?agent_id=' + agentId;
                break;
            case 'dismiss':
                _confirmAndDismiss(agentId);
                break;
            case 'download-transcript':
                if (global.Toast) global.Toast.success('Transcript', 'Preparing transcript\u2026');
                window.open('/api/agents/' + agentId + '/transcript', '_blank');
                break;
            case 'attach':
                if (window.FocusAPI) window.FocusAPI.attachAgent(agentId);
                break;
            case 'context':
                checkContext(agentId);
                break;
            case 'info':
                if (window.AgentInfo) AgentInfo.open(agentId);
                break;
            case 'reconcile':
                _doReconcile(agentId);
                break;
            case 'handoff':
                _confirmAndHandoff(agentId);
                break;
        }
    }

    /**
     * Confirm and dismiss (shutdown) an agent from the kebab menu.
     */
    function _confirmAndDismiss(agentId) {
        // Read hero from the card's kebab button data attributes
        var btn = document.querySelector('.card-kebab-btn[data-agent-id="' + agentId + '"]');
        var heroChars = btn ? btn.getAttribute('data-hero-chars') || '' : '';
        var heroTrail = btn ? btn.getAttribute('data-hero-trail') || '' : '';
        var heroLabel = heroChars + heroTrail || ('#' + agentId);

        function _immediateRemoveAndShutdown(aid, label) {
            var card = document.querySelector('article[data-agent-id="' + aid + '"]');
            if (card) {
                card.style.transition = 'opacity 0.3s, transform 0.3s';
                card.style.opacity = '0';
                card.style.transform = 'scale(0.95)';
                setTimeout(function() { card.remove(); }, 300);
            }
            if (global.Toast) {
                global.Toast.success('Shutting down', 'Agent ' + label + ' dismissed');
            }
            global._agentOperationInProgress = true;
            shutdownAgent(aid).then(function(data) {
                if (data && data.error) {
                    return _silentDismiss(aid);
                }
            }).catch(function() {
                return _silentDismiss(aid);
            }).finally(function() {
                global._agentOperationInProgress = false;
                if (global._sseReloadDeferred) {
                    var deferred = global._sseReloadDeferred;
                    global._sseReloadDeferred = null;
                    deferred();
                }
            });
        }

        if (typeof ConfirmDialog !== 'undefined') {
            var styledTitle = heroChars
                ? 'Shut down agent ' + CHUtils.heroHTML(heroChars, heroTrail) + '?'
                : 'Shut down agent #' + agentId + '?';
            ConfirmDialog.show(
                'Shut down agent ' + heroLabel + '?',
                'This will send /exit to the agent. It will clean up and fire shutdown hooks.',
                { titleHTML: styledTitle, confirmText: 'Shut down', cancelText: 'Cancel' }
            ).then(function(confirmed) {
                if (confirmed) {
                    _immediateRemoveAndShutdown(agentId, heroLabel);
                }
            });
        } else if (confirm('Shut down agent ' + heroLabel + '?')) {
            _immediateRemoveAndShutdown(agentId, heroLabel);
        }
    }

    /**
     * Confirm and trigger a handoff from the kebab menu.
     */
    function _confirmAndHandoff(agentId) {
        if (typeof ConfirmDialog !== 'undefined') {
            ConfirmDialog.show(
                'Handoff this agent?',
                'The agent will write a handoff document and a successor agent will be created with the same persona. The current agent will remain alive.',
                { confirmText: 'Handoff', cancelText: 'Cancel' }
            ).then(function(confirmed) {
                if (confirmed) _doHandoff(agentId);
            });
        } else if (confirm('Handoff this agent? A successor will be created.')) {
            _doHandoff(agentId);
        }
    }

    /**
     * Trigger reconcile for an agent.
     */
    function _doReconcile(agentId) {
        fetch('/api/agents/' + agentId + '/reconcile', { method: 'POST' })
            .then(function(r) { return r.json().then(function(d) { return { data: d, status: r.status }; }); })
            .then(function(res) {
                if (global.Toast) {
                    if (res.status === 409) {
                        global.Toast.info('Reconcile', 'Already in progress');
                    } else if (res.data.created > 0) {
                        global.Toast.success('Reconciled', res.data.created + ' turn(s) recovered');
                    } else {
                        global.Toast.info('Reconcile', 'No missing turns found');
                    }
                }
            })
            .catch(function() {
                if (global.Toast) global.Toast.error('Reconcile failed', 'Could not reach server');
            });
    }

    /**
     * Keyboard-aware positioning for the mobile bottom sheet.
     * iOS keeps the keyboard visible even after blurring if the timing
     * is tight. This watches visualViewport and pushes the sheet up.
     */
    var _keyboardWatchHandler = null;

    function _startKeyboardWatch(menuEl) {
        if (window.innerWidth > 640 || !window.visualViewport) return;
        _stopKeyboardWatch(menuEl);
        _keyboardWatchHandler = function() {
            var vv = window.visualViewport;
            var keyboardHeight = window.innerHeight - vv.height - vv.offsetTop;
            if (keyboardHeight > 50) {
                menuEl.style.bottom = keyboardHeight + 'px';
            } else {
                menuEl.style.bottom = '';
            }
        };
        window.visualViewport.addEventListener('resize', _keyboardWatchHandler);
        window.visualViewport.addEventListener('scroll', _keyboardWatchHandler);
        // Apply immediately in case keyboard is already visible
        _keyboardWatchHandler();
    }

    function _stopKeyboardWatch(menuEl) {
        if (_keyboardWatchHandler && window.visualViewport) {
            window.visualViewport.removeEventListener('resize', _keyboardWatchHandler);
            window.visualViewport.removeEventListener('scroll', _keyboardWatchHandler);
            _keyboardWatchHandler = null;
        }
        if (menuEl) menuEl.style.bottom = '';
    }

    /**
     * Close the new-agent popover menu and reset to project step.
     */
    function closeNewAgentMenu() {
        var menu = document.getElementById('new-agent-menu');
        var btn = document.getElementById('new-agent-btn');
        _stopKeyboardWatch(menu);
        if (menu) menu.classList.remove('open');
        if (btn) btn.setAttribute('aria-expanded', 'false');
        // Reset to project step for next open
        var projectStep = document.getElementById('new-agent-step-project');
        var personaStep = document.getElementById('new-agent-step-persona');
        if (projectStep) projectStep.style.display = '';
        if (personaStep) personaStep.style.display = 'none';
        // Remove mobile backdrop if present
        var backdrop = document.getElementById('new-agent-backdrop');
        if (backdrop) backdrop.remove();
    }

    /**
     * Show mobile backdrop overlay behind the bottom-sheet menu.
     */
    function showMobileBackdrop() {
        if (window.innerWidth > 640) return;
        var existing = document.getElementById('new-agent-backdrop');
        if (existing) return;
        var backdrop = document.createElement('div');
        backdrop.id = 'new-agent-backdrop';
        backdrop.style.cssText = 'position:fixed;inset:0;background:rgba(0,0,0,0.5);z-index:49;';
        backdrop.addEventListener('click', function() { closeNewAgentMenu(); });
        document.body.appendChild(backdrop);
    }

    // Track the selected project ID for two-step flow
    var _selectedProjectId = null;
    // Cache fetched personas
    var _personasCache = null;

    /**
     * Fetch active personas from the API (cached).
     * @returns {Promise<Array>}
     */
    function fetchActivePersonas() {
        if (_personasCache !== null) {
            return Promise.resolve(_personasCache);
        }
        return CHUtils.apiFetch('/api/personas/active')
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (Array.isArray(data)) {
                    _personasCache = data;
                    return data;
                }
                return [];
            })
            .catch(function() { return []; });
    }

    /**
     * Render the persona selector list grouped by role.
     * @param {Array} personas - Active personas from API
     */
    function renderPersonaSelector(personas) {
        var container = document.getElementById('new-agent-persona-list');
        if (!container) return;

        // Keep the "No persona" default button, remove any dynamic content
        var defaultBtn = container.querySelector('.new-agent-persona-item[data-persona-slug=""]');
        container.innerHTML = '';
        if (defaultBtn) {
            container.appendChild(defaultBtn);
        } else {
            var noPersonaBtn = document.createElement('button');
            noPersonaBtn.className = 'new-agent-item new-agent-persona-item';
            noPersonaBtn.setAttribute('data-persona-slug', '');
            noPersonaBtn.textContent = 'No persona (default)';
            container.appendChild(noPersonaBtn);
        }

        // Group by role
        var grouped = {};
        for (var i = 0; i < personas.length; i++) {
            var p = personas[i];
            var role = p.role || 'other';
            if (!grouped[role]) grouped[role] = [];
            grouped[role].push(p);
        }

        // Render groups
        var roles = Object.keys(grouped).sort();
        for (var r = 0; r < roles.length; r++) {
            var roleName = roles[r];
            var header = document.createElement('div');
            header.className = 'new-agent-persona-role-header';
            header.textContent = roleName;
            container.appendChild(header);

            var group = grouped[roleName];
            for (var j = 0; j < group.length; j++) {
                var persona = group[j];
                var btn = document.createElement('button');
                btn.className = 'new-agent-item new-agent-persona-item';
                btn.setAttribute('data-persona-slug', persona.slug);
                var nameSpan = document.createTextNode(persona.name);
                btn.appendChild(nameSpan);
                if (persona.description) {
                    var desc = document.createElement('div');
                    desc.className = 'new-agent-persona-desc';
                    desc.textContent = persona.description;
                    btn.appendChild(desc);
                }
                container.appendChild(btn);
            }
        }
    }

    /**
     * Show the persona selection step.
     */
    function showPersonaStep() {
        var projectStep = document.getElementById('new-agent-step-project');
        var personaStep = document.getElementById('new-agent-step-persona');
        if (projectStep) projectStep.style.display = 'none';
        if (personaStep) personaStep.style.display = '';
    }

    /**
     * Show the project selection step (reset).
     */
    function showProjectStep() {
        var projectStep = document.getElementById('new-agent-step-project');
        var personaStep = document.getElementById('new-agent-step-persona');
        if (projectStep) projectStep.style.display = '';
        if (personaStep) personaStep.style.display = 'none';
        _selectedProjectId = null;
    }

    /**
     * Initialize event handlers.
     */
    function init() {
        // New Agent popover control
        var createBtn = document.getElementById('new-agent-btn');
        var menu = document.getElementById('new-agent-menu');

        if (createBtn && menu) {
            // Toggle popover on button click
            createBtn.addEventListener('click', function(e) {
                e.stopPropagation();
                var isOpen = menu.classList.contains('open');
                // Close card kebabs if any are open
                if (typeof PortalKebabMenu !== 'undefined') PortalKebabMenu.close();
                if (isOpen) {
                    closeNewAgentMenu();
                } else {
                    // Dismiss iOS keyboard before opening the bottom sheet —
                    // a focused respond-widget input keeps the keyboard visible
                    // and it covers the persona selector on iPhone.
                    if (document.activeElement && document.activeElement !== document.body) {
                        document.activeElement.blur();
                    }
                    // Always reset to project step when opening
                    showProjectStep();
                    showMobileBackdrop();
                    menu.classList.add('open');
                    createBtn.setAttribute('aria-expanded', 'true');
                    _startKeyboardWatch(menu);
                }
            });

            // Handle project item clicks — transition to persona step
            menu.addEventListener('click', function(e) {
                // Project selection (step 1)
                var projectItem = e.target.closest('.new-agent-project-item');
                if (projectItem) {
                    e.stopPropagation();
                    var projectId = parseInt(projectItem.getAttribute('data-project-id'), 10);
                    if (!projectId) return;

                    _selectedProjectId = projectId;

                    // Fetch personas and show step 2
                    fetchActivePersonas().then(function(personas) {
                        if (personas.length === 0) {
                            // No personas — create agent directly without persona
                            var originalText = projectItem.textContent;
                            projectItem.textContent = 'Starting...';
                            projectItem.style.pointerEvents = 'none';

                            createAgent(projectId).then(function() {
                                closeNewAgentMenu();
                                projectItem.textContent = originalText;
                                projectItem.style.pointerEvents = '';
                            }).catch(function() {
                                projectItem.textContent = originalText;
                                projectItem.style.pointerEvents = '';
                                closeNewAgentMenu();
                            });
                        } else {
                            renderPersonaSelector(personas);
                            showPersonaStep();
                        }
                    });
                    return;
                }

                // Persona selection (step 2)
                var personaItem = e.target.closest('.new-agent-persona-item');
                if (personaItem && _selectedProjectId) {
                    e.stopPropagation();
                    var personaSlug = personaItem.getAttribute('data-persona-slug') || null;

                    var originalText = personaItem.textContent;
                    personaItem.textContent = 'Starting...';
                    personaItem.style.pointerEvents = 'none';

                    createAgent(_selectedProjectId, personaSlug).then(function() {
                        closeNewAgentMenu();
                        personaItem.textContent = originalText;
                        personaItem.style.pointerEvents = '';
                    }).catch(function() {
                        personaItem.textContent = originalText;
                        personaItem.style.pointerEvents = '';
                        closeNewAgentMenu();
                    });
                    return;
                }

                // Back button
                var backBtn = e.target.closest('#new-agent-back-btn');
                if (backBtn) {
                    e.stopPropagation();
                    showProjectStep();
                    return;
                }
            });

            // Close on Escape
            document.addEventListener('keydown', function(e) {
                if (e.key === 'Escape') closeNewAgentMenu();
            });
        }

        // Dashboard card footer kebab menu (portal-based)
        document.addEventListener('click', function(e) {
            // Kebab toggle via portal
            var kebabBtn = e.target.closest('.card-kebab-btn');
            if (kebabBtn) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = parseInt(kebabBtn.getAttribute('data-agent-id'), 10);
                if (typeof PortalKebabMenu !== 'undefined' && PortalKebabMenu.isOpen()) {
                    PortalKebabMenu.close();
                    return;
                }
                if (typeof PortalKebabMenu !== 'undefined') {
                    PortalKebabMenu.open(kebabBtn, {
                        agentId: agentId,
                        actions: buildDashboardActions(kebabBtn),
                        onAction: handleDashboardAction
                    });
                }
                return;
            }

            // Handoff button (card footer — not in kebab menu)
            var handoffAction = e.target.closest('.handoff-btn');
            if (handoffAction) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = parseInt(handoffAction.getAttribute('data-agent-id'), 10);
                if (agentId && !handoffAction.disabled) {
                    handoffAction.disabled = true;
                    handoffAction.classList.add('loading');
                    handoffAction.textContent = 'Handing off\u2026';
                    fetch('/api/agents/' + agentId + '/handoff', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ reason: 'context_limit' })
                    })
                    .then(function(r) { return r.json().then(function(d) { return { data: d, status: r.status }; }); })
                    .then(function(res) {
                        if (res.status >= 200 && res.status < 300) {
                            if (global.Toast) global.Toast.success('Handoff', 'Handoff initiated');
                        } else {
                            if (global.Toast) global.Toast.error('Handoff', res.data.error || 'Handoff failed');
                            handoffAction.disabled = false;
                            handoffAction.classList.remove('loading');
                            handoffAction.textContent = 'Handoff';
                        }
                    })
                    .catch(function() {
                        if (global.Toast) global.Toast.error('Handoff', 'Could not reach server');
                        handoffAction.disabled = false;
                        handoffAction.classList.remove('loading');
                        handoffAction.textContent = 'Handoff';
                    });
                }
                return;
            }

            // Close portal menu on click outside
            if (typeof PortalKebabMenu !== 'undefined' && PortalKebabMenu.isOpen()) {
                PortalKebabMenu.close();
            }
            // Close new-agent menu on click outside
            if (!e.target.closest('.new-agent-wrapper')) {
                closeNewAgentMenu();
            }
        });
    }

    // Export
    global.AgentLifecycle = {
        init: init,
        createAgent: createAgent,
        shutdownAgent: shutdownAgent,
        checkContext: checkContext,
        reviveAgent: reviveAgent
    };

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})(typeof window !== 'undefined' ? window : this);
