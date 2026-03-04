/* VoiceChannelChat — channel conversation view: message rendering,
 * send, live injection, and scroll-up pagination.
 *
 * Dependencies: VoiceState, VoiceAPI, VoiceChatRenderer, VoiceLayout, VoiceSidebar.
 */
window.VoiceChannelChat = (function () {
  'use strict';

  var MESSAGE_LIMIT = 50;
  var TIMESTAMP_GAP_MS = 5 * 60 * 1000; // 5 minutes between timestamp separators
  var _optimisticIdCounter = 0;

  // --- Public methods ---

  /**
   * Open channel chat screen for the given slug.
   * Fetches members + messages in parallel, renders, scrolls to bottom.
   */
  function showChannelChatScreen(slug) {
    VoiceState.currentChannelSlug = slug;
    VoiceState.channelMembers = [];
    VoiceState.channelHasMore = false;
    VoiceState.channelLoadingMore = false;
    VoiceState.channelOldestMessageTime = null;

    // Update header
    var nameEl = document.getElementById('channel-chat-name');
    if (nameEl) nameEl.textContent = '#' + slug;
    var badgeEl = document.getElementById('channel-chat-type-badge');
    var memberCountEl = document.getElementById('channel-chat-member-count');

    // Find channel info from sidebar state
    var channels = VoiceState.channels;
    for (var i = 0; i < channels.length; i++) {
      if (channels[i].slug === slug) {
        if (badgeEl) badgeEl.textContent = channels[i].channel_type || 'channel';
        break;
      }
    }

    // Clear messages container
    var messagesEl = document.getElementById('channel-chat-messages');
    if (messagesEl) {
      messagesEl.innerHTML = '<div id="channel-chat-load-more" class="chat-load-more" style="display:none"></div>'
        + '<div class="channel-chat-loading">Loading messages...</div>';
    }

    // Fetch members and messages in parallel
    var membersPromise = VoiceAPI.getChannelMembers(slug).then(function (members) {
      VoiceState.channelMembers = members || [];
      if (memberCountEl) {
        var count = VoiceState.channelMembers.length;
        memberCountEl.textContent = count + ' member' + (count !== 1 ? 's' : '');
      }
    }).catch(function () {
      VoiceState.channelMembers = [];
    });

    var messagesPromise = VoiceAPI.getChannelMessages(slug, { limit: MESSAGE_LIMIT }).then(function (messages) {
      messages = messages || [];
      // Messages arrive in chronological order (oldest first) from the API
      VoiceState.channelMessages[slug] = messages;
      VoiceState.channelHasMore = messages.length >= MESSAGE_LIMIT;
      if (messages.length > 0) {
        VoiceState.channelOldestMessageTime = messages[0].sent_at;
      }
    }).catch(function () {
      VoiceState.channelMessages[slug] = [];
    });

    Promise.all([membersPromise, messagesPromise]).then(function () {
      _renderAllMessages(slug);
      _scrollToBottom();
    });

    VoiceLayout.showScreen('channel-chat');
  }

  /**
   * SSE callback: append a new message from a channel_message event.
   */
  function appendMessage(data) {
    var slug = data.channel_slug;
    if (!slug) return;

    // Build message object from SSE data
    var msg = {
      id: data.message_id || data.id || ('sse-ch-' + Date.now()),
      channel_slug: slug,
      persona_slug: data.persona_slug || null,
      persona_name: data.persona_name || null,
      agent_id: data.agent_id || null,
      content: data.content || '',
      message_type: data.message_type || 'message',
      sent_at: data.sent_at || new Date().toISOString()
    };

    // Add to cache
    if (!VoiceState.channelMessages[slug]) {
      VoiceState.channelMessages[slug] = [];
    }
    // Deduplicate by id
    var existing = VoiceState.channelMessages[slug];
    for (var i = 0; i < existing.length; i++) {
      if (existing[i].id === msg.id) return;
    }
    existing.push(msg);

    // Render bubble if this channel is currently open
    if (VoiceState.currentChannelSlug === slug && VoiceState.currentScreen === 'channel-chat') {
      var messagesEl = document.getElementById('channel-chat-messages');
      if (!messagesEl) return;
      var wasNearBottom = _isNearBottom(messagesEl);
      var prevMsg = existing.length > 1 ? existing[existing.length - 2] : null;
      _maybeInsertTimeSeparator(messagesEl, msg, prevMsg);
      messagesEl.appendChild(_createMessageEl(msg, prevMsg));
      if (wasNearBottom) _scrollToBottom();
    }
  }

  /**
   * Load older messages when user scrolls to top.
   */
  function loadOlderMessages() {
    var slug = VoiceState.currentChannelSlug;
    if (!slug || !VoiceState.channelHasMore || VoiceState.channelLoadingMore) return;

    VoiceState.channelLoadingMore = true;
    var loadMoreEl = document.getElementById('channel-chat-load-more');
    if (loadMoreEl) {
      loadMoreEl.style.display = 'block';
      loadMoreEl.textContent = 'Loading older messages...';
    }

    var messagesEl = document.getElementById('channel-chat-messages');
    var prevScrollHeight = messagesEl ? messagesEl.scrollHeight : 0;

    VoiceAPI.getChannelMessages(slug, {
      before: VoiceState.channelOldestMessageTime,
      limit: MESSAGE_LIMIT
    }).then(function (messages) {
      VoiceState.channelLoadingMore = false;
      if (loadMoreEl) loadMoreEl.style.display = 'none';
      messages = messages || [];
      if (messages.length < MESSAGE_LIMIT) VoiceState.channelHasMore = false;
      if (messages.length === 0) return;

      // Messages arrive chronologically — prepend to cache
      var cached = VoiceState.channelMessages[slug] || [];
      VoiceState.channelMessages[slug] = messages.concat(cached);
      VoiceState.channelOldestMessageTime = messages[0].sent_at;

      // Prepend to DOM, preserving scroll position
      if (messagesEl) {
        var frag = document.createDocumentFragment();
        for (var i = 0; i < messages.length; i++) {
          var prevMsg = i > 0 ? messages[i - 1] : null;
          _maybeInsertTimeSeparator(frag, messages[i], prevMsg);
          frag.appendChild(_createMessageEl(messages[i], prevMsg));
        }
        // Insert after load-more div
        var firstChild = loadMoreEl ? loadMoreEl.nextSibling : messagesEl.firstChild;
        messagesEl.insertBefore(frag, firstChild);

        // Preserve scroll position
        var newScrollHeight = messagesEl.scrollHeight;
        messagesEl.scrollTop = newScrollHeight - prevScrollHeight;
      }
    }).catch(function () {
      VoiceState.channelLoadingMore = false;
      if (loadMoreEl) loadMoreEl.style.display = 'none';
    });
  }

  /**
   * Send a message to the current channel.
   * Optimistic render, then POST.
   */
  function sendMessage(text) {
    if (!text || !text.trim()) return;
    text = text.trim();
    var slug = VoiceState.currentChannelSlug;
    if (!slug) return;

    // Create optimistic message
    var optimisticId = 'opt-ch-' + (++_optimisticIdCounter);
    var msg = {
      id: optimisticId,
      channel_slug: slug,
      persona_slug: null,
      persona_name: 'You',
      agent_id: null,
      content: text,
      message_type: 'message',
      sent_at: new Date().toISOString(),
      _optimistic: true
    };

    // Add to cache and render
    if (!VoiceState.channelMessages[slug]) VoiceState.channelMessages[slug] = [];
    var cached = VoiceState.channelMessages[slug];
    cached.push(msg);

    var messagesEl = document.getElementById('channel-chat-messages');
    if (messagesEl) {
      var prevMsg = cached.length > 1 ? cached[cached.length - 2] : null;
      _maybeInsertTimeSeparator(messagesEl, msg, prevMsg);
      messagesEl.appendChild(_createMessageEl(msg, prevMsg));
      _scrollToBottom();
    }

    // POST to API
    VoiceAPI.sendChannelMessage(slug, text).then(function (resp) {
      // Promote optimistic message with real ID
      for (var i = 0; i < cached.length; i++) {
        if (cached[i].id === optimisticId) {
          cached[i].id = resp.id || cached[i].id;
          cached[i].sent_at = resp.sent_at || cached[i].sent_at;
          delete cached[i]._optimistic;
          break;
        }
      }
      // Update DOM element
      var bubble = messagesEl ? messagesEl.querySelector('[data-msg-id="' + optimisticId + '"]') : null;
      if (bubble) {
        bubble.setAttribute('data-msg-id', resp.id || optimisticId);
        bubble.classList.remove('send-pending');
      }
    }).catch(function () {
      // Mark as failed
      var bubble = messagesEl ? messagesEl.querySelector('[data-msg-id="' + optimisticId + '"]') : null;
      if (bubble) {
        bubble.classList.add('send-failed');
        bubble.classList.remove('send-pending');
      }
    });
  }

  // --- Private helpers ---

  function _renderAllMessages(slug) {
    var messagesEl = document.getElementById('channel-chat-messages');
    if (!messagesEl) return;

    var messages = VoiceState.channelMessages[slug] || [];
    messagesEl.innerHTML = '<div id="channel-chat-load-more" class="chat-load-more" style="display:none"></div>';

    if (messages.length === 0) {
      messagesEl.innerHTML += '<div class="channel-chat-empty">No messages yet</div>';
      return;
    }

    var frag = document.createDocumentFragment();
    for (var i = 0; i < messages.length; i++) {
      var prevMsg = i > 0 ? messages[i - 1] : null;
      _maybeInsertTimeSeparator(frag, messages[i], prevMsg);
      frag.appendChild(_createMessageEl(messages[i], prevMsg));
    }
    messagesEl.appendChild(frag);
  }

  function _createMessageEl(msg, prevMsg) {
    var senderType = _getSenderType(msg);
    var div = document.createElement('div');
    div.className = 'ch-msg ch-msg-' + senderType;
    if (msg._optimistic) div.classList.add('send-pending');
    div.setAttribute('data-msg-id', msg.id);

    // Sender name (skip if same sender as previous and within 2 min gap)
    var showSender = true;
    if (prevMsg && _getSenderType(prevMsg) === senderType
        && (prevMsg.persona_name || 'Unknown') === (msg.persona_name || 'Unknown')) {
      var gap = new Date(msg.sent_at).getTime() - new Date(prevMsg.sent_at).getTime();
      if (gap < 120000) showSender = false;
    }

    var html = '';
    if (showSender && senderType !== 'system') {
      var nameClass = 'ch-msg-sender ch-sender-' + senderType;
      var displayName = msg.persona_name || 'Unknown';
      if (senderType === 'operator') displayName = msg.persona_name || 'Operator';
      html += '<div class="' + nameClass + '">' + VoiceChatRenderer.esc(displayName) + '</div>';
    }

    // Content
    if (senderType === 'system') {
      html += '<div class="ch-msg-system-text">' + VoiceChatRenderer.esc(msg.content) + '</div>';
    } else {
      html += '<div class="ch-msg-content">' + VoiceChatRenderer.renderMd(msg.content) + '</div>';
    }

    // Time
    var sentDate = new Date(msg.sent_at);
    var relTime = _formatRelativeTime(sentDate);
    var absTime = sentDate.toLocaleString();
    html += '<div class="ch-msg-time" title="' + VoiceChatRenderer.esc(absTime) + '">' + relTime + '</div>';

    div.innerHTML = html;
    return div;
  }

  function _getSenderType(msg) {
    if (msg.message_type === 'system') return 'system';
    if (!msg.agent_id) return 'operator';
    return 'agent';
  }

  function _maybeInsertTimeSeparator(container, msg, prevMsg) {
    if (!prevMsg) return;
    var gap = new Date(msg.sent_at).getTime() - new Date(prevMsg.sent_at).getTime();
    if (gap >= TIMESTAMP_GAP_MS) {
      var sep = document.createElement('div');
      sep.className = 'ch-time-separator';
      sep.textContent = _formatTimestamp(new Date(msg.sent_at));
      container.appendChild(sep);
    }
  }

  function _formatRelativeTime(date) {
    var diff = (Date.now() - date.getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  function _formatTimestamp(date) {
    var now = new Date();
    var isToday = date.toDateString() === now.toDateString();
    if (isToday) {
      return 'Today ' + date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
    }
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
      + ' ' + date.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' });
  }

  function _scrollToBottom() {
    var el = document.getElementById('channel-chat-messages');
    if (el) {
      requestAnimationFrame(function () { el.scrollTop = el.scrollHeight; });
    }
  }

  function _isNearBottom(el) {
    if (!el) return true;
    return (el.scrollHeight - el.scrollTop - el.clientHeight) < 120;
  }

  /**
   * Display a voice bridge response as a system message in channel chat.
   * @param {object} voice - Voice envelope {status_line, results, next_action}
   */
  function showVoiceResult(voice) {
    if (!voice) return;

    // Build content from voice envelope
    var parts = [];
    if (voice.status_line) parts.push(voice.status_line);
    if (voice.results && voice.results.length) {
      parts = parts.concat(voice.results);
    }
    if (voice.next_action) parts.push(voice.next_action);
    var content = parts.join('\n');
    if (!content) return;

    _showChannelSystemMessage(content);
  }

  // =====================================================================
  //  Channel chat kebab menu
  // =====================================================================

  /** Determine if the current user is the chair of this channel. */
  function _isCurrentUserChair() {
    // channelMembers comes from VoiceAPI.getChannelMembers(slug)
    // Operator (non-agent) entries have agent_id = null and is_chair flag
    var members = VoiceState.channelMembers || [];
    for (var i = 0; i < members.length; i++) {
      var m = members[i];
      if (!m.agent_id && m.is_chair) return true;
    }
    // Fallback: if no operator member found with is_chair, check if the operator
    // is first member (legacy channels without explicit is_chair)
    return false;
  }

  /** Build actions for the channel chat header kebab menu. */
  function buildChannelChatActions() {
    var I = (typeof PortalKebabMenu !== 'undefined') ? PortalKebabMenu.ICONS : {};
    var isChair = _isCurrentUserChair();

    var actions = [
      { id: 'download-transcript', label: 'Download Transcript', icon: I.download || '' },
      { id: 'add-member', label: 'Add member', icon: I.addMember || '' },
      { id: 'info', label: 'Channel info', icon: I.info || '' },
      { id: 'copy-slug', label: 'Copy slug', icon: I.copySlug || '' }
    ];

    if (isChair) {
      actions.push('divider');
      actions.push({ id: 'complete', label: 'Complete channel', icon: I.complete || '' });
      actions.push({ id: 'archive', label: 'Archive channel', icon: I.archive || '', className: 'kill-action' });
    }

    actions.push('divider');
    actions.push({ id: 'leave', label: 'Leave channel', icon: I.leave || '', className: 'kill-action' });

    return actions;
  }

  /** Handle channel chat kebab action. */
  function handleChannelChatAction(actionId, slug) {
    switch (actionId) {
      case 'download-transcript':
        _showChannelSystemMessage('Preparing transcript\u2026');
        window.open('/api/channels/' + encodeURIComponent(slug) + '/transcript', '_blank');
        break;
      case 'add-member':
        // Open member autocomplete - for now show a system message
        // In the voice app we don't have the full autocomplete widget yet
        _showChannelSystemMessage('Member picker not yet available in voice app. Use the dashboard to add members.');
        break;
      case 'info':
        // Show channel info (navigate to dashboard channel view)
        window.open('/?channel=' + encodeURIComponent(slug), '_blank');
        break;
      case 'copy-slug':
        if (navigator.clipboard) {
          navigator.clipboard.writeText(slug).then(function () {
            _showChannelSystemMessage('Channel slug copied to clipboard');
          }).catch(function () {
            _showChannelSystemMessage('Failed to copy slug');
          });
        }
        break;
      case 'complete':
        if (typeof ConfirmDialog !== 'undefined') {
          ConfirmDialog.show(
            'Complete Channel',
            'Mark this channel as complete? Members will be notified.',
            { confirmText: 'Complete', cancelText: 'Cancel' }
          ).then(function (confirmed) {
            if (!confirmed) return;
            _channelAction(slug, '/api/channels/' + encodeURIComponent(slug) + '/complete', 'Channel completed', 'Failed to complete channel');
          });
        }
        break;
      case 'archive':
        if (typeof ConfirmDialog !== 'undefined') {
          ConfirmDialog.show(
            'Archive Channel',
            'Archive this channel? This cannot be undone.',
            { confirmText: 'Archive', cancelText: 'Cancel', destructive: true }
          ).then(function (confirmed) {
            if (!confirmed) return;
            _channelAction(slug, '/api/channels/' + encodeURIComponent(slug) + '/archive', 'Channel archived', 'Failed to archive channel');
          });
        }
        break;
      case 'leave':
        if (typeof ConfirmDialog !== 'undefined') {
          ConfirmDialog.show(
            'Leave Channel',
            'Leave #' + slug + '? You will no longer receive messages.',
            { confirmText: 'Leave', cancelText: 'Cancel' }
          ).then(function (confirmed) {
            if (!confirmed) return;
            _channelAction(slug, '/api/channels/' + encodeURIComponent(slug) + '/leave', 'Left channel', 'Failed to leave channel', function () {
              VoiceState.currentChannelSlug = null;
              VoiceSidebar.refreshAgents();
              VoiceLayout.showScreen('agents');
            });
          });
        }
        break;
    }
  }

  /** Execute a channel POST action with success/error messages. */
  function _channelAction(slug, url, successMsg, errorMsg, onSuccess) {
    CHUtils.apiFetch(url, { method: 'POST' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) {
          _showChannelSystemMessage(errorMsg + ': ' + data.error);
        } else {
          _showChannelSystemMessage(successMsg);
          if (onSuccess) onSuccess();
          else {
            VoiceSidebar.refreshAgents();
          }
        }
      })
      .catch(function () {
        _showChannelSystemMessage(errorMsg);
      });
  }

  /** Show a system message in the channel chat. */
  function _showChannelSystemMessage(text) {
    var slug = VoiceState.currentChannelSlug;
    if (!slug) return;
    var msg = {
      id: 'sys-' + Date.now(),
      channel_slug: slug,
      persona_slug: null,
      persona_name: null,
      agent_id: null,
      content: text,
      message_type: 'system',
      sent_at: new Date().toISOString()
    };
    if (!VoiceState.channelMessages[slug]) VoiceState.channelMessages[slug] = [];
    VoiceState.channelMessages[slug].push(msg);
    var messagesEl = document.getElementById('channel-chat-messages');
    if (messagesEl) {
      var cached = VoiceState.channelMessages[slug];
      var prevMsg = cached.length > 1 ? cached[cached.length - 2] : null;
      _maybeInsertTimeSeparator(messagesEl, msg, prevMsg);
      messagesEl.appendChild(_createMessageEl(msg, prevMsg));
      _scrollToBottom();
    }
  }

  /** Open the channel chat kebab menu from the header trigger button. */
  function openChannelChatKebab() {
    var btn = document.getElementById('channel-chat-kebab-btn');
    var slug = VoiceState.currentChannelSlug;
    if (!btn || !slug) return;
    if (typeof PortalKebabMenu !== 'undefined') {
      if (PortalKebabMenu.isOpen()) {
        PortalKebabMenu.close();
        return;
      }
      PortalKebabMenu.open(btn, {
        agentId: slug,
        actions: buildChannelChatActions(),
        onAction: handleChannelChatAction
      });
    }
  }

  // --- Public API ---

  return {
    showChannelChatScreen: showChannelChatScreen,
    appendMessage: appendMessage,
    loadOlderMessages: loadOlderMessages,
    sendMessage: sendMessage,
    showVoiceResult: showVoiceResult,
    openChannelChatKebab: openChannelChatKebab
  };
})();
