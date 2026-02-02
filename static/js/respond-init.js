/**
 * Respond widget initialization for Claude Headspace dashboard.
 *
 * Checks commander availability for AWAITING_INPUT agents and shows/hides
 * the respond widget accordingly. Listens for SSE commander_availability
 * events to update in real-time.
 */

(function(global) {
    'use strict';

    var AVAILABILITY_ENDPOINT = '/api/respond';

    /**
     * Initialize respond widgets on all visible agent cards.
     */
    function initRespondWidgets() {
        var widgets = document.querySelectorAll('.respond-widget');
        widgets.forEach(function(widget) {
            var agentId = widget.getAttribute('data-agent-id');
            if (!agentId) return;

            // Check commander availability
            checkAndShowWidget(widget, parseInt(agentId, 10));
        });
    }

    /**
     * Check availability and show/populate widget if available.
     */
    function checkAndShowWidget(widget, agentId) {
        fetch(AVAILABILITY_ENDPOINT + '/' + agentId + '/availability')
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (data.commander_available) {
                    showWidget(widget);
                }
            })
            .catch(function() {
                // Silently fail - widget stays hidden
            });
    }

    /**
     * Show a respond widget and populate quick-action buttons.
     */
    function showWidget(widget) {
        var agentId = parseInt(widget.getAttribute('data-agent-id'), 10);
        var questionText = widget.getAttribute('data-question-text') || '';

        // Parse and render quick-action buttons
        var optionsContainer = widget.querySelector('.respond-options');
        if (optionsContainer && global.RespondAPI) {
            var options = global.RespondAPI.parseOptions(questionText);
            optionsContainer.innerHTML = '';

            if (options.length > 0) {
                options.forEach(function(opt) {
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'respond-option-btn px-3 py-1 text-xs font-medium rounded border border-amber/40 text-amber bg-amber/10 hover:bg-amber/20 transition-colors';
                    btn.textContent = opt.number + '. ' + opt.label;
                    btn.onclick = function() {
                        global.RespondAPI.sendOption(agentId, opt.number);
                    };
                    optionsContainer.appendChild(btn);
                });
            } else {
                // No options parsed - hide the options container
                optionsContainer.style.display = 'none';
            }
        }

        // Show the widget
        widget.style.display = '';
    }

    /**
     * Hide a respond widget.
     */
    function hideWidget(widget) {
        widget.style.display = 'none';
    }

    /**
     * Handle SSE commander_availability event.
     */
    function handleAvailabilityEvent(data) {
        var agentId = data.agent_id;
        var available = data.available;

        var widgets = document.querySelectorAll('.respond-widget[data-agent-id="' + agentId + '"]');
        widgets.forEach(function(widget) {
            if (available) {
                showWidget(widget);
            } else {
                hideWidget(widget);
            }
        });
    }

    /**
     * Handle SSE card_refresh event - may add or remove respond widgets.
     */
    function handleCardRefresh(data) {
        // After a card refresh (which replaces card HTML), re-initialize any
        // respond widgets that appeared
        setTimeout(initRespondWidgets, 100);
    }

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initRespondWidgets);
    } else {
        initRespondWidgets();
    }

    // Listen for SSE events via the shared SSE client
    // The dashboard-sse.js dispatches custom events on the document
    document.addEventListener('sse:commander_availability', function(e) {
        if (e.detail) handleAvailabilityEvent(e.detail);
    });

    document.addEventListener('sse:card_refresh', function(e) {
        if (e.detail) handleCardRefresh(e.detail);
    });

    // Export for manual use
    global.RespondInit = {
        init: initRespondWidgets,
        showWidget: showWidget,
        hideWidget: hideWidget
    };

})(typeof window !== 'undefined' ? window : this);
