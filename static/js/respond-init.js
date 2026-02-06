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
            .catch(function(err) {
                console.warn('Respond availability check failed:', err);
            });
    }

    /**
     * Show a respond widget and populate buttons.
     * When structured question_options are available (from AskUserQuestion),
     * renders labeled option buttons with descriptions. Otherwise falls
     * back to regex-parsed numbered options from question text.
     */
    function showWidget(widget) {
        var agentId = parseInt(widget.getAttribute('data-agent-id'), 10);
        var questionText = widget.getAttribute('data-question-text') || '';
        var questionOptionsRaw = widget.getAttribute('data-question-options');
        var questionOptions = null;

        if (questionOptionsRaw) {
            try { questionOptions = JSON.parse(questionOptionsRaw); } catch(e) { /* ignore */ }
        }

        var optionsContainer = widget.querySelector('.respond-options');
        var formContainer = widget.querySelector('.respond-form');

        if (optionsContainer && global.RespondAPI) {
            optionsContainer.innerHTML = '';

            // Check for structured AskUserQuestion options
            var structuredOptions = null;
            if (questionOptions && questionOptions.questions &&
                questionOptions.questions.length > 0) {
                var q = questionOptions.questions[0];
                if (q.options && q.options.length > 0) {
                    structuredOptions = q.options;
                }
            }

            if (structuredOptions) {
                // Render structured option buttons
                structuredOptions.forEach(function(opt, index) {
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'respond-option-btn w-full text-left px-3 py-2 text-xs rounded border border-amber/40 text-amber bg-amber/10 hover:bg-amber/20 transition-colors';
                    var label = document.createElement('span');
                    label.className = 'font-medium';
                    label.textContent = opt.label;
                    btn.appendChild(label);
                    if (opt.description) {
                        var desc = document.createElement('span');
                        desc.className = 'text-muted ml-2';
                        desc.textContent = opt.description;
                        btn.appendChild(desc);
                    }
                    btn.onclick = function() {
                        global.RespondAPI.sendSelect(agentId, index);
                    };
                    optionsContainer.appendChild(btn);
                });

                // Add "Other..." button that reveals the text input
                var otherBtn = document.createElement('button');
                otherBtn.type = 'button';
                otherBtn.className = 'respond-option-btn px-3 py-1.5 text-xs rounded border border-border text-muted hover:text-amber hover:border-amber/40 transition-colors';
                otherBtn.textContent = 'Other...';
                otherBtn.onclick = function() {
                    if (formContainer) {
                        formContainer.style.display = '';
                        var input = formContainer.querySelector('.respond-text-input');
                        if (input) input.focus();
                    }
                };
                optionsContainer.appendChild(otherBtn);
                optionsContainer.style.display = '';

                // Hide text input by default for structured options
                if (formContainer) {
                    formContainer.style.display = 'none';
                    // Re-wire form submit to use "other" mode
                    formContainer.onsubmit = function(event) {
                        event.preventDefault();
                        var input = formContainer.querySelector('.respond-text-input');
                        if (!input || !input.value.trim()) return;
                        var val = input.value.trim();
                        input.value = '';
                        input.disabled = true;
                        global.RespondAPI.sendOther(agentId, val).then(function(success) {
                            input.disabled = false;
                            if (!success) input.value = val;
                            input.focus();
                        });
                    };
                }
            } else {
                // Fallback: regex-parsed numbered options from question text
                var options = global.RespondAPI.parseOptions(questionText);
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
                    optionsContainer.style.display = '';
                } else {
                    optionsContainer.style.display = 'none';
                }
                // Show text input for legacy mode
                if (formContainer) formContainer.style.display = '';
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
