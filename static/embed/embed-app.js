/**
 * Embed App — Chat controller for the remote agent embed view.
 *
 * Handles text input, message thread rendering, question/option UI,
 * and communicates with the agent via the voice bridge API.
 */
(function () {
  'use strict';

  var config = window.EMBED_CONFIG || {};
  var agentId = config.agentId;
  var sessionToken = config.sessionToken;
  var applicationUrl = config.applicationUrl || '';

  // DOM references
  var loadingEl, errorEl, chatEl, messagesEl, typingEl, optionsEl;
  var inputEl, sendBtn, statusDot, statusText;
  var fileInput;

  // State
  var agentState = 'unknown';
  var agentEnded = false;
  var lastSeenTurnId = 0;
  var pendingUserSends = {};  // nonce -> {text, timestamp}
  var nonceCounter = 0;

  // ── Initialisation ──

  function init() {
    loadingEl = document.getElementById('embed-loading');
    errorEl = document.getElementById('embed-error');
    chatEl = document.getElementById('embed-chat');
    messagesEl = document.getElementById('embed-messages');
    typingEl = document.getElementById('embed-typing');
    optionsEl = document.getElementById('embed-options');
    inputEl = document.getElementById('embed-input');
    sendBtn = document.getElementById('embed-send');
    statusDot = document.getElementById('status-dot');
    statusText = document.getElementById('status-text');
    fileInput = document.getElementById('embed-file-input');

    // Input handlers
    inputEl.addEventListener('input', onInputChange);
    inputEl.addEventListener('keydown', onInputKeydown);
    sendBtn.addEventListener('click', onSend);

    // Auto-resize textarea
    inputEl.addEventListener('input', autoResize);

    // Error retry
    document.getElementById('error-retry').addEventListener('click', function () {
      showLoading();
      loadTranscript();
    });

    // Start SSE and load transcript
    EmbedSSE.init(config, {
      onTurnCreated: handleTurnCreated,
      onTurnUpdated: handleTurnUpdated,
      onCardRefresh: handleCardRefresh,
      onStateChange: handleStateChange,
      onAgentEnded: handleAgentEnded,
      onConnected: handleSSEConnected,
      onError: handleSSEError,
    });

    loadTranscript();
  }

  // ── View switching ──

  function showLoading() {
    loadingEl.style.display = 'flex';
    errorEl.style.display = 'none';
    chatEl.style.display = 'none';
  }

  function showError(message) {
    loadingEl.style.display = 'none';
    errorEl.style.display = 'flex';
    chatEl.style.display = 'none';
    document.getElementById('error-message').textContent = message || 'Connection failed';
  }

  function showChat() {
    loadingEl.style.display = 'none';
    errorEl.style.display = 'none';
    chatEl.style.display = 'flex';
  }

  // ── Transcript loading ──

  function loadTranscript() {
    var url = applicationUrl + '/api/voice/agents/' + agentId + '/transcript?limit=50';
    fetch(url, {
      headers: { 'Authorization': 'Bearer ' + sessionToken },
    })
      .then(function (resp) {
        if (!resp.ok) throw new Error('Failed to load transcript: ' + resp.status);
        return resp.json();
      })
      .then(function (data) {
        agentState = data.agent_state || 'idle';
        agentEnded = data.agent_ended || false;

        renderTranscript(data.turns || []);
        updateStatus();
        showChat();
        scrollToBottom();
      })
      .catch(function (err) {
        console.error('Transcript load failed:', err);
        // Even if transcript fails, show chat (SSE will deliver new turns)
        showChat();
        updateStatus();
      });
  }

  // ── Message rendering ──

  function renderTranscript(turns) {
    messagesEl.innerHTML = '';
    for (var i = 0; i < turns.length; i++) {
      var turn = turns[i];
      if (turn.type === 'command_boundary') continue;
      appendTurnBubble(turn);
      if (turn.id && turn.id > lastSeenTurnId) lastSeenTurnId = turn.id;
    }
  }

  function appendTurnBubble(turn) {
    // DOM dedup: skip if a bubble with this turn_id already exists
    if (turn.id && messagesEl.querySelector('[data-turn-id="' + turn.id + '"]')) {
      return;
    }

    var bubble = document.createElement('div');
    var isUser = turn.actor === 'user';
    bubble.className = 'embed-bubble ' + (isUser ? 'embed-bubble-user' : 'embed-bubble-agent');
    bubble.setAttribute('data-turn-id', turn.id || '');

    var text = turn.text || turn.summary || '';
    if (isUser) {
      bubble.textContent = text;
    } else {
      // Agent turns: strip internal markers and render as HTML
      bubble.innerHTML = escapeAndFormat(stripCommandComplete(text));
    }

    // Timestamp
    if (turn.timestamp) {
      var time = document.createElement('div');
      time.className = 'embed-bubble-time';
      time.textContent = formatTime(turn.timestamp);
      bubble.appendChild(time);
    }

    messagesEl.appendChild(bubble);

    // If this is a question turn, show options
    if (!isUser && turn.intent === 'question' && turn.question_options) {
      showOptions(turn.question_options, turn.id);
    }
  }

  function appendOptimisticBubble(text, nonce) {
    var bubble = document.createElement('div');
    bubble.className = 'embed-bubble embed-bubble-user embed-bubble-optimistic';
    bubble.setAttribute('data-nonce', nonce);
    bubble.textContent = text;
    messagesEl.appendChild(bubble);
    scrollToBottom();
  }

  function removeOptimisticBubble(nonce) {
    var el = messagesEl.querySelector('[data-nonce="' + nonce + '"]');
    if (el) el.remove();
  }

  function stripCommandComplete(text) {
    // Remove "---\nCOMMAND COMPLETE — ...\n---" block (with optional trailing whitespace)
    return text.replace(/\n?---\nCOMMAND COMPLETE\s*[—–-].*\n---\s*$/s, '').trimEnd();
  }

  function escapeAndFormat(text) {
    if (!text) return '';
    // Basic HTML escape
    var div = document.createElement('div');
    div.textContent = text;
    var escaped = div.innerHTML;
    // Simple formatting: **bold**, `code`, newlines
    escaped = escaped.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    escaped = escaped.replace(/`([^`]+)`/g, '<code>$1</code>');
    escaped = escaped.replace(/\n/g, '<br>');
    return escaped;
  }

  function formatTime(isoStr) {
    try {
      var d = new Date(isoStr);
      var hours = d.getHours();
      var minutes = d.getMinutes();
      var ampm = hours >= 12 ? 'PM' : 'AM';
      hours = hours % 12 || 12;
      return hours + ':' + (minutes < 10 ? '0' : '') + minutes + ' ' + ampm;
    } catch (e) {
      return '';
    }
  }

  // ── Options / Questions ──

  function showOptions(options, turnId) {
    optionsEl.innerHTML = '';
    optionsEl.style.display = 'flex';

    if (!Array.isArray(options)) return;

    for (var i = 0; i < options.length; i++) {
      var opt = options[i];
      var btn = document.createElement('button');
      btn.className = 'embed-option-btn';
      btn.textContent = opt.label || opt;
      btn.setAttribute('data-turn-id', turnId || '');
      btn.setAttribute('data-index', i);
      (function (label) {
        btn.addEventListener('click', function () {
          sendMessage(label);
          hideOptions();
        });
      })(opt.label || opt.toString());
      optionsEl.appendChild(btn);
    }
  }

  function hideOptions() {
    optionsEl.style.display = 'none';
    optionsEl.innerHTML = '';
  }

  // ── Input handling ──

  function onInputChange() {
    sendBtn.disabled = !inputEl.value.trim();
  }

  function onInputKeydown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSend();
    }
  }

  function autoResize() {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
  }

  function onSend() {
    var text = inputEl.value.trim();
    if (!text) return;

    inputEl.value = '';
    inputEl.style.height = 'auto';
    sendBtn.disabled = true;

    sendMessage(text);
  }

  function sendMessage(text) {
    var nonce = 'n' + (++nonceCounter);
    pendingUserSends[nonce] = { text: text, timestamp: Date.now() };

    // Optimistic bubble
    appendOptimisticBubble(text, nonce);
    hideOptions();

    // Send via voice command API (reuses existing tmux bridge)
    var url = applicationUrl + '/api/voice/command';
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer ' + sessionToken,
      },
      body: JSON.stringify({
        text: text,
        agent_id: agentId,
      }),
    })
      .then(function (resp) {
        if (!resp.ok) throw new Error('Send failed: ' + resp.status);
        return resp.json();
      })
      .then(function (data) {
        // Update state from response
        if (data.new_state) {
          agentState = data.new_state;
          updateStatus();
          updateTyping();
        }
      })
      .catch(function (err) {
        console.error('Send failed:', err);
        removeOptimisticBubble(nonce);
        delete pendingUserSends[nonce];
        // Show inline error
        var errBubble = document.createElement('div');
        errBubble.className = 'embed-bubble embed-bubble-system';
        errBubble.textContent = 'Failed to send message. Please try again.';
        messagesEl.appendChild(errBubble);
        scrollToBottom();
      });
  }

  // ── SSE event handlers ──

  function handleTurnCreated(data) {
    if (parseInt(data.agent_id, 10) !== agentId) return;

    // Skip internal/system turns (skill injection, team comms, etc.)
    if (data.is_internal) return;

    // Clean up matching optimistic bubble
    if (data.actor === 'user' && data.text) {
      for (var nonce in pendingUserSends) {
        if (pendingUserSends[nonce].text === data.text) {
          removeOptimisticBubble(nonce);
          delete pendingUserSends[nonce];
          break;
        }
      }
    }

    // Avoid duplicate turns
    if (data.turn_id && data.turn_id <= lastSeenTurnId) return;
    if (data.turn_id) lastSeenTurnId = data.turn_id;

    appendTurnBubble({
      id: data.turn_id,
      actor: data.actor,
      intent: data.intent,
      text: data.text,
      summary: data.summary,
      timestamp: data.timestamp,
      question_options: data.question_options,
    });

    updateTyping();
    scrollToBottom();
  }

  function handleTurnUpdated(data) {
    if (parseInt(data.agent_id, 10) !== agentId) return;

    // turn_updated carries timestamp corrections from transcript reconciliation.
    // Update the timestamp on the existing bubble; do NOT create a new bubble.
    if (!data.turn_id) return;

    var existing = messagesEl.querySelector('[data-turn-id="' + data.turn_id + '"]');
    if (existing && data.timestamp) {
      var timeEl = existing.querySelector('.embed-bubble-time');
      if (timeEl) {
        timeEl.textContent = formatTime(data.timestamp);
      }
    }
  }

  function handleCardRefresh(data) {
    if (parseInt(data.agent_id || data.id, 10) !== agentId) return;

    var newState = data.new_state || data.state;
    if (newState) {
      agentState = newState;
      updateStatus();
      updateTyping();
    }

    if (data.agent_ended) {
      handleAgentEnded();
    }
  }

  function handleStateChange(data) {
    if (parseInt(data.agent_id, 10) !== agentId) return;

    if (data.new_state) {
      agentState = data.new_state;
      updateStatus();
      updateTyping();
    }
  }

  function handleAgentEnded() {
    agentEnded = true;
    agentState = 'ended';
    updateStatus();
    updateTyping();

    // Disable input
    inputEl.disabled = true;
    inputEl.placeholder = 'Agent has ended';
    sendBtn.disabled = true;
  }

  function handleSSEConnected() {
    updateStatus();
  }

  function handleSSEError() {
    statusDot.className = 'status-dot status-error';
    statusText.textContent = 'Disconnected';
  }

  // ── UI updates ──

  function updateStatus() {
    var stateLabels = {
      'idle': 'Ready',
      'commanded': 'Starting...',
      'processing': 'Thinking...',
      'awaiting_input': 'Waiting for input',
      'complete': 'Complete',
      'ended': 'Ended',
    };

    var stateClasses = {
      'idle': 'status-idle',
      'commanded': 'status-processing',
      'processing': 'status-processing',
      'awaiting_input': 'status-awaiting',
      'complete': 'status-idle',
      'ended': 'status-ended',
    };

    statusDot.className = 'status-dot ' + (stateClasses[agentState] || 'status-idle');
    statusText.textContent = stateLabels[agentState] || agentState;
  }

  function updateTyping() {
    var showTyping = agentState === 'processing' || agentState === 'commanded';
    typingEl.style.display = showTyping ? 'flex' : 'none';
  }

  function scrollToBottom() {
    requestAnimationFrame(function () {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    });
  }

  // ── Startup ──

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose for SSE handler
  window.EmbedApp = {
    handleTurnCreated: handleTurnCreated,
    handleCardRefresh: handleCardRefresh,
    handleStateChange: handleStateChange,
    handleAgentEnded: handleAgentEnded,
  };
})();
