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

    function applyPriorityTier(badge, score) {
        badge.classList.remove('priority-low', 'priority-mid', 'priority-high', 'priority-top');
        var s = parseInt(score, 10) || 0;
        if (s >= 76) badge.classList.add('priority-top');
        else if (s >= 51) badge.classList.add('priority-high');
        else if (s >= 26) badge.classList.add('priority-mid');
        else badge.classList.add('priority-low');
        badge.setAttribute('data-priority', s);
    }

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

    // Track last received SSE event ID for gap detection (M6 client-side)
    let _lastEventId = 0;

    // Track fallback timeout IDs per agent for cleanup (M15)
    const _fallbackTimeouts = new Map();

    /**
     * Check for SSE event ID gaps indicating dropped events.
     * If the gap exceeds a threshold, trigger a safe reload to re-sync state.
     * Called from the shared SSE client's onMessage hook.
     */
    function checkEventIdGap(eventId) {
        if (!eventId) return;
        var id = parseInt(eventId, 10);
        if (isNaN(id)) return;
        if (_lastEventId > 0 && id - _lastEventId > 5) {
            console.warn('SSE event ID gap detected:', _lastEventId, '->', id, '- reloading to sync');
            _lastEventId = id;
            safeDashboardReload();
            return;
        }
        _lastEventId = id;
    }

    /**
     * Safe reload that defers if a ConfirmDialog is open or a respond widget
     * input is focused (FE-H3). Prevents SSE-triggered reloads from
     * flashing/dismissing dialogs or losing typed responses.
     */
    function safeDashboardReload() {
        if (typeof ConfirmDialog !== 'undefined' && ConfirmDialog.isOpen()) {
            console.log('SSE reload deferred — ConfirmDialog is open');
            window._sseReloadDeferred = function() {
                window.location.reload();
            };
            return;
        }
        // Defer reload if a respond widget input is focused
        var active = document.activeElement;
        if (active && active.closest && active.closest('.respond-widget')) {
            console.log('SSE reload deferred — respond widget input is focused');
            window._sseReloadDeferred = function() {
                window.location.reload();
            };
            return;
        }
        window.location.reload();
    }

    // Execute deferred reload when focus leaves a respond widget
    document.addEventListener('focusout', function(e) {
        if (!window._sseReloadDeferred) return;
        if (!e.target || !e.target.closest || !e.target.closest('.respond-widget')) return;
        // Small delay to allow focus to move to another element within the widget
        setTimeout(function() {
            var active = document.activeElement;
            if (!active || !active.closest || !active.closest('.respond-widget')) {
                var deferred = window._sseReloadDeferred;
                window._sseReloadDeferred = null;
                deferred();
            }
        }, 100);
    });

    // ── Kanban card movement utilities ──────────────────────────────

    /**
     * Check if the dashboard is currently in Kanban view.
     * Card movement only applies in Kanban view; project/priority views
     * keep existing in-place update behavior.
     */
    function isKanbanView() {
        return !!document.querySelector('.kanban-columns');
    }

    /**
     * Map an agent state string to the Kanban column data-kanban-state value.
     *   IDLE -> 'IDLE'
     *   COMPLETE -> 'COMPLETE'
     *   COMMANDED, PROCESSING, TIMED_OUT -> 'PROCESSING'
     *   AWAITING_INPUT -> 'AWAITING_INPUT'
     */
    function stateToKanbanColumn(state) {
        switch (state) {
            case 'IDLE':
                return 'IDLE';
            case 'COMPLETE':
                return 'COMPLETE';
            case 'COMMANDED':
            case 'PROCESSING':
            case 'TIMED_OUT':
                return 'PROCESSING';
            case 'AWAITING_INPUT':
                return 'AWAITING_INPUT';
            default:
                console.warn('stateToKanbanColumn: unknown state:', state);
                return 'IDLE';
        }
    }

    /**
     * Move an agent card to the correct Kanban column based on its new state.
     * Handles column count updates, empty placeholders, and highlight animation.
     */
    function moveCardToColumn(agentId, newState, projectId) {
        if (!isKanbanView()) return;

        var card = findAgentCard(agentId);
        if (!card) return;

        // Never move a full agent card (article) into the COMPLETE column.
        // COMPLETE column only holds condensed <details> cards created by
        // handleCardRefresh. Without this guard, a state_transition event
        // could move the full card there and orphan it from IDLE.
        if (newState === 'COMPLETE' && card.tagName === 'ARTICLE') return;

        var targetColName = stateToKanbanColumn(newState);

        // Find card's current column
        var currentColumn = card.closest('[data-kanban-state]');
        if (!currentColumn) return;

        var currentColName = currentColumn.getAttribute('data-kanban-state');

        // Already in the correct column — nothing to do
        if (currentColName === targetColName) return;

        // Find the target column body within the same project section
        var projectSection = card.closest('[data-project-id]');
        if (!projectSection) return;

        var targetColumn = projectSection.querySelector('[data-kanban-state="' + targetColName + '"]');
        if (!targetColumn) return;

        var targetBody = targetColumn.querySelector('.kanban-column-body');
        if (!targetBody) return;

        var sourceBody = currentColumn.querySelector('.kanban-column-body');

        // Move the card
        targetBody.appendChild(card);

        // Update source column: add empty placeholder if now empty
        if (sourceBody) {
            var remainingCards = sourceBody.querySelectorAll('article, details.kanban-completed-task');
            if (remainingCards.length === 0 && currentColName !== 'COMPLETE') {
                var emptyLabels = {
                    'IDLE': 'idle',
                    'PROCESSING': 'processing',
                    'AWAITING_INPUT': 'input needed'
                };
                var emptyText = 'No ' + (emptyLabels[currentColName] || currentColName.toLowerCase()) + ' tasks';
                var placeholder = document.createElement('p');
                placeholder.className = 'text-muted text-xs italic px-2';
                placeholder.textContent = emptyText;
                sourceBody.appendChild(placeholder);
            }
        }

        // Update target column: remove empty placeholder if present
        var targetPlaceholder = targetBody.querySelector('p.text-muted.italic');
        if (targetPlaceholder) {
            targetPlaceholder.remove();
        }

        // Update both column header counts
        updateColumnCount(currentColumn);
        updateColumnCount(targetColumn);

        // Highlight the moved card
        highlightMovedCard(card);
    }

    /**
     * Update the (N) count in a Kanban column header.
     * Counts article elements and details.kanban-completed-task elements.
     */
    function updateColumnCount(columnEl) {
        if (!columnEl) return;

        var body = columnEl.querySelector('.kanban-column-body');
        if (!body) return;

        var count = body.querySelectorAll('article, details.kanban-completed-task').length;
        var countSpan = columnEl.querySelector('.kanban-column-count');
        if (countSpan) {
            countSpan.textContent = '(' + count + ')';
        }
    }

    /**
     * Apply a brief highlight animation on a card that just moved columns.
     * Scrolls the card into view and adds a cyan ring for 1.5 seconds.
     */
    function highlightMovedCard(card) {
        card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        card.classList.add('ring-2', 'ring-cyan');
        setTimeout(function() {
            card.classList.remove('ring-2', 'ring-cyan');
        }, 1500);
    }

    // ── End Kanban card movement utilities ────────────────────────

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

        // Reload page on reconnect to catch up on missed events.
        // Track whether we've been connected before so we only reload
        // on RE-connections (not the initial page-load connection).
        // The old check (oldState === 'reconnecting') never matched because
        // state transitions go RECONNECTING → CONNECTING → CONNECTED,
        // so oldState was always 'connecting' when reaching 'connected'.
        var hasBeenConnected = false;
        client.onStateChange(function(newState, oldState) {
            console.log('SSE state:', oldState, '->', newState);
            if (newState === 'connected') {
                if (hasBeenConnected) {
                    console.log('SSE reconnected after drop — reloading to sync state');
                    safeDashboardReload();
                }
                hasBeenConnected = true;
            }
        });

        // Handle agent state changes
        // Canonical: state_transition | Aliases: state_changed, agent_state_changed
        client.on('state_changed', handleStateTransition);
        client.on('state_transition', handleStateTransition);
        client.on('agent_state_changed', handleStateTransition);

        // Handle turn created
        // Canonical: turn_detected | Alias: turn_created
        client.on('turn_detected', handleTurnCreated);
        client.on('turn_created', handleTurnCreated);

        // Handle agent activity
        // Canonical: agent_activity | Alias: agent_updated
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

        // Handle activity bar updates on turn events
        client.on('turn_detected', handleActivityBarUpdate);
        client.on('turn_created', handleActivityBarUpdate);

        // Track event IDs for gap detection (M6 client-side).
        // Uses a wildcard handler so every event type is checked.
        // The broadcaster includes _eid in the data payload for this purpose.
        client.on('*', function(data, eventType) {
            if (data && data._eid) {
                checkEventIdGap(data._eid);
            }
        });

        return client;
    }

    /**
     * Handle agent state transition events
     */
    function handleStateTransition(data, eventType) {
        const agentId = data.agent_id;
        const newState = data.new_state || data.state;

        if (!agentId || !newState) {
            return;
        }

        // In Kanban view, COMPLETE transitions are handled by handleCardRefresh
        // which creates the condensed card + resets the agent card to IDLE.
        // Ignore state_transition events for COMPLETE to avoid undoing that work.
        if (newState === 'COMPLETE' && isKanbanView()) {
            // M7 fallback: if handleCardRefresh doesn't arrive within 2s,
            // the card may be stuck. Check if the card is still in a non-IDLE
            // column and reload if so. Tracked per-agent so card_refresh can cancel (M15).
            (function(aid) {
                // Clear any existing fallback timeout for this agent
                var existingTimeout = _fallbackTimeouts.get(aid);
                if (existingTimeout) clearTimeout(existingTimeout);

                var timeoutId = setTimeout(function() {
                    _fallbackTimeouts.delete(aid);
                    var card = findAgentCard(aid);
                    if (!card) return;
                    var col = card.closest('[data-kanban-state]');
                    if (!col) return;
                    var colState = col.getAttribute('data-kanban-state');
                    // If the card is still in PROCESSING or AWAITING_INPUT, card_refresh
                    // was likely dropped — reload to resync.
                    if (colState === 'PROCESSING' || colState === 'AWAITING_INPUT') {
                        console.warn('COMPLETE fallback: card still in', colState, '— reloading');
                        safeDashboardReload();
                    }
                }, 2000);
                _fallbackTimeouts.set(aid, timeoutId);
            })(agentId);
            return;
        }

        // Update tracked state
        const oldState = agentStates.get(agentId);
        agentStates.set(agentId, newState);

        // Update agent card and recommended panel
        updateAgentCardState(agentId, newState);
        updateRecommendedPanel(agentId, newState);

        // Move card to correct Kanban column
        moveCardToColumn(agentId, newState, data.project_id);

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

        if (!card) {
            return;
        }

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

        console.log('Session ended:', agentId);

        // Remove from tracked states
        agentStates.delete(agentId);

        // In Kanban view, remove the card from DOM instead of full reload
        if (isKanbanView()) {
            var card = findAgentCard(agentId);
            if (card) {
                var column = card.closest('[data-kanban-state]');
                var body = column ? column.querySelector('.kanban-column-body') : null;

                card.remove();

                // Update source column: add empty placeholder if now empty
                if (body) {
                    var remaining = body.querySelectorAll('article, details.kanban-completed-task');
                    if (remaining.length === 0) {
                        var colName = column.getAttribute('data-kanban-state');
                        if (colName !== 'COMPLETE') {
                            var emptyLabels = {
                                'IDLE': 'idle',
                                'PROCESSING': 'processing',
                                'AWAITING_INPUT': 'input needed'
                            };
                            var placeholder = document.createElement('p');
                            placeholder.className = 'text-muted text-xs italic px-2';
                            placeholder.textContent = 'No ' + (emptyLabels[colName] || colName.toLowerCase()) + ' tasks';
                            body.appendChild(placeholder);
                        }
                    }
                }

                // Update column count
                if (column) updateColumnCount(column);

                // Recalculate header counts
                updateStatusCounts();
                return;
            }
        }

        // Fallback: reload for non-Kanban views or if card not found
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
            if (window.CardTooltip) window.CardTooltip.refresh(instructionEl);
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
            if (window.CardTooltip) window.CardTooltip.refresh(taskSummary);
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
            if (window.CardTooltip) window.CardTooltip.refresh(taskSummary);
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
            var scoreBadge = card.querySelector('.priority-score');
            if (scoreBadge) {
                var s = score != null ? score : 50;
                scoreBadge.textContent = s;
                applyPriorityTier(scoreBadge, s);
            }

            // Update priority reason
            var reasonEl = card.querySelector('.border-t .italic');
            if (reasonEl && reason) {
                reasonEl.textContent = '// ' + reason.substring(0, 60);
            }
        });
    }

    /**
     * Build a condensed completed-task accordion element for the COMPLETE column.
     * Matches the server-side template in _kanban_view.html.
     * Uses innerHTML with all dynamic values escaped via CHUtils.escapeHtml.
     */
    function buildCompletedTaskCard(data) {
        var details = document.createElement('details');
        details.className = 'kanban-completed-task bg-elevated rounded-lg border border-green/20 overflow-hidden';
        details.setAttribute('data-agent-id', data.id);

        var esc = window.CHUtils.escapeHtml;
        var instruction = esc(data.task_instruction || 'Task');
        var completionSummary = esc(data.task_completion_summary || data.task_summary || 'Completed');
        var heroChars = esc(data.hero_chars || '');
        var heroTrail = esc(data.hero_trail || '');
        var turnCount = data.turn_count != null ? parseInt(data.turn_count, 10) : 0;
        var elapsed = esc(data.elapsed || '');
        var turnLabel = turnCount === 1 ? 'turn' : 'turns';
        var elapsedStr = elapsed ? ' \u00b7 ' + elapsed : '';

        details.innerHTML =
            '<summary class="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-hover transition-colors">' +
                '<span class="text-xs text-muted">&#9654;</span>' +
                '<span class="flex items-baseline gap-0.5">' +
                    '<span class="agent-hero text-sm">' + heroChars + '</span>' +
                    '<span class="agent-hero-trail">' + heroTrail + '</span>' +
                '</span>' +
                '<span class="task-instruction text-primary text-sm font-medium truncate flex-1" title="' + instruction + '">' + instruction + '</span>' +
            '</summary>' +
            '<div class="card-editor border-t border-green/10">' +
                '<div class="card-line">' +
                    '<span class="line-num">01</span>' +
                    '<div class="line-content">' +
                        '<p class="task-instruction text-primary text-sm font-medium">' + instruction + '</p>' +
                    '</div>' +
                '</div>' +
                '<div class="card-line">' +
                    '<span class="line-num">02</span>' +
                    '<div class="line-content">' +
                        '<p class="task-summary text-green text-sm italic">' + completionSummary + '</p>' +
                    '</div>' +
                '</div>' +
                '<div class="card-line">' +
                    '<span class="line-num">03</span>' +
                    '<div class="line-content">' +
                        '<span class="text-muted text-xs">' + turnCount + ' ' + turnLabel + elapsedStr + '</span>' +
                    '</div>' +
                '</div>' +
            '</div>';

        return details;
    }

    /**
     * Build a respond widget element for AWAITING_INPUT state.
     * Matches the server-rendered widget in _agent_card.html.
     * Starts hidden — respond-init.js handles visibility after commander availability check.
     * Uses DOM APIs instead of innerHTML for XSS safety.
     */
    function buildRespondWidget(agentId, questionText, questionOptions) {
        var widget = document.createElement('div');
        widget.className = 'respond-widget px-3 py-2 border-t border-amber/20 bg-amber/5';
        widget.setAttribute('data-agent-id', agentId);
        widget.setAttribute('data-question-text', questionText || '');
        if (questionOptions) {
            widget.setAttribute('data-question-options', JSON.stringify(questionOptions));
        }
        widget.style.display = 'none';

        var optionsDiv = document.createElement('div');
        optionsDiv.className = 'respond-options flex flex-col gap-1.5 mb-2';
        widget.appendChild(optionsDiv);

        var form = document.createElement('form');
        form.className = 'respond-form flex gap-2';
        var safeAgentId = parseInt(agentId, 10);
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            if (window.RespondAPI) window.RespondAPI.handleSubmit(e, safeAgentId);
        });

        var input = document.createElement('input');
        input.type = 'text';
        input.className = 'respond-text-input form-well flex-1 px-2 py-1 text-sm';
        input.placeholder = 'Type a response...';
        input.autocomplete = 'off';
        form.appendChild(input);

        var button = document.createElement('button');
        button.type = 'submit';
        button.className = 'respond-send-btn px-3 py-1 text-xs font-medium rounded bg-amber/20 text-amber border border-amber/30 hover:bg-amber/30 transition-colors';
        button.textContent = 'Send';
        form.appendChild(button);

        widget.appendChild(form);
        return widget;
    }

    /**
     * Find an agent's card element — may be an <article> (full card) or
     * a <details> (condensed completed-task card).
     */
    function findAgentCard(agentId) {
        return document.querySelector('article[data-agent-id="' + agentId + '"]') ||
               document.querySelector('details[data-agent-id="' + agentId + '"]');
    }

    /**
     * Handle card_refresh events — authoritative full card state from server.
     * Updates all visible fields on the agent card in one shot.
     */
    function handleCardRefresh(data, eventType) {
        var agentId = parseInt(data.id);
        if (isNaN(agentId)) return;
        var state = data.state;
        var reason = data.reason || '';

        if (!agentId || !state) return;

        console.log('card_refresh:', agentId, 'state:', state, 'reason:', reason);

        // Clear any pending fallback timeout for this agent (M15)
        var pendingTimeout = _fallbackTimeouts.get(agentId);
        if (pendingTimeout) {
            clearTimeout(pendingTimeout);
            _fallbackTimeouts.delete(agentId);
        }

        var card = findAgentCard(agentId);

        // If card not found, a new agent may have appeared — reload to render it
        if (!card) {
            if (reason === 'session_start' || reason === 'session_reactivated') {
                safeDashboardReload();
            }
            return;
        }

        var isCondensed = card.tagName === 'DETAILS';

        // Condensed completed-task card transitioning to a non-COMPLETE state
        // means a new task started — reload to get the full agent card template
        if (isCondensed && state !== 'COMPLETE') {
            safeDashboardReload();
            return;
        }

        // Full agent card transitioning to COMPLETE in Kanban view —
        // create a condensed completed-task accordion in the COMPLETE column
        // AND reset the agent card to IDLE in the IDLE column
        if (!isCondensed && state === 'COMPLETE' && isKanbanView()) {
            agentStates.set(agentId, 'IDLE');

            var condensedCard = buildCompletedTaskCard(data);

            var projectSection = card.closest('[data-project-id]');
            var sourceColumn = card.closest('[data-kanban-state]');

            if (projectSection) {
                // 1. Add condensed card to COMPLETE column
                var completeColumn = projectSection.querySelector('[data-kanban-state="COMPLETE"]');
                var completeBody = completeColumn ? completeColumn.querySelector('.kanban-column-body') : null;

                if (completeBody) {
                    var placeholder = completeBody.querySelector('p.text-muted.italic');
                    if (placeholder) placeholder.remove();
                    var existingCondensed = completeBody.querySelector('details[data-agent-id="' + agentId + '"]');
                    if (existingCondensed) existingCondensed.remove();
                    completeBody.insertBefore(condensedCard, completeBody.firstChild);
                }

                // 2. Reset the agent card to IDLE state
                var idleInfo = STATE_INFO['IDLE'];
                card.setAttribute('data-state', 'IDLE');

                var stateBar = card.querySelector('.state-bar');
                if (stateBar) {
                    stateBar.className = stateBar.className.replace(/bg-\w+/g, '');
                    stateBar.classList.add(idleInfo.bg_class);
                }
                var stateLabel = card.querySelector('.state-label');
                if (stateLabel) stateLabel.textContent = idleInfo.label;

                var instructionEl = card.querySelector('.task-instruction');
                if (instructionEl) {
                    instructionEl.textContent = 'No active task';
                    instructionEl.classList.remove('text-primary', 'font-medium');
                    instructionEl.classList.add('text-muted', 'italic');
                }
                var taskSummary = card.querySelector('.task-summary');
                if (taskSummary) {
                    taskSummary.textContent = '';
                    taskSummary.classList.remove('text-green');
                    taskSummary.classList.add('text-secondary');
                }
                // Remove respond widget if present (agent was AWAITING_INPUT -> COMPLETE)
                var resetWidget = card.querySelector('.respond-widget');
                if (resetWidget) resetWidget.remove();
                // Hide line 04 and task stats for IDLE reset
                var line04Row = card.querySelector('.card-line-04');
                if (line04Row) line04Row.style.display = 'none';
                var statsEl = card.querySelector('.task-stats');
                if (statsEl) statsEl.style.display = 'none';

                // 3. Move the agent card to the IDLE column
                var idleColumn = projectSection.querySelector('[data-kanban-state="IDLE"]');
                var idleBody = idleColumn ? idleColumn.querySelector('.kanban-column-body') : null;

                if (idleBody) {
                    var idlePlaceholder = idleBody.querySelector('p.text-muted.italic');
                    if (idlePlaceholder) idlePlaceholder.remove();
                    idleBody.appendChild(card);
                }

                // 4. Update source column (where the card came from)
                if (sourceColumn && sourceColumn !== idleColumn) {
                    var sourceBody = sourceColumn.querySelector('.kanban-column-body');
                    if (sourceBody) {
                        var remaining = sourceBody.querySelectorAll('article, details.kanban-completed-task');
                        if (remaining.length === 0) {
                            var colName = sourceColumn.getAttribute('data-kanban-state');
                            if (colName !== 'COMPLETE') {
                                var emptyLabels = {
                                    'IDLE': 'idle',
                                    'PROCESSING': 'processing',
                                    'AWAITING_INPUT': 'input needed'
                                };
                                var emptyPlaceholder = document.createElement('p');
                                emptyPlaceholder.className = 'text-muted text-xs italic px-2';
                                emptyPlaceholder.textContent = 'No ' + (emptyLabels[colName] || colName.toLowerCase()) + ' tasks';
                                sourceBody.appendChild(emptyPlaceholder);
                            }
                        }
                    }
                    updateColumnCount(sourceColumn);
                }

                // 5. Update column counts
                if (idleColumn) updateColumnCount(idleColumn);
                if (completeColumn) updateColumnCount(completeColumn);
                highlightMovedCard(condensedCard);
            }

            updateStatusCounts();
            var projectId = data.project_id;
            if (projectId) updateProjectStateDots(projectId);

            document.dispatchEvent(new CustomEvent('sse:card_refresh', { detail: data }));
            return;
        }

        var stateInfo = data.state_info || STATE_INFO[state] || STATE_INFO['IDLE'];

        // Line 01: hero identity, status badge, last-seen, uptime
        if (data.hero_chars) {
            var heroEl = card.querySelector('.agent-hero');
            if (heroEl) heroEl.textContent = data.hero_chars;
            var trailEl = card.querySelector('.agent-hero-trail');
            if (trailEl) trailEl.textContent = data.hero_trail || '';
        }
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
        // Bridge indicator: mutually exclusive with status badge
        if (data.is_bridge_connected != null) {
            var bridgeEl = card.querySelector('.bridge-indicator');
            var badgeContainer = statusBadge ? statusBadge.parentElement : null;
            if (data.is_bridge_connected && !bridgeEl && badgeContainer) {
                bridgeEl = document.createElement('span');
                bridgeEl.className = 'bridge-indicator';
                bridgeEl.title = 'Bridge connected \u2014 tmux pane active';
                bridgeEl.setAttribute('aria-label', 'Bridge connected');
                var bridgeIcon = document.createElement('span');
                bridgeIcon.className = 'bridge-icon';
                bridgeIcon.textContent = '\u25B8\u25C2';
                bridgeEl.appendChild(bridgeIcon);
                badgeContainer.insertBefore(bridgeEl, statusBadge);
            } else if (!data.is_bridge_connected && bridgeEl) {
                bridgeEl.remove();
            }
            // Hide status badge when bridge connected, show when not
            if (statusBadge) {
                statusBadge.style.display = data.is_bridge_connected ? 'none' : '';
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
                instructionEl.textContent = 'No active task';
                instructionEl.classList.remove('text-primary', 'font-medium');
                instructionEl.classList.add('text-muted', 'italic');
            }
            if (window.CardTooltip) window.CardTooltip.refresh(instructionEl);
        }

        // Plan indicator on line 03
        var planIndicator = card.querySelector('.plan-indicator');
        if (data.has_plan && data.current_task_id) {
            if (!planIndicator && instructionEl) {
                planIndicator = document.createElement('button');
                planIndicator.className = 'plan-indicator plan-indicator-btn';
                planIndicator.type = 'button';
                planIndicator.textContent = 'plan';
                planIndicator.title = 'View plan';
                planIndicator.setAttribute('aria-label', 'View agent plan');
                instructionEl.parentElement.appendChild(planIndicator);
            }
            if (planIndicator) {
                planIndicator.style.display = '';
                planIndicator.onclick = function() {
                    if (window.FullTextModal) {
                        window.FullTextModal.show(data.current_task_id, 'plan');
                    }
                };
            }
        } else if (planIndicator) {
            planIndicator.style.display = 'none';
        }

        // Line 04: task summary / completion summary (hidden when redundant with line 03)
        var line04Row = card.querySelector('.card-line-04');
        var taskSummary = card.querySelector('.task-summary');
        var line04Text = '';
        var isGreen = false;
        if ((state === 'COMPLETE' || state === 'IDLE') && data.task_completion_summary) {
            line04Text = data.task_completion_summary;
            isGreen = true;
        } else {
            line04Text = data.task_summary || '';
        }

        var line03Text = data.task_instruction || 'No active task';
        var shouldShow04 = line04Text && line04Text !== line03Text;

        if (shouldShow04) {
            if (!line04Row) {
                // Create line 04 row if it doesn't exist (was hidden on initial render)
                var cardEditor = card.querySelector('.card-editor');
                if (cardEditor) {
                    var newRow = document.createElement('div');
                    newRow.className = 'card-line card-line-04';
                    newRow.innerHTML = '<span class="line-num">04</span>' +
                        '<div class="line-content flex items-baseline justify-between gap-2">' +
                        '<p class="task-summary text-sm italic flex-1 min-w-0 truncate ' + (isGreen ? 'text-green' : 'text-secondary') + '">' +
                        window.CHUtils.escapeHtml(line04Text) + '</p></div>';
                    cardEditor.appendChild(newRow);
                }
            } else {
                line04Row.style.display = '';
                if (taskSummary) {
                    taskSummary.textContent = line04Text;
                    if (isGreen) {
                        taskSummary.classList.remove('text-secondary');
                        taskSummary.classList.add('text-green');
                    } else {
                        taskSummary.classList.remove('text-green');
                        taskSummary.classList.add('text-secondary');
                    }
                    if (window.CardTooltip) window.CardTooltip.refresh(taskSummary);
                }
            }
        } else if (line04Row) {
            line04Row.style.display = 'none';
        }

        // Respond widget: inject for AWAITING_INPUT, remove otherwise
        var existingWidget = card.querySelector('.respond-widget');
        if (state === 'AWAITING_INPUT') {
            if (existingWidget) {
                // Update question text and options on existing widget
                existingWidget.setAttribute('data-question-text', data.task_summary || '');
                if (data.question_options) {
                    existingWidget.setAttribute('data-question-options', JSON.stringify(data.question_options));
                }
            } else {
                // Inject widget between card-editor and footer
                var footer = card.querySelector('.border-t.border-border');
                if (footer) {
                    card.insertBefore(
                        buildRespondWidget(agentId, data.task_summary || '', data.question_options || null),
                        footer
                    );
                }
            }
        } else if (existingWidget) {
            existingWidget.remove();
        }

        // Footer: priority score and task stats (turns + elapsed)
        var scoreBadge = card.querySelector('.priority-score');
        if (scoreBadge && data.priority != null) {
            scoreBadge.textContent = data.priority;
            applyPriorityTier(scoreBadge, data.priority);
        }
        var statsEl = card.querySelector('.task-stats');
        var turnCount = data.turn_count != null ? parseInt(data.turn_count, 10) : 0;
        if (turnCount > 0) {
            var turnLabel = turnCount === 1 ? 'turn' : 'turns';
            if (statsEl) {
                statsEl.textContent = turnCount + ' ' + turnLabel + (data.elapsed ? ' \u00b7 ' + data.elapsed : '');
                statsEl.style.display = '';
            } else {
                // Create stats element inside the left group (beside priority score)
                var leftGroup = scoreBadge ? scoreBadge.parentElement : null;
                if (leftGroup) {
                    var newStats = document.createElement('span');
                    newStats.className = 'task-stats text-muted text-xs';
                    newStats.textContent = turnCount + ' ' + turnLabel + (data.elapsed ? ' \u00b7 ' + data.elapsed : '');
                    leftGroup.appendChild(newStats);
                }
            }
        } else if (statsEl) {
            statsEl.style.display = 'none';
        }

        // Context usage display
        var ctxSpan = card.querySelector('.context-usage');
        if (data.context && data.context.percent_used != null) {
            var pct = data.context.percent_used;
            var ctxText = pct + '% \u00b7 ' + (data.context.remaining_tokens || '?') + ' rem';
            var ctxClass = 'text-muted';
            if (pct >= (data.context.high_threshold || 75)) ctxClass = 'text-red';
            else if (pct >= (data.context.warning_threshold || 65)) ctxClass = 'text-amber';
            if (ctxSpan) {
                ctxSpan.textContent = ctxText;
                ctxSpan.className = 'context-usage ' + ctxClass + ' text-xs font-mono whitespace-nowrap';
            } else {
                var leftGroup = scoreBadge ? scoreBadge.parentElement : null;
                if (leftGroup) {
                    var s = document.createElement('span');
                    s.className = 'context-usage ' + ctxClass + ' text-xs font-mono whitespace-nowrap';
                    s.setAttribute('data-agent-id', String(data.id));
                    s.textContent = ctxText;
                    leftGroup.appendChild(s);
                }
            }
        } else if (ctxSpan) {
            ctxSpan.remove();
        }

        // Update tracked state and move card if state changed
        var oldState = agentStates.get(agentId);
        agentStates.set(agentId, state);

        if (oldState !== state) {
            moveCardToColumn(agentId, state, data.project_id);
        }

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
        let inputNeeded = 0;
        let working = 0;
        let idle = 0;

        agentStates.forEach(function(state, key) {
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
        agentCards.forEach(function(card) {
            const agentId = card.getAttribute('data-agent-id');
            const state = card.getAttribute('data-state');
            if (agentId && state) {
                agentStates.set(parseInt(agentId), state);
            }
            var badge = card.querySelector('.priority-score');
            if (badge) {
                applyPriorityTier(badge, badge.textContent);
            }
        });
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
     * Fetch and populate the dashboard activity bar.
     *
     * Uses the browser's local timezone to compute "today" boundaries
     * (midnight local → midnight+1 local), matching the activity page exactly.
     * Computes totals from the history array using the same logic as activity.js.
     */
    function fetchActivityBar() {
        var bar = document.getElementById('dashboard-activity-bar');
        if (!bar) return;

        // Compute today's boundaries in local time (same as activity.js _periodStart)
        var now = new Date();
        var since = new Date(now.getFullYear(), now.getMonth(), now.getDate());
        var until = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
        var params = 'window=day' +
            '&since=' + encodeURIComponent(since.toISOString()) +
            '&until=' + encodeURIComponent(until.toISOString());

        fetch('/api/metrics/overall?' + params)
            .then(function(res) { return res.json(); })
            .then(function(data) {
                var history = data.history || [];
                if (history.length === 0) return;

                var totalTurns = CHUtils.sumTurns(history);

                // Rate: turns / elapsed hours today
                var hoursElapsed = Math.max((now - since) / (1000 * 60 * 60), 1);
                var rate = totalTurns / hoursElapsed;

                var avgTime = CHUtils.weightedAvgTime(history);

                // Active agents from daily_totals
                var activeAgents = data.daily_totals ? (data.daily_totals.active_agents || 0) : 0;

                // Populate DOM
                var turnsEl = document.getElementById('activity-bar-turns');
                if (turnsEl) turnsEl.textContent = totalTurns;

                var rateEl = document.getElementById('activity-bar-rate');
                if (rateEl) {
                    if (rate === 0) rateEl.textContent = '0';
                    else if (rate >= 10) rateEl.textContent = Math.round(rate).toString();
                    else rateEl.textContent = rate.toFixed(1);
                }

                var avgEl = document.getElementById('activity-bar-avg-time');
                if (avgEl) avgEl.textContent = avgTime != null ? avgTime.toFixed(1) + 's' : '--';

                var agentsEl = document.getElementById('activity-bar-agents');
                if (agentsEl) agentsEl.textContent = activeAgents;

                // Frustration from activity metrics (fallback if headspace unavailable)
                var frustEl = document.getElementById('activity-bar-frustration');
                if (frustEl) {
                    var frustSums = CHUtils.sumFrustrationHistory(history);
                    var frustAvg = frustSums.turns > 0 ? frustSums.total / frustSums.turns : null;
                    frustEl.textContent = frustAvg != null ? frustAvg.toFixed(1) : '--';
                    frustEl.className = 'activity-bar-value';
                    if (frustAvg != null) {
                        if (frustAvg >= 7) frustEl.classList.add('text-red');
                        else if (frustAvg >= 4) frustEl.classList.add('text-amber');
                        else frustEl.classList.add('text-green');
                    }
                }
            })
            .catch(function(err) {
                console.warn('Activity bar fetch failed:', err);
            });

        // Fetch immediate frustration from headspace (overrides activity avg)
        fetch('/api/headspace/current')
            .then(function(res) { return res.json(); })
            .then(function(data) {
                if (!data.enabled || !data.current) return;
                var frustEl = document.getElementById('activity-bar-frustration');
                if (frustEl && data.current.frustration_rolling_10 != null) {
                    var val = data.current.frustration_rolling_10;
                    frustEl.textContent = val.toFixed(1);
                    frustEl.className = 'activity-bar-value';
                    if (val >= 7) frustEl.classList.add('text-red');
                    else if (val >= 4) frustEl.classList.add('text-amber');
                    else frustEl.classList.add('text-green');
                }
            })
            .catch(function(err) { console.warn('Headspace fetch failed:', err); });
    }

    /**
     * Handle activity bar updates when turns are detected.
     * Debounces and delegates to fetchActivityBar.
     */
    var _activityBarDebounce = null;
    function handleActivityBarUpdate(data, eventType) {
        if (_activityBarDebounce) return;
        _activityBarDebounce = setTimeout(function() { _activityBarDebounce = null; }, 2000);
        fetchActivityBar();
    }

    /**
     * Handle commander availability events (Input Bridge).
     * Dispatches a custom event for respond-init.js to handle.
     */
    function handleCommanderAvailability(data, eventType) {
        console.log('Commander availability:', data.agent_id, 'available:', data.available);

        // Toggle bridge indicator on the agent card
        var agentId = data.agent_id;
        var card = findAgentCard(agentId);
        if (card) {
            var bridgeEl = card.querySelector('.bridge-indicator');
            if (data.available && !bridgeEl) {
                var statusBadge = card.querySelector('.status-badge');
                var container = statusBadge ? statusBadge.parentElement : null;
                if (container) {
                    bridgeEl = document.createElement('span');
                    bridgeEl.className = 'bridge-indicator';
                    bridgeEl.title = 'Bridge connected \u2014 tmux pane active';
                    bridgeEl.setAttribute('aria-label', 'Bridge connected');
                    var bridgeIcon = document.createElement('span');
                    bridgeIcon.className = 'bridge-icon';
                    bridgeIcon.textContent = '\u25B8\u25C2';
                    bridgeEl.appendChild(bridgeIcon);
                    container.insertBefore(bridgeEl, statusBadge);
                }
            } else if (!data.available && bridgeEl) {
                bridgeEl.remove();
            }
            // Hide status badge when bridge connected, show when not
            var statusBadge = card.querySelector('.status-badge');
            if (statusBadge) {
                statusBadge.style.display = data.available ? 'none' : '';
            }
        }

        document.dispatchEvent(new CustomEvent('sse:commander_availability', { detail: data }));
    }

    // Export
    global.DashboardSSE = {
        init: function() {
            initAgentStates();
            handleHighlightParam();
            // Fetch activity bar stats on page load (uses local timezone)
            fetchActivityBar();
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
