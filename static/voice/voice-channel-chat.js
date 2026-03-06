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
  var MAX_FETCH_RETRIES = 2;

  function _fetchMessagesWithRetry(slug, attempt) {
    return VoiceAPI.getChannelMessages(slug, { limit: MESSAGE_LIMIT }).then(function (messages) {
      messages = messages || [];
      VoiceState.channelMessages[slug] = messages;
      VoiceState.channelHasMore = messages.length >= MESSAGE_LIMIT;
      if (messages.length > 0) {
        VoiceState.channelOldestMessageTime = messages[0].sent_at;
      }
    }).catch(function (err) {
      console.error('[ChannelChat] fetch failed for', slug, err);
      if (attempt < MAX_FETCH_RETRIES) {
        return new Promise(function (resolve) {
          setTimeout(resolve, 500 * (attempt + 1));
        }).then(function () {
          return _fetchMessagesWithRetry(slug, attempt + 1);
        });
      }
      VoiceState.channelMessages[slug] = [];
      var messagesEl = document.getElementById('channel-chat-messages');
      if (messagesEl) {
        var errMsg = (err && err.error) || (err && err.message) || 'unknown error';
        messagesEl.innerHTML = '<div class="channel-chat-empty" style="color:#f87171">'
          + 'Failed to load messages: ' + errMsg + '</div>';
      }
    });
  }

  // --- Public methods ---

  function showChannelChatScreen(slug) {
    // Save current agent chat scroll state + draft before switching
    // (must happen while screen-chat is still visible / display:block)
    var currentAgentId = VoiceState.targetAgentId;
    if (currentAgentId && VoiceState.currentScreen === 'chat') {
      VoiceChatController.saveScrollState(currentAgentId);
    }
    var agentInput = document.getElementById('chat-text-input');
    if (agentInput && currentAgentId) {
      var agentDraft = agentInput.value;
      if (agentDraft) {
        VoiceState.agentDrafts[currentAgentId] = agentDraft;
      } else {
        delete VoiceState.agentDrafts[currentAgentId];
      }
    }

    // Save current channel draft if switching between channels
    var previousSlug = VoiceState.currentChannelSlug;
    if (previousSlug && previousSlug !== slug) {
      var prevInput = document.getElementById('channel-chat-input');
      if (prevInput) {
        var prevDraft = prevInput.value;
        if (prevDraft) {
          VoiceState.channelDrafts[previousSlug] = prevDraft;
        } else {
          delete VoiceState.channelDrafts[previousSlug];
        }
      }
    }

    VoiceState.currentChannelSlug = slug;
    VoiceState.channelMembers = [];
    VoiceState.channelHasMore = false;
    VoiceState.channelLoadingMore = false;
    VoiceState.channelOldestMessageTime = null;

    var nameEl = document.getElementById('channel-chat-name');
    var badgeEl = document.getElementById('channel-chat-type-badge');

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
      _renderMemberPills(VoiceState.channelMembers);
    }).catch(function (err) {
      console.error('[ChannelChat] Failed to fetch members for', slug, err);
      VoiceState.channelMembers = [];
    });

    var messagesPromise = _fetchMessagesWithRetry(slug, 0);

    Promise.all([membersPromise, messagesPromise]).then(function () {
      _renderAllMessages(slug);
      _scrollToBottom();
    });

    VoiceLayout.showScreen('channel-chat');
    VoiceSidebar.highlightSelectedChannel();

    // Restore channel draft
    var channelInput = document.getElementById('channel-chat-input');
    if (channelInput) {
      channelInput.value = VoiceState.channelDrafts[slug] || '';
    }
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
      // Exact ID match — already have this message
      if (existing[i].id === msg.id) return;
      // Match optimistic message: same content from same sender type (operator)
      if (existing[i]._optimistic && !msg.agent_id && !existing[i].agent_id
          && existing[i].content === msg.content) {
        // Capture old optimistic ID before overwriting
        var oldId = existing[i].id;
        existing[i].id = msg.id;
        existing[i].sent_at = msg.sent_at;
        existing[i].persona_name = msg.persona_name;
        delete existing[i]._optimistic;
        // Update the rendered bubble
        var bubble = document.querySelector('[data-turn-id="' + oldId + '"]');
        if (bubble) {
          bubble.setAttribute('data-turn-id', msg.id);
          bubble.classList.remove('send-pending');
          var senderEl = bubble.querySelector('.chat-bubble-sender');
          if (senderEl && msg.persona_name) senderEl.textContent = msg.persona_name;
        }
        return;
      }
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
    }).catch(function (err) {
      console.error('[ChannelChat] Failed to load older messages', err);
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
      if (msg.sent_at && prevMsg.sent_at) {
        var gap = new Date(msg.sent_at).getTime() - new Date(prevMsg.sent_at).getTime();
        if (gap < 120000) showSender = false;
      }
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
        VoiceState.addMemberTargetSlug = slug;
        VoiceSidebar.openChannelPicker('add-member');
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

  // --- Member pills ---

  function _stateClass(agentState) {
    if (!agentState) return '';
    return ' state-' + agentState.toLowerCase().replace(/_/g, '-');
  }

  function _renderMemberPills(memberships) {
    var container = document.getElementById('channel-chat-member-pills');
    if (!container) return;
    var html = '';
    var connected = 0, total = 0;
    for (var i = 0; i < memberships.length; i++) {
      var m = memberships[i];
      if (m.is_chair) continue; // operator chair pill is optional — skip
      total++;
      var pending = !m.agent_id;
      if (!pending) connected++;
      var name = m.persona_name || m.persona_slug || 'Unknown';
      if (pending) {
        html += '<span class="channel-member-pill pending" title="' + _esc(name) + ' (connecting...)">'
          + _esc(name) + '</span>';
      } else {
        var sc = _stateClass(m.agent_state);
        var tip = m.agent_state_label ? _esc(name) + ' — ' + _esc(m.agent_state_label) : 'Focus ' + _esc(name);
        var label = name;
        if (m.agent_state_label && m.agent_state && m.agent_state.toLowerCase() !== 'complete') {
          label += ' ' + m.agent_state_label.toLowerCase();
        }
        html += '<button class="channel-member-pill' + sc + '" data-agent-id="' + m.agent_id
          + '" data-agent-state="' + _esc(m.agent_state || '')
          + '" data-has-tmux="' + (m.has_tmux ? 'true' : 'false') + '" title="' + tip + '">'
          + _esc(label) + '</button>';
      }
    }
    if (total > 0) {
      html += '<span class="channel-member-count">' + connected + ' of ' + total + ' online</span>';
    }
    container.innerHTML = html;
    // Bind focus clicks — use attachAgent (tmux) when available, else focusAgent (iTerm)
    container.querySelectorAll('.channel-member-pill[data-agent-id]').forEach(function (btn) {
      btn.addEventListener('click', function () {
        var agentId = parseInt(btn.getAttribute('data-agent-id'), 10);
        var hasTmux = btn.getAttribute('data-has-tmux') === 'true';
        var apiFn = hasTmux ? VoiceAPI.attachAgent : VoiceAPI.focusAgent;
        apiFn(agentId).then(function () {
          btn.classList.add('focus-highlight');
          setTimeout(function () { btn.classList.remove('focus-highlight'); }, 1200);
        }).catch(function () {});
      });
    });
  }

  function _esc(str) {
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function onMemberConnected(data) {
    // Update the specific pending pill to connected state
    if (!data || !data.persona_slug) return;
    var container = document.getElementById('channel-chat-member-pills');
    if (!container) return;

    var pendingPill = container.querySelector('.channel-member-pill.pending');
    // Find the pending pill matching this persona
    var pills = container.querySelectorAll('.channel-member-pill.pending');
    for (var i = 0; i < pills.length; i++) {
      var pill = pills[i];
      if (pill.title.indexOf(data.persona_name || data.persona_slug) !== -1
          || pill.textContent.trim() === (data.persona_name || data.persona_slug)) {
        pendingPill = pill;
        break;
      }
    }
    if (pendingPill && data.agent_id) {
      var name = data.persona_name || data.persona_slug;
      var sc = _stateClass(data.agent_state);
      var newBtn = document.createElement('button');
      newBtn.className = 'channel-member-pill' + sc;
      newBtn.setAttribute('data-agent-id', data.agent_id);
      newBtn.setAttribute('data-agent-state', data.agent_state || '');
      newBtn.setAttribute('data-has-tmux', data.has_tmux ? 'true' : 'false');
      newBtn.title = data.agent_state_label ? name + ' — ' + data.agent_state_label : 'Focus ' + name;
      var pillLabel = name;
      if (data.agent_state_label && data.agent_state && data.agent_state.toLowerCase() !== 'complete') {
        pillLabel += ' ' + data.agent_state_label.toLowerCase();
      }
      newBtn.textContent = pillLabel;
      newBtn.addEventListener('click', function () {
        var apiFn = data.has_tmux ? VoiceAPI.attachAgent : VoiceAPI.focusAgent;
        apiFn(parseInt(data.agent_id, 10)).then(function () {
          newBtn.classList.add('focus-highlight');
          setTimeout(function () { newBtn.classList.remove('focus-highlight'); }, 1200);
        }).catch(function () {});
      });
      pendingPill.parentNode.replaceChild(newBtn, pendingPill);
    }

    // Update count text
    var countEl = container.querySelector('.channel-member-count');
    if (countEl && data.connected_count !== undefined && data.total_count !== undefined) {
      countEl.textContent = data.connected_count + ' of ' + data.total_count + ' online';
    }
  }

  function onChannelReady(data) {
    _showChannelSystemMessage('Channel ready \u2014 all agents connected.');
    // Enable chat input
    var input = document.getElementById('channel-chat-input');
    var sendBtn = document.getElementById('channel-chat-send');
    if (input) input.disabled = false;
    if (sendBtn) sendBtn.disabled = false;
  }

  /**
   * Handle card_refresh SSE — update pill state colours live.
   */
  function onCardRefresh(data) {
    if (!data) return;
    var container = document.getElementById('channel-chat-member-pills');
    if (!container) return;
    var agentId = String(data.id);
    var newState = data.state;
    if (!agentId || !newState) return;

    var pill = container.querySelector('.channel-member-pill[data-agent-id="' + agentId + '"]');
    if (!pill) return;

    // Strip old state-* classes, apply new one
    var classes = pill.className.split(/\s+/).filter(function (c) { return c.indexOf('state-') !== 0; });
    classes.push('state-' + newState.toLowerCase().replace(/_/g, '-'));
    pill.className = classes.join(' ');
    pill.setAttribute('data-agent-state', newState);

    // Update pill text — show state after name when not complete
    var stateLabel = (data.state_info && data.state_info.label) || data.state_label || newState.replace(/_/g, ' ').toLowerCase();
    var personaName = (data.persona_name || pill.textContent.trim().split(' ')[0] || '').trim();
    if (newState.toLowerCase() !== 'complete') {
      pill.textContent = personaName + ' ' + stateLabel;
    } else {
      pill.textContent = personaName;
    }
    pill.title = personaName + ' — ' + stateLabel;
  }

  // --- Public API ---

  return {
    showChannelChatScreen: showChannelChatScreen,
    appendMessage: appendMessage,
    loadOlderMessages: loadOlderMessages,
    sendMessage: sendMessage,
    showVoiceResult: showVoiceResult,
    openChannelChatKebab: openChannelChatKebab,
    onMemberConnected: onMemberConnected,
    onChannelReady: onChannelReady,
    onCardRefresh: onCardRefresh
  };
})();
