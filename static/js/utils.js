/**
 * Shared utility functions for Claude Headspace frontend.
 *
 * Loaded in base.html before all other scripts.
 * Access via window.CHUtils namespace.
 */
(function() {
    'use strict';

    var _escapeDiv = document.createElement('div');

    /**
     * Escape HTML special characters to prevent XSS.
     * Uses DOM textContent/innerHTML for correctness.
     *
     * @param {string} text - Raw text to escape
     * @returns {string} HTML-safe string
     */
    function escapeHtml(text) {
        if (text == null) return '';
        _escapeDiv.textContent = String(text);
        return _escapeDiv.innerHTML;
    }

    // Export to global namespace
    window.CHUtils = {
        escapeHtml: escapeHtml
    };
})();
