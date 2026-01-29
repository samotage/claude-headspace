/**
 * Objective page client for Claude Headspace.
 *
 * Handles auto-save with debounce and history pagination.
 */

(function(global) {
    'use strict';

    const API_ENDPOINT = '/api/objective';
    const HISTORY_ENDPOINT = '/api/objective/history';
    const DEBOUNCE_DELAY = 2500; // 2.5 seconds
    const PER_PAGE = 10;

    /**
     * Objective page controller
     */
    const ObjectivePage = {
        debounceTimer: null,
        currentPage: 1,
        isSaving: false,

        /**
         * Initialize the objective page
         */
        init: function() {
            this.textInput = document.getElementById('objective-text');
            this.constraintsInput = document.getElementById('objective-constraints');
            this.saveStatus = document.getElementById('save-status');
            this.loadMoreBtn = document.getElementById('load-more-btn');
            this.historyList = document.getElementById('history-list');

            if (this.textInput) {
                this.textInput.addEventListener('input', () => this._handleInput());
            }
            if (this.constraintsInput) {
                this.constraintsInput.addEventListener('input', () => this._handleInput());
            }
            if (this.loadMoreBtn) {
                this.loadMoreBtn.addEventListener('click', () => this._loadMore());
                this.currentPage = parseInt(this.loadMoreBtn.dataset.page) || 2;
            }
        },

        /**
         * Handle input changes with debounce
         */
        _handleInput: function() {
            // Cancel any pending save
            if (this.debounceTimer) {
                clearTimeout(this.debounceTimer);
            }

            // Don't show "saving" status while still typing
            // Start new debounce timer
            this.debounceTimer = setTimeout(() => {
                this._save();
            }, DEBOUNCE_DELAY);
        },

        /**
         * Save the objective
         */
        _save: async function() {
            const text = this.textInput ? this.textInput.value.trim() : '';

            // Don't save empty objectives
            if (!text) {
                return;
            }

            // Prevent concurrent saves
            if (this.isSaving) {
                return;
            }

            this.isSaving = true;
            this._updateStatus('saving');

            const constraints = this.constraintsInput ? this.constraintsInput.value.trim() : '';

            try {
                const response = await fetch(API_ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        text: text,
                        constraints: constraints || null
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    this._updateStatus('saved');
                    // Refresh history to show new entry
                    this._refreshHistory();
                } else {
                    this._updateStatus('error', data.error || 'Failed to save');
                }
            } catch (error) {
                console.error('ObjectivePage: Save failed', error);
                this._updateStatus('error', 'Network error');
            } finally {
                this.isSaving = false;
            }
        },

        /**
         * Update the save status indicator
         */
        _updateStatus: function(status, message) {
            if (!this.saveStatus) return;

            switch (status) {
                case 'saving':
                    this.saveStatus.textContent = 'Saving...';
                    this.saveStatus.className = 'text-sm text-amber';
                    break;
                case 'saved':
                    this.saveStatus.textContent = 'Saved';
                    this.saveStatus.className = 'text-sm text-green';
                    // Auto-dismiss after 3 seconds
                    setTimeout(() => {
                        if (this.saveStatus.textContent === 'Saved') {
                            this.saveStatus.textContent = '';
                        }
                    }, 3000);
                    break;
                case 'error':
                    this.saveStatus.textContent = message || 'Error saving';
                    this.saveStatus.className = 'text-sm text-red';
                    break;
                default:
                    this.saveStatus.textContent = '';
                    this.saveStatus.className = 'text-sm text-muted';
            }
        },

        /**
         * Refresh the history list after saving
         */
        _refreshHistory: async function() {
            try {
                const response = await fetch(`${HISTORY_ENDPOINT}?page=1&per_page=${PER_PAGE}`);
                const data = await response.json();

                if (response.ok && data.items) {
                    this._renderHistory(data.items, true);
                    this._updateLoadMoreButton(data);
                }
            } catch (error) {
                console.error('ObjectivePage: Failed to refresh history', error);
            }
        },

        /**
         * Load more history items
         */
        _loadMore: async function() {
            if (!this.loadMoreBtn) return;

            const page = this.currentPage;
            this.loadMoreBtn.disabled = true;
            this.loadMoreBtn.textContent = 'Loading...';

            try {
                const response = await fetch(`${HISTORY_ENDPOINT}?page=${page}&per_page=${PER_PAGE}`);
                const data = await response.json();

                if (response.ok && data.items) {
                    this._renderHistory(data.items, false);
                    this.currentPage++;
                    this._updateLoadMoreButton(data);
                }
            } catch (error) {
                console.error('ObjectivePage: Failed to load more history', error);
            } finally {
                this.loadMoreBtn.disabled = false;
                this.loadMoreBtn.textContent = 'Load more';
            }
        },

        /**
         * Render history items
         */
        _renderHistory: function(items, replace) {
            if (!this.historyList) {
                // Create history list if it doesn't exist (was empty state)
                const emptyHistory = document.getElementById('empty-history');
                if (emptyHistory) {
                    const container = emptyHistory.parentElement;
                    emptyHistory.remove();
                    this.historyList = document.createElement('div');
                    this.historyList.id = 'history-list';
                    this.historyList.className = 'space-y-4';
                    container.insertBefore(this.historyList, container.querySelector('.mt-4'));
                }
            }

            if (!this.historyList) return;

            const html = items.map(item => this._renderHistoryItem(item)).join('');

            if (replace) {
                this.historyList.innerHTML = html;
            } else {
                this.historyList.insertAdjacentHTML('beforeend', html);
            }
        },

        /**
         * Render a single history item
         */
        _renderHistoryItem: function(item) {
            const startedAt = new Date(item.started_at);
            const endedAt = item.ended_at ? new Date(item.ended_at) : null;

            const constraintsHtml = item.constraints
                ? `<p class="mt-2 text-sm text-secondary break-words">
                       <span class="text-muted">Constraints:</span> ${this._escapeHtml(item.constraints)}
                   </p>`
                : '';

            const endedHtml = endedAt
                ? `<span>Ended: <time datetime="${item.ended_at}">${this._formatDate(endedAt)}</time></span>`
                : '<span class="text-cyan">Current</span>';

            return `
                <article class="p-4 bg-surface rounded border border-border">
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex-1 min-w-0">
                            <p class="text-primary break-words">${this._escapeHtml(item.text)}</p>
                            ${constraintsHtml}
                        </div>
                    </div>
                    <div class="mt-3 flex flex-wrap gap-4 text-xs text-muted">
                        <span>Started: <time datetime="${item.started_at}">${this._formatDate(startedAt)}</time></span>
                        ${endedHtml}
                    </div>
                </article>
            `;
        },

        /**
         * Update the load more button visibility
         */
        _updateLoadMoreButton: function(data) {
            const hasMore = data.page < data.pages;

            if (!this.loadMoreBtn) {
                // Create button if needed
                if (hasMore && this.historyList) {
                    const container = this.historyList.parentElement;
                    const btnContainer = document.createElement('div');
                    btnContainer.className = 'mt-4 text-center';
                    btnContainer.innerHTML = `
                        <button id="load-more-btn"
                                class="px-6 py-2 bg-surface border border-border rounded text-secondary hover:text-primary hover:border-cyan transition-colors min-h-[44px]"
                                data-page="${data.page + 1}"
                                data-total="${data.total}">
                            Load more
                        </button>
                    `;
                    container.appendChild(btnContainer);
                    this.loadMoreBtn = document.getElementById('load-more-btn');
                    this.loadMoreBtn.addEventListener('click', () => this._loadMore());
                    this.currentPage = data.page + 1;
                }
            } else {
                if (hasMore) {
                    this.loadMoreBtn.style.display = '';
                    this.loadMoreBtn.dataset.page = data.page + 1;
                } else {
                    this.loadMoreBtn.style.display = 'none';
                }
            }
        },

        /**
         * Format a date for display
         */
        _formatDate: function(date) {
            return date.toISOString().slice(0, 16).replace('T', ' ');
        },

        /**
         * Escape HTML to prevent XSS
         */
        _escapeHtml: function(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => ObjectivePage.init());
    } else {
        ObjectivePage.init();
    }

    // Export for potential external use
    global.ObjectivePage = ObjectivePage;

})(typeof window !== 'undefined' ? window : this);
