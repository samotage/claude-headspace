/* Voice Bridge main app controller */
window.VoiceApp = (function () {
  'use strict';

  // Settings defaults now in VoiceState.DEFAULTS

  // _settings now managed by VoiceState.settings via VoiceSettings module
  var _targetAgentId = null;
  // VoiceState.currentScreen now in VoiceState.currentScreen
  var _chatPendingUserSends = [];  // {text, sentAt, fakeTurnId} — pending sends awaiting real turn
  var PENDING_SEND_TTL_MS = 10000; // 10s window for optimistic send confirmation
  var _chatAgentState = null;
  var _chatAgentStateLabel = null;
  var _chatHasMore = false;
  var _chatLoadingMore = false;
  var _chatAgentEnded = false;
  // _chatTranscriptSeq kept for initial load guard only (stale navigation detection)
  var _chatSyncTimer = null;   // Periodic transcript sync timer (safety net)
  var _responseCatchUpTimers = []; // Aggressive post-send fetch timers
  var _isLocalhost = (location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.hostname === '::1');
  var _isTrustedNetwork = _isLocalhost
    || /^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|100\.)/.test(location.hostname)
    || /\.ts\.net$/.test(location.hostname);
  var _navStack = [];           // Stack of agent IDs for back navigation
  var _pendingAttachment = null; // File object pending upload
  var _pendingBlobUrl = null;    // Blob URL for image preview (revoke on clear)
  // Per-agent scroll position memory (in-memory, dies with tab)
  var _agentScrollState = {};        // agentId -> { scrollTop, scrollHeight, lastTurnId }
  var _newMessagesPillVisible = false;
  var _newMessagesFirstTurnId = null;

  // Layout/FAB/hamburger state now in VoiceState

  // File upload constants now in VoiceState

  // --- Settings (delegated to VoiceSettings module) ---

  // --- Layout, screen, FAB, hamburger, menu (delegated to VoiceLayout module) ---

  // --- Voice from FAB/hamburger ---

  function _triggerVoiceFromMenu() {
    VoiceOutput.initAudio();
    if (VoiceInput.isListening()) {
      _stopListening();
      return;
    }
    if (VoiceState.settings.autoTarget) {
      var auto = VoiceSidebar.autoTarget();
      if (auto) { _showListeningScreen(auto); }
    }
    if (!_targetAgentId) {
      var agentStatus = document.getElementById('agent-status-message');
      if (agentStatus) {
        agentStatus.textContent = 'Select an agent first';
        setTimeout(function () { agentStatus.textContent = ''; }, 2000);
      }
      return;
    }
    _startListening();
  }

  // --- Sidebar functions moved to VoiceSidebar module (Phase 6) ---

  // --- Listening / Command mode (task 2.21) ---

  function _showListeningScreen(agent) {
    var el = document.getElementById('listening-target');
    if (el && agent) el.textContent = agent.project;
    VoiceLayout.showScreen('listening');
  }

  function _startListening() {
    VoiceOutput.initAudio(); // unlock audio context on user gesture
    VoiceInput.start();
  }

  function _stopListening() {
    VoiceInput.stop();
  }

  // --- Question / Response mode (task 2.22) ---

  function _loadQuestion(agentId) {
    VoiceAPI.getQuestion(agentId).then(function (data) {
      _renderQuestion(data);
      VoiceLayout.showScreen('question');
    }).catch(function () {
      _showListeningScreen(null);
    });
  }

  function _renderQuestion(data) {
    var q = data.question || {};
    var textEl = document.getElementById('question-text');
    var optionsEl = document.getElementById('question-options');
    var freeEl = document.getElementById('question-free');

    if (textEl) textEl.textContent = q.question_text || 'Agent needs input';

    // Speak the question
    if (data.voice) VoiceOutput.speakResponse(data.voice);

    if (q.question_options && q.question_options.length > 0) {
      // Structured options
      if (freeEl) freeEl.style.display = 'none';
      if (optionsEl) {
        optionsEl.style.display = 'block';
        var html = '';
        for (var i = 0; i < q.question_options.length; i++) {
          var opt = q.question_options[i];
          html += '<button class="option-btn" data-label="' + VoiceChatRenderer.esc(opt.label) + '" data-opt-idx="' + i + '">'
            + '<strong>' + VoiceChatRenderer.esc(opt.label) + '</strong>'
            + (opt.description ? '<br><span class="option-desc">' + VoiceChatRenderer.esc(opt.description) + '</span>' : '')
            + '</button>';
        }
        optionsEl.innerHTML = html;

        var btns = optionsEl.querySelectorAll('.option-btn');
        for (var j = 0; j < btns.length; j++) {
          btns[j].addEventListener('click', function () {
            var idx = parseInt(this.getAttribute('data-opt-idx'), 10);
            _sendSelect(idx);
          });
        }
      }
    } else {
      // Free-text question
      if (optionsEl) optionsEl.style.display = 'none';
      if (freeEl) freeEl.style.display = 'block';
    }
  }

  // --- Chat screen ---

  function _stopChatSyncTimer() {
    if (_chatSyncTimer) { clearInterval(_chatSyncTimer); _chatSyncTimer = null; }
  }

  function _startChatSyncTimer() {
    // No-op: SSE is now the primary delivery mechanism for turns.
    // Transcript fetch is only used for initial load, gap recovery,
    // and SSE reconnect scenarios.
    _stopChatSyncTimer();
  }

  /**
   * Cancel any active response catch-up timers (no-op — SSE-primary).
   */
  function _cancelResponseCatchUp() {
    // No-op: SSE delivers turns directly; polling catch-up removed
  }

  /**
   * Schedule response catch-up (no-op — SSE-primary).
   * SSE now delivers all turns (user and agent) directly.
   */
  function _scheduleResponseCatchUp() {
    // No-op: SSE delivers turns directly; polling catch-up removed
  }

  function _showChatScreen(agentId) {
    // Save scroll state for the agent we're leaving
    var previousAgentId = _targetAgentId;
    if (previousAgentId && previousAgentId !== agentId) {
      _saveScrollState(previousAgentId);
    }
    _dismissNewMessagesPill();
    _targetAgentId = agentId;
    VoiceState.targetAgentId = agentId;
    var focusLink = document.getElementById('chat-focus-link');
    if (focusLink) focusLink.setAttribute('data-agent-id', agentId);
    VoiceState.lastSeenTurnId = 0;
    _chatPendingUserSends = [];
    _chatHasMore = false;
    _chatLoadingMore = false;
    VoiceState.chatOldestTurnId = null;
    _chatAgentEnded = false;
    VoiceState.chatLastTaskId = null;
    _fetchInFlight = false; // Reset in-flight guard for new agent
    if (_fetchDebounceTimer) { clearTimeout(_fetchDebounceTimer); _fetchDebounceTimer = null; }
    _cancelResponseCatchUp();
    _startChatSyncTimer();
    var messagesEl = document.getElementById('chat-messages');
    if (messagesEl) messagesEl.innerHTML = '';
    var bannersEl = document.getElementById('attention-banners');
    if (bannersEl) bannersEl.innerHTML = '';

    // Fetch other agent states for attention banners
    VoiceAPI.getSessions().then(function (data) {
      var agents = data.agents || [];
      VoiceState.otherAgentStates = {};
      for (var i = 0; i < agents.length; i++) {
        var a = agents[i];
        if (a.agent_id !== agentId) {
          VoiceState.otherAgentStates[a.agent_id] = {
            hero_chars: a.hero_chars || '',
            hero_trail: a.hero_trail || '',
            task_instruction: a.task_instruction || '',
            state: (a.state || '').toLowerCase(),
            project_name: a.project || ''
          };
        }
      }
      VoiceChatRenderer.renderAttentionBanners();
    }).catch(function () { /* ignore */ });

    var initAgentId = agentId;
    VoiceAPI.getTranscript(agentId).then(function (data) {
      if (initAgentId !== _targetAgentId) return; // Stale response — user navigated away
      var nameEl = document.getElementById('chat-agent-name');
      var projEl = document.getElementById('chat-project-name');
      var heroEl = document.getElementById('chat-hero');
      if (heroEl) {
        var hc = data.hero_chars || '';
        var ht = data.hero_trail || '';
        heroEl.innerHTML = '<span class="agent-hero">' + VoiceChatRenderer.esc(hc) + '</span><span class="agent-hero-trail">' + VoiceChatRenderer.esc(ht) + '</span>';
      }
      if (nameEl) nameEl.textContent = data.project || 'Agent';
      if (projEl) projEl.textContent = '';

      // Update browser tab title with agent identity
      var titleHero = (data.hero_chars || '').trim();
      var titleProject = (data.project || 'Agent').trim();
      document.title = titleHero + ' ' + titleProject + ' \u2014 Claude Chat';

      _chatAgentState = data.agent_state;
      _chatAgentStateLabel = null; // Reset; will be set by SSE with richer label if available
      _chatHasMore = data.has_more || false;
      _chatAgentEnded = data.agent_ended || false;
      var focusLink = document.getElementById('chat-focus-link');
      if (focusLink) {
        focusLink.setAttribute('data-tmux-session', data.tmux_session || '');
        focusLink.title = data.tmux_session ? 'Attach to tmux session' : 'Focus iTerm window';
      }
      VoiceChatRenderer.renderTranscriptTurns(data);
      // Restore scroll position if returning to a previously-viewed agent
      var saved = _agentScrollState[agentId];
      if (saved) {
        delete _agentScrollState[agentId]; // one-shot restore
        // Determine which rendered turn IDs are new (numeric only) via DOM
        var newTurnIds = [];
        var renderedBubbles = document.querySelectorAll('.chat-bubble[data-turn-id]');
        for (var ri = 0; ri < renderedBubbles.length; ri++) {
          var rid = parseInt(renderedBubbles[ri].getAttribute('data-turn-id'), 10);
          if (!isNaN(rid) && rid > saved.lastTurnId) newTurnIds.push(rid);
        }
        newTurnIds.sort(function (a, b) { return a - b; });
        var messagesEl = document.getElementById('chat-messages');
        if (newTurnIds.length === 0) {
          // No new turns — restore exact position
          if (messagesEl) messagesEl.scrollTop = saved.scrollTop;
        } else {
          // New turns arrived — restore position + show pill
          if (messagesEl) messagesEl.scrollTop = saved.scrollTop;
          _showNewMessagesPill(newTurnIds.length, newTurnIds[0]);
        }
      } else {
        _scrollChatToBottom();
      }
      _updateTypingIndicator();
      _updateChatStatePill();
      // Show most recent task instruction in header
      _updateChatTaskInstruction(data.turns || []);
      _updateEndedAgentUI();
      _updateLoadMoreIndicator();
    }).catch(function () {
      var nameEl = document.getElementById('chat-agent-name');
      if (nameEl) nameEl.textContent = 'Agent ' + agentId;
    });

    VoiceLayout.showScreen('chat');
    VoiceSidebar.highlightSelectedAgent();
  }

  function _loadOlderMessages() {
    if (_chatLoadingMore || !_chatHasMore || !VoiceState.chatOldestTurnId) return;
    _chatLoadingMore = true;
    _updateLoadMoreIndicator();

    var messagesEl = document.getElementById('chat-messages');
    var prevScrollHeight = messagesEl ? messagesEl.scrollHeight : 0;

    VoiceAPI.getTranscript(_targetAgentId, { before: VoiceState.chatOldestTurnId, limit: 50 }).then(function (data) {
      _chatHasMore = data.has_more || false;
      var turns = data.turns || [];
      if (turns.length > 0) {
        // Prepend older turns at top
        VoiceChatRenderer.prependTranscriptTurns(turns);
        // Preserve scroll position
        if (messagesEl) {
          var newScrollHeight = messagesEl.scrollHeight;
          messagesEl.scrollTop = newScrollHeight - prevScrollHeight;
        }
      }
      _chatLoadingMore = false;
      _updateLoadMoreIndicator();
    }).catch(function () {
      _chatLoadingMore = false;
      _updateLoadMoreIndicator();
    });
  }

  function _updateLoadMoreIndicator() {
    var indicator = document.getElementById('chat-load-more');
    if (!indicator) return;
    if (_chatLoadingMore) {
      indicator.className = 'chat-load-more loading';
      indicator.textContent = 'Loading...';
      indicator.style.display = 'block';
    } else if (!_chatHasMore && VoiceState.chatOldestTurnId) {
      indicator.className = 'chat-load-more done';
      indicator.textContent = 'Beginning of conversation';
      indicator.style.display = 'block';
    } else {
      indicator.style.display = 'none';
    }
  }

  function _updateEndedAgentUI() {
    var inputArea = document.getElementById('chat-input-area');
    var endedBanner = document.getElementById('chat-ended-banner');
    if (_chatAgentEnded) {
      if (inputArea) inputArea.style.display = 'none';
      if (endedBanner) endedBanner.style.display = 'block';
    } else {
      if (inputArea) inputArea.style.display = '';
      if (endedBanner) endedBanner.style.display = 'none';
    }
  }

  function _navigateToAgentFromBanner(agentId) {
    _navStack.push(_targetAgentId);
    _showChatScreen(agentId);
  }

  /**
   * Check if the user is scrolled near the bottom of the chat.
   * "Near" = within 150px of the bottom edge.  If they've scrolled
   * up to read older messages, we don't want to yank them away.
   */
  function _isUserNearBottom() {
    var el = document.getElementById('chat-messages');
    if (!el) return true;
    return (el.scrollHeight - el.scrollTop - el.clientHeight) < 150;
  }

  function _scrollChatToBottom() {
    var messagesEl = document.getElementById('chat-messages');
    if (messagesEl) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  /**
   * Scroll to bottom ONLY if the user is already near the bottom.
   * Call this for incoming messages (SSE, transcript refresh, typing
   * indicator) — anywhere the user didn't just perform an action.
   */
  function _scrollChatToBottomIfNear() {
    if (_isUserNearBottom()) _scrollChatToBottom();
  }

  function _saveScrollState(agentId) {
    if (!agentId) return;
    var el = document.getElementById('chat-messages');
    if (!el) return;
    _agentScrollState[agentId] = {
      scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight,
      lastTurnId: VoiceState.lastSeenTurnId
    };
  }

  function _showNewMessagesPill(count, firstNewTurnId) {
    _newMessagesFirstTurnId = firstNewTurnId;
    var pill = document.getElementById('new-messages-pill');
    if (!pill) {
      pill = document.createElement('div');
      pill.id = 'new-messages-pill';
      pill.className = 'new-messages-pill';
      pill.addEventListener('click', function () {
        if (!_newMessagesFirstTurnId) return;
        var bubble = document.querySelector('[data-turn-id="' + _newMessagesFirstTurnId + '"]');
        if (bubble) {
          bubble.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        _dismissNewMessagesPill();
      });
      // Insert as child of #screen-chat, between attention-banners and chat-messages
      var chatScreen = document.getElementById('screen-chat');
      var messagesEl = document.getElementById('chat-messages');
      if (chatScreen && messagesEl) {
        chatScreen.insertBefore(pill, messagesEl);
      }
    }
    pill.textContent = count + ' new message' + (count !== 1 ? 's' : '');
    pill.style.display = '';
    _newMessagesPillVisible = true;
  }

  function _dismissNewMessagesPill() {
    var pill = document.getElementById('new-messages-pill');
    if (pill) pill.style.display = 'none';
    _newMessagesPillVisible = false;
    _newMessagesFirstTurnId = null;
  }

  var _STATE_LABELS = {
    idle: 'Idle',
    commanded: 'Command received',
    processing: 'Processing\u2026',
    awaiting_input: 'Input needed',
    complete: 'Task complete',
    timed_out: 'Timed out'
  };

  function _getStateLabel(state) {
    return _STATE_LABELS[(state || '').toLowerCase()] || state || 'Unknown';
  }

  function _updateTypingIndicator() {
    var typingEl = document.getElementById('chat-typing');
    if (!typingEl) return;
    var state = (_chatAgentState || '').toLowerCase();
    var isProcessing = state === 'processing' || state === 'commanded';
    typingEl.style.display = isProcessing ? 'block' : 'none';
    if (isProcessing) _scrollChatToBottomIfNear();
  }

  function _updateChatStatePill() {
    var pill = document.getElementById('chat-state-pill');
    if (!pill) return;
    var state = (_chatAgentState || '').toLowerCase();
    if (!state) { pill.style.display = 'none'; return; }
    pill.style.display = '';
    var label = _chatAgentStateLabel || _getStateLabel(state);
    // Remove previous state-* classes (but not chat-state-pill base class)
    pill.className = pill.className.replace(/(?:^|\s)state-\S+/g, '').trim();
    if (pill.className.indexOf('chat-state-pill') === -1) pill.classList.add('chat-state-pill');
    pill.classList.add('state-' + state);
    pill.textContent = label;
    // Pulse animation for active states
    if (state === 'processing' || state === 'commanded') {
      pill.classList.add('state-pill-active');
    } else {
      pill.classList.remove('state-pill-active');
    }
  }

  function _updateChatTaskInstruction(turns) {
    var el = document.getElementById('chat-task-instruction');
    if (!el) return;
    // Find the most recent task_instruction from turns (last non-empty)
    var instruction = '';
    for (var i = turns.length - 1; i >= 0; i--) {
      if (turns[i].task_instruction) {
        instruction = turns[i].task_instruction;
        break;
      }
    }
    if (instruction) {
      el.textContent = instruction.length > 80 ? instruction.substring(0, 80) + '...' : instruction;
      el.style.display = '';
    } else {
      el.textContent = '';
      el.style.display = 'none';
    }
  }

  function _markAllQuestionsAnswered() {
    var containers = document.querySelectorAll('.bubble-options:not(.answered)');
    containers.forEach(function(el) {
      el.classList.add('answered');
      el.querySelectorAll('button').forEach(function(btn) { btn.disabled = true; });
    });
  }

  function _showChatSystemMessage(text) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    var el = document.createElement('div');
    el.className = 'chat-system-message';
    el.textContent = text;
    messagesEl.appendChild(el);
    _scrollChatToBottomIfNear();
  }

  // --- File upload helpers (delegated to VoiceFileUpload module) ---

  // --- Chat send with attachment ---

  function _sendChatWithAttachment(text) {
    if (!_pendingAttachment) {
      _sendChatCommand(text);
      return;
    }

    var file = _pendingAttachment;
    var trimText = (text || '').trim();

    // Guard: agent state check
    var state = (_chatAgentState || '').toLowerCase();
    if (state === 'processing' || state === 'commanded') {
      _showChatSystemMessage('Agent is processing \u2014 please wait.');
      return;
    }

    // Show optimistic user bubble via shared helper
    var displayText = trimText ? trimText : '[File: ' + file.name + ']';
    var pendingEntry = _renderOptimisticUserBubble(displayText, {
      file_metadata: {
        original_filename: file.name,
        file_type: VoiceFileUpload.isImageFile(file) ? 'image' : 'document',
        file_size: file.size,
        _localPreviewUrl: URL.createObjectURL(file)
      }
    });

    // Clear input
    var input = document.getElementById('chat-text-input');
    if (input) {
      input.value = '';
      input.style.height = 'auto';
    }
    VoiceFileUpload.clearPendingAttachment();

    // Show progress
    VoiceFileUpload.showUploadProgress(0);
    _chatAgentState = 'processing';
    _chatAgentStateLabel = null;
    _updateTypingIndicator();
    _updateChatStatePill();

    VoiceAPI.uploadFile(_targetAgentId, file, trimText || null, function (pct) {
      VoiceFileUpload.showUploadProgress(pct);
    }).then(function (data) {
      VoiceFileUpload.hideUploadProgress();
      // Schedule aggressive catch-up fetches in case SSE events are missed
      _scheduleResponseCatchUp();
    }).catch(function (err) {
      VoiceFileUpload.hideUploadProgress();
      // Remove the ghost optimistic bubble on failure (Finding 10)
      _removeOptimisticBubble(pendingEntry);
      var errMsg = (err && err.error) || 'Upload failed';
      VoiceFileUpload.showUploadError(errMsg);
      _chatAgentState = 'idle';
      _chatAgentStateLabel = null;
      _updateTypingIndicator();
      _updateChatStatePill();
    });
  }

  /**
   * Render an optimistic (provisional) user bubble immediately.
   * Sets a 10-second timeout to mark as send-failed if not confirmed
   * by a turn_created SSE event promoting the pending ID to a real ID.
   *
   * @param {string} text - The user's message text
   * @param {object} [extraFields] - Optional extra fields for the turn (e.g., file_metadata)
   * @returns {object} pendingEntry for tracking
   */
  function _renderOptimisticUserBubble(text, extraFields) {
    var now = new Date().toISOString();
    var fakeId = 'pending-' + Date.now();
    var fakeTurn = {
      id: fakeId,
      actor: 'user',
      intent: 'answer',
      text: text,
      timestamp: now
    };
    if (extraFields) {
      for (var key in extraFields) {
        if (extraFields.hasOwnProperty(key)) fakeTurn[key] = extraFields[key];
      }
    }

    var messagesEl = document.getElementById('chat-messages');
    var lastBubble = messagesEl ? messagesEl.querySelector('.chat-bubble:last-child') : null;
    var prevTurn = null;
    if (lastBubble) {
      prevTurn = { timestamp: now };
    }
    var pendingEntry = { text: text, sentAt: Date.now(), fakeTurnId: fakeId };

    // 10-second timeout: mark as send-failed if not confirmed
    pendingEntry.failTimer = setTimeout(function () {
      var bubble = document.querySelector('[data-turn-id="' + fakeId + '"]');
      if (bubble) {
        bubble.classList.add('send-failed');
      }
      // Remove from pending sends
      var idx = _chatPendingUserSends.indexOf(pendingEntry);
      if (idx !== -1) _chatPendingUserSends.splice(idx, 1);
    }, PENDING_SEND_TTL_MS);

    _chatPendingUserSends.push(pendingEntry);
    VoiceChatRenderer.renderChatBubble(fakeTurn, prevTurn);
    _scrollChatToBottom();
    return pendingEntry;
  }

  function _sendChatCommand(text) {
    if (!text || !text.trim()) return;

    // Render optimistic user bubble immediately
    var pendingEntry = _renderOptimisticUserBubble(text.trim());

    // Clear input and reset textarea height
    var input = document.getElementById('chat-text-input');
    if (input) {
      input.value = '';
      input.style.height = 'auto';
    }

    // Show typing indicator (agent will be processing)
    _chatAgentState = 'processing';
    _chatAgentStateLabel = null;
    _updateTypingIndicator();
    _updateChatStatePill();

    VoiceAPI.sendCommand(text.trim(), _targetAgentId).then(function () {
      // Command sent — schedule aggressive catch-up fetches in case
      // SSE events are missed (common on iOS Safari).
      _scheduleResponseCatchUp();
    }).catch(function (err) {
      // Remove the ghost optimistic bubble on failure (Finding 10)
      _removeOptimisticBubble(pendingEntry);
      // Show error as system message
      var errBubble = document.createElement('div');
      errBubble.className = 'chat-bubble agent';
      errBubble.innerHTML = '<div class="bubble-intent">Error</div><div class="bubble-text">' + VoiceChatRenderer.esc(err.error || 'Send failed') + '</div>';
      var msgEl = document.getElementById('chat-messages');
      if (msgEl) msgEl.appendChild(errBubble);
      _chatAgentState = 'idle';
      _chatAgentStateLabel = null;
      _updateTypingIndicator();
      _updateChatStatePill();
      _scrollChatToBottom();
    });
  }

  function _sendChatSelect(optionIndex, label, bubble) {
    // Render optimistic user bubble with the label text
    var pendingEntry = _renderOptimisticUserBubble(label);

    // Disable option buttons in this bubble to prevent double-sends
    if (bubble) {
      var allBtns = bubble.querySelectorAll('.bubble-option-btn');
      for (var k = 0; k < allBtns.length; k++) {
        allBtns[k].disabled = true;
        allBtns[k].style.opacity = '0.5';
        allBtns[k].style.pointerEvents = 'none';
      }
    }

    // Show typing indicator
    _chatAgentState = 'processing';
    _chatAgentStateLabel = null;
    _updateTypingIndicator();
    _updateChatStatePill();

    VoiceAPI.sendSelect(_targetAgentId, optionIndex, label).then(function () {
      _scheduleResponseCatchUp();
    }).catch(function (err) {
      _removeOptimisticBubble(pendingEntry);
      var errBubble = document.createElement('div');
      errBubble.className = 'chat-bubble agent';
      errBubble.innerHTML = '<div class="bubble-intent">Error</div><div class="bubble-text">' + VoiceChatRenderer.esc(err.error || 'Select failed') + '</div>';
      var msgEl = document.getElementById('chat-messages');
      if (msgEl) msgEl.appendChild(errBubble);
      _chatAgentState = 'idle';
      _chatAgentStateLabel = null;
      _updateTypingIndicator();
      _updateChatStatePill();
      _scrollChatToBottom();

      // Re-enable buttons on error
      if (bubble) {
        var btns = bubble.querySelectorAll('.bubble-option-btn');
        for (var k = 0; k < btns.length; k++) {
          btns[k].disabled = false;
          btns[k].style.opacity = '';
          btns[k].style.pointerEvents = '';
        }
      }
    });
  }

  function _handleChatSSE(data) {
    if (VoiceState.currentScreen !== 'chat') return;

    var agentId = data.agent_id || data.id;
    if (parseInt(agentId, 10) !== parseInt(_targetAgentId, 10)) return;

    var newState = data.new_state || data.state;
    if (newState) {
      _chatAgentState = newState;
      _chatAgentStateLabel = (data.state_info && data.state_info.label) ? data.state_info.label : null;
      _updateTypingIndicator();
      _updateChatStatePill();
    }

    // Recover from false ended state: card_refresh with is_active clears ended
    if (data.is_active === true && _chatAgentEnded) {
      _chatAgentEnded = false;
      _updateEndedAgentUI();
    }

    // Check for ended agent
    if (data.agent_ended || (newState && newState.toLowerCase() === 'ended')) {
      _chatAgentEnded = true;
      delete _agentScrollState[_targetAgentId];
      _updateEndedAgentUI();
    }

    // SSE-primary: state changes update indicators only.
    // Turns are delivered directly via turn_created SSE events.
  }

  // --- Command sending ---

  function _sendCommand(text) {
    if (!text || !text.trim()) return;

    var status = document.getElementById('status-message');
    if (status) status.textContent = 'Sending...';

    VoiceAPI.sendCommand(text.trim(), _targetAgentId).then(function (data) {
      VoiceOutput.playCue('sent');
      if (data.voice) VoiceOutput.speakResponse(data.voice);
      if (status) status.textContent = 'Sent!';
      // Return to agent list after a moment
      setTimeout(function () { VoiceSidebar.refreshAgents(); VoiceLayout.showScreen('agents'); }, 1500);
    }).catch(function (err) {
      VoiceOutput.playCue('error');
      if (status) status.textContent = 'Error: ' + (err.error || 'Send failed');
    });
  }

  function _sendSelect(optionIndex) {
    var status = document.getElementById('status-message');
    if (status) status.textContent = 'Sending...';

    VoiceAPI.sendSelect(_targetAgentId, optionIndex).then(function (data) {
      VoiceOutput.playCue('sent');
      if (status) status.textContent = 'Sent!';
      setTimeout(function () { VoiceSidebar.refreshAgents(); VoiceLayout.showScreen('agents'); }, 1500);
    }).catch(function (err) {
      VoiceOutput.playCue('error');
      if (status) status.textContent = 'Error: ' + (err.error || 'Select failed');
    });
  }

  // --- SSE event handling ---

  function _handleGap(data) {
    // Server detected dropped events — do a full refresh to catch up
    VoiceSidebar.refreshAgents();
    if (VoiceState.currentScreen === 'chat' && _targetAgentId) {
      _fetchTranscriptForChat();
    }
  }

  function _handleTurnUpdated(data) {
    if (VoiceState.currentScreen !== 'chat') return;
    if (!data || !data.agent_id) return;
    if (parseInt(data.agent_id, 10) !== parseInt(_targetAgentId, 10)) return;

    if (data.update_type === 'timestamp_correction' && data.turn_id) {
      var bubble = document.querySelector('[data-turn-id="' + data.turn_id + '"]');
      if (bubble && data.timestamp) {
        bubble.setAttribute('data-timestamp', data.timestamp);
        VoiceChatRenderer.reorderBubble(bubble);
      }
    }
  }

  function _handleTurnCreated(data) {
    if (VoiceState.currentScreen !== 'chat') return;
    if (!data || !data.agent_id) return;
    if (parseInt(data.agent_id, 10) !== parseInt(_targetAgentId, 10)) return;
    if (data.is_internal) return;
    if (!data.text || !data.text.trim()) return;

    // For user turns from SSE: promote optimistic (pending) bubbles if they exist
    if (data.actor === 'user' && data.turn_id) {
      var realId = data.turn_id;
      // Look for a pending optimistic bubble to promote
      var promoted = false;
      for (var pi = 0; pi < _chatPendingUserSends.length; pi++) {
        var pending = _chatPendingUserSends[pi];
        if (pending.fakeTurnId) {
          var fakeBubble = document.querySelector('[data-turn-id="' + pending.fakeTurnId + '"]');
          if (fakeBubble) {
            // Promote: swap fake ID to real server ID
            fakeBubble.setAttribute('data-turn-id', realId);
            if (data.timestamp) fakeBubble.setAttribute('data-timestamp', data.timestamp);
            // Clear the send-failed timeout
            if (pending.failTimer) clearTimeout(pending.failTimer);
            _chatPendingUserSends.splice(pi, 1);
            promoted = true;
            break;
          }
        }
      }
      if (promoted) return;
      // Not promoted — check if already in DOM (e.g., from initial load)
      if (document.querySelector('[data-turn-id="' + realId + '"]')) return;
    }

    var isTerminalIntent = (data.intent === 'completion' || data.intent === 'end_of_task');

    // Build a turn-like object for direct rendering
    var turn = {
      id: data.turn_id || ('sse-' + Date.now()),
      actor: data.actor || 'agent',
      intent: data.intent || 'progress',
      text: data.text,
      timestamp: data.timestamp || new Date().toISOString(),
      tool_input: data.tool_input || null,
      question_text: data.text,
      question_options: null,
      task_id: data.task_id || null,
      task_instruction: data.task_instruction || null
    };

    // Extract question_options from tool_input for immediate rendering
    if (data.tool_input && data.tool_input.questions) {
      var questions = data.tool_input.questions;
      if (questions.length > 1) {
        // Multi-question: preserve full question objects array
        // (each element has .question, .header, .multiSelect, .options)
        turn.question_options = questions;
      } else if (questions.length > 0 && questions[0].options) {
        turn.question_options = questions[0].options;
      }
    }

    // Skip if already rendered in DOM — but always render terminal intents
    // (completion/end_of_task) so the agent's final response is visible
    // even if a PROGRESS turn with the same ID was already shown.
    if (document.querySelector('[data-turn-id="' + turn.id + '"]')) {
      if (!isTerminalIntent) return;
    }

    // Insert task separator if this turn starts a new task
    VoiceChatRenderer.maybeInsertTaskSeparator(turn);

    VoiceChatRenderer.renderChatBubble(turn, null, isTerminalIntent);
    _scrollChatToBottomIfNear();
  }

  function _handleAgentUpdate(data) {
    // Handle session_ended: remove from other agent states and re-render banners
    if (data._type === 'session_ended') {
      var endedId = data.agent_id || data.id;
      if (endedId && VoiceState.otherAgentStates[endedId]) {
        delete VoiceState.otherAgentStates[endedId];
        if (VoiceState.currentScreen === 'chat') VoiceChatRenderer.renderAttentionBanners();
      }
    }

    // Update attention banners for non-target agents on chat screen
    if (VoiceState.currentScreen === 'chat') {
      var agentId = data.agent_id || data.id;
      if (agentId && parseInt(agentId, 10) !== parseInt(_targetAgentId, 10)) {
        var newState = data.new_state || data.state;
        if (newState && VoiceState.otherAgentStates[agentId]) {
          VoiceState.otherAgentStates[agentId].state = newState.toLowerCase();
          if (data.task_instruction) VoiceState.otherAgentStates[agentId].task_instruction = data.task_instruction;
          if (data.hero_chars) VoiceState.otherAgentStates[agentId].hero_chars = data.hero_chars;
          if (data.hero_trail) VoiceState.otherAgentStates[agentId].hero_trail = data.hero_trail;
          VoiceChatRenderer.renderAttentionBanners();
        } else if (newState && !VoiceState.otherAgentStates[agentId]) {
          // New agent appeared via SSE — add it
          VoiceState.otherAgentStates[agentId] = {
            hero_chars: data.hero_chars || '',
            hero_trail: data.hero_trail || '',
            task_instruction: data.task_instruction || '',
            state: newState.toLowerCase(),
            project_name: data.project || ''
          };
          VoiceChatRenderer.renderAttentionBanners();
        }
      }
    }

    // Sync state to chat if this is the target agent
    if (VoiceState.currentScreen === 'chat' && _targetAgentId) {
      var updateAgentId = data.agent_id || data.id;
      if (parseInt(updateAgentId, 10) === parseInt(_targetAgentId, 10)) {
        var chatNewState = data.new_state || data.state;
        if (chatNewState) {
          var prevState = _chatAgentState;
          _chatAgentState = chatNewState;
          _chatAgentStateLabel = (data.state_info && data.state_info.label) ? data.state_info.label : null;
          _updateTypingIndicator();
          _updateChatStatePill();

          // If state left AWAITING_INPUT, update question options to "answered"
          if (prevState && prevState.toLowerCase() === 'awaiting_input'
              && chatNewState.toLowerCase() !== 'awaiting_input') {
            _markAllQuestionsAnswered();
          }
        }
        // Update task instruction in header if SSE provides it
        if (data.task_instruction) {
          var instrEl = document.getElementById('chat-task-instruction');
          if (instrEl) {
            var instr = data.task_instruction;
            instrEl.textContent = instr.length > 80 ? instr.substring(0, 80) + '...' : instr;
            instrEl.style.display = '';
          }
        }
      }
    }

    // Update chat screen if active
    _handleChatSSE(data);

    // Polling fallback: if data is a sessions list (no agent_id), and chat
    // is active, check if the target agent's state changed
    if (!data.agent_id && !data.id && data.agents && VoiceState.currentScreen === 'chat' && _targetAgentId) {
      for (var i = 0; i < data.agents.length; i++) {
        if (data.agents[i].agent_id === _targetAgentId) {
          // Recover from false ended state via polling (agent reappeared in active list)
          var justRecovered = false;
          if (_chatAgentEnded && data.agents[i].is_active !== false) {
            _chatAgentEnded = false;
            _updateEndedAgentUI();
            justRecovered = true;
          }
          var polledState = data.agents[i].state;
          if (justRecovered || (polledState && polledState.toLowerCase() !== (_chatAgentState || '').toLowerCase())) {
            if (polledState) {
              _chatAgentState = polledState;
              _chatAgentStateLabel = data.agents[i].state_label || null;
              _updateTypingIndicator();
              _updateChatStatePill();
            }
            _fetchTranscriptForChat();
          }
          break;
        }
      }
    }

    // Re-fetch agent list on any update (but defer if confirm dialog is open)
    if (typeof ConfirmDialog !== 'undefined' && ConfirmDialog.isOpen()) {
      window._sseReloadDeferred = function () { VoiceSidebar.refreshAgents(); };
    } else {
      VoiceSidebar.refreshAgents();
    }

    // Play cue if an agent transitions to awaiting_input
    if (data && data.new_state === 'awaiting_input') {
      VoiceOutput.playCue('needs-input');
    }
  }

  // _refreshAgents moved to VoiceSidebar module (Phase 6)

  // --- Connection indicator (task 2.18) ---

  var _previousConnectionState = 'disconnected';
  var _connectionLostTimer = null;
  var _connectionLostShown = false;

  function _updateConnectionIndicator() {
    var el = document.getElementById('connection-status');
    if (!el) return;
    var state = VoiceAPI.getConnectionState();
    el.className = 'connection-dot ' + state;
    el.title = state;

    if (state === 'connected' && _previousConnectionState !== 'connected') {
      _catchUpAfterReconnect();
      // Cancel pending "connection lost" — hiccup recovered before timeout
      if (_connectionLostTimer) {
        clearTimeout(_connectionLostTimer);
        _connectionLostTimer = null;
      }
      // Only show "Reconnected" if we actually showed "Connection lost"
      if (_connectionLostShown && VoiceState.currentScreen === 'chat') {
        _showChatSystemMessage('Reconnected');
      }
      _connectionLostShown = false;
    }
    if (state === 'reconnecting' && _previousConnectionState === 'connected') {
      // Debounce: wait 2s before showing. If recovered within window, suppress.
      if (!_connectionLostTimer) {
        _connectionLostTimer = setTimeout(function () {
          _connectionLostTimer = null;
          if (VoiceAPI.getConnectionState() !== 'connected') {
            _connectionLostShown = true;
            if (VoiceState.currentScreen === 'chat') {
              _showChatSystemMessage('Connection lost \u2014 reconnecting\u2026');
            }
          }
        }, 2000);
      }
    }
    _previousConnectionState = state;
  }

  function _catchUpAfterReconnect() {
    // Always refresh agent list
    VoiceSidebar.refreshAgents();

    // If chat screen is active, re-fetch transcript to catch missed events
    if (VoiceState.currentScreen === 'chat' && _targetAgentId) {
      _fetchTranscriptForChat();

      // Deferred stops create turns 0.5-5s after the initial stop hook.
      // If we reconnected during that gap the first fetch finds nothing.
      // A second fetch 3s later catches those late-arriving turns.
      var deferredAgentId = _targetAgentId;
      setTimeout(function () {
        if (VoiceState.currentScreen === 'chat' && _targetAgentId === deferredAgentId) {
          _fetchTranscriptForChat();
        }
      }, 3000);
    }
  }

  /**
   * Shared transcript fetch + render logic used by reconnect catch-up,
   * periodic sync, and anywhere else that needs to pull new turns.
   *
   * Debounced: multiple calls within 500ms collapse into one fetch.
   * This prevents SSE event bursts and the sync timer from cancelling
   * each other's responses (Finding 5).
   */
  var _fetchDebounceTimer = null;
  var _fetchInFlight = false;

  function _fetchTranscriptForChat() {
    if (!_targetAgentId) return;
    // If a fetch is already in flight, just schedule another after it finishes
    if (_fetchInFlight) {
      _fetchDebounceTimer = _fetchDebounceTimer || setTimeout(function () {
        _fetchDebounceTimer = null;
        _fetchTranscriptForChat();
      }, 500);
      return;
    }
    // Clear any pending debounce since we're about to fetch now
    if (_fetchDebounceTimer) {
      clearTimeout(_fetchDebounceTimer);
      _fetchDebounceTimer = null;
    }
    _fetchInFlight = true;
    var agentId = _targetAgentId;
    VoiceAPI.getTranscript(agentId).then(function (resp) {
      _fetchInFlight = false;
      // Discard if user navigated to a different agent while fetching
      if (agentId !== _targetAgentId) return;
      var turns = resp.turns || [];
      var messagesContainer = document.getElementById('chat-messages');

      for (var ti = 0; ti < turns.length; ti++) {
        var t = turns[ti];

        // Handle synthetic task_boundary entries from backend
        if (t.type === 'task_boundary') {
          if (messagesContainer && !messagesContainer.querySelector('.chat-task-separator[data-task-id="' + t.task_id + '"]')) {
            messagesContainer.appendChild(VoiceChatRenderer.createTaskSeparatorEl(t));
          }
          VoiceState.chatLastTaskId = t.task_id;
          continue;
        }

        // Track max turn ID for gap recovery
        var numId = typeof t.id === 'number' ? t.id : parseInt(t.id, 10);
        if (!isNaN(numId) && numId > VoiceState.lastSeenTurnId) VoiceState.lastSeenTurnId = numId;

        // Check if this turn is already in the DOM
        var existingBubble = messagesContainer
          ? messagesContainer.querySelector('[data-turn-id="' + t.id + '"]')
          : null;

        if (existingBubble) {
          // Already rendered — update timestamp if changed, reorder if needed
          var currentTs = existingBubble.getAttribute('data-timestamp');
          if (t.timestamp && currentTs !== t.timestamp) {
            existingBubble.setAttribute('data-timestamp', t.timestamp);
            VoiceChatRenderer.reorderBubble(existingBubble);
          }
          // Still track task ID for boundary detection
          if (t.task_id) VoiceState.chatLastTaskId = t.task_id;
        } else {
          // Insert task separator if this turn starts a new task
          VoiceChatRenderer.maybeInsertTaskSeparator(t);
          // Not in DOM — render at correct chronological position
          var prev = ti > 0 ? turns[ti - 1] : null;
          var forceTerminal = (t.intent === 'completion' || t.intent === 'end_of_task');
          VoiceChatRenderer.renderChatBubble(t, prev, forceTerminal);
        }
      }

      if (resp.agent_state) {
        _chatAgentState = resp.agent_state;
        _updateTypingIndicator();
        _updateChatStatePill();
      }
      if (resp.agent_ended !== undefined) {
        var wasEnded = _chatAgentEnded;
        _chatAgentEnded = !!resp.agent_ended;
        if (_chatAgentEnded !== wasEnded) _updateEndedAgentUI();
      }
      // Only auto-scroll if user is near the bottom — don't yank them
      // away from reading older messages (mobile reading experience)
      _scrollChatToBottomIfNear();
    }).catch(function () {
      _fetchInFlight = false;
    });
  }

  /**
   * Remove an optimistic (fake) user bubble when send fails (Finding 10).
   * Cleans up both the DOM element and the pending send entry.
   */
  function _removeOptimisticBubble(pendingEntry) {
    // Remove from pending sends list
    var idx = _chatPendingUserSends.indexOf(pendingEntry);
    if (idx !== -1) _chatPendingUserSends.splice(idx, 1);
    // Remove the fake bubble from DOM
    var messagesEl = document.getElementById('chat-messages');
    if (messagesEl && pendingEntry.fakeTurnId) {
      var bubble = messagesEl.querySelector('[data-turn-id="' + pendingEntry.fakeTurnId + '"]');
      if (bubble) bubble.remove();
    }
  }

  // --- Initialization ---

  function init() {
    // Wire callbacks before loading settings
    VoiceSettings.setRefreshAgentsHandler(VoiceSidebar.refreshAgents);
    VoiceLayout.setScreenChangeHandler(function (name) {
      if (name !== 'chat') { _stopChatSyncTimer(); _cancelResponseCatchUp(); document.title = 'Claude Chat'; }
      _updateConnectionIndicator();
    });
    VoiceLayout.setHighlightHandler(VoiceSidebar.highlightSelectedAgent);
    VoiceLayout.setMenuHandler(function (action) {
      if (action === 'new-chat') {
        VoiceSidebar.openProjectPicker();
      } else if (action === 'voice') {
        _triggerVoiceFromMenu();
      } else if (action === 'close') {
        window.location.href = '/';
      }
    });
    VoiceChatRenderer.setOptionSelectHandler(_sendChatSelect);
    VoiceChatRenderer.setNavigateToBannerHandler(_navigateToAgentFromBanner);
    VoiceSidebar.setAgentSelectedHandler(function (id) { _showChatScreen(id); });
    VoiceSettings.loadSettings();

    // Initialize layout mode
    VoiceLayout.initLayoutMode();

    // Listen for resize and orientation to switch layout modes
    var _resizeTimer = null;
    window.addEventListener('resize', function () {
      clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(VoiceLayout.detectLayoutMode, 100);
    });
    window.addEventListener('orientationchange', function () {
      clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(VoiceLayout.detectLayoutMode, 100);
    });

    // iOS Safari: the bottom toolbar overlaps content.  `100dvh` in CSS
    // handles the static case, but when the keyboard appears/disappears
    // or Safari toggles its toolbar, we need to dynamically resize the
    // app layout so the chat input stays above the toolbar.
    if (window.visualViewport) {
      var _vpTimer = null;
      window.visualViewport.addEventListener('resize', function () {
        clearTimeout(_vpTimer);
        _vpTimer = setTimeout(function () {
          var layout = document.getElementById('app-layout');
          if (!layout) return;
          // visualViewport.height is the *actually visible* area,
          // excluding Safari toolbar and on-screen keyboard.
          var vpH = window.visualViewport.height;
          layout.style.height = vpH + 'px';
        }, 50);
      });
    }

    // Close kebab menus on click/touch outside
    function _handleCloseKebabs(e) {
      if (!e.target.closest('.agent-kebab-btn') && !e.target.closest('.agent-kebab-menu')
          && !e.target.closest('.project-kebab-btn') && !e.target.closest('.project-kebab-menu')) {
        VoiceSidebar.closeAllKebabMenus();
      }
    }
    document.addEventListener('click', _handleCloseKebabs);
    document.addEventListener('touchstart', _handleCloseKebabs, { passive: true });

    // Detect agent_id URL param (from dashboard "Chat" link)
    var urlParams = new URLSearchParams(window.location.search);
    var paramAgentId = urlParams.get('agent_id');

    // Trusted network (localhost, LAN, Tailscale): skip setup, use current origin
    if (_isTrustedNetwork && (!VoiceState.settings.serverUrl || !VoiceState.settings.token)) {
      VoiceState.settings.serverUrl = window.location.origin;
      VoiceState.settings.token = _isLocalhost ? 'localhost' : 'lan';
      VoiceSettings.saveSettings();
    }

    // Check if we have credentials
    if (!VoiceState.settings.serverUrl || !VoiceState.settings.token) {
      VoiceLayout.showScreen('setup');
      return;
    }

    // Initialize API
    VoiceAPI.init(VoiceState.settings.serverUrl, VoiceState.settings.token);

    // Wire up speech input callbacks
    VoiceInput.onResult(function (text) {
      if (VoiceState.currentScreen === 'chat') {
        _sendChatCommand(text);
      } else {
        _sendCommand(text);
      }
    });

    VoiceInput.onPartial(function (text) {
      var el = document.getElementById('live-transcript');
      if (el) el.textContent = text;
    });

    VoiceInput.onStateChange(function (listening) {
      var chatMic = document.getElementById('chat-mic-btn');
      if (chatMic) chatMic.classList.toggle('active', listening);
    });

    // Wire up SSE
    VoiceAPI.onConnectionChange(_updateConnectionIndicator);
    VoiceAPI.onAgentUpdate(_handleAgentUpdate);
    VoiceAPI.onTurnCreated(_handleTurnCreated);
    VoiceAPI.onTurnUpdated(_handleTurnUpdated);
    VoiceAPI.onGap(_handleGap);
    VoiceAPI.connectSSE();

    // iOS recovery: when the tab returns from background, SSE is dead and
    // timers were suspended.  Force an immediate catch-up.
    document.addEventListener('visibilitychange', function () {
      if (document.hidden) return;
      // Reconnect SSE if it died in the background
      if (VoiceAPI.getConnectionState() !== 'connected') {
        VoiceAPI.connectSSE();
      }
      // Immediately refresh state and transcript
      VoiceSidebar.refreshAgents();
      if (VoiceState.currentScreen === 'chat' && _targetAgentId) {
        _fetchTranscriptForChat();
      }
    });

    // Play ready cue
    VoiceOutput.playCue('ready');

    // If agent_id param present, go directly to chat screen
    if (paramAgentId) {
      _showChatScreen(parseInt(paramAgentId, 10));
      return;
    }

    // Load agents and show list
    VoiceSidebar.refreshAgents();
    VoiceLayout.showScreen('agents');
  }

  // --- Event binding (called once DOM is ready) ---

  function bindEvents() {
    // Setup form
    var setupForm = document.getElementById('setup-form');
    if (setupForm) {
      setupForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var url = document.getElementById('setup-url').value.trim();
        var token = document.getElementById('setup-token').value.trim();
        if (url && token) {
          VoiceSettings.setSetting('serverUrl', url);
          VoiceSettings.setSetting('token', token);
          init();
        }
      });
    }

    // Title link — navigate back to agent list (or show sidebar in split mode)
    var titleLink = document.getElementById('app-title-link');
    if (titleLink) {
      titleLink.addEventListener('click', function (e) {
        e.preventDefault();
        if (VoiceState.currentScreen === 'chat' && _targetAgentId) {
          _saveScrollState(_targetAgentId);
        }
        VoiceSidebar.refreshAgents();
        VoiceLayout.showScreen('agents');
      });
    }

    // Text input fallback (task 2.10)
    var textForm = document.getElementById('text-form');
    if (textForm) {
      textForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var input = document.getElementById('text-input');
        if (input && input.value.trim()) {
          _sendCommand(input.value);
          input.value = '';
        }
      });
    }

    // Free-text question form
    var freeForm = document.getElementById('question-free-form');
    if (freeForm) {
      freeForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var input = document.getElementById('question-free-input');
        if (input && input.value.trim()) {
          _sendCommand(input.value);
          input.value = '';
        }
      });
    }

    // --- FAB (split mode) ---
    var fabBtn = document.getElementById('fab-btn');
    if (fabBtn) {
      fabBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        VoiceLayout.toggleFab();
      });
    }
    var fabBackdrop = document.getElementById('fab-backdrop');
    if (fabBackdrop) {
      fabBackdrop.addEventListener('click', function () { VoiceLayout.closeFab(); });
    }
    // FAB menu items
    var fabItems = document.querySelectorAll('.fab-menu-item');
    for (var fi = 0; fi < fabItems.length; fi++) {
      fabItems[fi].addEventListener('click', function (e) {
        e.stopPropagation();
        VoiceLayout.handleMenuAction(this.getAttribute('data-action'));
      });
    }

    // --- Hamburger (stacked mode) ---
    var hamburgerBtn = document.getElementById('hamburger-btn');
    if (hamburgerBtn) {
      hamburgerBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (VoiceState.hamburgerOpen) { VoiceLayout.closeHamburger(); } else { VoiceLayout.openHamburger(); }
      });
    }
    var hamburgerBackdrop = document.getElementById('hamburger-backdrop');
    if (hamburgerBackdrop) {
      hamburgerBackdrop.addEventListener('click', function () { VoiceLayout.closeHamburger(); });
    }
    var hamburgerItems = document.querySelectorAll('.hamburger-item');
    for (var hi = 0; hi < hamburgerItems.length; hi++) {
      hamburgerItems[hi].addEventListener('click', function () {
        VoiceLayout.handleMenuAction(this.getAttribute('data-action'));
      });
    }

    // --- Project Picker ---
    var pickerClose = document.getElementById('project-picker-close');
    if (pickerClose) {
      pickerClose.addEventListener('click', function () { VoiceSidebar.closeProjectPicker(); });
    }
    var pickerBackdrop = document.getElementById('project-picker-backdrop');
    if (pickerBackdrop) {
      pickerBackdrop.addEventListener('click', function () { VoiceSidebar.closeProjectPicker(); });
    }
    var pickerSearch = document.getElementById('project-picker-search');
    if (pickerSearch) {
      pickerSearch.addEventListener('input', function () {
        VoiceSidebar.filterProjectList(this.value.trim());
      });
    }

    // --- Escape key handler ---
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        if (VoiceState.projectPickerOpen) { VoiceSidebar.closeProjectPicker(); e.preventDefault(); return; }
        if (VoiceState.fabOpen) { VoiceLayout.closeFab(); e.preventDefault(); return; }
        if (VoiceState.hamburgerOpen) { VoiceLayout.closeHamburger(); e.preventDefault(); return; }
      }
    });

    // Close FAB on outside click
    document.addEventListener('click', function (e) {
      if (VoiceState.fabOpen && !e.target.closest('.fab-container')) {
        VoiceLayout.closeFab();
      }
    });

    // Settings close button
    var settingsCloseBtn = document.getElementById('settings-close-btn');
    if (settingsCloseBtn) {
      settingsCloseBtn.addEventListener('click', function () {
        VoiceSettings.closeSettings();
      });
    }

    // Settings overlay click — close
    var settingsOverlay = document.getElementById('settings-overlay');
    if (settingsOverlay) {
      settingsOverlay.addEventListener('click', function () {
        VoiceSettings.closeSettings();
      });
    }

    // Settings form — save and close
    var settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
      settingsForm.addEventListener('submit', function (e) {
        e.preventDefault();
        VoiceSettings.applySettingsForm();
        VoiceSettings.closeSettings();
      });
    }

    // Chat input form + textarea auto-resize
    var chatForm = document.getElementById('chat-input-form');
    var chatInput = document.getElementById('chat-text-input');
    if (chatForm) {
      chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var hasText = chatInput && chatInput.value.trim();
        var hasFile = !!_pendingAttachment;
        if (hasText || hasFile) {
          _sendChatWithAttachment(chatInput ? chatInput.value : '');
          if (chatInput) chatInput.style.height = 'auto';
        }
      });
    }
    if (chatInput) {
      // Auto-resize textarea as content grows
      chatInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 240) + 'px';
      });
      // iOS Safari: when keyboard opens, scroll the input into view
      // after a short delay (let Safari finish its viewport resize).
      chatInput.addEventListener('focus', function () {
        var self = this;
        setTimeout(function () {
          self.scrollIntoView({ block: 'end', behavior: 'smooth' });
        }, 300);
      });
    }

    // Chat mic button
    var chatMicBtn = document.getElementById('chat-mic-btn');
    if (chatMicBtn) {
      chatMicBtn.addEventListener('click', function () {
        VoiceOutput.initAudio();
        if (VoiceInput.isListening()) {
          _stopListening();
        } else {
          _startListening();
        }
      });
    }

    // Attach file button + hidden file input
    var chatAttachBtn = document.getElementById('chat-attach-btn');
    var chatFileInput = document.getElementById('chat-file-input');
    if (chatAttachBtn && chatFileInput) {
      chatAttachBtn.addEventListener('click', function () {
        chatFileInput.click();
      });
      chatFileInput.addEventListener('change', function () {
        if (chatFileInput.files && chatFileInput.files[0]) {
          VoiceFileUpload.handleFileDrop(chatFileInput.files[0]);
          chatFileInput.value = '';
        }
      });
    }

    // Attachment remove button
    var attachRemoveBtn = document.getElementById('attachment-remove');
    if (attachRemoveBtn) {
      attachRemoveBtn.addEventListener('click', function () {
        VoiceFileUpload.clearPendingAttachment();
      });
    }

    // Drag-and-drop file handling on chat screen
    var chatScreen = document.getElementById('screen-chat');
    var dropZone = document.getElementById('chat-drop-zone');
    if (chatScreen && dropZone) {
      var _dragCounter = 0;
      chatScreen.addEventListener('dragenter', function (e) {
        e.preventDefault();
        _dragCounter++;
        dropZone.style.display = 'flex';
      });
      chatScreen.addEventListener('dragover', function (e) {
        e.preventDefault();
      });
      chatScreen.addEventListener('dragleave', function (e) {
        e.preventDefault();
        _dragCounter--;
        if (_dragCounter <= 0) {
          _dragCounter = 0;
          dropZone.style.display = 'none';
        }
      });
      chatScreen.addEventListener('drop', function (e) {
        e.preventDefault();
        _dragCounter = 0;
        dropZone.style.display = 'none';
        if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
          VoiceFileUpload.handleFileDrop(e.dataTransfer.files[0]);
        }
      });
    }

    // Clipboard paste handler for images
    if (chatInput) {
      chatInput.addEventListener('paste', function (e) {
        var items = e.clipboardData && e.clipboardData.items;
        if (!items) return;
        for (var pi = 0; pi < items.length; pi++) {
          if (items[pi].type && items[pi].type.indexOf('image/') === 0) {
            e.preventDefault();
            var file = items[pi].getAsFile();
            if (file) {
              // Give pasted images a meaningful name
              var ext = file.type.split('/')[1] || 'png';
              if (ext === 'jpeg') ext = 'jpg';
              var pastedFile = new File([file], 'pasted-image.' + ext, { type: file.type });
              VoiceFileUpload.handleFileDrop(pastedFile);
            }
            break;
          }
        }
      });
    }

    // Scroll-up pagination for chat history
    var chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
      chatMessages.addEventListener('scroll', function () {
        if (chatMessages.scrollTop < 50) {
          _loadOlderMessages();
        }
        // Auto-dismiss new messages pill when user scrolls to the first new message
        if (_newMessagesPillVisible && _newMessagesFirstTurnId) {
          var bubble = document.querySelector('[data-turn-id="' + _newMessagesFirstTurnId + '"]');
          if (bubble) {
            var containerRect = chatMessages.getBoundingClientRect();
            var bubbleRect = bubble.getBoundingClientRect();
            if (bubbleRect.top < containerRect.bottom) {
              _dismissNewMessagesPill();
            }
          }
        }
      });
    }

    // Chat header focus link — click to attach (tmux) or focus (iTerm)
    var chatFocusLink = document.getElementById('chat-focus-link');
    if (chatFocusLink) {
      chatFocusLink.addEventListener('click', function () {
        if (_targetAgentId) {
          var tmuxSession = this.getAttribute('data-tmux-session');
          if (tmuxSession) {
            VoiceAPI.attachAgent(_targetAgentId).catch(function (err) {
              console.warn('Attach failed:', err);
            });
          } else {
            VoiceAPI.focusAgent(_targetAgentId).catch(function (err) {
              console.warn('Focus failed:', err);
            });
          }
        }
      });
    }

    // Chat back button — pop nav stack or go to agent list
    var chatBackBtn = document.querySelector('.chat-back-btn');
    if (chatBackBtn) {
      chatBackBtn.addEventListener('click', function () {
        if (_navStack.length > 0) {
          var prevId = _navStack.pop();
          _showChatScreen(prevId);
        } else {
          _saveScrollState(_targetAgentId);
          VoiceState.otherAgentStates = {};
          VoiceSidebar.refreshAgents();
          VoiceLayout.showScreen('agents');
        }
      });
    }

    // Back buttons (listening, question screens)
    var backBtns = document.querySelectorAll('.back-btn');
    for (var i = 0; i < backBtns.length; i++) {
      backBtns[i].addEventListener('click', function () {
        if (VoiceState.layoutMode === 'split') {
          // In split mode, back from listening/question goes to chat or agents
          if (_targetAgentId) {
            _showChatScreen(_targetAgentId);
          } else {
            VoiceLayout.showScreen('agents');
          }
        } else {
          VoiceLayout.showScreen('agents');
        }
      });
    }

    // Theme chip selector — instant apply
    var themeSelector = document.getElementById('theme-selector');
    if (themeSelector) {
      themeSelector.addEventListener('click', function (e) {
        var chip = e.target.closest('.theme-chip');
        if (!chip) return;
        var theme = chip.getAttribute('data-theme');
        if (!theme) return;
        // Update active state
        var chips = themeSelector.querySelectorAll('.theme-chip');
        for (var tc = 0; tc < chips.length; tc++) {
          chips[tc].classList.toggle('active', chips[tc] === chip);
        }
        // Apply immediately
        VoiceSettings.setSetting('theme', theme);
        VoiceSettings.applyTheme();
      });
    }

    // Font size slider display + live preview
    var fontSlider = document.getElementById('setting-fontsize');
    if (fontSlider) {
      fontSlider.addEventListener('input', function () {
        var display = document.getElementById('fontsize-value');
        if (display) display.textContent = this.value + 'px';
      });
    }

    // Silence timeout slider display
    var slider = document.getElementById('setting-silence');
    if (slider) {
      slider.addEventListener('input', function () {
        var display = document.getElementById('silence-value');
        if (display) display.textContent = this.value + 'ms';
      });
    }
  }

  // _populateSettingsForm and _applySettingsForm moved to VoiceSettings

  return {
    init: init,
    bindEvents: bindEvents,
    _sendCommand: _sendCommand,
    _showChatScreen: _showChatScreen
  };
})();
