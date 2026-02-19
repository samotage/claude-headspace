/* VoiceSSEHandler — SSE event handling, connection state, transcript fetch,
 * and optimistic bubble cleanup.
 *
 * Reads/writes VoiceState for chatAgentState, chatAgentStateLabel,
 * chatAgentEnded, chatPendingUserSends, agentScrollState, otherAgentStates,
 * chatLastCommandId, lastSeenTurnId, previousConnectionState,
 * connectionLostTimer, connectionLostShown, fetchDebounceTimer, fetchInFlight.
 *
 * Uses callbacks for UI updates that remain in VoiceApp (typing indicator,
 * state pill, ended agent UI, scroll, question marking, system messages).
 *
 * Dependencies: VoiceState, VoiceChatRenderer, VoiceSidebar, VoiceAPI,
 * VoiceOutput, ConfirmDialog (optional).
 */
window.VoiceSSEHandler = (function () {
  'use strict';

  // --- Callbacks (wired by VoiceApp.init) ---
  var _onUpdateTypingIndicator = null;
  var _onUpdateStatePill = null;
  var _onUpdateEndedUI = null;
  var _onScrollChat = null;         // fn(nearOnly: boolean) — true = scroll if near bottom, false = force scroll
  var _onMarkQuestionsAnswered = null;
  var _onShowSystemMessage = null;

  function setUpdateTypingHandler(fn) { _onUpdateTypingIndicator = fn; }
  function setUpdateStatePillHandler(fn) { _onUpdateStatePill = fn; }
  function setUpdateEndedUIHandler(fn) { _onUpdateEndedUI = fn; }
  function setScrollChatHandler(fn) { _onScrollChat = fn; }
  function setMarkQuestionsHandler(fn) { _onMarkQuestionsAnswered = fn; }
  function setShowSystemMessageHandler(fn) { _onShowSystemMessage = fn; }

  // --- Internal helpers ---

  function _scrollIfNear() {
    if (_onScrollChat) _onScrollChat(true);
  }

  function _showSystemMessage(text) {
    if (_onShowSystemMessage) _onShowSystemMessage(text);
  }

  // --- SSE event handlers ---

  function handleChatSSE(data) {
    if (VoiceState.currentScreen !== 'chat') return;

    var agentId = data.agent_id || data.id;
    if (parseInt(agentId, 10) !== parseInt(VoiceState.targetAgentId, 10)) return;

    var newState = data.new_state || data.state;
    if (newState) {
      VoiceState.chatAgentState = newState;
      VoiceState.chatAgentStateLabel = (data.state_info && data.state_info.label) ? data.state_info.label : null;
      if (_onUpdateTypingIndicator) _onUpdateTypingIndicator();
      if (_onUpdateStatePill) _onUpdateStatePill();
    }

    // Recover from false ended state: card_refresh with is_active clears ended
    if (data.is_active === true && VoiceState.chatAgentEnded) {
      VoiceState.chatAgentEnded = false;
      if (_onUpdateEndedUI) _onUpdateEndedUI();
    }

    // Check for ended agent
    if (data.agent_ended || (newState && newState.toLowerCase() === 'ended')) {
      VoiceState.chatAgentEnded = true;
      delete VoiceState.agentScrollState[VoiceState.targetAgentId];
      if (_onUpdateEndedUI) _onUpdateEndedUI();
    }

    // SSE-primary: state changes update indicators only.
    // Turns are delivered directly via turn_created SSE events.
  }

  function handleGap(data) {
    // Server detected dropped events -- do a full refresh to catch up
    VoiceSidebar.refreshAgents();
    if (VoiceState.currentScreen === 'chat' && VoiceState.targetAgentId) {
      fetchTranscriptForChat();
    }
  }

  function handleTurnUpdated(data) {
    if (VoiceState.currentScreen !== 'chat') return;
    if (!data || !data.agent_id) return;
    if (parseInt(data.agent_id, 10) !== parseInt(VoiceState.targetAgentId, 10)) return;

    if (data.update_type === 'timestamp_correction' && data.turn_id) {
      var bubble = document.querySelector('[data-turn-id="' + data.turn_id + '"]');
      if (bubble && data.timestamp) {
        bubble.setAttribute('data-timestamp', data.timestamp);
        VoiceChatRenderer.reorderBubble(bubble);
      }
    }

    if (data.update_type === 'options_recaptured' && data.turn_id && data.question_options) {
      var safetyClass = data.safety ? ' safety-' + data.safety : '';
      var injected = VoiceChatRenderer.injectOptionsIntoBubble(data.turn_id, data.question_options, safetyClass);
      if (injected) {
        // Update bubble text if a better question_text was captured
        if (data.question_text) {
          var bub = document.querySelector('[data-turn-id="' + data.turn_id + '"]');
          if (bub) {
            var textEl = bub.querySelector('.bubble-text');
            if (textEl) textEl.innerHTML = VoiceChatRenderer.renderMd(data.question_text);
          }
        }
        _scrollIfNear();
      }
    }
  }

  function handleTurnCreated(data) {
    if (VoiceState.currentScreen !== 'chat') return;
    if (!data || !data.agent_id) return;
    if (parseInt(data.agent_id, 10) !== parseInt(VoiceState.targetAgentId, 10)) return;
    if (data.is_internal) return;
    if (!data.text || !data.text.trim()) return;

    // For user turns from SSE: promote optimistic (pending) bubbles if they exist
    var pendingSends = VoiceState.chatPendingUserSends;
    if (data.actor === 'user' && data.turn_id) {
      var realId = data.turn_id;
      // Look for a pending optimistic bubble to promote
      var promoted = false;
      for (var pi = 0; pi < pendingSends.length; pi++) {
        var pending = pendingSends[pi];
        if (pending.fakeTurnId) {
          var fakeBubble = document.querySelector('[data-turn-id="' + pending.fakeTurnId + '"]');
          if (fakeBubble) {
            // Promote: swap fake ID to real server ID
            fakeBubble.setAttribute('data-turn-id', realId);
            if (data.timestamp) fakeBubble.setAttribute('data-timestamp', data.timestamp);
            // Clear the send-failed timeout
            if (pending.failTimer) clearTimeout(pending.failTimer);
            pendingSends.splice(pi, 1);
            promoted = true;
            break;
          }
        }
      }
      if (promoted) return;
      // Not promoted -- check if already in DOM (e.g., from initial load)
      if (document.querySelector('[data-turn-id="' + realId + '"]')) return;
    }

    var isTerminalIntent = (data.intent === 'completion' || data.intent === 'end_of_command');

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
      question_source_type: data.question_source_type || null,
      command_id: data.command_id || null,
      command_instruction: data.command_instruction || null
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

    // Skip if already rendered in DOM -- but always render terminal intents
    // (completion/end_of_command) so the agent's final response is visible
    // even if a PROGRESS turn with the same ID was already shown.
    if (document.querySelector('[data-turn-id="' + turn.id + '"]')) {
      if (!isTerminalIntent) return;
    }

    // Insert command separator + bubble via appendChild (not insertBubbleOrdered)
    // so the separator stays immediately before its bubble.
    // SSE turns are always the newest, so append order is correct.
    // Capture scroll position BEFORE appending — after append, scrollHeight
    // increases and the near-bottom check would see stale distance.
    var wasNearBottom = VoiceChatController.isUserNearBottom();
    VoiceChatRenderer.maybeInsertCommandSeparator(turn);
    var messagesEl = document.getElementById('chat-messages');
    var bubbleEl = VoiceChatRenderer.createBubbleEl(turn, null, isTerminalIntent);
    if (bubbleEl && messagesEl) messagesEl.appendChild(bubbleEl);
    if (wasNearBottom && _onScrollChat) _onScrollChat(false);

    // If this is a permission question with no options, trigger recapture after
    // a delay to give the terminal time to render the options.
    // Only recapture for permission_request turns — free_text questions are
    // conversational and should never get Yes/No permission buttons.
    if (turn.intent === 'question' && !turn.question_options
        && turn.question_source_type === 'permission_request') {
      _scheduleRecapture(parseInt(data.agent_id, 10), turn.id);
    }
  }

  function handleAgentUpdate(data) {
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
      if (agentId && parseInt(agentId, 10) !== parseInt(VoiceState.targetAgentId, 10)) {
        var newState = data.new_state || data.state;
        if (newState && VoiceState.otherAgentStates[agentId]) {
          VoiceState.otherAgentStates[agentId].state = newState.toLowerCase();
          if (data.command_instruction) VoiceState.otherAgentStates[agentId].command_instruction = data.command_instruction;
          if (data.hero_chars) VoiceState.otherAgentStates[agentId].hero_chars = data.hero_chars;
          if (data.hero_trail) VoiceState.otherAgentStates[agentId].hero_trail = data.hero_trail;
          VoiceChatRenderer.renderAttentionBanners();
        } else if (newState && !VoiceState.otherAgentStates[agentId]) {
          // New agent appeared via SSE -- add it
          VoiceState.otherAgentStates[agentId] = {
            hero_chars: data.hero_chars || '',
            hero_trail: data.hero_trail || '',
            command_instruction: data.command_instruction || '',
            state: newState.toLowerCase(),
            project_name: data.project || ''
          };
          VoiceChatRenderer.renderAttentionBanners();
        }
      }
    }

    // Sync state to chat if this is the target agent
    if (VoiceState.currentScreen === 'chat' && VoiceState.targetAgentId) {
      var updateAgentId = data.agent_id || data.id;
      if (parseInt(updateAgentId, 10) === parseInt(VoiceState.targetAgentId, 10)) {
        var chatNewState = data.new_state || data.state;
        if (chatNewState) {
          var prevState = VoiceState.chatAgentState;
          VoiceState.chatAgentState = chatNewState;
          VoiceState.chatAgentStateLabel = (data.state_info && data.state_info.label) ? data.state_info.label : null;
          if (_onUpdateTypingIndicator) _onUpdateTypingIndicator();
          if (_onUpdateStatePill) _onUpdateStatePill();

          // If state left AWAITING_INPUT, update question options to "answered"
          if (prevState && prevState.toLowerCase() === 'awaiting_input'
              && chatNewState.toLowerCase() !== 'awaiting_input') {
            if (_onMarkQuestionsAnswered) _onMarkQuestionsAnswered();
          }
        }
        // Update command instruction in header if SSE provides it
        if (data.command_instruction) {
          var instrEl = document.getElementById('chat-command-instruction');
          if (instrEl) {
            var instr = data.command_instruction;
            instrEl.textContent = instr.length > 80 ? instr.substring(0, 80) + '...' : instr;
            instrEl.style.display = '';
          }
        }
      }
    }

    // Update chat screen if active
    handleChatSSE(data);

    // Polling fallback: if data is a sessions list (no agent_id), and chat
    // is active, check if the target agent's state changed
    if (!data.agent_id && !data.id && data.agents && VoiceState.currentScreen === 'chat' && VoiceState.targetAgentId) {
      for (var i = 0; i < data.agents.length; i++) {
        if (data.agents[i].agent_id === VoiceState.targetAgentId) {
          // Recover from false ended state via polling (agent reappeared in active list)
          var justRecovered = false;
          if (VoiceState.chatAgentEnded && data.agents[i].is_active !== false) {
            VoiceState.chatAgentEnded = false;
            if (_onUpdateEndedUI) _onUpdateEndedUI();
            justRecovered = true;
          }
          var polledState = data.agents[i].state;
          if (justRecovered || (polledState && polledState.toLowerCase() !== (VoiceState.chatAgentState || '').toLowerCase())) {
            if (polledState) {
              VoiceState.chatAgentState = polledState;
              VoiceState.chatAgentStateLabel = data.agents[i].state_label || null;
              if (_onUpdateTypingIndicator) _onUpdateTypingIndicator();
              if (_onUpdateStatePill) _onUpdateStatePill();
            }
            fetchTranscriptForChat();
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

  // --- Connection indicator ---

  function updateConnectionIndicator() {
    var el = document.getElementById('connection-status');
    if (!el) return;
    var state = VoiceAPI.getConnectionState();
    el.className = 'connection-dot ' + state;
    el.title = state;

    if (state === 'connected' && VoiceState.previousConnectionState !== 'connected') {
      catchUpAfterReconnect();
      // Cancel pending "connection lost" -- hiccup recovered before timeout
      if (VoiceState.connectionLostTimer) {
        clearTimeout(VoiceState.connectionLostTimer);
        VoiceState.connectionLostTimer = null;
      }
      // Only show "Reconnected" if we actually showed "Connection lost"
      if (VoiceState.connectionLostShown && VoiceState.currentScreen === 'chat') {
        _showSystemMessage('Reconnected');
      }
      VoiceState.connectionLostShown = false;
    }
    if (state === 'reconnecting' && VoiceState.previousConnectionState === 'connected') {
      // Debounce: wait 2s before showing. If recovered within window, suppress.
      if (!VoiceState.connectionLostTimer) {
        VoiceState.connectionLostTimer = setTimeout(function () {
          VoiceState.connectionLostTimer = null;
          if (VoiceAPI.getConnectionState() !== 'connected') {
            VoiceState.connectionLostShown = true;
            if (VoiceState.currentScreen === 'chat') {
              _showSystemMessage('Connection lost \u2014 reconnecting\u2026');
            }
          }
        }, 2000);
      }
    }
    VoiceState.previousConnectionState = state;
  }

  function catchUpAfterReconnect() {
    // Always refresh agent list
    VoiceSidebar.refreshAgents();

    // If chat screen is active, re-fetch transcript to catch missed events
    if (VoiceState.currentScreen === 'chat' && VoiceState.targetAgentId) {
      fetchTranscriptForChat();

      // Deferred stops create turns 0.5-5s after the initial stop hook.
      // If we reconnected during that gap the first fetch finds nothing.
      // A second fetch 3s later catches those late-arriving turns.
      var deferredAgentId = VoiceState.targetAgentId;
      setTimeout(function () {
        if (VoiceState.currentScreen === 'chat' && VoiceState.targetAgentId === deferredAgentId) {
          fetchTranscriptForChat();
        }
      }, 3000);
    }
  }

  // --- Transcript fetch ---

  /**
   * Shared transcript fetch + render logic used by reconnect catch-up,
   * periodic sync, and anywhere else that needs to pull new turns.
   *
   * Debounced: multiple calls within 500ms collapse into one fetch.
   * This prevents SSE event bursts and the sync timer from cancelling
   * each other's responses (Finding 5).
   */
  function fetchTranscriptForChat() {
    if (!VoiceState.targetAgentId) return;
    // If a fetch is already in flight, just schedule another after it finishes
    if (VoiceState.fetchInFlight) {
      VoiceState.fetchDebounceTimer = VoiceState.fetchDebounceTimer || setTimeout(function () {
        VoiceState.fetchDebounceTimer = null;
        fetchTranscriptForChat();
      }, 500);
      return;
    }
    // Clear any pending debounce since we're about to fetch now
    if (VoiceState.fetchDebounceTimer) {
      clearTimeout(VoiceState.fetchDebounceTimer);
      VoiceState.fetchDebounceTimer = null;
    }
    VoiceState.fetchInFlight = true;
    var agentId = VoiceState.targetAgentId;
    VoiceAPI.getTranscript(agentId).then(function (resp) {
      VoiceState.fetchInFlight = false;
      // Discard if user navigated to a different agent while fetching
      if (agentId !== VoiceState.targetAgentId) return;
      // Capture scroll position BEFORE appending new turns
      var wasNearBottom = VoiceChatController.isUserNearBottom();
      var turns = resp.turns || [];
      var messagesContainer = document.getElementById('chat-messages');

      for (var ti = 0; ti < turns.length; ti++) {
        var t = turns[ti];

        // Handle synthetic command_boundary entries from backend
        if (t.type === 'command_boundary') {
          if (messagesContainer && !messagesContainer.querySelector('.chat-command-separator[data-command-id="' + t.command_id + '"]')) {
            messagesContainer.appendChild(VoiceChatRenderer.createCommandSeparatorEl(t));
          }
          VoiceState.chatLastCommandId = t.command_id;
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
          // Already rendered -- update timestamp if changed, reorder if needed
          var currentTs = existingBubble.getAttribute('data-timestamp');
          if (t.timestamp && currentTs !== t.timestamp) {
            existingBubble.setAttribute('data-timestamp', t.timestamp);
            VoiceChatRenderer.reorderBubble(existingBubble);
          }
          // Still track command ID for boundary detection
          if (t.command_id) VoiceState.chatLastCommandId = t.command_id;
        } else {
          // Insert command separator + bubble via appendChild (not insertBubbleOrdered)
          // so the separator stays immediately before its bubble.
          // Sync turns arrive in chronological order; new turns are appended.
          VoiceChatRenderer.maybeInsertCommandSeparator(t);
          var prev = ti > 0 ? turns[ti - 1] : null;
          var forceTerminal = (t.intent === 'completion' || t.intent === 'end_of_command');
          var bubbleEl = VoiceChatRenderer.createBubbleEl(t, prev, forceTerminal);
          if (bubbleEl && messagesContainer) messagesContainer.appendChild(bubbleEl);
        }
      }

      if (resp.agent_state) {
        VoiceState.chatAgentState = resp.agent_state;
        if (_onUpdateTypingIndicator) _onUpdateTypingIndicator();
        if (_onUpdateStatePill) _onUpdateStatePill();
      }
      if (resp.agent_ended !== undefined) {
        var wasEnded = VoiceState.chatAgentEnded;
        VoiceState.chatAgentEnded = !!resp.agent_ended;
        if (VoiceState.chatAgentEnded !== wasEnded) {
          if (_onUpdateEndedUI) _onUpdateEndedUI();
        }
      }
      // Check if the last turn is a permission question with no options — trigger recapture.
      // Only recapture for permission_request turns — free_text questions are conversational
      // and should never get Yes/No permission buttons injected.
      if (turns.length > 0) {
        var lastTurn = turns[turns.length - 1];
        if (lastTurn.intent === 'question' && !lastTurn.question_options && !lastTurn.answered_by_turn_id
            && lastTurn.question_source_type === 'permission_request') {
          // Also check tool_input fallback
          var hasFallbackOpts = lastTurn.tool_input && lastTurn.tool_input.questions;
          if (!hasFallbackOpts) {
            _scheduleRecapture(parseInt(agentId, 10), lastTurn.id);
          }
        }
      }

      // Disable stale question buttons if agent is not awaiting input
      var syncedState = (VoiceState.chatAgentState || '').toLowerCase();
      if (syncedState !== 'awaiting_input' && _onMarkQuestionsAnswered) {
        _onMarkQuestionsAnswered();
      }

      // Auto-scroll if user was near the bottom before new turns were appended
      if (wasNearBottom && _onScrollChat) _onScrollChat(false);
    }).catch(function () {
      VoiceState.fetchInFlight = false;
    });
  }

  // --- Permission options recapture ---

  var _recaptureTimer = null;
  var _recaptureAttempts = 0;
  var _MAX_RECAPTURE_ATTEMPTS = 5;

  function _scheduleRecapture(agentId, turnId) {
    if (_recaptureTimer) clearTimeout(_recaptureTimer);
    _recaptureAttempts = 0;
    _attemptRecapture(agentId, turnId);
  }

  function _attemptRecapture(agentId, turnId) {
    _recaptureAttempts++;
    // Increasing delay: 1.5s, 3s, 4.5s, 6s, 7.5s
    var delayMs = _recaptureAttempts * 1500;
    _recaptureTimer = setTimeout(function () {
      // Don't recapture if user navigated away
      if (parseInt(VoiceState.targetAgentId, 10) !== agentId) return;
      // Don't recapture if bubble already has options
      var bubble = document.querySelector('[data-turn-id="' + turnId + '"]');
      if (bubble && (bubble.querySelector('.bubble-options') || bubble.querySelector('.bubble-multi-question'))) return;

      fetch('/api/voice/agents/' + agentId + '/recapture-permission', { method: 'POST' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.recaptured && data.question_options) {
            var safetyClass = (data.tool_input && data.tool_input.safety) ? ' safety-' + data.tool_input.safety : '';
            VoiceChatRenderer.injectOptionsIntoBubble(data.turn_id, data.question_options, safetyClass);
            if (data.question_text) {
              var bub = document.querySelector('[data-turn-id="' + data.turn_id + '"]');
              if (bub) {
                var textEl = bub.querySelector('.bubble-text');
                if (textEl) textEl.innerHTML = VoiceChatRenderer.renderMd(data.question_text);
              }
            }
            _scrollIfNear();
          } else if (data.already_present && data.question_options) {
            // Options were already in DB, inject them
            VoiceChatRenderer.injectOptionsIntoBubble(data.turn_id, data.question_options, '');
            _scrollIfNear();
          } else if (_recaptureAttempts < _MAX_RECAPTURE_ATTEMPTS) {
            // Retry with increasing delay
            _attemptRecapture(agentId, turnId);
          }
        })
        .catch(function () {
          if (_recaptureAttempts < _MAX_RECAPTURE_ATTEMPTS) {
            _attemptRecapture(agentId, turnId);
          }
        });
    }, delayMs);
  }

  // --- Optimistic bubble cleanup ---

  /**
   * Remove an optimistic (fake) user bubble when send fails (Finding 10).
   * Cleans up both the DOM element and the pending send entry.
   */
  function removeOptimisticBubble(pendingEntry) {
    // Remove from pending sends list
    var pendingSends = VoiceState.chatPendingUserSends;
    var idx = pendingSends.indexOf(pendingEntry);
    if (idx !== -1) pendingSends.splice(idx, 1);
    // Remove the fake bubble from DOM
    var messagesEl = document.getElementById('chat-messages');
    if (messagesEl && pendingEntry.fakeTurnId) {
      var bubble = messagesEl.querySelector('[data-turn-id="' + pendingEntry.fakeTurnId + '"]');
      if (bubble) bubble.remove();
    }
  }

  // --- Public API ---

  return {
    // Callback setters
    setUpdateTypingHandler: setUpdateTypingHandler,
    setUpdateStatePillHandler: setUpdateStatePillHandler,
    setUpdateEndedUIHandler: setUpdateEndedUIHandler,
    setScrollChatHandler: setScrollChatHandler,
    setMarkQuestionsHandler: setMarkQuestionsHandler,
    setShowSystemMessageHandler: setShowSystemMessageHandler,
    // SSE event handlers
    handleChatSSE: handleChatSSE,
    handleGap: handleGap,
    handleTurnUpdated: handleTurnUpdated,
    handleTurnCreated: handleTurnCreated,
    handleAgentUpdate: handleAgentUpdate,
    // Connection
    updateConnectionIndicator: updateConnectionIndicator,
    catchUpAfterReconnect: catchUpAfterReconnect,
    fetchTranscriptForChat: fetchTranscriptForChat,
    removeOptimisticBubble: removeOptimisticBubble
  };
})();
