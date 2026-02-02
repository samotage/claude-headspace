/**
 * Objective page client for Claude Headspace.
 *
 * Handles explicit save via button/form submit and history pagination.
 */

(function(global) {
    'use strict';

    const API_ENDPOINT = '/api/objective';
    const HISTORY_ENDPOINT = '/api/objective/history';
    const DELETE_HISTORY_ENDPOINT = '/api/objective/history/';
    const PRIORITY_ENDPOINT = '/api/objective/priority';
    const PER_PAGE = 10;

    /**
     * Objective page controller
     */
    const ObjectivePage = {
        currentPage: 1,
        isSaving: false,

        /**
         * Initialize the objective page
         */
        init: function() {
            this.form = document.getElementById('objective-form');
            this.textInput = document.getElementById('objective-text');
            this.constraintsInput = document.getElementById('objective-constraints');
            this.saveBtn = document.getElementById('save-btn');
            this.newBtn = document.getElementById('new-objective-btn');
            this.saveStatus = document.getElementById('save-status');
            this.loadMoreBtn = document.getElementById('load-more-btn');
            this.historyList = document.getElementById('history-list');
            this.priorityToggle = document.getElementById('priority-toggle');
            this.priorityLabel = document.getElementById('priority-toggle-label');

            if (this.priorityToggle && !this.priorityToggle.disabled) {
                this.priorityToggle.addEventListener('click', () => this._togglePriority());
            }
            if (this.form) {
                this.form.addEventListener('submit', (e) => {
                    e.preventDefault();
                    this._save(false);
                });
            }
            if (this.newBtn) {
                this.newBtn.addEventListener('click', () => this._save(true));
            }
            if (this.loadMoreBtn) {
                this.loadMoreBtn.addEventListener('click', () => this._loadMore());
                this.currentPage = parseInt(this.loadMoreBtn.dataset.page) || 2;
            }

            // Event delegation for delete buttons on history items
            document.addEventListener('click', (e) => {
                const btn = e.target.closest('.delete-history-btn');
                if (btn) {
                    const id = btn.dataset.historyId;
                    if (id) this._deleteHistory(parseInt(id, 10), btn);
                }
            });
        },

        /**
         * Save the objective
         * @param {boolean} isNew - If true, archives current and creates new objective
         */
        _save: async function(isNew) {
            const text = this.textInput ? this.textInput.value.trim() : '';

            // Don't save empty objectives
            if (!text) {
                this._updateStatus('error', 'Objective text is required');
                return;
            }

            // Prevent concurrent saves
            if (this.isSaving) {
                return;
            }

            this.isSaving = true;
            this._updateStatus('saving');
            if (this.saveBtn) this.saveBtn.disabled = true;
            if (this.newBtn) this.newBtn.disabled = true;

            const constraints = this.constraintsInput ? this.constraintsInput.value.trim() : '';

            try {
                const response = await fetch(API_ENDPOINT, {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        text: text,
                        constraints: constraints || null,
                        new: isNew || false
                    })
                });

                const data = await response.json();

                if (response.ok) {
                    this._updateStatus(isNew ? 'created' : 'saved');
                    this._refreshHistory();
                } else {
                    this._updateStatus('error', data.error || 'Failed to save');
                }
            } catch (error) {
                console.error('ObjectivePage: Save failed', error);
                this._updateStatus('error', 'Network error');
            } finally {
                this.isSaving = false;
                if (this.saveBtn) this.saveBtn.disabled = false;
                if (this.newBtn) this.newBtn.disabled = false;
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
                    setTimeout(() => {
                        if (this.saveStatus.textContent === 'Saved') {
                            this.saveStatus.textContent = '';
                        }
                    }, 3000);
                    break;
                case 'created':
                    this.saveStatus.textContent = 'New objective created';
                    this.saveStatus.className = 'text-sm text-green';
                    setTimeout(() => {
                        if (this.saveStatus.textContent === 'New objective created') {
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
         * Delete a history item after confirmation
         */
        _deleteHistory: async function(id, button) {
            if (!window.confirm('Delete this objective history item?')) return;

            button.disabled = true;

            try {
                var response = await fetch(DELETE_HISTORY_ENDPOINT + id, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    var article = button.closest('article');
                    if (article) {
                        article.style.transition = 'opacity 0.3s';
                        article.style.opacity = '0';
                        setTimeout(function() { article.remove(); }, 300);
                    }

                    // Update total count on load-more button
                    if (this.loadMoreBtn && this.loadMoreBtn.dataset.total) {
                        var newTotal = parseInt(this.loadMoreBtn.dataset.total, 10) - 1;
                        this.loadMoreBtn.dataset.total = newTotal;
                    }
                } else {
                    console.error('ObjectivePage: Delete failed', response.status);
                    button.disabled = false;
                }
            } catch (error) {
                console.error('ObjectivePage: Delete failed', error);
                button.disabled = false;
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
                <article class="p-4 bg-surface rounded border border-border" data-history-id="${item.id}">
                    <div class="flex items-start justify-between gap-4">
                        <div class="flex-1 min-w-0">
                            <p class="text-primary break-words">${this._escapeHtml(item.text)}</p>
                            ${constraintsHtml}
                        </div>
                        <button type="button"
                                class="delete-history-btn flex-shrink-0 text-muted hover:text-red transition-colors text-xs font-mono px-1"
                                data-history-id="${item.id}"
                                title="Delete history item">[x]</button>
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
         * Toggle priority scoring on/off
         */
        _togglePriority: async function() {
            if (!this.priorityToggle || this.priorityToggle.disabled) return;

            // Read current state from the dot position
            var dot = this.priorityToggle.querySelector('.toggle-dot');
            var currentlyEnabled = dot && dot.classList.contains('left-7');
            var newEnabled = !currentlyEnabled;

            // Optimistic UI update
            this._updateToggleUI(newEnabled);

            try {
                var response = await fetch(PRIORITY_ENDPOINT, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ enabled: newEnabled })
                });

                if (!response.ok) {
                    // Revert on failure
                    this._updateToggleUI(currentlyEnabled);
                }
            } catch (error) {
                console.error('ObjectivePage: Priority toggle failed', error);
                this._updateToggleUI(currentlyEnabled);
            }
        },

        /**
         * Update toggle button UI
         */
        _updateToggleUI: function(enabled) {
            if (!this.priorityToggle) return;

            var dot = this.priorityToggle.querySelector('.toggle-dot');

            if (enabled) {
                this.priorityToggle.classList.add('bg-cyan');
                this.priorityToggle.classList.remove('bg-surface', 'border', 'border-border');
                if (dot) {
                    dot.classList.add('left-7');
                    dot.classList.remove('left-1');
                }
            } else {
                this.priorityToggle.classList.remove('bg-cyan');
                this.priorityToggle.classList.add('bg-surface', 'border', 'border-border');
                if (dot) {
                    dot.classList.remove('left-7');
                    dot.classList.add('left-1');
                }
            }

            if (this.priorityLabel) {
                this.priorityLabel.textContent = enabled ? 'Enabled' : 'Disabled';
                this.priorityLabel.classList.toggle('text-green', enabled);
                this.priorityLabel.classList.toggle('text-muted', !enabled);
            }

            this.priorityToggle.title = enabled ? 'Disable priority scoring' : 'Enable priority scoring';
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
