/**
 * Dashboard SSE integration for Claude Headspace.
 *
 * Handles real-time updates via Server-Sent Events:
 * - Agent state changes
 * - Turn created events
 * - Agent activity updates
 * - Session end events
 *
 * Updates DOM elements:
 * - Status counts in header
 * - State indicator dots on project groups
 * - Agent card state bars, status badges, task summaries
 * - Recommended next panel
 * - Connection status indicator
 */

(function(global) {
    'use strict';

    // State info mapping (matches Python get_state_info)
    const STATE_INFO = {
        'IDLE': { color: 'green', bg_class: 'bg-green', label: 'Idle - ready for task' },
        'COMMANDED': { color: 'yellow', bg_class: 'bg-amber', label: 'Command received' },
        'PROCESSING': { color: 'blue', bg_class: 'bg-blue', label: 'Processing...' },
        'AWAITING_INPUT': { color: 'orange', bg_class: 'bg-amber', label: 'Input needed' },
        'COMPLETE': { color: 'green', bg_class: 'bg-green', label: 'Task complete' },
        'TIMED_OUT': { color: 'red', bg_class: 'bg-red', label: 'Timed out' }
    };

    // Track agent states for recalculating counts
    let agentStates = new Map();

    /**
     * Safe reload that defers if a ConfirmDialog is open.
     * Prevents SSE-triggered reloads from flashing/dismissing confirm dialogs.
     */
    function safeDashboardReload() {
        if (typeof ConfirmDialog !== 'undefined' && ConfirmDialog.isOpen()) {
            console.log('SSE reload deferred — ConfirmDialog is open');
            window._sseReloadDeferred = function() {
                window.location.reload();
            };
            return;
        }
        window.location.reload();
    }

    /**
     * Initialize the dashboard SSE client.
     * Uses the shared SSE connection from header-sse.js (window.headerSSEClient).
     */
    function initDashboardSSE() {
        var client = window.headerSSEClient;
        if (!client) {
            console.error('Shared SSE client not available (headerSSEClient)');
            return null;
        }

        // Reload page on reconnect to catch up on missed events
        client.onStateChange(function(newState, oldState) {
            console.log('SSE state:', oldState, '->', newState);
            if (newState === 'connected' && oldState === 'reconnecting') {
                console.log('SSE reconnected after drop — reloading to sync state');
                safeDashboardReload();
            }
        });

        // Handle agent state changes
        client.on('state_changed', handleStateTransition);
        client.on('state_transition', handleStateTransition);
        client.on('agent_state_changed', handleStateTransition);

        // Handle turn created
        client.on('turn_detected', handleTurnCreated);
        client.on('turn_created', handleTurnCreated);

        // Handle agent activity
        client.on('agent_updated', handleAgentActivity);
        client.on('agent_activity', handleAgentActivity);

        // Handle session end
        client.on('session_ended', handleSessionEnded);

        // Handle session lifecycle changes that require page refresh
        client.on('session_created', handleSessionCreated);

        // Handle summary updates
        client.on('task_summary', handleTaskSummary);
        client.on('turn_summary', handleTurnSummary);
        client.on('instruction_summary', handleInstructionSummary);

        // Handle priority score updates
        client.on('priority_update', handlePriorityUpdate);

        // Handle full card refresh (authoritative state from server)
        client.on('card_refresh', handleCardRefresh);

        // Handle priority toggle
        client.on('priority_toggle', handlePriorityToggle);

        // Handle commander availability changes (Input Bridge)
        client.on('commander_availability', handleCommanderAvailability);

        // DEBUG: Wildcard handler to see ALL events
        client.on('*', function(data, eventType) {
            console.log('[DEBUG] SSE EVENT RECEIVED:', eventType, JSON.stringify(data));
        });

        return client;
    }

    /**
     * Handle agent state transition events
     */
    function handleStateTransition(data, eventType) {
        const agentId = data.agent_id;
        const newState = data.new_state || data.state;

        console.log('[DEBUG] handleStateTransition called:', {
            eventType: eventType,
            rawData: JSON.stringify(data),
            agentId: agentId,
            agentIdType: typeof agentId,
            newState: newState,
            newStateType: typeof newState,
        });

        if (!agentId || !newState) {
            console.warn('[DEBUG] Invalid state transition event (missing agentId or newState):', data);
            return;
        }

        // Update tracked state
        const oldState = agentStates.get(agentId);
        console.log('[DEBUG] agentStates lookup:', {
            agentId: agentId,
            agentIdType: typeof agentId,
            oldState: oldState,
            mapSize: agentStates.size,
            mapKeys: Array.from(agentStates.keys()).map(k => `${k} (${typeof k})`),
        });
        agentStates.set(agentId, newState);

        // Update agent card and recommended panel
        updateAgentCardState(agentId, newState);
        updateRecommendedPanel(agentId, newState);

        // Clear line 04 when leaving AWAITING_INPUT — the question is no longer relevant
        if (oldState === 'AWAITING_INPUT' && newState !== 'AWAITING_INPUT') {
            const card = document.querySelector(`article[data-agent-id="${agentId}"]`);
            if (card) {
                const taskSummary = card.querySelector('.task-summary');
                if (taskSummary) {
                    taskSummary.textContent = '';
                }
            }
        }

        // Recalculate and update header counts
        updateStatusCounts();

        // Update project traffic light
        const projectId = data.project_id;
        if (projectId) {
            updateProjectStateDots(projectId);
        }

        // Trigger recommended next update (full page would need data from server)
        // For now, just highlight if state changed to AWAITING_INPUT or TIMED_OUT
        if (newState === 'AWAITING_INPUT' || newState === 'TIMED_OUT') {
            highlightRecommendedUpdate();
        }
    }

    /**
     * Update an agent card's state display
     */
    function updateAgentCardState(agentId, state) {
        // Use article selector to avoid matching the recommended-next panel's div
        const selector = `article[data-agent-id="${agentId}"]`;
        const card = document.querySelector(selector);

        console.log('[DEBUG] updateAgentCardState:', {
            agentId: agentId,
            agentIdType: typeof agentId,
            selector: selector,
            cardFound: !!card,
        });

        if (!card) {
            console.warn('[DEBUG] Card NOT FOUND for selector:', selector);
            return;
        }

        const stateInfo = STATE_INFO[state] || STATE_INFO['IDLE'];

        // Update state bar
        const stateBar = card.querySelector('.state-bar');
        console.log('[DEBUG] stateBar found:', !!stateBar, 'className before:', stateBar ? stateBar.className : 'N/A');
        if (stateBar) {
            // Remove old bg classes
            stateBar.className = stateBar.className.replace(/bg-\w+/g, '');
            stateBar.classList.add(stateInfo.bg_class);
            console.log('[DEBUG] stateBar className after:', stateBar.className);
        }

        // Update state label
        const stateLabel = card.querySelector('.state-label');
        console.log('[DEBUG] stateLabel found:', !!stateLabel, 'text before:', stateLabel ? stateLabel.textContent : 'N/A');
        if (stateLabel) {
            stateLabel.textContent = stateInfo.label;
            console.log('[DEBUG] stateLabel text after:', stateLabel.textContent);
        }

        // Update data attribute
        card.setAttribute('data-state', state);
        console.log('[DEBUG] Card data-state set to:', state);
    }

    /**
     * Handle turn created events
     */
    function handleTurnCreated(data, eventType) {
        const agentId = data.agent_id;
        const turnText = data.text || data.turn_text || '';

        if (!agentId) return;

        console.log('Turn created:', agentId);

        // Update task summary (scope to article to avoid recommended panel)
        const card = document.querySelector(`article[data-agent-id="${agentId}"]`);
        if (!card) return;

        const taskSummary = card.querySelector('.task-summary');
        if (taskSummary) {
            // Truncate to 100 chars
            let text = turnText;
            if (text.length > 100) {
                text = text.substring(0, 100) + '...';
            }
            taskSummary.textContent = text || 'No active task';
        }
    }

    /**
     * Handle agent activity events
     */
    function handleAgentActivity(data, eventType) {
        const agentId = data.agent_id;
        const isActive = data.is_active;

        if (!agentId) return;

        console.log('Agent activity:', agentId, 'active:', isActive);

        // Update status badge (scope to article to avoid recommended panel)
        const card = document.querySelector(`article[data-agent-id="${agentId}"]`);
        if (!card) return;

        const statusBadge = card.querySelector('.status-badge');
        if (statusBadge) {
            if (isActive) {
                statusBadge.textContent = 'ACTIVE';
                statusBadge.className = 'status-badge px-2 py-0.5 text-xs font-medium rounded bg-green/20 text-green';
            } else {
                statusBadge.textContent = 'IDLE';
                statusBadge.className = 'status-badge px-2 py-0.5 text-xs font-medium rounded bg-muted/20 text-muted';
            }
        }

        // Update uptime if provided
        if (data.uptime) {
            const uptimeEl = card.querySelector('.uptime');
            if (uptimeEl) {
                uptimeEl.textContent = data.uptime;
            }
        }

        // Update last seen if provided
        if (data.last_seen) {
            const lastSeenEl = card.querySelector('.last-seen');
            if (lastSeenEl) {
                lastSeenEl.textContent = data.last_seen;
            }
        }
    }

    /**
     * Handle session created events.
     * Reloads the page to render the new agent card.
     */
    function handleSessionCreated(data, eventType) {
        console.log('Session created:', data.agent_id, '- reloading dashboard');
        safeDashboardReload();
    }

    /**
     * Handle session ended events.
     * Reloads the page to remove the ended agent card.
     */
    function handleSessionEnded(data, eventType) {
        const agentId = data.agent_id;
        if (!agentId) return;

        console.log('Session ended:', agentId, '- reloading dashboard');

        // Remove from tracked states
        agentStates.delete(agentId);

        safeDashboardReload();
    }

    /**
     * Handle instruction summary events (AI-generated task instruction)
     */
    function handleInstructionSummary(data, eventType) {
        const agentId = data.agent_id;
        const instruction = data.summary || data.text;

        if (!agentId || !instruction) return;

        console.log('Instruction summary:', agentId);

        var card = document.querySelector('article[data-agent-id="' + agentId + '"]');
        if (!card) return;

        var instructionEl = card.querySelector('.task-instruction');
        if (instructionEl) {
            instructionEl.textContent = instruction;
            instructionEl.classList.remove('text-muted', 'italic');
            instructionEl.classList.add('text-primary', 'font-medium');
        }
    }

    /**
     * Handle task summary events (AI-generated task-level completion summary).
     * Updates the secondary line (.task-summary).
     * When is_completion is true, applies completion styling (green text).
     */
    function handleTaskSummary(data, eventType) {
        const agentId = data.agent_id;
        const summary = data.summary || data.text;

        if (!agentId || !summary) return;

        console.log('Task summary:', agentId, 'is_completion:', data.is_completion);

        var card = document.querySelector('article[data-agent-id="' + agentId + '"]');
        if (!card) return;

        var taskSummary = card.querySelector('.task-summary');
        if (taskSummary) {
            taskSummary.textContent = summary;
            if (data.is_completion) {
                taskSummary.classList.remove('text-secondary');
                taskSummary.classList.add('text-green');
            }
        }
    }

    /**
     * Handle turn summary events (AI-generated turn-level summary).
     * Updates the secondary line (.task-summary).
     * Always updates to show latest turn context.
     * Resets to secondary styling (active task, not completion).
     */
    function handleTurnSummary(data, eventType) {
        const agentId = data.agent_id;
        const summary = data.summary || data.text;

        if (!agentId || !summary) return;

        console.log('Turn summary:', agentId);

        var card = document.querySelector('article[data-agent-id="' + agentId + '"]');
        if (!card) return;

        // Don't overwrite completion summary when task is COMPLETE
        if (card.getAttribute('data-state') === 'COMPLETE') return;

        var taskSummary = card.querySelector('.task-summary');
        if (taskSummary) {
            taskSummary.textContent = summary;
            taskSummary.classList.remove('text-green');
            taskSummary.classList.add('text-secondary');
        }
    }

    /**
     * Handle priority update events (AI-generated priority scores).
     * Updates the priority footer on each agent card.
     */
    function handlePriorityUpdate(data, eventType) {
        var agents = data.agents;
        if (!agents || !Array.isArray(agents)) return;

        console.log('Priority update:', agents.length, 'agents');

        agents.forEach(function(agentData) {
            var agentId = agentData.agent_id;
            var score = agentData.score;
            var reason = agentData.reason;

            if (!agentId) return;

            var card = document.querySelector('article[data-agent-id="' + agentId + '"]');
            if (!card) return;

            // Update priority score badge
            var scoreBadge = card.querySelector('.border-t .font-mono');
            if (scoreBadge) {
                scoreBadge.textContent = score != null ? score : 50;
            }

            // Update priority reason
            var reasonEl = card.querySelector('.border-t .italic');
            if (reasonEl && reason) {
                reasonEl.textContent = '// ' + reason.substring(0, 60);
            }
        });
    }

    /**
     * Handle card_refresh events — authoritative full card state from server.
     * Updates all visible fields on the agent card in one shot.
     */
    function handleCardRefresh(data, eventType) {
        var agentId = parseInt(data.id);
        var state = data.state;
        var reason = data.reason || '';

        if (!agentId || !state) return;

        console.log('card_refresh:', agentId, 'state:', state, 'reason:', reason);

        var card = document.querySelector('article[data-agent-id="' + agentId + '"]');

        // If card not found, a new agent may have appeared — reload to render it
        if (!card) {
            if (reason === 'session_start' || reason === 'session_reactivated') {
                safeDashboardReload();
            }
            return;
        }

        var stateInfo = data.state_info || STATE_INFO[state] || STATE_INFO['IDLE'];

        // Line 01: status badge, last-seen, uptime
        var statusBadge = card.querySelector('.status-badge');
        if (statusBadge) {
            if (data.is_active) {
                statusBadge.textContent = 'ACTIVE';
                statusBadge.className = 'status-badge px-2 py-0.5 text-xs font-medium rounded bg-green/20 text-green';
            } else {
                statusBadge.textContent = 'IDLE';
                statusBadge.className = 'status-badge px-2 py-0.5 text-xs font-medium rounded bg-muted/20 text-muted';
            }
        }
        var lastSeenEl = card.querySelector('.last-seen');
        if (lastSeenEl && data.last_seen) {
            lastSeenEl.textContent = data.last_seen;
        }
        var uptimeEl = card.querySelector('.uptime');
        if (uptimeEl && data.uptime) {
            uptimeEl.textContent = data.uptime;
        }

        // Line 02: state bar + state label
        var stateBar = card.querySelector('.state-bar');
        if (stateBar) {
            stateBar.className = stateBar.className.replace(/bg-\w+/g, '');
            stateBar.classList.add(stateInfo.bg_class);
        }
        var stateLabel = card.querySelector('.state-label');
        if (stateLabel) {
            stateLabel.textContent = stateInfo.label;
        }
        card.setAttribute('data-state', state);

        // Line 03: task instruction
        var instructionEl = card.querySelector('.task-instruction');
        if (instructionEl) {
            if (data.task_instruction) {
                instructionEl.textContent = data.task_instruction;
                instructionEl.classList.remove('text-muted', 'italic');
                instructionEl.classList.add('text-primary', 'font-medium');
            } else {
                instructionEl.textContent = 'No instruction';
                instructionEl.classList.remove('text-primary', 'font-medium');
                instructionEl.classList.add('text-muted', 'italic');
            }
        }

        // Line 04: task summary / completion summary
        var taskSummary = card.querySelector('.task-summary');
        if (taskSummary) {
            if ((state === 'COMPLETE' || state === 'IDLE') && data.task_completion_summary) {
                taskSummary.textContent = data.task_completion_summary;
                taskSummary.classList.remove('text-secondary');
                taskSummary.classList.add('text-green');
            } else {
                taskSummary.textContent = data.task_summary || '';
                taskSummary.classList.remove('text-green');
                taskSummary.classList.add('text-secondary');
            }
        }

        // Footer: priority score and reason
        var scoreBadge = card.querySelector('.border-t .font-mono');
        if (scoreBadge && data.priority != null) {
            scoreBadge.textContent = data.priority;
        }
        var reasonEl = card.querySelector('.border-t .italic');
        if (reasonEl && data.priority_reason) {
            reasonEl.textContent = '// ' + data.priority_reason.substring(0, 60);
        }

        // Update tracked state
        agentStates.set(agentId, state);

        // Recalculate header counts and project dots
        updateStatusCounts();
        var projectId = data.project_id;
        if (projectId) {
            updateProjectStateDots(projectId);
        }

        // Highlight if needs attention
        if (state === 'AWAITING_INPUT' || state === 'TIMED_OUT') {
            highlightRecommendedUpdate();
        }

        // Dispatch custom event for respond widget re-initialization
        document.dispatchEvent(new CustomEvent('sse:card_refresh', { detail: data }));
    }

    /**
     * Handle priority toggle events — update the banner badge
     */
    function handlePriorityToggle(data, eventType) {
        var badge = document.getElementById('priority-status-badge');
        if (!badge) return;

        var enabled = data.priority_enabled;
        console.log('Priority toggle:', enabled);

        badge.textContent = 'prioritisation ' + (enabled ? 'enabled' : 'disabled');
        badge.className = 'objective-banner-priority-badge ' + (enabled ? 'priority-enabled' : 'priority-disabled');
        badge.title = 'Priority scoring is ' + (enabled ? 'enabled' : 'disabled');
    }

    /**
     * Recalculate and update header status counts
     */
    function updateStatusCounts() {
        let timedOut = 0;
        let inputNeeded = 0;
        let working = 0;
        let idle = 0;

        console.log('[DEBUG] updateStatusCounts: agentStates dump:');
        agentStates.forEach(function(state, key) {
            console.log('[DEBUG]   key:', key, '(' + typeof key + ') -> state:', state);
            if (state === 'TIMED_OUT') {
                timedOut++;
            } else if (state === 'AWAITING_INPUT') {
                inputNeeded++;
            } else if (state === 'COMMANDED' || state === 'PROCESSING') {
                working++;
            } else {
                idle++;
            }
        });

        console.log('[DEBUG] updateStatusCounts result:', { timedOut, inputNeeded, working, idle });

        // Update header badges
        const inputBadge = document.querySelector('#status-input-needed .status-count');
        const workingBadge = document.querySelector('#status-working .status-count');
        const idleBadge = document.querySelector('#status-idle .status-count');

        if (inputBadge) inputBadge.textContent = '[' + inputNeeded + ']';
        if (workingBadge) workingBadge.textContent = '[' + working + ']';
        if (idleBadge) idleBadge.textContent = '[' + idle + ']';
    }

    /**
     * Update a project's state indicator dots
     */
    function updateProjectStateDots(projectId) {
        var projectEl = document.querySelector('[data-project-id="' + projectId + '"]');
        if (!projectEl) return;

        var dots = projectEl.querySelectorAll('.state-dot');
        if (dots.length < 4) return;

        var agentCards = projectEl.querySelectorAll('[data-agent-id]');
        var hasTimedOut = false, hasInput = false, hasWorking = false, hasIdle = false;

        agentCards.forEach(function(card) {
            var state = card.getAttribute('data-state');
            if (state === 'TIMED_OUT') hasTimedOut = true;
            else if (state === 'AWAITING_INPUT') hasInput = true;
            else if (state === 'COMMANDED' || state === 'PROCESSING') hasWorking = true;
            else hasIdle = true;
        });

        // dots[0] = red (timed out), dots[1] = amber (input needed), dots[2] = blue (working), dots[3] = green (idle)
        dots[0].classList.toggle('opacity-25', !hasTimedOut);
        dots[1].classList.toggle('opacity-25', !hasInput);
        dots[2].classList.toggle('opacity-25', !hasWorking);
        dots[3].classList.toggle('opacity-25', !hasIdle);
    }

    /**
     * Highlight the recommended next panel to indicate an update
     */
    function highlightRecommendedUpdate() {
        const panel = document.getElementById('recommended-next-panel');
        if (!panel) return;

        panel.classList.add('border-amber', 'animate-pulse');

        setTimeout(function() {
            panel.classList.remove('border-amber', 'animate-pulse');
        }, 2000);
    }

    /**
     * Handle URL highlight parameter for notification click-to-navigate.
     * Scrolls to agent card and applies highlight animation.
     */
    function handleHighlightParam() {
        const urlParams = new URLSearchParams(window.location.search);
        const highlightId = urlParams.get('highlight');

        if (!highlightId) return;

        // Find the agent card (scope to article to avoid recommended panel)
        const card = document.querySelector(`article[data-agent-id="${highlightId}"]`);
        if (!card) {
            console.warn('Agent card not found for highlight:', highlightId);
            return;
        }

        // Scroll to the card with smooth behavior
        card.scrollIntoView({
            behavior: 'smooth',
            block: 'center'
        });

        // Add highlight animation
        card.classList.add('ring-2', 'ring-cyan', 'ring-opacity-75', 'animate-pulse');

        // Remove highlight after 3 seconds
        setTimeout(function() {
            card.classList.remove('ring-2', 'ring-cyan', 'ring-opacity-75', 'animate-pulse');
        }, 3000);

        // Clean up URL (remove highlight param without page reload)
        urlParams.delete('highlight');
        const newUrl = urlParams.toString()
            ? window.location.pathname + '?' + urlParams.toString()
            : window.location.pathname;
        window.history.replaceState({}, '', newUrl);
    }

    /**
     * Initialize agent states from the DOM on page load
     */
    function initAgentStates() {
        // Scope to article elements to avoid the recommended-next panel div
        const agentCards = document.querySelectorAll('article[data-agent-id][data-state]');
        console.log('[DEBUG] initAgentStates: found', agentCards.length, 'agent cards');
        agentCards.forEach(function(card) {
            const agentId = card.getAttribute('data-agent-id');
            const state = card.getAttribute('data-state');
            console.log('[DEBUG] initAgentStates card:', {
                rawAgentId: agentId,
                parsedAgentId: parseInt(agentId),
                state: state,
            });
            if (agentId && state) {
                agentStates.set(parseInt(agentId), state);
            }
        });
        console.log('[DEBUG] initAgentStates complete. Map keys:', Array.from(agentStates.keys()).map(k => `${k} (${typeof k})`));
    }

    /**
     * Update the recommended-next panel's state display
     */
    function updateRecommendedPanel(agentId, state) {
        var panel = document.getElementById('recommended-next-panel');
        if (!panel) return;

        var panelDiv = panel.querySelector('[data-agent-id="' + agentId + '"]');
        if (!panelDiv) return;

        var stateInfo = STATE_INFO[state] || STATE_INFO['IDLE'];

        // Update the state bar fill
        var barFill = panelDiv.querySelector('.bg-deep > div');
        if (barFill) {
            barFill.className = barFill.className.replace(/bg-\w+/g, '');
            barFill.classList.add('h-full', stateInfo.bg_class);
        }

        // Update the state label text next to the bar
        var labelSpan = panelDiv.querySelector('.bg-deep');
        if (labelSpan && labelSpan.nextElementSibling) {
            var textEl = labelSpan.nextElementSibling;
            textEl.textContent = stateInfo.label;
            // Update text color for AWAITING_INPUT
            textEl.className = textEl.className.replace(/text-\w+/g, '');
            textEl.classList.add('text-xs', 'whitespace-nowrap');
            textEl.classList.add(state === 'TIMED_OUT' ? 'text-red' : (state === 'AWAITING_INPUT' ? 'text-amber' : 'text-secondary'));
        }
    }

    /**
     * Handle commander availability events (Input Bridge).
     * Dispatches a custom event for respond-init.js to handle.
     */
    function handleCommanderAvailability(data, eventType) {
        console.log('Commander availability:', data.agent_id, 'available:', data.available);
        document.dispatchEvent(new CustomEvent('sse:commander_availability', { detail: data }));
    }

    // Export
    global.DashboardSSE = {
        init: function() {
            initAgentStates();
            handleHighlightParam();
            return initDashboardSSE();
        },
        highlightAgent: function(agentId) {
            // Allow programmatic highlighting (scope to article to avoid recommended panel)
            const card = document.querySelector(`article[data-agent-id="${agentId}"]`);
            if (card) {
                card.scrollIntoView({ behavior: 'smooth', block: 'center' });
                card.classList.add('ring-2', 'ring-cyan', 'ring-opacity-75', 'animate-pulse');
                setTimeout(function() {
                    card.classList.remove('ring-2', 'ring-cyan', 'ring-opacity-75', 'animate-pulse');
                }, 3000);
            }
        }
    };

    // Auto-initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            global.DashboardSSE.init();
        });
    } else {
        global.DashboardSSE.init();
    }

})(typeof window !== 'undefined' ? window : this);
