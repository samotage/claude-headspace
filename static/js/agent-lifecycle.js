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
     * Close the new-agent popover menu.
     */
    function closeNewAgentMenu() {
        var menu = document.getElementById('new-agent-menu');
        var btn = document.getElementById('new-agent-btn');
        if (menu) menu.classList.remove('open');
        if (btn) btn.setAttribute('aria-expanded', 'false');
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
                    menu.classList.add('open');
                    createBtn.setAttribute('aria-expanded', 'true');
                }
            });

            // Handle project item clicks
            menu.addEventListener('click', function(e) {
                var item = e.target.closest('.new-agent-item');
                if (!item) return;
                e.stopPropagation();

                var projectId = parseInt(item.getAttribute('data-project-id'), 10);
                if (!projectId) return;

                var originalText = item.textContent;
                item.textContent = 'Starting...';
                item.style.pointerEvents = 'none';

                createAgent(projectId).then(function() {
                    closeNewAgentMenu();
                    item.textContent = originalText;
                    item.style.pointerEvents = '';
                }).catch(function() {
                    item.textContent = originalText;
                    item.style.pointerEvents = '';
                    closeNewAgentMenu();
                });
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
