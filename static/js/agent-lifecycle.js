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
     * Close all open card footer kebab menus.
     */
    function closeCardKebabs() {
        var openMenus = document.querySelectorAll('.card-kebab-menu.open');
        for (var i = 0; i < openMenus.length; i++) {
            openMenus[i].classList.remove('open');
        }
        var expandedBtns = document.querySelectorAll('.card-kebab-btn[aria-expanded="true"]');
        for (var j = 0; j < expandedBtns.length; j++) {
            expandedBtns[j].setAttribute('aria-expanded', 'false');
        }
        // Lower all elevated cards
        var elevatedCards = document.querySelectorAll('article.kebab-open');
        for (var k = 0; k < elevatedCards.length; k++) {
            elevatedCards[k].classList.remove('kebab-open');
        }
        // Restore overflow on all ancestor containers
        var unclipped = document.querySelectorAll('.kebab-child-open');
        for (var m = 0; m < unclipped.length; m++) {
            unclipped[m].classList.remove('kebab-child-open');
        }
    }

    /**
     * Close the new-agent popover menu and reset to project step.
     */
    function closeNewAgentMenu() {
        var menu = document.getElementById('new-agent-menu');
        var btn = document.getElementById('new-agent-btn');
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
                closeCardKebabs();
                if (isOpen) {
                    closeNewAgentMenu();
                } else {
                    // Always reset to project step when opening
                    showProjectStep();
                    showMobileBackdrop();
                    menu.classList.add('open');
                    createBtn.setAttribute('aria-expanded', 'true');
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

        // Dashboard card footer kebab menu
        document.addEventListener('click', function(e) {
            // Kebab toggle
            var kebabBtn = e.target.closest('.card-kebab-btn');
            if (kebabBtn) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = kebabBtn.getAttribute('data-agent-id');
                var menu = document.querySelector('.card-kebab-menu[data-agent-id="' + agentId + '"]');
                // Close all other open card kebabs first
                closeCardKebabs();
                if (menu) {
                    var isOpen = !menu.classList.contains('open');
                    menu.classList.toggle('open');
                    kebabBtn.setAttribute('aria-expanded', isOpen);
                    if (isOpen) {
                        // Elevate the parent card above siblings
                        var card = kebabBtn.closest('article');
                        if (card) card.classList.add('kebab-open');
                        // Disable overflow clipping on all ancestor containers
                        var el = kebabBtn.parentElement;
                        while (el && el !== document.body) {
                            var style = window.getComputedStyle(el);
                            if (style.overflow !== 'visible' || style.overflowY !== 'visible' || style.overflowX !== 'visible') {
                                el.classList.add('kebab-child-open');
                            }
                            el = el.parentElement;
                        }
                    }
                }
                return;
            }

            // Context check (kebab menu item)
            var ctxAction = e.target.closest('.card-ctx-action');
            if (ctxAction) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = parseInt(ctxAction.getAttribute('data-agent-id'), 10);
                closeCardKebabs();
                if (agentId) checkContext(agentId);
                return;
            }

            // Chat (kebab menu item)
            var chatAction = e.target.closest('.card-chat-action');
            if (chatAction) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = parseInt(chatAction.getAttribute('data-agent-id'), 10);
                closeCardKebabs();
                if (agentId) window.location.href = '/voice?agent_id=' + agentId;
                return;
            }

            // Attach (kebab menu item)
            var attachAction = e.target.closest('.card-attach-action');
            if (attachAction) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = parseInt(attachAction.getAttribute('data-agent-id'), 10);
                closeCardKebabs();
                if (agentId && window.FocusAPI) window.FocusAPI.attachAgent(agentId);
                return;
            }

            // Agent info (kebab menu item)
            var infoAction = e.target.closest('.card-info-action');
            if (infoAction) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = parseInt(infoAction.getAttribute('data-agent-id'), 10);
                closeCardKebabs();
                if (agentId && window.AgentInfo) AgentInfo.open(agentId);
                return;
            }

            // Reconcile (kebab menu item)
            var reconcileAction = e.target.closest('.card-reconcile-action');
            if (reconcileAction) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = parseInt(reconcileAction.getAttribute('data-agent-id'), 10);
                closeCardKebabs();
                if (agentId) {
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
                return;
            }

            // Handoff button (card footer)
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

            // Kill (kebab menu item)
            var killAction = e.target.closest('.card-kill-action');
            if (killAction) {
                e.preventDefault();
                e.stopPropagation();
                var agentId = parseInt(killAction.getAttribute('data-agent-id'), 10);
                closeCardKebabs();
                if (!agentId) return;

                var heroChars = killAction.getAttribute('data-hero-chars') || '';
                var heroTrail = killAction.getAttribute('data-hero-trail') || '';
                var heroLabel = heroChars + heroTrail || ('#' + agentId);
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
                            shutdownAgent(agentId).then(function(data) {
                                if (data && data.error) {
                                    // Shutdown failed (no pane, etc.) — fall back to dismiss
                                    window.FocusAPI.dismissAgent(agentId);
                                }
                            }).catch(function() {
                                window.FocusAPI.dismissAgent(agentId);
                            });
                        }
                    });
                } else if (confirm('Shut down agent ' + heroLabel + '?')) {
                    shutdownAgent(agentId).then(function(data) {
                        if (data && data.error) {
                            window.FocusAPI.dismissAgent(agentId);
                        }
                    }).catch(function() {
                        window.FocusAPI.dismissAgent(agentId);
                    });
                }
                return;
            }

            // Close card kebabs on click outside
            if (!e.target.closest('.card-kebab-wrapper')) {
                closeCardKebabs();
            }
            // Close new-agent menu on click outside
            if (!e.target.closest('.new-agent-wrapper')) {
                closeNewAgentMenu();
            }
        });

        // iOS tap-in-scroll fix: cards sit inside overflow-y:auto columns,
        // so iOS often treats taps as scroll-start and never fires the click.
        // Track touch position and synthesize clicks for short, stationary taps.
        var _touchStartPos = null;
        var _lastTouchClick = 0;

        document.addEventListener('touchstart', function(e) {
            _touchStartPos = { x: e.touches[0].clientX, y: e.touches[0].clientY };
            // Close menus on tap outside
            if (!e.target.closest('.card-kebab-wrapper')) {
                closeCardKebabs();
            }
            if (!e.target.closest('.new-agent-wrapper')) {
                closeNewAgentMenu();
            }
        }, { passive: true });

        document.addEventListener('touchend', function(e) {
            if (!_touchStartPos) return;
            var touch = e.changedTouches[0];
            var dx = touch.clientX - _touchStartPos.x;
            var dy = touch.clientY - _touchStartPos.y;
            _touchStartPos = null;
            // If finger moved more than 10px, it was a scroll — bail
            if (Math.abs(dx) > 10 || Math.abs(dy) > 10) return;

            var kebabBtn = e.target.closest('.card-kebab-btn');
            var kebabItem = e.target.closest('.card-kebab-item');
            if (kebabBtn || kebabItem) {
                e.preventDefault();
                _lastTouchClick = Date.now();
                (kebabBtn || kebabItem).click();
            }
        });

        // Guard: suppress native click that iOS may fire after our touchend-triggered click
        document.addEventListener('click', function(e) {
            if (_lastTouchClick && Date.now() - _lastTouchClick < 500) {
                var kebab = e.target.closest('.card-kebab-btn') || e.target.closest('.card-kebab-item');
                if (kebab && !e.isTrusted) return; // skip programmatic duplicates
                if (kebab && e.isTrusted) {
                    // Native click arrived after our touchend click — suppress it
                    e.stopImmediatePropagation();
                    e.preventDefault();
                    _lastTouchClick = 0;
                    return;
                }
            }
        }, true); // capture phase — runs before the main click handler
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
