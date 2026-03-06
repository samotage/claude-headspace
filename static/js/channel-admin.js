/**
 * ChannelAdmin — admin page controller for /channels.
 *
 * IIFE module exposing a `ChannelAdmin` global. Handles:
 * - Channel list fetching and rendering
 * - Status filter tabs (Active default, Pending, Complete, Archived, All)
 * - Client-side text search by name/slug
 * - Channel detail expand/collapse with member list
 * - Create channel form with MemberAutocomplete picker
 * - Lifecycle actions: Complete, Archive, Delete (with confirmation)
 * - Member management: Add, Remove (with sole-chair prevention)
 * - SSE subscription for real-time updates
 * - Attention signal indicators (amber pulse for stale active channels)
 */
(function(global) {
    'use strict';

    // ── Config ──────────────────────────────────────────────────
    var ATTENTION_THRESHOLD_MS = 2 * 60 * 60 * 1000; // 2 hours
    var _channels = [];           // full channel list from API
    var _activeFilter = 'active'; // current status filter
    var _searchQuery = '';        // current search text
    var _expandedSlug = null;     // slug of currently expanded detail
    var _detailMembers = [];      // members of expanded channel
    var _memberPickerInited = false;

    var _escapeHtml = (global.CHUtils && global.CHUtils.escapeHtml) || function(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    };

    /** Parse fetch response into { ok, data } for consistent error handling. */
    function _parseResponse(r) {
        return r.json().then(function(d) { return { ok: r.ok, data: d }; });
    }

    /** Best-effort last activity timestamp for a channel. */
    function _lastActivity(ch) {
        return ch.completed_at || ch.archived_at || ch.created_at;
    }

    // ── Initialization ──────────────────────────────────────────

    function init() {
        _bindFilterTabs();
        _bindSearch();
        _fetchChannels();
        _subscribeSSE();
    }

    // ── Data fetching ───────────────────────────────────────────

    function _fetchChannels() {
        var loadingEl = document.getElementById('channels-loading');
        if (loadingEl) loadingEl.classList.remove('hidden');

        fetch('/api/channels?all=true')
            .then(function(r) { return r.json(); })
            .then(function(data) {
                if (loadingEl) loadingEl.classList.add('hidden');
                if (Array.isArray(data)) {
                    _channels = data;
                } else if (data.error) {
                    _channels = [];
                }
                _renderTable();
            })
            .catch(function(err) {
                if (loadingEl) loadingEl.classList.add('hidden');
                console.error('Failed to fetch channels:', err);
                _channels = [];
                _renderTable();
            });
    }

    function _fetchChannelDetail(slug) {
        return fetch('/api/channels/' + encodeURIComponent(slug))
            .then(function(r) { return r.json(); });
    }

    function _fetchMembers(slug) {
        return fetch('/api/channels/' + encodeURIComponent(slug) + '/members')
            .then(function(r) { return r.json(); });
    }

    // ── Filter tabs ─────────────────────────────────────────────

    function _bindFilterTabs() {
        var tabs = document.querySelectorAll('.channel-filter-tab');
        tabs.forEach(function(tab) {
            tab.addEventListener('click', function() {
                tabs.forEach(function(t) {
                    t.classList.remove('active');
                    t.setAttribute('aria-selected', 'false');
                });
                tab.classList.add('active');
                tab.setAttribute('aria-selected', 'true');
                _activeFilter = tab.getAttribute('data-status');
                _renderTable();
            });
        });
    }

    // ── Search ──────────────────────────────────────────────────

    function _bindSearch() {
        var input = document.getElementById('channel-search-input');
        if (!input) return;
        input.addEventListener('input', function() {
            _searchQuery = input.value.trim().toLowerCase();
            _renderTable();
        });
    }

    // ── Table rendering ─────────────────────────────────────────

    function _filterChannels() {
        return _channels.filter(function(ch) {
            // Status filter
            if (_activeFilter !== 'all' && ch.status !== _activeFilter) return false;
            // Text search
            if (_searchQuery) {
                var name = (ch.name || '').toLowerCase();
                var slug = (ch.slug || '').toLowerCase();
                if (name.indexOf(_searchQuery) === -1 && slug.indexOf(_searchQuery) === -1) return false;
            }
            return true;
        });
    }

    function _renderTable() {
        var tbody = document.getElementById('channels-tbody');
        var emptyEl = document.getElementById('channels-empty');
        var tableContainer = document.getElementById('channels-table-container');
        if (!tbody) return;

        var filtered = _filterChannels();

        if (filtered.length === 0) {
            if (tableContainer) tableContainer.classList.add('hidden');
            if (emptyEl) emptyEl.classList.remove('hidden');
            return;
        }

        if (tableContainer) tableContainer.classList.remove('hidden');
        if (emptyEl) emptyEl.classList.add('hidden');

        var html = '';
        filtered.forEach(function(ch) {
            var isStale = _isAttentionNeeded(ch);
            var attentionClass = isStale ? ' channel-attention' : '';
            var rowClass = _expandedSlug === ch.slug ? 'bg-surface/50' : '';

            html += '<tr class="border-b border-border/50 hover:bg-surface/30 cursor-pointer ' + rowClass + attentionClass + '"'
                 + ' data-slug="' + _escapeHtml(ch.slug) + '"'
                 + ' onclick="ChannelAdmin.toggleDetail(\'' + _escapeHtml(ch.slug) + '\')">';

            // Name
            html += '<td class="py-3 pr-4">';
            if (isStale) html += '<span class="channel-attention-dot" title="Needs attention"></span> ';
            html += '<span class="text-primary font-medium">' + _escapeHtml(ch.name) + '</span>';
            html += '<span class="text-muted text-xs ml-2 font-mono">' + _escapeHtml(ch.slug) + '</span>';
            html += '</td>';

            // Type badge
            html += '<td class="py-3 pr-4"><span class="channel-type-badge channel-type-' + _escapeHtml(ch.channel_type) + '">'
                 + _escapeHtml(ch.channel_type) + '</span></td>';

            // Status
            html += '<td class="py-3 pr-4"><span class="channel-status-label channel-status-' + _escapeHtml(ch.status) + '">'
                 + _escapeHtml(ch.status) + '</span></td>';

            // Member count
            html += '<td class="py-3 pr-4 text-center text-secondary">' + (ch.member_count || 0) + '</td>';

            // Last activity (use created_at as proxy — full implementation would need message timestamps)
            html += '<td class="py-3 pr-4 text-muted text-sm">' + _formatDate(_lastActivity(ch)) + '</td>';

            // Created
            html += '<td class="py-3 pr-4 text-muted text-sm">' + _formatDate(ch.created_at) + '</td>';

            // Actions (stop propagation for buttons)
            html += '<td class="py-3 pr-4 text-right">';
            html += '<button onclick="event.stopPropagation(); ChannelAdmin.toggleDetail(\'' + _escapeHtml(ch.slug) + '\')"'
                 + ' class="text-cyan text-sm hover:underline">details</button>';
            html += '</td>';

            html += '</tr>';
        });

        tbody.innerHTML = html;
    }

    // ── Attention signal ────────────────────────────────────────

    function _isAttentionNeeded(ch) {
        if (ch.status !== 'active') return false;
        var lastTime = _lastActivity(ch);
        if (!lastTime) return false;
        var elapsed = Date.now() - new Date(lastTime).getTime();
        return elapsed > ATTENTION_THRESHOLD_MS;
    }

    // ── Detail panel ────────────────────────────────────────────

    function toggleDetail(slug) {
        if (_expandedSlug === slug) {
            closeDetail();
            return;
        }
        _expandDetail(slug);
    }

    function _expandDetail(slug) {
        _expandedSlug = slug;
        _renderTable(); // highlight active row

        var panel = document.getElementById('channel-detail-panel');
        if (!panel) return;

        // Find channel data
        var ch = _channels.find(function(c) { return c.slug === slug; });
        if (!ch) return;

        // Fill metadata
        _setText('detail-channel-name', ch.name || '');
        _setText('detail-channel-slug', '#' + (ch.slug || ''));
        _setText('detail-channel-type', ch.channel_type || '');
        _setText('detail-channel-description', ch.description || '(none)');
        _setText('detail-channel-created', _formatDate(ch.created_at));
        _setText('detail-channel-chair', ch.chair_persona_slug || '(none)');

        // Status with badge
        var statusEl = document.getElementById('detail-channel-status');
        if (statusEl) {
            statusEl.innerHTML = '<span class="channel-status-label channel-status-' + _escapeHtml(ch.status) + '">'
                              + _escapeHtml(ch.status) + '</span>';
        }

        // Show/hide add member button based on status
        var addMemberBtn = document.getElementById('detail-add-member-btn');
        if (addMemberBtn) {
            addMemberBtn.classList.toggle('hidden', ch.status === 'complete' || ch.status === 'archived');
        }

        // Hide add member form
        var addMemberForm = document.getElementById('detail-add-member-form');
        if (addMemberForm) addMemberForm.classList.add('hidden');

        // Fetch members
        _fetchMembers(slug).then(function(members) {
            _detailMembers = Array.isArray(members) ? members : [];
            _renderMembers(ch);
        });

        // Render actions
        _renderActions(ch);

        panel.classList.remove('hidden');
        panel.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    function closeDetail() {
        _expandedSlug = null;
        var panel = document.getElementById('channel-detail-panel');
        if (panel) panel.classList.add('hidden');
        _renderTable();
    }

    function _renderMembers(ch) {
        var container = document.getElementById('detail-members-list');
        if (!container) return;

        if (_detailMembers.length === 0) {
            container.innerHTML = '<p class="text-muted text-sm">No members</p>';
            return;
        }

        var html = '';
        _detailMembers.forEach(function(m) {
            var isActive = m.status === 'active' || m.status === 'muted';
            var statusClass = isActive ? 'text-green' : 'text-muted';
            var chairBadge = m.is_chair ? ' <span class="text-amber text-xs">[chair]</span>' : '';

            html += '<div class="flex items-center justify-between py-1 px-2 rounded hover:bg-surface/30">';
            html += '<div>';
            html += '<span class="' + statusClass + '">' + _escapeHtml(m.persona_name || m.persona_slug || 'Unknown') + '</span>';
            html += chairBadge;
            html += ' <span class="text-muted text-xs">(' + _escapeHtml(m.status) + ')</span>';
            html += '</div>';

            // Remove button — only for active/muted members in active/pending channels
            if (isActive && (ch.status === 'active' || ch.status === 'pending')) {
                html += '<button onclick="ChannelAdmin.removeMember(\'' + _escapeHtml(ch.slug) + '\', \''
                     + _escapeHtml(m.persona_slug) + '\', \'' + _escapeHtml(m.persona_name || '') + '\')"'
                     + ' class="text-red text-xs hover:underline ml-2">remove</button>';
            }
            html += '</div>';
        });

        container.innerHTML = html;
    }

    function _renderActions(ch) {
        var container = document.getElementById('detail-actions');
        if (!container) return;

        var html = '';

        if (ch.status === 'active' || ch.status === 'pending') {
            html += '<button onclick="ChannelAdmin.completeChannel(\'' + _escapeHtml(ch.slug) + '\')"'
                 + ' class="px-3 py-1 text-sm bg-green/20 border border-green/30 rounded text-green hover:bg-green/30 transition-colors">Complete</button>';
        }

        if (ch.status === 'complete') {
            html += '<button onclick="ChannelAdmin.archiveChannel(\'' + _escapeHtml(ch.slug) + '\')"'
                 + ' class="px-3 py-1 text-sm bg-amber/20 border border-amber/30 rounded text-amber hover:bg-amber/30 transition-colors">Archive</button>';
        }

        if (ch.status === 'archived' || ch.member_count === 0) {
            html += '<button onclick="ChannelAdmin.deleteChannel(\'' + _escapeHtml(ch.slug) + '\', \'' + _escapeHtml(ch.name) + '\')"'
                 + ' class="px-3 py-1 text-sm bg-red/20 border border-red/30 rounded text-red hover:bg-red/30 transition-colors">Delete</button>';
        }

        container.innerHTML = html;
    }

    // ── Lifecycle actions ───────────────────────────────────────

    function completeChannel(slug) {
        _postAction('/api/channels/' + encodeURIComponent(slug) + '/complete', 'Channel completed');
    }

    function archiveChannel(slug) {
        _postAction('/api/channels/' + encodeURIComponent(slug) + '/archive', 'Channel archived');
    }

    async function deleteChannel(slug, name) {
        var ok = await (global.ConfirmDialog
            ? global.ConfirmDialog.show('Delete Channel', 'Permanently delete "' + (name || slug) + '"? This cannot be undone.', {
                confirmText: 'Delete',
                confirmClass: 'bg-red hover:bg-red/90'
              })
            : Promise.resolve(confirm('Delete channel "' + (name || slug) + '"?')));

        if (!ok) return;

        fetch('/api/channels/' + encodeURIComponent(slug), { method: 'DELETE' })
            .then(function(r) { return _parseResponse(r); })
            .then(function(res) {
                if (res.ok) {
                    if (global.Toast) global.Toast.success('Deleted', 'Channel removed.');
                    closeDetail();
                    _fetchChannels();
                } else {
                    var msg = (res.data.error && res.data.error.message) || 'Delete failed';
                    if (global.Toast) global.Toast.error('Error', msg);
                }
            })
            .catch(function(err) {
                console.error('Delete channel error:', err);
                if (global.Toast) global.Toast.error('Error', 'Network error');
            });
    }

    function _postAction(url, successMsg) {
        fetch(url, { method: 'POST' })
            .then(function(r) { return _parseResponse(r); })
            .then(function(res) {
                if (res.ok) {
                    if (global.Toast) global.Toast.success('Success', successMsg);
                    _fetchChannels();
                    if (_expandedSlug) _expandDetail(_expandedSlug);
                } else {
                    var msg = (res.data.error && res.data.error.message) || 'Action failed';
                    if (global.Toast) global.Toast.error('Error', msg);
                }
            })
            .catch(function(err) {
                console.error('Channel action error:', err);
                if (global.Toast) global.Toast.error('Error', 'Network error');
            });
    }

    // ── Member management ───────────────────────────────────────

    function showAddMember() {
        var form = document.getElementById('detail-add-member-form');
        if (!form) return;
        form.classList.remove('hidden');

        // Init MemberAutocomplete on the picker container
        if (global.MemberAutocomplete) {
            var pickerEl = document.getElementById('detail-member-picker');
            if (pickerEl) {
                // Get existing member persona slugs to exclude
                var excludeSlugs = _detailMembers
                    .filter(function(m) { return m.status === 'active' || m.status === 'muted'; })
                    .map(function(m) { return m.persona_slug; })
                    .filter(Boolean);

                global.MemberAutocomplete.init(pickerEl, {
                    excludePersonaSlugs: excludeSlugs
                });
            }
        }
    }

    function hideAddMember() {
        var form = document.getElementById('detail-add-member-form');
        if (form) form.classList.add('hidden');
        if (global.MemberAutocomplete) global.MemberAutocomplete.reset();
    }

    function confirmAddMember() {
        if (!_expandedSlug || !global.MemberAutocomplete) return;

        var agentIds = global.MemberAutocomplete.getSelectedAgentIds();
        var personaSlugs = global.MemberAutocomplete.getSelectedPersonaSlugs
            ? global.MemberAutocomplete.getSelectedPersonaSlugs() : [];

        // Try agent IDs first, then persona slugs
        var promises = [];
        agentIds.forEach(function(aid) {
            promises.push(
                fetch('/api/channels/' + encodeURIComponent(_expandedSlug) + '/members', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ agent_id: aid })
                })
            );
        });
        personaSlugs.forEach(function(slug) {
            promises.push(
                fetch('/api/channels/' + encodeURIComponent(_expandedSlug) + '/members', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ persona_slug: slug })
                })
            );
        });

        if (promises.length === 0) {
            if (global.Toast) global.Toast.error('Error', 'Select at least one member to add.');
            return;
        }

        Promise.all(promises)
            .then(function(responses) {
                var allOk = responses.every(function(r) { return r.ok; });
                if (allOk) {
                    if (global.Toast) global.Toast.success('Added', 'Member(s) added to channel.');
                    hideAddMember();
                    _expandDetail(_expandedSlug);
                    _fetchChannels();
                } else {
                    responses.forEach(function(r) {
                        if (!r.ok) {
                            r.json().then(function(d) {
                                var msg = (d.error && d.error.message) || 'Failed to add member';
                                if (global.Toast) global.Toast.error('Error', msg);
                            });
                        }
                    });
                }
            })
            .catch(function(err) {
                console.error('Add member error:', err);
                if (global.Toast) global.Toast.error('Error', 'Network error');
            });
    }

    async function removeMember(channelSlug, personaSlug, personaName) {
        var ok = await (global.ConfirmDialog
            ? global.ConfirmDialog.show('Remove Member',
                'Remove "' + (personaName || personaSlug) + '" from this channel?',
                { confirmText: 'Remove', confirmClass: 'bg-red hover:bg-red/90' })
            : Promise.resolve(confirm('Remove ' + (personaName || personaSlug) + '?')));

        if (!ok) return;

        fetch('/api/channels/' + encodeURIComponent(channelSlug) + '/members/' + encodeURIComponent(personaSlug), {
            method: 'DELETE'
        })
            .then(function(r) { return _parseResponse(r); })
            .then(function(res) {
                if (res.ok) {
                    if (global.Toast) global.Toast.success('Removed', 'Member removed from channel.');
                    _expandDetail(channelSlug);
                    _fetchChannels();
                } else {
                    var msg = (res.data.error && res.data.error.message) || 'Remove failed';
                    if (global.Toast) global.Toast.error('Error', msg);
                }
            })
            .catch(function(err) {
                console.error('Remove member error:', err);
                if (global.Toast) global.Toast.error('Error', 'Network error');
            });
    }

    // ── Create channel ──────────────────────────────────────────

    function openCreateForm() {
        var form = document.getElementById('channel-create-form');
        if (!form) return;
        form.classList.remove('hidden');
        form.scrollIntoView({ behavior: 'smooth', block: 'nearest' });

        // Init MemberAutocomplete for member picker
        if (global.MemberAutocomplete) {
            var pickerEl = document.getElementById('create-member-picker');
            if (pickerEl) {
                global.MemberAutocomplete.init(pickerEl);
                _memberPickerInited = true;
            }
        }

        // Focus name input
        var nameInput = document.getElementById('create-channel-name');
        if (nameInput) nameInput.focus();
    }

    function closeCreateForm() {
        var form = document.getElementById('channel-create-form');
        if (form) form.classList.add('hidden');

        // Reset form fields
        var nameEl = document.getElementById('create-channel-name');
        var typeEl = document.getElementById('create-channel-type');
        var descEl = document.getElementById('create-channel-desc');
        if (nameEl) nameEl.value = '';
        if (typeEl) typeEl.selectedIndex = 0;
        if (descEl) descEl.value = '';
        if (global.MemberAutocomplete && _memberPickerInited) {
            global.MemberAutocomplete.reset();
        }
    }

    function submitCreate() {
        var name = (document.getElementById('create-channel-name') || {}).value || '';
        var channelType = (document.getElementById('create-channel-type') || {}).value || 'workshop';
        var description = (document.getElementById('create-channel-desc') || {}).value || '';

        if (!name.trim()) {
            if (global.Toast) global.Toast.error('Error', 'Channel name is required.');
            return;
        }

        var body = {
            name: name.trim(),
            channel_type: channelType,
            description: description.trim() || undefined
        };

        // Add member agents from picker
        if (global.MemberAutocomplete) {
            var agentIds = global.MemberAutocomplete.getSelectedAgentIds();
            if (agentIds.length > 0) {
                body.member_agents = agentIds;
            }
            var personaSlugs = global.MemberAutocomplete.getSelectedPersonaSlugs
                ? global.MemberAutocomplete.getSelectedPersonaSlugs() : [];
            if (personaSlugs.length > 0) {
                body.members = personaSlugs;
            }
        }

        fetch('/api/channels', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body)
        })
            .then(function(r) { return _parseResponse(r); })
            .then(function(res) {
                if (res.ok) {
                    if (global.Toast) global.Toast.success('Created', 'Channel "' + name.trim() + '" created.');
                    closeCreateForm();
                    _fetchChannels();
                } else {
                    var msg = (res.data.error && res.data.error.message) || 'Create failed';
                    if (global.Toast) global.Toast.error('Error', msg);
                }
            })
            .catch(function(err) {
                console.error('Create channel error:', err);
                if (global.Toast) global.Toast.error('Error', 'Network error');
            });
    }

    // ── SSE ─────────────────────────────────────────────────────

    function _subscribeSSE() {
        if (!global.sseClient) return;

        global.sseClient.on('channel_update', function(data) {
            // Refresh channel list on any update
            _fetchChannels();
            // If detail is open for updated channel, refresh it
            if (_expandedSlug && data && data.slug === _expandedSlug) {
                setTimeout(function() { _expandDetail(_expandedSlug); }, 300);
            }
        });

        global.sseClient.on('channel_message', function(data) {
            // A new message means activity — refresh to update "last activity"
            if (data && data.channel_slug) {
                // Update the channel's activity timestamp in our local cache
                var ch = _channels.find(function(c) { return c.slug === data.channel_slug; });
                if (ch) {
                    // Force re-render to update attention signals
                    _renderTable();
                }
            }
        });

        global.sseClient.on('channel_member_connected', function(data) {
            if (global.ChannelChat && data) {
                global.ChannelChat.onMemberConnected(data);
            }
        });

        global.sseClient.on('channel_ready', function(data) {
            if (global.ChannelChat && data) {
                global.ChannelChat.onChannelReady(data);
            }
            // Refresh channel list to reflect active status
            _fetchChannels();
        });

        // S12: update member pill state colours on card_refresh
        global.sseClient.on('card_refresh', function(data) {
            if (global.ChannelChat && data) {
                global.ChannelChat.onCardRefresh(data);
            }
        });
    }

    // ── Helpers ──────────────────────────────────────────────────

    function _setText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
    }

    function _formatDate(isoStr) {
        if (!isoStr) return '-';
        try {
            var d = new Date(isoStr);
            var now = new Date();
            var diff = now - d;

            // Less than 1 hour: show relative
            if (diff < 3600000) {
                var mins = Math.floor(diff / 60000);
                return mins <= 1 ? 'just now' : mins + 'm ago';
            }
            // Less than 24 hours
            if (diff < 86400000) {
                var hrs = Math.floor(diff / 3600000);
                return hrs + 'h ago';
            }
            // Less than 7 days
            if (diff < 604800000) {
                var days = Math.floor(diff / 86400000);
                return days + 'd ago';
            }
            // Otherwise: date
            return d.toLocaleDateString();
        } catch (e) {
            return isoStr;
        }
    }

    // ── Public API ──────────────────────────────────────────────

    global.ChannelAdmin = {
        init: init,
        toggleDetail: toggleDetail,
        closeDetail: closeDetail,
        openCreateForm: openCreateForm,
        closeCreateForm: closeCreateForm,
        submitCreate: submitCreate,
        completeChannel: completeChannel,
        archiveChannel: archiveChannel,
        deleteChannel: deleteChannel,
        showAddMember: showAddMember,
        hideAddMember: hideAddMember,
        confirmAddMember: confirmAddMember,
        removeMember: removeMember
    };

    // Auto-init when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

})(window);
