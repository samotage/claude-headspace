/* VoiceChannelChat — channel conversation view: message rendering,
 * send, live injection, and scroll-up pagination.
 *
 * Dependencies: VoiceState, VoiceAPI, ChatBubbles, VoiceLayout, VoiceSidebar.
 */
window.VoiceChannelChat = (function () {
  'use strict';

  var MESSAGE_LIMIT = 50;
  var TIMESTAMP_GAP_MS = 5 * 60 * 1000; // 5 minutes between timestamp separators
  var _optimisticIdCounter = 0;

  // --- Public methods ---

  function showChannelChatScreen(slug) {
    VoiceState.currentChannelSlug = slug;
    VoiceState.channelMembers = [];
    VoiceState.channelHasMore = false;
    VoiceState.channelLoadingMore = false;
    VoiceState.channelOldestMessageTime = null;

    var nameEl = document.getElementById('channel-chat-name');
    var badgeEl = document.getElementById('channel-chat-type-badge');
    var memberCountEl = document.getElementById('channel-chat-member-count');

    var channelName = slug;
    var channels = VoiceState.channels;
    for (var i = 0; i < channels.length; i++) {
      if (channels[i].slug === slug) {
        channelName = channels[i].name || slug;
        if (badgeEl) badgeEl.textContent = channels[i].channel_type || 'channel';
        break;
      }
    }
    if (nameEl) nameEl.textContent = '#' + channelName;

    var messagesEl = document.getElementById('channel-chat-messages');
    if (messagesEl) {
      messagesEl.innerHTML = '<div id="channel-chat-load-more" class="chat-load-more" style="display:none"></div>'
        + '<div class="channel-chat-loading">Loading messages...</div>';
    }

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

  function appendMessage(data) {
    var slug = data.channel_slug;
    if (!slug) return;

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

    if (!VoiceState.channelMessages[slug]) {
      VoiceState.channelMessages[slug] = [];
    }
    var existing = VoiceState.channelMessages[slug];
    for (var i = 0; i < existing.length; i++) {
      if (existing[i].id === msg.id) return;
    }
    existing.push(msg);

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

      var cached = VoiceState.channelMessages[slug] || [];
      VoiceState.channelMessages[slug] = messages.concat(cached);
      VoiceState.channelOldestMessageTime = messages[0].sent_at;

      if (messagesEl) {
        var frag = document.createDocumentFragment();
        for (var i = 0; i < messages.length; i++) {
          var prevMsg = i > 0 ? messages[i - 1] : null;
          _maybeInsertTimeSeparator(frag, messages[i], prevMsg);
          frag.appendChild(_createMessageEl(messages[i], prevMsg));
        }
        var firstChild = loadMoreEl ? loadMoreEl.nextSibling : messagesEl.firstChild;
        messagesEl.insertBefore(frag, firstChild);

        var newScrollHeight = messagesEl.scrollHeight;
        messagesEl.scrollTop = newScrollHeight - prevScrollHeight;
      }
    }).catch(function () {
      VoiceState.channelLoadingMore = false;
      if (loadMoreEl) loadMoreEl.style.display = 'none';
    });
  }

  function sendMessage(text) {
    if (!text || !text.trim()) return;
    text = text.trim();
    var slug = VoiceState.currentChannelSlug;
    if (!slug) return;

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

    VoiceAPI.sendChannelMessage(slug, text).then(function (resp) {
      for (var i = 0; i < cached.length; i++) {
        if (cached[i].id === optimisticId) {
          cached[i].id = resp.id || cached[i].id;
          cached[i].sent_at = resp.sent_at || cached[i].sent_at;
          delete cached[i]._optimistic;
          break;
        }
      }
      var bubble = messagesEl ? messagesEl.querySelector('[data-turn-id="' + optimisticId + '"]') : null;
      if (bubble) {
        bubble.setAttribute('data-turn-id', resp.id || optimisticId);
        bubble.classList.remove('send-pending');
      }
    }).catch(function () {
      var bubble = messagesEl ? messagesEl.querySelector('[data-turn-id="' + optimisticId + '"]') : null;
      if (bubble) {
        bubble.classList.add('send-failed');
        bubble.classList.remove('send-pending');
      }
    });
  }

  // --- Private helpers ---

  function _getSenderType(msg) {
    if (msg.message_type === 'system') return 'system';
    if (!msg.agent_id) return 'operator';
    return 'agent';
  }

  /** Map channel message -> normalized msg for ChatBubbles */
  function _toNormalizedMsg(msg) {
    var senderType = _getSenderType(msg);
    var displayName = msg.persona_name || 'Unknown';
    if (senderType === 'operator') displayName = msg.persona_name || 'Operator';

    return {
      id: msg.id,
      actor: senderType === 'system' ? 'system' : (senderType === 'operator' ? 'user' : 'agent'),
      senderName: displayName,
      senderType: senderType,
      text: msg.content || '',
      timestamp: msg.sent_at
    };
  }

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

    // Determine if sender name should be shown
    var showSender = true;
    if (prevMsg && _getSenderType(prevMsg) === senderType
        && (prevMsg.persona_name || 'Unknown') === (msg.persona_name || 'Unknown')) {
      var gap = new Date(msg.sent_at).getTime() - new Date(prevMsg.sent_at).getTime();
      if (gap < 120000) showSender = false;
    }

    var normalized = _toNormalizedMsg(msg);
    var opts = {
      showSenderName: showSender,
      showCopyButton: senderType !== 'system',
      showIntentBadge: false
    };

    var frag = ChatBubbles.createBubble(normalized, opts);

    // Extract the bubble element from the fragment for class additions
    var bubble = frag.querySelector('.chat-bubble');
    if (bubble) {
      if (msg._optimistic) bubble.classList.add('send-pending');
    }

    return frag;
  }

  function _maybeInsertTimeSeparator(container, msg, prevMsg) {
    if (!prevMsg) return;
    var gap = new Date(msg.sent_at).getTime() - new Date(prevMsg.sent_at).getTime();
    if (gap >= TIMESTAMP_GAP_MS) {
      container.appendChild(ChatBubbles.createTimeSeparator(
        ChatBubbles.formatChatTime(msg.sent_at)
      ));
    }
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

  function showVoiceResult(voice) {
    if (!voice) return;
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

  function _isCurrentUserChair() {
    var members = VoiceState.channelMembers || [];
    for (var i = 0; i < members.length; i++) {
      var m = members[i];
      if (!m.agent_id && m.is_chair) return true;
    }
    return false;
  }

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

  function handleChannelChatAction(actionId, slug) {
    switch (actionId) {
      case 'download-transcript':
        _showChannelSystemMessage('Preparing transcript\u2026');
        window.open('/api/channels/' + encodeURIComponent(slug) + '/transcript', '_blank');
        break;
      case 'add-member':
        _showChannelSystemMessage('Member picker not yet available in voice app. Use the dashboard to add members.');
        break;
      case 'info':
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
