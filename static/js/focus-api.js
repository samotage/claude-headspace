/**
 * Focus API client for Claude Headspace.
 *
 * Handles click-to-focus integration with iTerm windows.
 */

(function(global) {
    'use strict';

    const FOCUS_ENDPOINT = '/api/focus';
    const HIGHLIGHT_DURATION = 1000; // 1 second

    /**
     * Focus API client
     */
    const FocusAPI = {
        /**
         * Focus on an agent's iTerm window
         * @param {number} agentId - The agent ID
         * @returns {Promise<boolean>} True if focus succeeded
         */
        focusAgent: async function(agentId) {
            if (!agentId) {
                console.error('FocusAPI: No agent ID provided');
                return false;
            }

            try {
                const response = await fetch(`${FOCUS_ENDPOINT}/${agentId}`, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });

                const data = await response.json();

                if (response.ok && data.status === 'ok') {
                    // Success - show highlight
                    this._showSuccessFeedback(agentId);
                    return true;
                } else {
                    // Error - show toast with dismiss option
                    this._handleError(data, agentId);
                    return false;
                }
            } catch (error) {
                console.error('FocusAPI: Request failed', error);

                // Network or other error
                if (window.Toast) {
                    window.Toast.error(
                        'Could not focus terminal',
                        'Network error - check if the server is running'
                    );
                }
                return false;
            }
        },

        /**
         * Show success feedback on the agent card
         */
        _showSuccessFeedback: function(agentId) {
            // Find the agent card
            const card = document.querySelector(`[data-agent-id="${agentId}"]`);
            if (!card) return;

            // Add highlight class
            card.classList.add('focus-highlight');

            // Also highlight the recommended next panel if it shows this agent
            const recommendedPanel = document.querySelector('#recommended-next-panel [data-agent-id="' + agentId + '"]');
            if (recommendedPanel) {
                recommendedPanel.classList.add('focus-highlight');
            }

            // Remove after animation
            setTimeout(() => {
                card.classList.remove('focus-highlight');
                if (recommendedPanel) {
                    recommendedPanel.classList.remove('focus-highlight');
                }
            }, HIGHLIGHT_DURATION);
        },

        /**
         * Dismiss an agent (mark as ended) and remove its card from the dashboard
         */
        dismissAgent: async function(agentId) {
            try {
                const response = await fetch(`/api/agents/${agentId}/dismiss`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                if (response.ok) {
                    // Remove agent card from DOM
                    const card = document.querySelector(`[data-agent-id="${agentId}"]`);
                    if (card) {
                        card.style.transition = 'opacity 0.3s, transform 0.3s';
                        card.style.opacity = '0';
                        card.style.transform = 'scale(0.95)';
                        setTimeout(() => card.remove(), 300);
                    }
                    if (window.Toast) {
                        window.Toast.success('Agent dismissed', 'Agent card removed from dashboard');
                    }
                } else {
                    const data = await response.json();
                    if (window.Toast) {
                        window.Toast.error('Dismiss failed', data.message || 'Could not dismiss agent');
                    }
                }
            } catch (error) {
                console.error('FocusAPI: Dismiss failed', error);
                if (window.Toast) {
                    window.Toast.error('Dismiss failed', 'Network error');
                }
            }
        },

        /**
         * Handle error responses with appropriate toasts
         */
        _handleError: function(data, agentId) {
            if (!window.Toast) {
                console.error('FocusAPI: Error -', data.message || 'Unknown error');
                return;
            }

            const message = data.message || '';

            // Build dismiss action for stale/unfocusable agents
            var dismissAction = agentId ? [{
                label: 'Dismiss Agent',
                className: 'text-xs font-medium px-3 py-1 rounded border border-red/40 text-red hover:bg-red/10 transition-colors mr-2',
                onClick: function() {
                    window.FocusAPI.dismissAgent(agentId);
                }
            }] : [];

            if (message.includes('permission') || message.includes('automation')) {
                window.Toast.show('error',
                    'Permission required',
                    'Grant iTerm automation permission in System Preferences → Privacy → Automation',
                    { actions: dismissAction }
                );
            } else if (message.includes('inactive') || message.includes('ended') || message.includes('not found')) {
                window.Toast.show('error',
                    'Session ended',
                    'Cannot focus terminal — session no longer active',
                    { actions: dismissAction }
                );
            } else {
                window.Toast.show('error',
                    'Could not focus terminal',
                    message || 'Check if iTerm is running',
                    { actions: dismissAction }
                );
            }
        }
    };

    // Export
    global.FocusAPI = FocusAPI;

})(typeof window !== 'undefined' ? window : this);
