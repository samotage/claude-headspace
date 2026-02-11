/**
 * Respond API client for Claude Headspace.
 *
 * Handles sending text responses to Claude Code sessions via the
 * commander socket, with quick-action buttons and free-text input.
 */

(function(global) {
    'use strict';

    var RESPOND_ENDPOINT = '/api/respond';
    var HIGHLIGHT_DURATION = 1000;

    /**
     * Parse numbered options from question text.
     * Matches patterns like "1. Yes / 2. No / 3. Cancel" or "1. Yes\n2. No"
     *
     * @param {string} questionText - The question text from the agent
     * @returns {Array<{number: string, label: string}>} Parsed options
     */
    function parseOptions(questionText) {
        if (!questionText) return [];

        var options = [];
        // Match "N. Label" or "N) Label" patterns
        var regex = /(\d+)[.)]\s*([^\n/]+)/g;
        var match;
        while ((match = regex.exec(questionText)) !== null) {
            var label = match[2].trim();
            // Clean up trailing separators
            label = label.replace(/\s*[/|]\s*$/, '').trim();
            if (label) {
                options.push({ number: match[1], label: label });
            }
        }

        return options;
    }

    /**
     * Auto-resize a textarea to fit its content.
     */
    function autoResizeTextarea(textarea) {
        textarea.style.height = 'auto';
        textarea.style.height = Math.min(textarea.scrollHeight, 160) + 'px';
    }

    /**
     * Attach auto-resize and Enter-to-submit behaviour to a respond textarea.
     */
    function initTextarea(textarea, agentId) {
        if (!textarea || textarea._respondInitDone) return;
        textarea._respondInitDone = true;

        textarea.addEventListener('input', function() {
            autoResizeTextarea(textarea);
        });

        textarea.addEventListener('keydown', function(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                var form = textarea.closest('form');
                if (form) form.requestSubmit();
            }
        });
    }

    /**
     * Respond API client
     */
    var RespondAPI = {
        /**
         * Send a text response to an agent's Claude Code session
         * @param {number} agentId - The agent ID
         * @param {string} text - The text to send
         * @returns {Promise<boolean>} True if response sent successfully
         */
        sendResponse: async function(agentId, text) {
            if (!agentId) {
                console.error('RespondAPI: No agent ID provided');
                return false;
            }
            if (!text || !text.trim()) {
                console.error('RespondAPI: No text provided');
                return false;
            }

            try {
                var response = await CHUtils.apiFetch(RESPOND_ENDPOINT + '/' + agentId, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ text: text.trim() })
                });

                var data = await response.json();

                if (response.ok && data.status === 'ok') {
                    this._showSuccessFeedback(agentId);
                    return true;
                } else {
                    this._handleError(data, agentId);
                    return false;
                }
            } catch (error) {
                console.error('RespondAPI: Request failed', error);
                if (global.Toast) {
                    global.Toast.error(
                        'Could not send response',
                        'Network error - check if the server is running'
                    );
                }
                return false;
            }
        },

        /**
         * Select a structured AskUserQuestion option via arrow keys
         * @param {number} agentId - The agent ID
         * @param {number} optionIndex - Zero-based option index
         * @returns {Promise<boolean>} True if sent successfully
         */
        sendSelect: async function(agentId, optionIndex) {
            if (!agentId) return false;

            try {
                var response = await CHUtils.apiFetch(RESPOND_ENDPOINT + '/' + agentId, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: 'select', option_index: optionIndex })
                });
                var data = await response.json();
                if (response.ok && data.status === 'ok') {
                    this._showSuccessFeedback(agentId);
                    return true;
                } else {
                    this._handleError(data, agentId);
                    return false;
                }
            } catch (error) {
                console.error('RespondAPI: Select request failed', error);
                if (global.Toast) {
                    global.Toast.error('Could not send selection', 'Network error');
                }
                return false;
            }
        },

        /**
         * Send multi-select answers for a multi-tab AskUserQuestion
         * @param {number} agentId - The agent ID
         * @param {Array} answers - Array of {option_index: int} or {option_indices: [int]}
         * @returns {Promise<boolean>} True if sent successfully
         */
        sendMultiSelect: async function(agentId, answers) {
            if (!agentId || !answers || !answers.length) return false;

            try {
                var response = await CHUtils.apiFetch(RESPOND_ENDPOINT + '/' + agentId, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: 'multi_select', answers: answers })
                });
                var data = await response.json();
                if (response.ok && data.status === 'ok') {
                    this._showSuccessFeedback(agentId);
                    return true;
                } else {
                    this._handleError(data, agentId);
                    return false;
                }
            } catch (error) {
                console.error('RespondAPI: Multi-select request failed', error);
                if (global.Toast) {
                    global.Toast.error('Could not send selections', 'Network error');
                }
                return false;
            }
        },

        /**
         * Select "Other" and type custom text
         * @param {number} agentId - The agent ID
         * @param {string} text - Custom text to type
         * @returns {Promise<boolean>} True if sent successfully
         */
        sendOther: async function(agentId, text) {
            if (!agentId || !text || !text.trim()) return false;

            try {
                var response = await CHUtils.apiFetch(RESPOND_ENDPOINT + '/' + agentId, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ mode: 'other', text: text.trim() })
                });
                var data = await response.json();
                if (response.ok && data.status === 'ok') {
                    this._showSuccessFeedback(agentId);
                    return true;
                } else {
                    this._handleError(data, agentId);
                    return false;
                }
            } catch (error) {
                console.error('RespondAPI: Other request failed', error);
                if (global.Toast) {
                    global.Toast.error('Could not send response', 'Network error');
                }
                return false;
            }
        },

        /**
         * Handle a quick-action button click (legacy numbered options)
         * @param {number} agentId - The agent ID
         * @param {string} optionNumber - The option number to send
         */
        sendOption: function(agentId, optionNumber) {
            return this.sendResponse(agentId, optionNumber);
        },

        /**
         * Handle free-text form submission
         * @param {Event} event - The form submit event
         * @param {number} agentId - The agent ID
         */
        handleSubmit: function(event, agentId) {
            event.preventDefault();
            var input = event.target.querySelector('.respond-text-input');
            if (!input || !input.value.trim()) return;

            var text = input.value.trim();
            input.value = '';
            input.disabled = true;
            autoResizeTextarea(input);

            this.sendResponse(agentId, text).then(function(success) {
                input.disabled = false;
                if (!success) {
                    input.value = text; // Restore text on failure
                    autoResizeTextarea(input);
                }
                input.focus();
            });
        },

        /**
         * Show success feedback on the agent card
         * @param {number} agentId
         */
        _showSuccessFeedback: function(agentId) {
            var card = document.querySelector('[data-agent-id="' + agentId + '"]');
            if (!card) return;

            // Add success highlight
            card.classList.add('respond-success');
            setTimeout(function() {
                card.classList.remove('respond-success');
            }, HIGHLIGHT_DURATION);

            // Hide the input widget (state will transition to PROCESSING)
            var widget = card.querySelector('.respond-widget');
            if (widget) {
                widget.style.transition = 'opacity 0.3s';
                widget.style.opacity = '0';
                setTimeout(function() {
                    widget.style.display = 'none';
                }, 300);
            }

            if (global.Toast) {
                global.Toast.success('Response sent', 'Agent is now processing');
            }
        },

        /**
         * Handle error responses with appropriate toasts
         * @param {Object} data - Error response data
         * @param {number} agentId
         */
        _handleError: function(data, agentId) {
            if (!global.Toast) {
                console.error('RespondAPI: Error -', data.message || 'Unknown error');
                return;
            }

            var errorType = data.error_type || '';
            var message = data.message || data.error || 'Unknown error';

            if (errorType === 'wrong_state') {
                global.Toast.show('warning',
                    'Agent not waiting for input',
                    'The agent may have already continued. State will refresh automatically.'
                );
            } else if (errorType === 'socket_not_found' || errorType === 'connection_refused' || errorType === 'process_dead') {
                global.Toast.show('error',
                    'Session unreachable',
                    'Commander socket is not available. Was the session started with claudec?'
                );
            } else if (errorType === 'no_session_id') {
                global.Toast.show('error',
                    'No session ID',
                    'This agent does not have a session ID for commander socket access.'
                );
            } else {
                global.Toast.error('Send failed', message);
            }
        },

        /**
         * Parse options from question text (exposed for template use)
         */
        parseOptions: parseOptions,

        /**
         * Initialize a respond textarea with auto-resize and Enter-to-submit.
         */
        initTextarea: initTextarea
    };

    // Export
    global.RespondAPI = RespondAPI;

})(typeof window !== 'undefined' ? window : this);
