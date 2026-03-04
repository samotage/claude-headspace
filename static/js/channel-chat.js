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

    var _infoOpen = false;
    var _addMemberOpen = false;

    // DOM references (cached on first use)
    var _panel = null;
    var _feed = null;
    var _messagesEl = null;
    var _input = null;
    var _nameEl = null;
    var _typeEl = null;
    var _loadEarlierEl = null;
    var _loadingEl = null;
    var _newIndicatorEl = null;
    var _infoPanel = null;
    var _infoToggle = null;
    var _membersEl = null;
    var _detailsEl = null;
    var _memberPillsEl = null;
    var _addMemberArea = null;
    var _addMemberPicker = null;
    var _addBtn = null;
    var _completeBtn = null;
    var _endBtn = null;

    function _getElements() {
        if (_panel) return;
        _panel = document.getElementById('channel-chat-panel');
        _feed = document.getElementById('channel-chat-feed');
        _messagesEl = document.getElementById('channel-chat-messages');
        _input = document.getElementById('channel-chat-input');
        _nameEl = document.getElementById('channel-chat-name');
        _typeEl = document.getElementById('channel-chat-type');
        _loadEarlierEl = document.getElementById('channel-chat-load-earlier');
        _loadingEl = document.getElementById('channel-chat-loading');
        _newIndicatorEl = document.getElementById('channel-chat-new-indicator');
        _infoPanel = document.getElementById('channel-chat-info');
        _infoToggle = document.getElementById('channel-chat-info-toggle');
        _membersEl = document.getElementById('channel-chat-members');
        _detailsEl = document.getElementById('channel-chat-details');
        _memberPillsEl = document.getElementById('channel-chat-member-pills');
        _addMemberArea = document.getElementById('channel-chat-add-member');
        _addMemberPicker = document.getElementById('channel-chat-add-member-picker');
        _addBtn = document.getElementById('channel-chat-add-btn');
        _completeBtn = document.getElementById('channel-chat-complete-btn');
        _endBtn = document.getElementById('channel-chat-end-btn');
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
            _loadMembers(slug);
            _loadMessages(slug);
            _collapseAddMember();
            return;
        }

        // Open panel
        _activeChannelSlug = slug;
        _isOpen = true;
        _updateHeader(slug);
        _loadMembers(slug);
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
        _infoOpen = false;
        _pendingOptimistic.clear();

        _panel.classList.remove('open');
        _panel.setAttribute('aria-hidden', 'true');

        // Collapse info panel
        if (_infoPanel) _infoPanel.classList.add('hidden');
        if (_infoToggle) _infoToggle.classList.remove('text-cyan');

        // Collapse add-member area
        _collapseAddMember();

        // Hide chair controls
        if (_completeBtn) _completeBtn.classList.add('hidden');
        if (_endBtn) _endBtn.classList.add('hidden');

        document.removeEventListener('keydown', _handleEscape);
    }

    /**
     * Toggle the info panel (members + technical details).
     */
    function toggleInfo() {
        _getElements();
        _infoOpen = !_infoOpen;
        if (_infoPanel) {
            _infoPanel.classList.toggle('hidden', !_infoOpen);
        }
        if (_infoToggle) {
            _infoToggle.classList.toggle('text-cyan', _infoOpen);
        }
    }

    /**
     * Toggle the add-member area below the header.
     */
    function toggleAddMember() {
        _getElements();
        if (_addMemberOpen) {
            _collapseAddMember();
        } else {
            _expandAddMember();
        }
    }

    var _selectionWatcher = null;

    function _expandAddMember() {
        _addMemberOpen = true;
        if (_addMemberArea) _addMemberArea.classList.add('open');
        if (_addBtn) _addBtn.classList.add('text-cyan');

        // Fetch current members to exclude from picker, then init autocomplete
        if (_addMemberPicker && global.MemberAutocomplete && _activeChannelSlug) {
            var membersUrl = '/api/channels/' + encodeURIComponent(_activeChannelSlug) + '/members';
            fetch(membersUrl)
                .then(function(r) { return r.ok ? r.json() : []; })
                .then(function(members) {
                    var membersList = Array.isArray(members) ? members : (members.members || []);
                    var excludeAgentIds = [];
                    var excludePersonaSlugs = [];
                    membersList.forEach(function(m) {
                        if (m.agent_id) excludeAgentIds.push(m.agent_id);
                        if (m.persona_slug) excludePersonaSlugs.push(m.persona_slug);
                    });
                    global.MemberAutocomplete.init(_addMemberPicker, {
                        excludeAgentIds: excludeAgentIds,
                        excludePersonaSlugs: excludePersonaSlugs,
                    });
                    _startSelectionWatcher();
                })
                .catch(function() {
                    // Fallback: init without exclusion
                    global.MemberAutocomplete.init(_addMemberPicker);
                    _startSelectionWatcher();
                });
        }
    }

    function _startSelectionWatcher() {
        // Watch for selections and auto-add (MemberAutocomplete has no event callback)
        if (_selectionWatcher) clearInterval(_selectionWatcher);
        _selectionWatcher = setInterval(function() {
            if (!_addMemberOpen || !global.MemberAutocomplete) {
                clearInterval(_selectionWatcher);
                _selectionWatcher = null;
                return;
            }
            var ids = global.MemberAutocomplete.getSelectedAgentIds();
            if (ids.length > 0) {
                _addMemberById(ids[0]);
                clearInterval(_selectionWatcher);
                _selectionWatcher = null;
                return;
            }
            var slugs = global.MemberAutocomplete.getSelectedPersonaSlugs();
            if (slugs.length > 0) {
                _addMemberBySlug(slugs[0]);
                clearInterval(_selectionWatcher);
                _selectionWatcher = null;
            }
        }, 200);
    }

    function _collapseAddMember() {
        _addMemberOpen = false;
        if (_addMemberArea) _addMemberArea.classList.remove('open');
        if (_addBtn) _addBtn.classList.remove('text-cyan');
        if (_selectionWatcher) {
            clearInterval(_selectionWatcher);
            _selectionWatcher = null;
        }
        if (global.MemberAutocomplete) {
            global.MemberAutocomplete.destroy();
        }
    }

    function _addMemberById(agentId) {
        if (!_activeChannelSlug) return;
        var slug = _activeChannelSlug;

        fetch('/api/channels/' + encodeURIComponent(slug) + '/members', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ agent_id: agentId }),
        })
        .then(function(response) {
            if (!response.ok) {
                return response.json().then(function(data) {
                    throw new Error((data.error && data.error.message) || 'HTTP ' + response.status);
                });
            }
            return response.json();
        })
        .then(function() {
            _loadMembers(slug);
            _loadChannelInfo(slug);
            _collapseAddMember();
            if (global.Toast) global.Toast.success('Member added');
        })
        .catch(function(err) {
            console.error('Failed to add member:', err);
            if (global.Toast) global.Toast.error('Error', err.message || 'Failed to add member');
        });
    }

    function _addMemberBySlug(personaSlug) {
        if (!_activeChannelSlug) return;
        var slug = _activeChannelSlug;

        fetch('/api/channels/' + encodeURIComponent(slug) + '/members', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ persona_slug: personaSlug }),
        })
        .then(function(response) {
            if (!response.ok) {
                return response.json().then(function(data) {
                    throw new Error((data.error && data.error.message) || 'HTTP ' + response.status);
                });
            }
            return response.json();
        })
        .then(function() {
            _loadMembers(slug);
            _loadChannelInfo(slug);
            _collapseAddMember();
            if (global.Toast) global.Toast.success('Member added');
        })
        .catch(function(err) {
            console.error('Failed to add member:', err);
            if (global.Toast) global.Toast.error('Error', err.message || 'Failed to add member');
        });
    }

    /**
     * Complete the channel (chair action) with confirmation.
     */
    function completeChannel() {
        if (!_activeChannelSlug) return;
        var slug = _activeChannelSlug;
        if (typeof ConfirmDialog === 'undefined') return;

        ConfirmDialog.show('Complete Channel', 'Mark this channel as complete? Members will be notified.', {
            confirmText: 'Complete',
            confirmClass: 'bg-green hover:bg-green/90',
        }).then(function(ok) {
            if (!ok) return;
            fetch('/api/channels/' + encodeURIComponent(slug) + '/complete', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            })
            .then(function(r) {
                if (!r.ok) {
                    return r.json().then(function(data) {
                        throw new Error((data.error && data.error.message) || 'HTTP ' + r.status);
                    });
                }
                return r.json();
            })
            .then(function() {
                if (global.Toast) global.Toast.success('Channel completed');
                close();
            })
            .catch(function(err) {
                console.error('Failed to complete channel:', err);
                if (global.Toast) global.Toast.error('Error', err.message || 'Failed to complete channel');
            });
        });
    }

    /**
     * End/archive the channel (chair action) with confirmation.
     */
    function endChannel() {
        if (!_activeChannelSlug) return;
        var slug = _activeChannelSlug;
        if (typeof ConfirmDialog === 'undefined') return;

        ConfirmDialog.show('End Channel', 'Archive this channel? This cannot be undone.', {
            confirmText: 'End Channel',
            confirmClass: 'bg-red hover:bg-red/90',
        }).then(function(ok) {
            if (!ok) return;
            fetch('/api/channels/' + encodeURIComponent(slug) + '/archive', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            })
            .then(function(r) {
                if (!r.ok) {
                    return r.json().then(function(data) {
                        throw new Error((data.error && data.error.message) || 'HTTP ' + r.status);
                    });
                }
                return r.json();
            })
            .then(function() {
                if (global.Toast) global.Toast.success('Channel archived');
                close();
            })
            .catch(function(err) {
                console.error('Failed to archive channel:', err);
                if (global.Toast) global.Toast.error('Error', err.message || 'Failed to archive channel');
            });
        });
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
                return response.json().then(function(data) {
                    throw new Error((data.error && data.error.message) || 'HTTP ' + response.status);
                });
            }
            return response.json();
        })
        .then(function(data) {
            // Mark optimistic message as confirmed but keep it in the map
            // so the SSE handler can find and dedup it. If we deleted from
            // the map here, the SSE event would render a duplicate message.
            var optimisticEl = _pendingOptimistic.get(tempId);
            if (optimisticEl) {
                optimisticEl.classList.add('channel-chat-msg-confirmed');
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
        // by looking for a matching content from the operator.
        // Only dedup messages from the operator (agent_id is null for
        // dashboard-sent messages) to avoid dropping agent messages
        // that happen to have the same content.
        var isDuplicate = false;
        if (!data.agent_id && _pendingOptimistic.size > 0) {
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
        }

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
            // Close add-member first if open
            if (_addMemberOpen) {
                _collapseAddMember();
                return;
            }
            close();
        }
    }

    function _updateHeader(slug) {
        _getElements();
        // Pull info from the channel card data attributes for instant display
        var card = document.querySelector('.channel-card[data-channel-slug="' + slug + '"]');
        if (card) {
            if (_nameEl) _nameEl.textContent = card.getAttribute('data-channel-name') || slug;
            if (_typeEl) _typeEl.textContent = card.getAttribute('data-channel-type') || '';
        } else {
            if (_nameEl) _nameEl.textContent = slug;
            if (_typeEl) _typeEl.textContent = '';
        }

        // Fetch full channel info + members for the info panel
        _loadChannelInfo(slug);
    }

    /**
     * Fetch members and render pills in the header + show/hide chair controls.
     */
    function _loadMembers(slug) {
        _getElements();
        var membersUrl = '/api/channels/' + encodeURIComponent(slug) + '/members';

        fetch(membersUrl)
            .then(function(r) { return r.ok ? r.json() : null; })
            .then(function(members) {
                if (!members) return;
                var membersList = Array.isArray(members) ? members : (members.members || []);
                _renderMemberPills(membersList);

                // Show chair controls — operator always has access,
                // backend enforces actual permissions
                var hasChair = membersList.some(function(m) { return m.is_chair; });
                if (_completeBtn) _completeBtn.classList.toggle('hidden', !hasChair);
                if (_endBtn) _endBtn.classList.toggle('hidden', !hasChair);
            })
            .catch(function(err) {
                console.error('Failed to load members for pills:', err);
            });
    }

    /**
     * Render member name pills in the header row.
     */
    function _renderMemberPills(members) {
        if (!_memberPillsEl) return;
        _memberPillsEl.innerHTML = '';

        if (!members || members.length === 0) {
            _memberPillsEl.innerHTML = '<span class="text-muted text-xs italic">No members</span>';
            return;
        }

        members.forEach(function(m) {
            var pill = document.createElement('span');
            var name = _escapeHtml(m.persona_name || m.persona_slug || 'Unknown');

            if (m.is_chair) {
                pill.className = 'channel-chat-member-pill channel-chat-member-pill-chair';
                pill.innerHTML = name + ' <span class="text-amber">&#9733;</span>';
            } else {
                pill.className = 'channel-chat-member-pill';
                pill.textContent = m.persona_name || m.persona_slug || 'Unknown';
            }

            if (m.status !== 'active') {
                pill.style.opacity = '0.5';
            }

            _memberPillsEl.appendChild(pill);
        });
    }

    function _loadChannelInfo(slug) {
        // Fetch channel detail and members in parallel
        var channelUrl = '/api/channels/' + encodeURIComponent(slug);
        var membersUrl = '/api/channels/' + encodeURIComponent(slug) + '/members';

        Promise.all([
            fetch(channelUrl).then(function(r) { return r.ok ? r.json() : null; }),
            fetch(membersUrl).then(function(r) { return r.ok ? r.json() : null; }),
        ]).then(function(results) {
            var channel = results[0];
            var members = results[1];

            // Render members in info panel (pills handled by _loadMembers)
            if (members) {
                var membersList = Array.isArray(members) ? members : (members.members || []);

                if (_membersEl) {
                    if (membersList.length === 0) {
                        _membersEl.innerHTML = '<span class="text-muted italic">No members</span>';
                    } else {
                        var html = '';
                        membersList.forEach(function(m) {
                            var name = _escapeHtml(m.persona_name || m.persona_slug || 'Unknown');
                            var statusDot = m.status === 'active'
                                ? '<span class="inline-block w-1.5 h-1.5 rounded-full bg-green mr-1.5"></span>'
                                : '<span class="inline-block w-1.5 h-1.5 rounded-full bg-muted mr-1.5"></span>';
                            var chairBadge = m.is_chair
                                ? ' <span class="text-amber text-[9px]">chair</span>'
                                : '';
                            var agentInfo = m.agent_id
                                ? ' <span class="text-muted">agent:' + m.agent_id + '</span>'
                                : ' <span class="text-muted/50">no agent</span>';
                            html += '<div class="flex items-center gap-1">' +
                                statusDot +
                                '<span class="text-secondary">' + name + '</span>' +
                                chairBadge + agentInfo +
                                '</div>';
                        });
                        _membersEl.innerHTML = html;
                    }
                }
            }

            // Render technical details
            if (_detailsEl && channel) {
                var lines = [];
                lines.push('<div class="flex justify-between"><span class="text-muted">slug</span><span class="text-secondary">' + _escapeHtml(channel.slug) + '</span></div>');
                lines.push('<div class="flex justify-between"><span class="text-muted">id</span><span class="text-secondary">' + channel.id + '</span></div>');
                lines.push('<div class="flex justify-between"><span class="text-muted">type</span><span class="text-secondary">' + _escapeHtml(channel.channel_type) + '</span></div>');
                lines.push('<div class="flex justify-between"><span class="text-muted">status</span><span class="text-secondary">' + _escapeHtml(channel.status) + '</span></div>');
                if (channel.chair_persona_slug) {
                    lines.push('<div class="flex justify-between"><span class="text-muted">chair</span><span class="text-secondary">' + _escapeHtml(channel.chair_persona_slug) + '</span></div>');
                }
                if (channel.project_id) {
                    lines.push('<div class="flex justify-between"><span class="text-muted">project_id</span><span class="text-secondary">' + channel.project_id + '</span></div>');
                }
                if (channel.organisation_id) {
                    lines.push('<div class="flex justify-between"><span class="text-muted">org_id</span><span class="text-secondary">' + channel.organisation_id + '</span></div>');
                }
                if (channel.created_at) {
                    var created = new Date(channel.created_at);
                    lines.push('<div class="flex justify-between"><span class="text-muted">created</span><span class="text-secondary">' + created.toLocaleString() + '</span></div>');
                }
                if (channel.description) {
                    lines.push('<div class="mt-1.5"><span class="text-muted">description</span><div class="text-secondary mt-0.5">' + _escapeHtml(channel.description) + '</div></div>');
                }
                _detailsEl.innerHTML = lines.join('');
            }
        }).catch(function(err) {
            console.error('Failed to load channel info:', err);
        });
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

    var _escapeHtml = (global.CHUtils && global.CHUtils.escapeHtml) || function(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    };

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
        toggleInfo: toggleInfo,
        toggleAddMember: toggleAddMember,
        completeChannel: completeChannel,
        endChannel: endChannel,
        get _activeChannelSlug() { return _activeChannelSlug; },
    };

})(window);
