/**
 * Channel Chat Panel — slide-out message feed for channel communication.
 *
 * Provides:
 * - toggle(slug) — open/close/switch channel
 * - close() — slide out and clear state
 * - send() — POST message, optimistic render, clear input
 * - appendMessage(data) — append SSE message to feed
 * - scrollToBottom() — scroll to newest message
 * - isOpenFor(slug) — check if panel is open for a specific channel
 * - isActivelyViewing(slug) — check active view state (v2 suppression infra)
 * - loadEarlier() — cursor pagination for older messages
 */
(function(global) {
    'use strict';

    // Internal state
    var _activeChannelSlug = null;
    var _isOpen = false;
    var _oldestSentAt = null;  // For cursor pagination
    var _isNearBottom = true;
    var _pendingOptimistic = new Map(); // tempId -> element

    // DOM references (cached on first use)
    var _panel = null;
    var _feed = null;
    var _messagesEl = null;
    var _input = null;
    var _nameEl = null;
    var _typeEl = null;
    var _metaEl = null;
    var _loadEarlierEl = null;
    var _loadingEl = null;
    var _newIndicatorEl = null;

    function _getElements() {
        if (_panel) return;
        _panel = document.getElementById('channel-chat-panel');
        _feed = document.getElementById('channel-chat-feed');
        _messagesEl = document.getElementById('channel-chat-messages');
        _input = document.getElementById('channel-chat-input');
        _nameEl = document.getElementById('channel-chat-name');
        _typeEl = document.getElementById('channel-chat-type');
        _metaEl = document.getElementById('channel-chat-meta');
        _loadEarlierEl = document.getElementById('channel-chat-load-earlier');
        _loadingEl = document.getElementById('channel-chat-loading');
        _newIndicatorEl = document.getElementById('channel-chat-new-indicator');
    }

    /**
     * Toggle the chat panel for a given channel slug.
     */
    function toggle(slug) {
        _getElements();

        if (_isOpen && _activeChannelSlug === slug) {
            // Same channel — close
            close();
            return;
        }

        if (_isOpen && _activeChannelSlug !== slug) {
            // Different channel — instant swap (no close animation)
            _activeChannelSlug = slug;
            _clearMessages();
            _updateHeader(slug);
            _loadMessages(slug);
            return;
        }

        // Open panel
        _activeChannelSlug = slug;
        _isOpen = true;
        _updateHeader(slug);
        _clearMessages();
        _loadMessages(slug);

        _panel.classList.add('open');
        _panel.setAttribute('aria-hidden', 'false');

        // Focus input
        setTimeout(function() {
            if (_input) _input.focus();
        }, 300);

        // Add escape listener
        document.addEventListener('keydown', _handleEscape);
    }

    /**
     * Close the chat panel.
     */
    function close() {
        _getElements();
        if (!_isOpen) return;

        _isOpen = false;
        _activeChannelSlug = null;
        _oldestSentAt = null;
        _pendingOptimistic.clear();

        _panel.classList.remove('open');
        _panel.setAttribute('aria-hidden', 'true');

        document.removeEventListener('keydown', _handleEscape);
    }

    /**
     * Send a message to the active channel.
     */
    function send() {
        _getElements();
        if (!_activeChannelSlug || !_input) return;

        var content = _input.value.trim();
        if (!content) return;

        var slug = _activeChannelSlug;

        // Clear input immediately
        _input.value = '';
        _input.style.height = 'auto';

        // Optimistic render
        var tempId = 'temp-' + Date.now() + '-' + Math.random().toString(36).substr(2, 6);
        var optimisticData = {
            id: tempId,
            persona_name: 'You',
            content: content,
            message_type: 'message',
            sent_at: new Date().toISOString(),
            _optimistic: true,
        };
        _renderMessage(optimisticData, true);
        scrollToBottom();

        // POST to API
        fetch('/api/channels/' + encodeURIComponent(slug) + '/messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content: content }),
        })
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }
            return response.json();
        })
        .then(function(data) {
            // Remove optimistic message (SSE will bring the real one, or
            // if SSE is slow, the optimistic one stays in place)
            var optimisticEl = _pendingOptimistic.get(tempId);
            if (optimisticEl) {
                optimisticEl.classList.remove('channel-chat-msg-optimistic');
                _pendingOptimistic.delete(tempId);
            }
        })
        .catch(function(err) {
            console.error('Failed to send message:', err);
            // Mark optimistic message as failed
            var optimisticEl = _pendingOptimistic.get(tempId);
            if (optimisticEl) {
                optimisticEl.classList.add('channel-chat-msg-error');
                // Add retry button
                var retryBtn = document.createElement('button');
                retryBtn.className = 'text-xs text-red hover:text-primary transition-colors ml-2';
                retryBtn.textContent = 'Retry';
                retryBtn.onclick = function() {
                    // Remove failed message
                    optimisticEl.remove();
                    _pendingOptimistic.delete(tempId);
                    // Put content back in input
                    _input.value = content;
                    _input.focus();
                };
                optimisticEl.appendChild(retryBtn);
            }
        });
    }

    /**
     * Append a message from an SSE event to the feed.
     */
    function appendMessage(data) {
        _getElements();
        if (!_isOpen) return;

        // Check if this message was already optimistically rendered
        // by looking for a matching content from the operator
        // (SSE messages from self should replace optimistic ones)
        var isDuplicate = false;
        _pendingOptimistic.forEach(function(el, tempId) {
            if (!isDuplicate) {
                var msgContent = el.getAttribute('data-content');
                if (msgContent === data.content) {
                    // Replace optimistic with real
                    el.classList.remove('channel-chat-msg-optimistic');
                    _pendingOptimistic.delete(tempId);
                    isDuplicate = true;
                }
            }
        });

        if (!isDuplicate) {
            _renderMessage(data, false);
        }

        // Auto-scroll or show indicator
        if (_isNearBottom) {
            scrollToBottom();
        } else {
            _showNewIndicator();
        }
    }

    /**
     * Scroll the feed to the bottom.
     */
    function scrollToBottom() {
        _getElements();
        if (!_feed) return;
        _feed.scrollTop = _feed.scrollHeight;
        _hideNewIndicator();
    }

    /**
     * Check if the panel is open for a specific channel.
     */
    function isOpenFor(slug) {
        return _isOpen && _activeChannelSlug === slug;
    }

    /**
     * Check if the user is actively viewing a specific channel.
     * Infrastructure for v2 notification suppression.
     */
    function isActivelyViewing(slug) {
        return _isOpen && _activeChannelSlug === slug && document.hasFocus();
    }

    /**
     * Load earlier messages (cursor pagination).
     */
    function loadEarlier() {
        _getElements();
        if (!_activeChannelSlug || !_oldestSentAt) return;

        var slug = _activeChannelSlug;
        var url = '/api/channels/' + encodeURIComponent(slug) + '/messages?before=' +
                  encodeURIComponent(_oldestSentAt) + '&limit=50';

        fetch(url)
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(messages) {
                if (!messages || messages.length === 0) {
                    if (_loadEarlierEl) _loadEarlierEl.classList.add('hidden');
                    return;
                }

                // Remember scroll position
                var scrollHeight = _feed.scrollHeight;
                var scrollTop = _feed.scrollTop;

                // Prepend messages (they arrive newest-first from the API, reverse for chronological)
                var sortedMessages = messages.slice().sort(function(a, b) {
                    return new Date(a.sent_at) - new Date(b.sent_at);
                });

                // Update oldest timestamp
                if (sortedMessages.length > 0) {
                    _oldestSentAt = sortedMessages[0].sent_at;
                }

                // Prepend to DOM
                var fragment = document.createDocumentFragment();
                sortedMessages.forEach(function(msg) {
                    var el = _createMessageElement(msg);
                    fragment.appendChild(el);
                });
                _messagesEl.insertBefore(fragment, _messagesEl.firstChild);

                // Restore scroll position
                var newScrollHeight = _feed.scrollHeight;
                _feed.scrollTop = scrollTop + (newScrollHeight - scrollHeight);

                // Hide button if fewer than 50 messages returned
                if (messages.length < 50) {
                    if (_loadEarlierEl) _loadEarlierEl.classList.add('hidden');
                }
            })
            .catch(function(err) {
                console.error('Failed to load earlier messages:', err);
                if (global.Toast) {
                    global.Toast.error('Error', 'Failed to load earlier messages');
                }
            });
    }

    // ── Internal Helpers ──────────────────────────────────────

    function _handleEscape(e) {
        if (e.key === 'Escape') {
            // Don't close if a modal is open
            if (typeof ConfirmDialog !== 'undefined' && ConfirmDialog.isOpen()) return;
            var mgmtModal = document.getElementById('channel-management-modal');
            if (mgmtModal && !mgmtModal.classList.contains('hidden')) return;
            close();
        }
    }

    function _updateHeader(slug) {
        // Pull info from the channel card data attributes
        var card = document.querySelector('.channel-card[data-channel-slug="' + slug + '"]');
        if (card) {
            if (_nameEl) _nameEl.textContent = card.getAttribute('data-channel-name') || slug;
            if (_typeEl) _typeEl.textContent = card.getAttribute('data-channel-type') || '';
            var members = card.getAttribute('data-channel-members') || '';
            var memberCount = members ? members.split(',').length : 0;
            if (_metaEl) _metaEl.textContent = memberCount + ' member' + (memberCount !== 1 ? 's' : '');
        } else {
            if (_nameEl) _nameEl.textContent = slug;
            if (_typeEl) _typeEl.textContent = '';
            if (_metaEl) _metaEl.textContent = '';
        }
    }

    function _clearMessages() {
        if (_messagesEl) _messagesEl.innerHTML = '';
        _oldestSentAt = null;
        _pendingOptimistic.clear();
        _hideNewIndicator();
    }

    function _loadMessages(slug) {
        _getElements();
        if (_loadingEl) _loadingEl.classList.remove('hidden');
        if (_loadEarlierEl) _loadEarlierEl.classList.add('hidden');

        fetch('/api/channels/' + encodeURIComponent(slug) + '/messages?limit=50')
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(messages) {
                if (_loadingEl) _loadingEl.classList.add('hidden');

                if (!messages || messages.length === 0) {
                    _messagesEl.innerHTML = '<div class="text-center text-muted text-sm italic py-8">No messages yet</div>';
                    return;
                }

                // Sort chronologically (oldest first)
                var sorted = messages.slice().sort(function(a, b) {
                    return new Date(a.sent_at) - new Date(b.sent_at);
                });

                // Track oldest for pagination
                _oldestSentAt = sorted[0].sent_at;

                // Render messages
                sorted.forEach(function(msg) {
                    _renderMessage(msg, false);
                });

                // Show load-earlier if we got a full page
                if (messages.length >= 50 && _loadEarlierEl) {
                    _loadEarlierEl.classList.remove('hidden');
                }

                // Scroll to bottom
                scrollToBottom();
            })
            .catch(function(err) {
                console.error('Failed to load messages:', err);
                if (_loadingEl) _loadingEl.classList.add('hidden');
                _messagesEl.innerHTML = '<div class="text-center text-red text-sm py-8">Failed to load messages</div>';
            });
    }

    function _renderMessage(data, isOptimistic) {
        var el = _createMessageElement(data);

        if (isOptimistic) {
            el.classList.add('channel-chat-msg-optimistic');
            el.setAttribute('data-content', data.content || '');
            _pendingOptimistic.set(data.id, el);
        }

        _messagesEl.appendChild(el);
    }

    function _createMessageElement(data) {
        var el = document.createElement('div');
        var isSystem = data.message_type === 'system';

        if (isSystem) {
            el.className = 'channel-chat-msg channel-chat-msg-system text-center text-muted text-xs italic py-1';
            el.textContent = data.content || '';
            return el;
        }

        el.className = 'channel-chat-msg py-1';

        var personaName = data.persona_name || 'Unknown';
        // Determine color: "You" (operator) = cyan, agents = green
        var nameClass = (personaName === 'You' || data._optimistic) ? 'text-cyan' : 'text-green';

        var timestamp = '';
        if (data.sent_at) {
            var date = new Date(data.sent_at);
            var now = new Date();
            var diff = now - date;
            if (diff < 60000) {
                timestamp = 'just now';
            } else if (diff < 3600000) {
                timestamp = Math.floor(diff / 60000) + 'm ago';
            } else if (diff < 86400000) {
                timestamp = Math.floor(diff / 3600000) + 'h ago';
            } else {
                timestamp = date.toLocaleDateString();
            }
        }

        var html = '<div class="flex items-baseline gap-2">' +
            '<span class="' + nameClass + ' text-xs font-medium">' + _escapeHtml(personaName) + '</span>' +
            '<span class="text-muted text-[10px]" title="' + _escapeHtml(data.sent_at || '') + '">' + _escapeHtml(timestamp) + '</span>' +
            '</div>' +
            '<div class="text-secondary text-sm mt-0.5 whitespace-pre-wrap break-words">' + _escapeHtml(data.content || '') + '</div>';

        el.innerHTML = html;
        return el;
    }

    function _showNewIndicator() {
        if (_newIndicatorEl) _newIndicatorEl.classList.remove('hidden');
    }

    function _hideNewIndicator() {
        if (_newIndicatorEl) _newIndicatorEl.classList.add('hidden');
    }

    function _escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    // Track scroll position for auto-scroll decisions
    function _initScrollTracking() {
        _getElements();
        if (!_feed) return;

        _feed.addEventListener('scroll', function() {
            var threshold = 50;
            _isNearBottom = (_feed.scrollHeight - _feed.scrollTop - _feed.clientHeight) < threshold;
            if (_isNearBottom) {
                _hideNewIndicator();
            }
        });
    }

    // Initialize
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', _initScrollTracking);
    } else {
        _initScrollTracking();
    }

    // Public API
    global.ChannelChat = {
        toggle: toggle,
        close: close,
        send: send,
        appendMessage: appendMessage,
        scrollToBottom: scrollToBottom,
        isOpenFor: isOpenFor,
        isActivelyViewing: isActivelyViewing,
        loadEarlier: loadEarlier,
        get _activeChannelSlug() { return _activeChannelSlug; },
    };

})(window);
