/* VoiceChatController — chat screen lifecycle, scroll management, state display,
 * chat sending, and legacy listening/question screen send helpers.
 *
 * Extracted from VoiceApp (Phase 8 modularisation).
 *
 * Dependencies:
 *   VoiceState        — all shared mutable state
 *   VoiceChatRenderer — renderTranscriptTurns, prependTranscriptTurns,
 *                       renderChatBubble, renderAttentionBanners, esc
 *   VoiceSidebar      — refreshAgents, highlightSelectedAgent
 *   VoiceSSEHandler   — fetchTranscriptForChat, removeOptimisticBubble
 *   VoiceAPI          — getTranscript, getSessions, sendCommand, sendSelect,
 *                       uploadFile
 *   VoiceLayout       — showScreen
 *   VoiceFileUpload   — clearPendingAttachment, showUploadProgress,
 *                       hideUploadProgress, showUploadError, isImageFile
 *   VoiceOutput       — playCue, speakResponse, initAudio
 *   VoiceInput         — (used by VoiceApp for voice mode)
 */
window.VoiceChatController = (function () {
  'use strict';

  // --- State label map (also in VoiceState.STATE_LABELS) ---
  var _STATE_LABELS = {
    idle: 'Idle',
    commanded: 'Command received',
    processing: 'Processing\u2026',
    awaiting_input: 'Input needed',
    complete: 'Command complete',
    timed_out: 'Timed out'
  };

  // =====================================================================
  //  Chat screen lifecycle
  // =====================================================================

  function showChatScreen(agentId) {
    // Save scroll state for the agent we're leaving
    var previousAgentId = VoiceState.targetAgentId;
    if (previousAgentId && previousAgentId !== agentId) {
      saveScrollState(previousAgentId);
    }
    dismissNewMessagesPill();
    VoiceState.targetAgentId = agentId;
    var focusLink = document.getElementById('chat-focus-link');
    if (focusLink) focusLink.setAttribute('data-agent-id', agentId);
    VoiceState.lastSeenTurnId = 0;
    VoiceState.chatPendingUserSends = [];
    VoiceState.chatHasMore = false;
    VoiceState.chatLoadingMore = false;
    VoiceState.chatOldestTurnId = null;
    VoiceState.chatAgentEnded = false;
    VoiceState.chatLastCommandId = null;
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
            command_instruction: a.command_instruction || '',
            state: (a.state || '').toLowerCase(),
            project_name: a.project || ''
          };
        }
      }
      VoiceChatRenderer.renderAttentionBanners();
    }).catch(function () { /* ignore */ });

    var initAgentId = agentId;
    VoiceAPI.getTranscript(agentId).then(function (data) {
      if (initAgentId !== VoiceState.targetAgentId) return; // Stale response -- user navigated away
      var nameEl = document.getElementById('chat-agent-name');
      var projEl = document.getElementById('chat-project-name');
      var heroEl = document.getElementById('chat-hero');
      if (heroEl) {
        if (data.persona_name) {
          heroEl.innerHTML = '<span class="agent-hero">' + VoiceChatRenderer.esc(data.persona_name) + '</span>';
        } else {
          var hc = data.hero_chars || '';
          var ht = data.hero_trail || '';
          heroEl.innerHTML = '<span class="agent-hero">' + VoiceChatRenderer.esc(hc) + '</span><span class="agent-hero-trail">' + VoiceChatRenderer.esc(ht) + '</span>';
        }
      }
      // Show/hide persona badge
      var personaBadge = document.getElementById('chat-persona-badge');
      if (personaBadge) {
        if (data.persona_name) {
          personaBadge.textContent = data.persona_name;
          personaBadge.style.display = '';
        } else {
          personaBadge.style.display = 'none';
        }
      }
      if (nameEl) nameEl.textContent = data.project || 'Agent';
      if (projEl) projEl.textContent = '';

      // Update browser tab title with agent identity
      var titleHero = data.persona_name || (data.hero_chars || '').trim();
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
          // No new turns -- restore exact position
          if (messagesEl) messagesEl.scrollTop = saved.scrollTop;
        } else {
          // New turns arrived -- restore position + show pill
          if (messagesEl) messagesEl.scrollTop = saved.scrollTop;
          showNewMessagesPill(newTurnIds.length, newTurnIds[0]);
        }
      } else {
        scrollChatToBottom();
      }
      updateTypingIndicator();
      updateChatStatePill();
      // Show most recent command instruction in header
      updateChatCommandInstruction(data.turns || []);
      updateEndedAgentUI();
      updateLoadMoreIndicator();
      // Disable stale question buttons if agent is not awaiting input
      var agentState = (VoiceState.chatAgentState || '').toLowerCase();
      if (agentState !== 'awaiting_input') {
        markAllQuestionsAnswered();
      }
    }).catch(function () {
      var nameEl = document.getElementById('chat-agent-name');
      if (nameEl) nameEl.textContent = 'Agent ' + agentId;
    });

    VoiceLayout.showScreen('chat');
    VoiceSidebar.highlightSelectedAgent();
  }

  function loadOlderMessages() {
    if (VoiceState.chatLoadingMore || !VoiceState.chatHasMore || !VoiceState.chatOldestTurnId) return;
    VoiceState.chatLoadingMore = true;
    updateLoadMoreIndicator();

    var messagesEl = document.getElementById('chat-messages');
    var prevScrollHeight = messagesEl ? messagesEl.scrollHeight : 0;

    VoiceAPI.getTranscript(VoiceState.targetAgentId, { before: VoiceState.chatOldestTurnId, limit: 50 }).then(function (data) {
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
      updateLoadMoreIndicator();
    }).catch(function () {
      VoiceState.chatLoadingMore = false;
      updateLoadMoreIndicator();
    });
  }

  function updateLoadMoreIndicator() {
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

  function updateEndedAgentUI() {
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

  function navigateToAgentFromBanner(agentId) {
    VoiceState.navStack.push(VoiceState.targetAgentId);
    showChatScreen(agentId);
  }

  // =====================================================================
  //  Scroll management
  // =====================================================================

  /**
   * Check if the user is scrolled near the bottom of the chat.
   * "Near" = within 150px of the bottom edge.  If they've scrolled
   * up to read older messages, we don't want to yank them away.
   */
  function isUserNearBottom() {
    var el = document.getElementById('chat-messages');
    if (!el) return true;
    return (el.scrollHeight - el.scrollTop - el.clientHeight) < 300;
  }

  function scrollChatToBottom() {
    var messagesEl = document.getElementById('chat-messages');
    if (messagesEl) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  /**
   * Scroll to bottom ONLY if the user is already near the bottom.
   * Call this for incoming messages (SSE, transcript refresh, typing
   * indicator) -- anywhere the user didn't just perform an action.
   */
  function scrollChatToBottomIfNear() {
    if (isUserNearBottom()) scrollChatToBottom();
  }

  function saveScrollState(agentId) {
    if (!agentId) return;
    var el = document.getElementById('chat-messages');
    if (!el) return;
    VoiceState.agentScrollState[agentId] = {
      scrollTop: el.scrollTop,
      scrollHeight: el.scrollHeight,
      lastTurnId: VoiceState.lastSeenTurnId
    };
  }

  function showNewMessagesPill(count, firstNewTurnId) {
    VoiceState.newMessagesFirstTurnId = firstNewTurnId;
    var pill = document.getElementById('new-messages-pill');
    if (!pill) {
      pill = document.createElement('div');
      pill.id = 'new-messages-pill';
      pill.className = 'new-messages-pill';
      pill.addEventListener('click', function () {
        if (!VoiceState.newMessagesFirstTurnId) return;
        var bubble = document.querySelector('[data-turn-id="' + VoiceState.newMessagesFirstTurnId + '"]');
        if (bubble) {
          bubble.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
        dismissNewMessagesPill();
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
    VoiceState.newMessagesPillVisible = true;
  }

  function dismissNewMessagesPill() {
    var pill = document.getElementById('new-messages-pill');
    if (pill) pill.style.display = 'none';
    VoiceState.newMessagesPillVisible = false;
    VoiceState.newMessagesFirstTurnId = null;
  }

  // =====================================================================
  //  State display
  // =====================================================================

  function getStateLabel(state) {
    return _STATE_LABELS[(state || '').toLowerCase()] || state || 'Unknown';
  }

  function updateTypingIndicator() {
    var typingEl = document.getElementById('chat-typing');
    if (!typingEl) return;
    var state = (VoiceState.chatAgentState || '').toLowerCase();
    var isProcessing = state === 'processing' || state === 'commanded';
    typingEl.style.display = isProcessing ? 'block' : 'none';
    if (isProcessing) scrollChatToBottomIfNear();
  }

  function updateChatStatePill() {
    var pill = document.getElementById('chat-state-pill');
    if (!pill) return;
    var state = (VoiceState.chatAgentState || '').toLowerCase();
    if (!state) { pill.style.display = 'none'; return; }
    pill.style.display = '';
    var label = VoiceState.chatAgentStateLabel || getStateLabel(state);
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

  function updateChatCommandInstruction(turns) {
    var el = document.getElementById('chat-command-instruction');
    if (!el) return;
    // Find the most recent command_instruction from turns (last non-empty)
    var instruction = '';
    for (var i = turns.length - 1; i >= 0; i--) {
      if (turns[i].command_instruction) {
        instruction = turns[i].command_instruction;
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

  function markAllQuestionsAnswered() {
    var containers = document.querySelectorAll('.bubble-options:not(.answered)');
    containers.forEach(function(el) {
      el.classList.add('answered');
      el.querySelectorAll('button').forEach(function(btn) { btn.disabled = true; });
    });
  }

  function showChatSystemMessage(text) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    var el = document.createElement('div');
    el.className = 'chat-system-message';
    el.textContent = text;
    messagesEl.appendChild(el);
    scrollChatToBottomIfNear();
  }

  // =====================================================================
  //  Chat sending
  // =====================================================================

  /**
   * Render an optimistic (provisional) user bubble immediately.
   * Sets a 10-second timeout to mark as send-failed if not confirmed
   * by a turn_created SSE event promoting the pending ID to a real ID.
   *
   * @param {string} text - The user's message text
   * @param {object} [extraFields] - Optional extra fields for the turn (e.g., file_metadata)
   * @returns {object} pendingEntry for tracking
   */
  function renderOptimisticUserBubble(text, extraFields) {
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
    scrollChatToBottom();
    return pendingEntry;
  }

  function sendChatCommand(text) {
    if (!text || !text.trim()) return;
    var trimmedText = text.trim();

    // Render optimistic user bubble immediately
    var pendingEntry = renderOptimisticUserBubble(trimmedText);

    // Clear input and reset textarea height
    var input = document.getElementById('chat-text-input');
    if (input) {
      input.value = '';
      input.style.height = 'auto';
    }

    // Show typing indicator (agent will be processing)
    VoiceState.chatAgentState = 'processing';
    VoiceState.chatAgentStateLabel = null;
    updateTypingIndicator();
    updateChatStatePill();

    VoiceAPI.sendCommand(trimmedText, VoiceState.targetAgentId).then(function (data) {
      if (data && data.interrupted) {
        VoiceSidebar.showToast('Interrupted agent — sending new instruction');
      }
    }).catch(function (err) {
      // Remove the ghost optimistic bubble on failure (Finding 10)
      VoiceSSEHandler.removeOptimisticBubble(pendingEntry);
      // Restore the text so user doesn't lose their work
      var restoreInput = document.getElementById('chat-text-input');
      if (restoreInput) {
        restoreInput.value = trimmedText;
        restoreInput.style.height = 'auto';
      }
      // Show error as system message
      var errBubble = document.createElement('div');
      errBubble.className = 'chat-bubble agent';
      errBubble.innerHTML = '<div class="bubble-intent">Error</div><div class="bubble-text">' + VoiceChatRenderer.esc(err.error || 'Send failed \u2014 your text has been restored to the input.') + '</div>';
      var msgEl = document.getElementById('chat-messages');
      if (msgEl) msgEl.appendChild(errBubble);
      VoiceState.chatAgentState = 'idle';
      VoiceState.chatAgentStateLabel = null;
      updateTypingIndicator();
      updateChatStatePill();
      scrollChatToBottom();
    });
  }

  function sendChatSelect(optionIndex, label, bubble) {
    // Render optimistic user bubble with the label text
    var pendingEntry = renderOptimisticUserBubble(label);

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
    updateTypingIndicator();
    updateChatStatePill();

    VoiceAPI.sendSelect(VoiceState.targetAgentId, optionIndex, label).then(function () {
      // Select sent -- SSE delivers the response directly
    }).catch(function (err) {
      VoiceSSEHandler.removeOptimisticBubble(pendingEntry);
      var errBubble = document.createElement('div');
      errBubble.className = 'chat-bubble agent';
      errBubble.innerHTML = '<div class="bubble-intent">Error</div><div class="bubble-text">' + VoiceChatRenderer.esc(err.error || 'Select failed') + '</div>';
      var msgEl = document.getElementById('chat-messages');
      if (msgEl) msgEl.appendChild(errBubble);
      VoiceState.chatAgentState = 'idle';
      VoiceState.chatAgentStateLabel = null;
      updateTypingIndicator();
      updateChatStatePill();
      scrollChatToBottom();

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

  function sendChatWithAttachment(text) {
    if (!VoiceState.pendingAttachment) {
      sendChatCommand(text);
      return;
    }

    var file = VoiceState.pendingAttachment;
    var trimText = (text || '').trim();

    // Guard: agent state check
    var state = (VoiceState.chatAgentState || '').toLowerCase();
    if (state === 'processing' || state === 'commanded') {
      showChatSystemMessage('Agent is processing \u2014 please wait.');
      return;
    }

    // Show optimistic user bubble via shared helper
    var displayText = trimText ? trimText : '[File: ' + file.name + ']';
    var pendingEntry = renderOptimisticUserBubble(displayText, {
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
    updateTypingIndicator();
    updateChatStatePill();

    VoiceAPI.uploadFile(VoiceState.targetAgentId, file, trimText || null, function (pct) {
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
      updateTypingIndicator();
      updateChatStatePill();
    });
  }

  // =====================================================================
  //  Legacy screens (listening/question)
  // =====================================================================

  function sendCommand(text) {
    if (!text || !text.trim()) return;

    var status = document.getElementById('status-message');
    if (status) status.textContent = 'Sending...';

    VoiceAPI.sendCommand(text.trim(), VoiceState.targetAgentId).then(function (data) {
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

  function sendSelect(optionIndex) {
    var status = document.getElementById('status-message');
    if (status) status.textContent = 'Sending...';

    VoiceAPI.sendSelect(VoiceState.targetAgentId, optionIndex).then(function (data) {
      VoiceOutput.playCue('sent');
      if (status) status.textContent = 'Sent!';
      setTimeout(function () { VoiceSidebar.refreshAgents(); VoiceLayout.showScreen('agents'); }, 1500);
    }).catch(function (err) {
      VoiceOutput.playCue('error');
      if (status) status.textContent = 'Error: ' + (err.error || 'Select failed');
    });
  }

  // =====================================================================
  //  Public API
  // =====================================================================

  return {
    showChatScreen: showChatScreen,
    loadOlderMessages: loadOlderMessages,
    updateLoadMoreIndicator: updateLoadMoreIndicator,
    updateEndedAgentUI: updateEndedAgentUI,
    navigateToAgentFromBanner: navigateToAgentFromBanner,
    isUserNearBottom: isUserNearBottom,
    scrollChatToBottom: scrollChatToBottom,
    scrollChatToBottomIfNear: scrollChatToBottomIfNear,
    saveScrollState: saveScrollState,
    showNewMessagesPill: showNewMessagesPill,
    dismissNewMessagesPill: dismissNewMessagesPill,
    getStateLabel: getStateLabel,
    updateTypingIndicator: updateTypingIndicator,
    updateChatStatePill: updateChatStatePill,
    updateChatCommandInstruction: updateChatCommandInstruction,
    markAllQuestionsAnswered: markAllQuestionsAnswered,
    showChatSystemMessage: showChatSystemMessage,
    renderOptimisticUserBubble: renderOptimisticUserBubble,
    sendChatCommand: sendChatCommand,
    sendChatSelect: sendChatSelect,
    sendChatWithAttachment: sendChatWithAttachment,
    sendCommand: sendCommand,
    sendSelect: sendSelect
  };
})();
