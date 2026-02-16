/* Voice Bridge main app controller */
window.VoiceApp = (function () {
  'use strict';

  // Settings defaults now in VoiceState.DEFAULTS

  // _settings now managed by VoiceState.settings via VoiceSettings module
  var _targetAgentId = null;
  var _isLocalhost = (location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.hostname === '::1');
  var _isTrustedNetwork = _isLocalhost
    || /^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|100\.)/.test(location.hostname)
    || /\.ts\.net$/.test(location.hostname);
  var _navStack = [];           // Stack of agent IDs for back navigation
  var _pendingAttachment = null; // File object pending upload
  var _pendingBlobUrl = null;    // Blob URL for image preview (revoke on clear)
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
    VoiceState.chatPendingUserSends = [];
    VoiceState.chatHasMore = false;
    VoiceState.chatLoadingMore = false;
    VoiceState.chatOldestTurnId = null;
    VoiceState.chatAgentEnded = false;
    VoiceState.chatLastTaskId = null;
    VoiceState.fetchInFlight = false; // Reset in-flight guard for new agent
    if (VoiceState.fetchDebounceTimer) { clearTimeout(VoiceState.fetchDebounceTimer); VoiceState.fetchDebounceTimer = null; }
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

      VoiceState.chatAgentState = data.agent_state;
      VoiceState.chatAgentStateLabel = null; // Reset; will be set by SSE with richer label if available
      VoiceState.chatHasMore = data.has_more || false;
      VoiceState.chatAgentEnded = data.agent_ended || false;
      var focusLink = document.getElementById('chat-focus-link');
      if (focusLink) {
        focusLink.setAttribute('data-tmux-session', data.tmux_session || '');
        focusLink.title = data.tmux_session ? 'Attach to tmux session' : 'Focus iTerm window';
      }
      VoiceChatRenderer.renderTranscriptTurns(data);
      // Restore scroll position if returning to a previously-viewed agent
      var saved = VoiceState.agentScrollState[agentId];
      if (saved) {
        delete VoiceState.agentScrollState[agentId]; // one-shot restore
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
    if (VoiceState.chatLoadingMore || !VoiceState.chatHasMore || !VoiceState.chatOldestTurnId) return;
    VoiceState.chatLoadingMore = true;
    _updateLoadMoreIndicator();

    var messagesEl = document.getElementById('chat-messages');
    var prevScrollHeight = messagesEl ? messagesEl.scrollHeight : 0;

    VoiceAPI.getTranscript(_targetAgentId, { before: VoiceState.chatOldestTurnId, limit: 50 }).then(function (data) {
      VoiceState.chatHasMore = data.has_more || false;
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
      VoiceState.chatLoadingMore = false;
      _updateLoadMoreIndicator();
    }).catch(function () {
      VoiceState.chatLoadingMore = false;
      _updateLoadMoreIndicator();
    });
  }

  function _updateLoadMoreIndicator() {
    var indicator = document.getElementById('chat-load-more');
    if (!indicator) return;
    if (VoiceState.chatLoadingMore) {
      indicator.className = 'chat-load-more loading';
      indicator.textContent = 'Loading...';
      indicator.style.display = 'block';
    } else if (!VoiceState.chatHasMore && VoiceState.chatOldestTurnId) {
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
    if (VoiceState.chatAgentEnded) {
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
    VoiceState.agentScrollState[agentId] = {
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
    var state = (VoiceState.chatAgentState || '').toLowerCase();
    var isProcessing = state === 'processing' || state === 'commanded';
    typingEl.style.display = isProcessing ? 'block' : 'none';
    if (isProcessing) _scrollChatToBottomIfNear();
  }

  function _updateChatStatePill() {
    var pill = document.getElementById('chat-state-pill');
    if (!pill) return;
    var state = (VoiceState.chatAgentState || '').toLowerCase();
    if (!state) { pill.style.display = 'none'; return; }
    pill.style.display = '';
    var label = VoiceState.chatAgentStateLabel || _getStateLabel(state);
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
    var state = (VoiceState.chatAgentState || '').toLowerCase();
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
    VoiceState.chatAgentState = 'processing';
    VoiceState.chatAgentStateLabel = null;
    _updateTypingIndicator();
    _updateChatStatePill();

    VoiceAPI.uploadFile(_targetAgentId, file, trimText || null, function (pct) {
      VoiceFileUpload.showUploadProgress(pct);
    }).then(function (data) {
      VoiceFileUpload.hideUploadProgress();
    }).catch(function (err) {
      VoiceFileUpload.hideUploadProgress();
      // Remove the ghost optimistic bubble on failure (Finding 10)
      VoiceSSEHandler.removeOptimisticBubble(pendingEntry);
      var errMsg = (err && err.error) || 'Upload failed';
      VoiceFileUpload.showUploadError(errMsg);
      VoiceState.chatAgentState = 'idle';
      VoiceState.chatAgentStateLabel = null;
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
      var idx = VoiceState.chatPendingUserSends.indexOf(pendingEntry);
      if (idx !== -1) VoiceState.chatPendingUserSends.splice(idx, 1);
    }, VoiceState.PENDING_SEND_TTL_MS);

    VoiceState.chatPendingUserSends.push(pendingEntry);
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
    VoiceState.chatAgentState = 'processing';
    VoiceState.chatAgentStateLabel = null;
    _updateTypingIndicator();
    _updateChatStatePill();

    VoiceAPI.sendCommand(text.trim(), _targetAgentId).then(function () {
      // Command sent — SSE delivers the response directly
    }).catch(function (err) {
      // Remove the ghost optimistic bubble on failure (Finding 10)
      VoiceSSEHandler.removeOptimisticBubble(pendingEntry);
      // Show error as system message
      var errBubble = document.createElement('div');
      errBubble.className = 'chat-bubble agent';
      errBubble.innerHTML = '<div class="bubble-intent">Error</div><div class="bubble-text">' + VoiceChatRenderer.esc(err.error || 'Send failed') + '</div>';
      var msgEl = document.getElementById('chat-messages');
      if (msgEl) msgEl.appendChild(errBubble);
      VoiceState.chatAgentState = 'idle';
      VoiceState.chatAgentStateLabel = null;
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
    VoiceState.chatAgentState = 'processing';
    VoiceState.chatAgentStateLabel = null;
    _updateTypingIndicator();
    _updateChatStatePill();

    VoiceAPI.sendSelect(_targetAgentId, optionIndex, label).then(function () {
      // Select sent — SSE delivers the response directly
    }).catch(function (err) {
      VoiceSSEHandler.removeOptimisticBubble(pendingEntry);
      var errBubble = document.createElement('div');
      errBubble.className = 'chat-bubble agent';
      errBubble.innerHTML = '<div class="bubble-intent">Error</div><div class="bubble-text">' + VoiceChatRenderer.esc(err.error || 'Select failed') + '</div>';
      var msgEl = document.getElementById('chat-messages');
      if (msgEl) msgEl.appendChild(errBubble);
      VoiceState.chatAgentState = 'idle';
      VoiceState.chatAgentStateLabel = null;
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

  // --- Initialization ---

  function init() {
    // Wire callbacks before loading settings
    VoiceSettings.setRefreshAgentsHandler(VoiceSidebar.refreshAgents);
    VoiceLayout.setScreenChangeHandler(function (name) {
      if (name !== 'chat') { document.title = 'Claude Chat'; }
      VoiceSSEHandler.updateConnectionIndicator();
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
    VoiceSSEHandler.setUpdateTypingHandler(_updateTypingIndicator);
    VoiceSSEHandler.setUpdateStatePillHandler(_updateChatStatePill);
    VoiceSSEHandler.setUpdateEndedUIHandler(_updateEndedAgentUI);
    VoiceSSEHandler.setScrollChatHandler(function (nearOnly) {
      if (nearOnly) { _scrollChatToBottomIfNear(); } else { _scrollChatToBottom(); }
    });
    VoiceSSEHandler.setMarkQuestionsHandler(_markAllQuestionsAnswered);
    VoiceSSEHandler.setShowSystemMessageHandler(_showChatSystemMessage);
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
    VoiceAPI.onConnectionChange(VoiceSSEHandler.updateConnectionIndicator);
    VoiceAPI.onAgentUpdate(VoiceSSEHandler.handleAgentUpdate);
    VoiceAPI.onTurnCreated(VoiceSSEHandler.handleTurnCreated);
    VoiceAPI.onTurnUpdated(VoiceSSEHandler.handleTurnUpdated);
    VoiceAPI.onGap(VoiceSSEHandler.handleGap);
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
        VoiceSSEHandler.fetchTranscriptForChat();
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
