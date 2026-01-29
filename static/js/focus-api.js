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
                    // Error - show toast
                    this._handleError(data);
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
         * Handle error responses with appropriate toasts
         */
        _handleError: function(data) {
            if (!window.Toast) {
                console.error('FocusAPI: Error -', data.message || 'Unknown error');
                return;
            }

            const message = data.message || '';

            if (message.includes('permission') || message.includes('automation')) {
                window.Toast.error(
                    'Permission required',
                    'Grant iTerm automation permission in System Preferences → Privacy → Automation'
                );
            } else if (message.includes('inactive') || message.includes('ended') || message.includes('not found')) {
                window.Toast.error(
                    'Session ended',
                    'Cannot focus terminal - session no longer active'
                );
            } else {
                window.Toast.error(
                    'Could not focus terminal',
                    message || 'Check if iTerm is running'
                );
            }
        }
    };

    // Export
    global.FocusAPI = FocusAPI;

})(typeof window !== 'undefined' ? window : this);
