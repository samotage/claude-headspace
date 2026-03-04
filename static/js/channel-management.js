/**
 * Channel Management Modal — channel CRUD operations.
 *
 * Provides:
 * - open() — fetch channel list, render table, show modal
 * - close() — hide modal
 * - switchTab(tab) — switch between list and create views
 * - createChannel() — POST to /api/channels, update list and cards
 * - completeChannel(slug) — POST to /api/channels/<slug>/complete
 * - archiveChannel(slug) — POST to /api/channels/<slug>/archive
 */
(function(global) {
    'use strict';

    var _isOpen = false;

    /**
     * Open the channel management modal.
     */
    function open() {
        var modal = document.getElementById('channel-management-modal');
        if (!modal) return;

        modal.classList.remove('hidden');
        _isOpen = true;

        // Start on list tab
        switchTab('list');

        // Fetch channel data
        _loadChannels();

        // Escape key handler
        document.addEventListener('keydown', _handleEscape);
    }

    /**
     * Close the modal.
     */
    function close() {
        var modal = document.getElementById('channel-management-modal');
        if (!modal) return;

        modal.classList.add('hidden');
        _isOpen = false;

        document.removeEventListener('keydown', _handleEscape);
    }

    /**
     * Switch between list and create tabs.
     */
    function switchTab(tab) {
        var listTab = document.getElementById('channel-mgmt-tab-list');
        var createTab = document.getElementById('channel-mgmt-tab-create');
        var listView = document.getElementById('channel-mgmt-list-view');
        var createView = document.getElementById('channel-mgmt-create-view');

        if (tab === 'list') {
            listTab.classList.add('bg-cyan', 'text-void');
            listTab.classList.remove('text-secondary', 'hover:text-primary', 'hover:bg-hover');
            createTab.classList.remove('bg-cyan', 'text-void');
            createTab.classList.add('text-secondary', 'hover:text-primary', 'hover:bg-hover');
            listView.classList.remove('hidden');
            createView.classList.add('hidden');
        } else {
            createTab.classList.add('bg-cyan', 'text-void');
            createTab.classList.remove('text-secondary', 'hover:text-primary', 'hover:bg-hover');
            listTab.classList.remove('bg-cyan', 'text-void');
            listTab.classList.add('text-secondary', 'hover:text-primary', 'hover:bg-hover');
            createView.classList.remove('hidden');
            listView.classList.add('hidden');

            // Init member autocomplete when switching to create tab
            var acEl = document.getElementById('channel-member-autocomplete');
            if (acEl && global.MemberAutocomplete) {
                global.MemberAutocomplete.init(acEl);
            }
        }
    }

    /**
     * Create a new channel from the form data.
     */
    function createChannel() {
        var nameEl = document.getElementById('channel-create-name');
        var typeEl = document.getElementById('channel-create-type');
        var descEl = document.getElementById('channel-create-description');
        var statusEl = document.getElementById('channel-create-status');
        var submitBtn = document.getElementById('channel-create-submit-btn');

        var name = nameEl ? nameEl.value.trim() : '';
        var channelType = typeEl ? typeEl.value : '';

        if (!name) {
            if (statusEl) statusEl.textContent = 'Name is required';
            return;
        }
        if (!channelType) {
            if (statusEl) statusEl.textContent = 'Type is required';
            return;
        }

        var payload = {
            name: name,
            channel_type: channelType,
        };

        var desc = descEl ? descEl.value.trim() : '';
        if (desc) payload.description = desc;

        // Use autocomplete agent IDs and persona slugs, or fallback to slug text input
        if (global.MemberAutocomplete) {
            var agentIds = global.MemberAutocomplete.getSelectedAgentIds();
            var personaSlugs = global.MemberAutocomplete.getSelectedPersonaSlugs();
            if (agentIds.length) {
                payload.member_agents = agentIds;
            }
            if (personaSlugs.length) {
                payload.members = (payload.members || []).concat(personaSlugs);
            }
            if (!agentIds.length && !personaSlugs.length) {
                var fallbackMembers = global.MemberAutocomplete.getFallbackMembers();
                if (fallbackMembers) payload.members = fallbackMembers;
            }
        }

        if (submitBtn) submitBtn.disabled = true;
        if (statusEl) statusEl.textContent = 'Creating...';

        fetch('/api/channels', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        })
        .then(function(response) {
            if (!response.ok) {
                return response.json().then(function(data) {
                    var msg = (data.error && data.error.message) || 'Failed to create channel';
                    throw new Error(msg);
                });
            }
            return response.json();
        })
        .then(function(channel) {
            if (statusEl) statusEl.textContent = 'Created!';

            // Clear form
            if (nameEl) nameEl.value = '';
            if (typeEl) typeEl.value = '';
            if (descEl) descEl.value = '';
            if (global.MemberAutocomplete) global.MemberAutocomplete.reset();

            // Add card to dashboard
            if (global.ChannelCards) {
                global.ChannelCards.addCard({
                    slug: channel.slug,
                    name: channel.name,
                    channel_type: channel.channel_type,
                    status: channel.status,
                    members: [],
                });
            }

            // Toast
            if (global.Toast) {
                global.Toast.success('Channel Created', 'Channel "' + channel.name + '" created successfully');
            }

            // Switch back to list and reload
            switchTab('list');
            _loadChannels();

            setTimeout(function() {
                if (statusEl) statusEl.textContent = '';
            }, 2000);
        })
        .catch(function(err) {
            console.error('Failed to create channel:', err);
            if (statusEl) statusEl.textContent = err.message || 'Creation failed';
            if (global.Toast) {
                global.Toast.error('Error', err.message || 'Failed to create channel');
            }
        })
        .finally(function() {
            if (submitBtn) submitBtn.disabled = false;
        });
    }

    /**
     * Complete a channel.
     */
    function completeChannel(slug) {
        fetch('/api/channels/' + encodeURIComponent(slug) + '/complete', {
            method: 'POST',
        })
        .then(function(response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        })
        .then(function(channel) {
            if (global.Toast) {
                global.Toast.success('Channel Completed', '"' + channel.name + '" marked as completed');
            }
            if (global.ChannelCards) {
                global.ChannelCards.updateCardStatus(slug, 'completed');
            }
            _loadChannels();
        })
        .catch(function(err) {
            console.error('Failed to complete channel:', err);
            if (global.Toast) {
                global.Toast.error('Error', 'Failed to complete channel');
            }
        });
    }

    /**
     * Archive a channel.
     */
    function archiveChannel(slug) {
        fetch('/api/channels/' + encodeURIComponent(slug) + '/archive', {
            method: 'POST',
        })
        .then(function(response) {
            if (!response.ok) throw new Error('HTTP ' + response.status);
            return response.json();
        })
        .then(function(channel) {
            if (global.Toast) {
                global.Toast.success('Channel Archived', '"' + channel.name + '" has been archived');
            }
            if (global.ChannelCards) {
                global.ChannelCards.removeCard(slug);
            }
            // Close chat panel if open for this channel
            if (global.ChannelChat && global.ChannelChat.isOpenFor(slug)) {
                global.ChannelChat.close();
            }
            _loadChannels();
        })
        .catch(function(err) {
            console.error('Failed to archive channel:', err);
            if (global.Toast) {
                global.Toast.error('Error', 'Failed to archive channel');
            }
        });
    }

    // ── Internal Helpers ──────────────────────────────────────

    function _handleEscape(e) {
        if (e.key === 'Escape' && _isOpen) {
            close();
        }
    }

    function _loadChannels() {
        var loadingEl = document.getElementById('channel-mgmt-loading');
        var tableEl = document.getElementById('channel-mgmt-table');
        var tbodyEl = document.getElementById('channel-mgmt-tbody');
        var emptyEl = document.getElementById('channel-mgmt-empty');
        var countEl = document.getElementById('channel-mgmt-count');

        if (loadingEl) loadingEl.classList.remove('hidden');
        if (tableEl) tableEl.classList.add('hidden');
        if (emptyEl) emptyEl.classList.add('hidden');

        fetch('/api/channels?all=true')
            .then(function(response) {
                if (!response.ok) throw new Error('HTTP ' + response.status);
                return response.json();
            })
            .then(function(channels) {
                if (loadingEl) loadingEl.classList.add('hidden');

                if (!channels || channels.length === 0) {
                    if (emptyEl) emptyEl.classList.remove('hidden');
                    if (countEl) countEl.textContent = '0 channels';
                    return;
                }

                if (tableEl) tableEl.classList.remove('hidden');
                if (countEl) countEl.textContent = channels.length + ' channel' + (channels.length !== 1 ? 's' : '');

                // Render rows
                if (tbodyEl) {
                    tbodyEl.innerHTML = '';
                    channels.forEach(function(ch) {
                        var row = _createChannelRow(ch);
                        tbodyEl.appendChild(row);
                    });
                }
            })
            .catch(function(err) {
                console.error('Failed to load channels:', err);
                if (loadingEl) loadingEl.classList.add('hidden');
                if (emptyEl) {
                    emptyEl.textContent = 'Failed to load channels';
                    emptyEl.classList.remove('hidden');
                }
            });
    }

    function _createChannelRow(ch) {
        var tr = document.createElement('tr');
        tr.className = 'border-b border-border hover:bg-hover cursor-pointer transition-colors';

        // Click row to open chat panel
        tr.onclick = function(e) {
            // Don't trigger if clicking action buttons
            if (e.target.closest('button')) return;
            close();
            if (global.ChannelChat) global.ChannelChat.toggle(ch.slug);
        };

        var statusColor = ch.status === 'active' ? 'text-green' : ch.status === 'pending' ? 'text-amber' : 'text-muted';
        var createdAt = ch.created_at ? new Date(ch.created_at).toLocaleDateString() : '';

        // Build action buttons
        var actions = '';
        if (ch.status === 'active' || ch.status === 'pending') {
            actions += '<button class="text-xs text-amber hover:text-primary transition-colors mr-2" ' +
                       'onclick="event.stopPropagation(); window.ChannelManagement.completeChannel(\'' + _escapeAttr(ch.slug) + '\')">Complete</button>';
        }
        if (ch.status === 'completed') {
            actions += '<button class="text-xs text-red hover:text-primary transition-colors mr-2" ' +
                       'onclick="event.stopPropagation(); window.ChannelManagement.archiveChannel(\'' + _escapeAttr(ch.slug) + '\')">Archive</button>';
        }
        actions += '<button class="text-xs text-cyan hover:text-primary transition-colors" ' +
                   'onclick="event.stopPropagation(); window.ChannelManagement.close(); window.ChannelChat && window.ChannelChat.toggle(\'' + _escapeAttr(ch.slug) + '\')">View</button>';

        tr.innerHTML =
            '<td class="py-2 pr-4 text-primary font-medium">' + _escapeHtml(ch.name) + '</td>' +
            '<td class="py-2 pr-4"><span class="px-1.5 py-0.5 text-[10px] uppercase tracking-wider rounded text-muted bg-surface border border-border">' + _escapeHtml(ch.channel_type) + '</span></td>' +
            '<td class="py-2 pr-4 ' + statusColor + '">' + _escapeHtml(ch.status) + '</td>' +
            '<td class="py-2 pr-4 text-muted">' + (ch.member_count || 0) + '</td>' +
            '<td class="py-2 pr-4 text-muted">' + _escapeHtml(createdAt) + '</td>' +
            '<td class="py-2">' + actions + '</td>';

        return tr;
    }

    var _escapeHtml = (global.CHUtils && global.CHUtils.escapeHtml) || function(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    };

    function _escapeAttr(str) {
        if (!str) return '';
        return str.replace(/&/g, '&amp;').replace(/'/g, '&#39;').replace(/"/g, '&quot;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // Public API
    global.ChannelManagement = {
        open: open,
        close: close,
        switchTab: switchTab,
        createChannel: createChannel,
        completeChannel: completeChannel,
        archiveChannel: archiveChannel,
    };

})(window);
