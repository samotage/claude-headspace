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
     * Map safety classification to color scheme classes.
     * Safety comes from classify_safety() in permission_summarizer.py.
     */
    function getSafetyColors(safety) {
        switch (safety) {
            case 'safe_read':
                return {
                    btn: 'border-green/40 text-green bg-green/10 hover:bg-green/20',
                    container: 'border-green/20 bg-green/5',
                    send: 'bg-green/20 text-green border-green/30 hover:bg-green/30',
                    label: 'read'
                };
            case 'destructive':
                return {
                    btn: 'border-red/40 text-red bg-red/10 hover:bg-red/20',
                    container: 'border-red/20 bg-red/5',
                    send: 'bg-red/20 text-red border-red/30 hover:bg-red/30',
                    label: 'destructive'
                };
            default:  // safe_write, unknown, missing
                return {
                    btn: 'border-amber/40 text-amber bg-amber/10 hover:bg-amber/20',
                    container: 'border-amber/20 bg-amber/5',
                    send: 'bg-amber/20 text-amber border-amber/30 hover:bg-amber/30',
                    label: 'write'
                };
        }
    }

    /**
     * Render a stacked multi-question form for AskUserQuestion with 2+ questions.
     * Each question gets its own section with radio (single-select) or checkbox
     * (multi-select) behavior. A submit button at the bottom is enabled when all
     * questions are answered.
     */
    function _renderMultiQuestionForm(container, questions, agentId, colors) {
        var form = document.createElement('div');
        form.className = 'multi-question-form';

        // Track selections: { questionIndex: int|null (single) or Set (multi) }
        var selections = {};

        questions.forEach(function(q, qIdx) {
            var isMulti = q.multiSelect === true;
            selections[qIdx] = isMulti ? new Set() : null;

            var section = document.createElement('div');
            section.className = 'question-section';

            var header = document.createElement('div');
            header.className = 'question-section-header';
            header.textContent = (q.header ? q.header + ': ' : '') + (q.question || '');
            section.appendChild(header);

            var optionsWrap = document.createElement('div');
            optionsWrap.className = 'question-section-options';

            var opts = q.options || [];
            opts.forEach(function(opt, optIdx) {
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'question-option ' + colors.btn;
                btn.setAttribute('data-q-idx', qIdx);
                btn.setAttribute('data-opt-idx', optIdx);

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
                    if (isMulti) {
                        // Checkbox behavior: toggle
                        if (selections[qIdx].has(optIdx)) {
                            selections[qIdx].delete(optIdx);
                            btn.classList.remove('toggled');
                        } else {
                            selections[qIdx].add(optIdx);
                            btn.classList.add('toggled');
                        }
                    } else {
                        // Radio behavior: deselect siblings, select this
                        var siblings = optionsWrap.querySelectorAll('.question-option');
                        for (var s = 0; s < siblings.length; s++) {
                            siblings[s].classList.remove('selected');
                        }
                        btn.classList.add('selected');
                        selections[qIdx] = optIdx;
                    }
                    _updateSubmitButton(submitBtn, selections, questions);
                };

                optionsWrap.appendChild(btn);
            });

            section.appendChild(optionsWrap);
            form.appendChild(section);
        });

        var submitBtn = document.createElement('button');
        submitBtn.type = 'button';
        submitBtn.className = 'multi-submit-btn';
        submitBtn.textContent = 'Submit All';
        submitBtn.disabled = true;

        submitBtn.onclick = function() {
            if (submitBtn.disabled) return;
            // Build answers array
            var answers = [];
            for (var i = 0; i < questions.length; i++) {
                var isMulti = questions[i].multiSelect === true;
                if (isMulti) {
                    answers.push({ option_indices: Array.from(selections[i]).sort() });
                } else {
                    answers.push({ option_index: selections[i] });
                }
            }
            submitBtn.disabled = true;
            submitBtn.textContent = 'Sending...';
            global.RespondAPI.sendMultiSelect(agentId, answers);
        };

        form.appendChild(submitBtn);
        container.appendChild(form);
    }

    /**
     * Enable/disable the multi-question submit button based on whether
     * all questions have at least one selection.
     */
    function _updateSubmitButton(btn, selections, questions) {
        var allAnswered = true;
        for (var i = 0; i < questions.length; i++) {
            var isMulti = questions[i].multiSelect === true;
            if (isMulti) {
                if (!selections[i] || selections[i].size === 0) {
                    allAnswered = false;
                    break;
                }
            } else {
                if (selections[i] === null || selections[i] === undefined) {
                    allAnswered = false;
                    break;
                }
            }
        }
        btn.disabled = !allAnswered;
    }

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

        // Extract safety classification and compute color scheme
        var safety = (questionOptions && questionOptions.safety) || 'unknown';
        var colors = getSafetyColors(safety);

        // Apply safety colors to the widget container (border-top + background)
        widget.className = widget.className
            .replace(/border-(?:amber|green|red)\/20/g, '')
            .replace(/bg-(?:amber|green|red)\/5/g, '')
            .trim();
        widget.classList.add.apply(widget.classList, colors.container.split(' '));

        var optionsContainer = widget.querySelector('.respond-options');
        var formContainer = widget.querySelector('.respond-form');

        // Apply safety colors to the Send button
        var sendBtn = widget.querySelector('.respond-send-btn');
        if (sendBtn) {
            sendBtn.className = 'respond-send-btn px-3 py-1 text-xs font-medium rounded border transition-colors ' + colors.send;
        }

        if (optionsContainer && global.RespondAPI) {
            optionsContainer.innerHTML = '';

            // Check for structured AskUserQuestion options
            var structuredOptions = null;
            var allQuestions = null;
            if (questionOptions && questionOptions.questions &&
                questionOptions.questions.length > 0) {
                allQuestions = questionOptions.questions;
                var q = allQuestions[0];
                if (q.options && q.options.length > 0) {
                    structuredOptions = q.options;
                }
            }

            // Multi-question form (2+ questions with options)
            if (allQuestions && allQuestions.length > 1) {
                _renderMultiQuestionForm(optionsContainer, allQuestions, agentId, colors);
                optionsContainer.style.display = '';
                if (formContainer) formContainer.style.display = 'none';
            } else if (structuredOptions) {
                // Render structured option buttons
                structuredOptions.forEach(function(opt, index) {
                    var btn = document.createElement('button');
                    btn.type = 'button';
                    btn.className = 'respond-option-btn w-full text-left px-3 py-2 text-xs rounded border transition-colors ' + colors.btn;
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
                        input.style.height = 'auto';
                        global.RespondAPI.sendOther(agentId, val).then(function(success) {
                            input.disabled = false;
                            if (!success) {
                                input.value = val;
                                input.style.height = 'auto';
                                input.style.height = Math.min(input.scrollHeight, 160) + 'px';
                            }
                            input.focus();
                        });
                    };
                }
            } else {
                // Check if this looks like a permission request (Bash:, Read:, etc.)
                // and generate default Yes/No buttons as fallback
                var isPermission = /^(Bash|Read|Write|Edit|Glob|Grep|NotebookEdit|WebFetch|WebSearch|Permission( needed)?):/.test(questionText)
                    || questionText === 'Claude is waiting for your input';

                if (isPermission) {
                    // Default Yes/No buttons for permission requests
                    [{label: 'Yes', desc: 'Allow this action', idx: 0},
                     {label: 'No', desc: 'Deny this action', idx: 1}].forEach(function(opt) {
                        var btn = document.createElement('button');
                        btn.type = 'button';
                        btn.className = 'respond-option-btn w-full text-left px-3 py-2 text-xs rounded border transition-colors ' + colors.btn;
                        var label = document.createElement('span');
                        label.className = 'font-medium';
                        label.textContent = opt.label;
                        btn.appendChild(label);
                        var desc = document.createElement('span');
                        desc.className = 'text-muted ml-2';
                        desc.textContent = opt.desc;
                        btn.appendChild(desc);
                        btn.onclick = function() {
                            global.RespondAPI.sendSelect(agentId, opt.idx);
                        };
                        optionsContainer.appendChild(btn);
                    });
                    optionsContainer.style.display = '';
                    if (formContainer) formContainer.style.display = 'none';
                } else {
                    // Fallback: regex-parsed numbered options from question text
                    var options = global.RespondAPI.parseOptions(questionText);
                    if (options.length > 0) {
                        options.forEach(function(opt) {
                            var btn = document.createElement('button');
                            btn.type = 'button';
                            btn.className = 'respond-option-btn px-3 py-1 text-xs font-medium rounded border transition-colors ' + colors.btn;
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
                    // Show text input for non-permission legacy mode
                    if (formContainer) formContainer.style.display = '';
                }
            }
        }

        // Initialize textarea auto-resize
        var textarea = widget.querySelector('.respond-text-input');
        if (textarea && global.RespondAPI) {
            global.RespondAPI.initTextarea(textarea, agentId);
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
        requestAnimationFrame(function() { requestAnimationFrame(initRespondWidgets); });
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
