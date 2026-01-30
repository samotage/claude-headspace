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
 * - Traffic lights on project groups
 * - Agent card state bars, status badges, task summaries
 * - Recommended next panel
 * - Connection status indicator
 */

(function(global) {
    'use strict';

    // State info mapping (matches Python get_state_info)
    const STATE_INFO = {
        'IDLE': { color: 'gray', bg_class: 'bg-muted', label: 'Idle - ready for task' },
        'COMMANDED': { color: 'yellow', bg_class: 'bg-amber', label: 'Command received' },
        'PROCESSING': { color: 'blue', bg_class: 'bg-blue', label: 'Processing...' },
        'AWAITING_INPUT': { color: 'orange', bg_class: 'bg-amber', label: 'Input needed' },
        'COMPLETE': { color: 'green', bg_class: 'bg-green', label: 'Task complete' }
    };

    // Track agent states for recalculating counts
    let agentStates = new Map();

    /**
     * Initialize the dashboard SSE client
     */
    function initDashboardSSE() {
        if (typeof SSEClient === 'undefined') {
            console.error('SSEClient not loaded');
            updateConnectionIndicator('disconnected');
            return null;
        }

        // Create SSE client
        const client = new SSEClient({
            url: '/api/events/stream',
            reconnectBaseDelay: 1000,
            reconnectMaxDelay: 30000
        });

        // Handle connection state changes
        client.onStateChange(function(newState, oldState) {
            console.log('SSE state:', oldState, '->', newState);
            updateConnectionIndicator(newState);
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

        // Connect
        client.connect();

        return client;
    }

    /**
     * Update the connection status indicator in the header
     */
    function updateConnectionIndicator(state) {
        const indicator = document.getElementById('connection-indicator');
        if (!indicator) return;

        const dot = indicator.querySelector('.connection-dot');
        const text = indicator.querySelector('.connection-text');

        if (!dot || !text) return;

        switch (state) {
            case 'connected':
                dot.className = 'connection-dot w-2 h-2 rounded-full bg-green animate-pulse';
                text.textContent = 'SSE live';
                text.className = 'connection-text text-green';
                break;
            case 'connecting':
            case 'reconnecting':
                dot.className = 'connection-dot w-2 h-2 rounded-full bg-muted';
                text.textContent = 'Reconnecting...';
                text.className = 'connection-text text-muted';
                break;
            case 'disconnected':
            default:
                dot.className = 'connection-dot w-2 h-2 rounded-full bg-red';
                text.textContent = 'Offline';
                text.className = 'connection-text text-red';
                break;
        }
    }

    /**
     * Handle agent state transition events
     */
    function handleStateTransition(data, eventType) {
        const agentId = data.agent_id;
        const newState = data.new_state || data.state;

        if (!agentId || !newState) {
            console.warn('Invalid state transition event:', data);
            return;
        }

        console.log('State transition:', agentId, '->', newState);

        // Update tracked state
        const oldState = agentStates.get(agentId);
        agentStates.set(agentId, newState);

        // Update agent card
        updateAgentCardState(agentId, newState);

        // Recalculate and update header counts
        updateStatusCounts();

        // Update project traffic light
        const projectId = data.project_id;
        if (projectId) {
            updateProjectTrafficLight(projectId);
        }

        // Trigger recommended next update (full page would need data from server)
        // For now, just highlight if state changed to AWAITING_INPUT
        if (newState === 'AWAITING_INPUT') {
            highlightRecommendedUpdate();
        }
    }

    /**
     * Update an agent card's state display
     */
    function updateAgentCardState(agentId, state) {
        const card = document.querySelector(`[data-agent-id="${agentId}"]`);
        if (!card) return;

        const stateInfo = STATE_INFO[state] || STATE_INFO['IDLE'];

        // Update state bar
        const stateBar = card.querySelector('.state-bar');
        if (stateBar) {
            // Remove old bg classes
            stateBar.className = stateBar.className.replace(/bg-\w+/g, '');
            stateBar.classList.add(stateInfo.bg_class);
        }

        // Update state label
        const stateLabel = card.querySelector('.state-label');
        if (stateLabel) {
            stateLabel.textContent = stateInfo.label;
        }

        // Update data attribute
        card.setAttribute('data-state', state);
    }

    /**
     * Handle turn created events
     */
    function handleTurnCreated(data, eventType) {
        const agentId = data.agent_id;
        const turnText = data.text || data.turn_text || '';

        if (!agentId) return;

        console.log('Turn created:', agentId);

        // Update task summary
        const card = document.querySelector(`[data-agent-id="${agentId}"]`);
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

        // Update status badge
        const card = document.querySelector(`[data-agent-id="${agentId}"]`);
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
    }

    /**
     * Handle session created events.
     * Reloads the page to render the new agent card.
     */
    function handleSessionCreated(data, eventType) {
        console.log('Session created:', data.agent_id, '- reloading dashboard');
        window.location.reload();
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

        window.location.reload();
    }

    /**
     * Recalculate and update header status counts
     */
    function updateStatusCounts() {
        let inputNeeded = 0;
        let working = 0;
        let idle = 0;

        agentStates.forEach(function(state) {
            if (state === 'AWAITING_INPUT') {
                inputNeeded++;
            } else if (state === 'COMMANDED' || state === 'PROCESSING') {
                working++;
            } else {
                idle++;
            }
        });

        // Update header badges
        const inputBadge = document.querySelector('#status-input-needed .status-count');
        const workingBadge = document.querySelector('#status-working .status-count');
        const idleBadge = document.querySelector('#status-idle .status-count');

        if (inputBadge) inputBadge.textContent = '[' + inputNeeded + ']';
        if (workingBadge) workingBadge.textContent = '[' + working + ']';
        if (idleBadge) idleBadge.textContent = '[' + idle + ']';
    }

    /**
     * Update a project's traffic light
     */
    function updateProjectTrafficLight(projectId) {
        const projectGroup = document.querySelector(`[data-project-id="${projectId}"]`);
        if (!projectGroup) return;

        const trafficLight = projectGroup.querySelector('.traffic-light');
        if (!trafficLight) return;

        // Find all agent cards in this project and check their states
        const agentCards = projectGroup.querySelectorAll('[data-agent-id]');
        let hasAwaitingInput = false;
        let hasWorking = false;

        agentCards.forEach(function(card) {
            const state = card.getAttribute('data-state');
            if (state === 'AWAITING_INPUT') {
                hasAwaitingInput = true;
            } else if (state === 'COMMANDED' || state === 'PROCESSING') {
                hasWorking = true;
            }
        });

        // Update traffic light color
        trafficLight.className = trafficLight.className.replace(/bg-\w+/g, '');
        if (hasAwaitingInput) {
            trafficLight.classList.add('bg-red');
        } else if (hasWorking) {
            trafficLight.classList.add('bg-amber');
        } else {
            trafficLight.classList.add('bg-green');
        }
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

        // Find the agent card
        const card = document.querySelector(`[data-agent-id="${highlightId}"]`);
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
        const agentCards = document.querySelectorAll('[data-agent-id][data-state]');
        agentCards.forEach(function(card) {
            const agentId = card.getAttribute('data-agent-id');
            const state = card.getAttribute('data-state');
            if (agentId && state) {
                agentStates.set(parseInt(agentId), state);
            }
        });
    }

    // Export
    global.DashboardSSE = {
        init: function() {
            initAgentStates();
            handleHighlightParam();
            return initDashboardSSE();
        },
        updateConnectionIndicator: updateConnectionIndicator,
        highlightAgent: function(agentId) {
            // Allow programmatic highlighting
            const card = document.querySelector(`[data-agent-id="${agentId}"]`);
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
