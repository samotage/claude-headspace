/**
 * Channel Cards — SSE-driven channel card management for the dashboard.
 *
 * Handles:
 * - Real-time card updates via channel_message and channel_update SSE events
 * - Card click delegation to toggle the chat panel
 * - Dynamic card add/remove for channel join/archive events
 */
(function(global) {
    'use strict';

    /**
     * Update the last-message preview on a channel card.
     */
    function _updateCardLastMessage(slug, personaName, contentPreview) {
        var card = document.querySelector('.channel-card[data-channel-slug="' + slug + '"]');
        if (!card) return;

        var el = card.querySelector('.channel-card-last-message');
        if (!el) return;

        var preview = contentPreview || '';
        if (preview.length > 100) {
            preview = preview.substring(0, 100) + '...';
        }

        el.innerHTML = '<span class="text-cyan">' + _escapeHtml(personaName || 'Unknown') + '</span> ' +
                        '<span class="text-secondary">' + _escapeHtml(preview) + '</span>';
    }

    /**
     * Update the member list on a channel card.
     */
    function _updateCardMembers(slug, members) {
        var card = document.querySelector('.channel-card[data-channel-slug="' + slug + '"]');
        if (!card) return;

        var el = card.querySelector('.channel-card-members');
        if (!el) return;

        if (members && members.length > 0) {
            el.textContent = members.join(', ');
            card.setAttribute('data-channel-members', members.join(','));
        } else {
            el.textContent = 'No members';
            card.setAttribute('data-channel-members', '');
        }
    }

    /**
     * Update the status indicator on a channel card.
     */
    function _updateCardStatus(slug, status) {
        var card = document.querySelector('.channel-card[data-channel-slug="' + slug + '"]');
        if (!card) return;

        var dot = card.querySelector('.channel-card-status');
        if (!dot) return;

        dot.classList.remove('bg-green', 'bg-amber', 'bg-muted');
        if (status === 'active') {
            dot.classList.add('bg-green');
        } else if (status === 'pending') {
            dot.classList.add('bg-amber');
        } else {
            dot.classList.add('bg-muted');
        }
        dot.setAttribute('title', status);
        card.setAttribute('data-channel-status', status);
    }

    /**
     * Remove a channel card from the section.
     */
    function _removeCard(slug) {
        var card = document.querySelector('.channel-card[data-channel-slug="' + slug + '"]');
        if (card) {
            card.remove();
        }

        // Hide the section if no cards remain
        var container = document.getElementById('channel-cards-container');
        if (container && container.children.length === 0) {
            var section = document.getElementById('channel-cards-section');
            if (section) section.remove();
        }
    }

    /**
     * Add a new channel card to the section.
     */
    function _addCard(data) {
        var container = document.getElementById('channel-cards-container');

        // If the section doesn't exist yet, create it
        if (!container) {
            var section = document.createElement('div');
            section.id = 'channel-cards-section';
            section.className = 'mb-4';
            section.innerHTML = '<div class="flex items-center gap-2 mb-2">' +
                '<span class="text-muted text-xs font-medium uppercase tracking-wider">Channels</span>' +
                '<span class="text-muted text-xs" id="channel-cards-count">[1]</span>' +
                '</div>' +
                '<div class="flex flex-wrap gap-3" id="channel-cards-container"></div>';

            // Insert before the content area
            var sortControls = document.querySelector('.flex.items-center.justify-between.gap-4.mb-4');
            if (sortControls && sortControls.nextElementSibling) {
                sortControls.parentNode.insertBefore(section, sortControls.nextElementSibling);
            }
            container = document.getElementById('channel-cards-container');
        }

        if (!container) return;

        // Don't add duplicate
        if (document.querySelector('.channel-card[data-channel-slug="' + data.slug + '"]')) return;

        var members = data.members || [];
        var statusClass = data.status === 'active' ? 'bg-green' : data.status === 'pending' ? 'bg-amber' : 'bg-muted';

        var card = document.createElement('div');
        card.className = 'channel-card bg-elevated rounded-lg border border-border px-4 py-3 cursor-pointer transition-all hover:border-cyan/40 hover:bg-hover min-w-[220px] max-w-[320px] flex-1';
        card.setAttribute('data-channel-slug', data.slug);
        card.setAttribute('data-channel-name', data.name);
        card.setAttribute('data-channel-type', data.channel_type || '');
        card.setAttribute('data-channel-status', data.status || 'active');
        card.setAttribute('data-channel-members', members.join(','));
        card.onclick = function() {
            if (global.ChannelChat) global.ChannelChat.toggle(data.slug);
        };

        card.innerHTML =
            '<div class="flex items-center justify-between gap-2 mb-1">' +
                '<div class="flex items-center gap-2 min-w-0">' +
                    '<span class="channel-card-name text-primary text-sm font-medium truncate">' + _escapeHtml(data.name) + '</span>' +
                    '<span class="channel-card-type px-1.5 py-0.5 text-[10px] uppercase tracking-wider rounded text-muted bg-surface border border-border">' + _escapeHtml(data.channel_type || '') + '</span>' +
                '</div>' +
                '<span class="channel-card-status flex-shrink-0 w-2 h-2 rounded-full ' + statusClass + '" title="' + _escapeHtml(data.status || 'active') + '"></span>' +
            '</div>' +
            '<div class="channel-card-members text-muted text-xs truncate mb-1">' + _escapeHtml(members.join(', ') || 'No members') + '</div>' +
            '<div class="channel-card-last-message text-xs truncate"><span class="text-muted italic">No messages yet</span></div>';

        container.appendChild(card);

        // Update count
        _updateCardCount();
    }

    /**
     * Update the channel card count label.
     */
    function _updateCardCount() {
        var container = document.getElementById('channel-cards-container');
        if (!container) return;
        var section = document.getElementById('channel-cards-section');
        if (!section) return;
        var countEl = section.querySelector('.text-muted.text-xs:not(.font-medium)');
        if (countEl) {
            countEl.textContent = '[' + container.children.length + ']';
        }
    }

    /**
     * Escape HTML to prevent XSS.
     */
    function _escapeHtml(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    /**
     * SSE handler for channel_message events.
     */
    function _handleChannelMessage(data) {
        var slug = data.channel_slug;
        if (!slug) return;

        // Update card preview
        _updateCardLastMessage(slug, data.persona_name, data.content);

        // Forward to chat panel if it's open for this channel
        if (global.ChannelChat && global.ChannelChat.isOpenFor(slug)) {
            global.ChannelChat.appendMessage(data);
        }
    }

    /**
     * SSE handler for channel_update events.
     */
    function _handleChannelUpdate(data) {
        var slug = data.channel_slug;
        var updateType = data.update_type;

        if (!slug || !updateType) return;

        switch (updateType) {
            case 'member_joined':
            case 'member_left':
                if (data.members) {
                    _updateCardMembers(slug, data.members);
                }
                break;

            case 'channel_completed':
                _updateCardStatus(slug, 'completed');
                break;

            case 'channel_archived':
                _removeCard(slug);
                // Close chat panel if open for this channel
                if (global.ChannelChat && global.ChannelChat.isOpenFor(slug)) {
                    global.ChannelChat.close();
                }
                break;

            case 'channel_created':
                if (data.channel) {
                    _addCard(data.channel);
                }
                break;

            case 'status_changed':
                if (data.status) {
                    _updateCardStatus(slug, data.status);
                }
                break;
        }
    }

    /**
     * Initialize SSE event listeners.
     */
    function init() {
        if (global.sseClient) {
            global.sseClient.on('channel_message', _handleChannelMessage);
            global.sseClient.on('channel_update', _handleChannelUpdate);
        }
    }

    // Auto-initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Public API
    global.ChannelCards = {
        init: init,
        updateCardLastMessage: _updateCardLastMessage,
        updateCardMembers: _updateCardMembers,
        updateCardStatus: _updateCardStatus,
        removeCard: _removeCard,
        addCard: _addCard,
    };

})(window);
