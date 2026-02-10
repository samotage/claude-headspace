/* Voice Bridge main app controller */
window.VoiceApp = (function () {
  'use strict';

  // --- Settings defaults ---
  var DEFAULTS = {
    serverUrl: '',
    token: '',
    silenceTimeout: 800,
    doneWord: 'send',
    autoTarget: false,
    ttsEnabled: true,
    cuesEnabled: true,
    verbosity: 'normal'
  };

  var _settings = {};
  var _agents = [];
  var _targetAgentId = null;
  var _currentScreen = 'setup'; // setup | agents | listening | question | chat | settings
  var _chatRenderedTurnIds = new Set();
  var _chatAgentState = null;
  var _chatHasMore = false;
  var _chatLoadingMore = false;
  var _chatOldestTurnId = null;
  var _chatAgentEnded = false;
  var _isLocalhost = (location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.hostname === '::1');

  // --- Settings persistence (tasks 2.25, 2.26, 2.27) ---

  function loadSettings() {
    var s = {};
    try {
      var stored = localStorage.getItem('voice_settings');
      if (stored) s = JSON.parse(stored);
    } catch (e) { /* ignore */ }

    _settings = {
      serverUrl: s.serverUrl || DEFAULTS.serverUrl,
      token: s.token || DEFAULTS.token,
      silenceTimeout: s.silenceTimeout || DEFAULTS.silenceTimeout,
      doneWord: s.doneWord || DEFAULTS.doneWord,
      autoTarget: s.autoTarget !== undefined ? s.autoTarget : DEFAULTS.autoTarget,
      ttsEnabled: s.ttsEnabled !== undefined ? s.ttsEnabled : DEFAULTS.ttsEnabled,
      cuesEnabled: s.cuesEnabled !== undefined ? s.cuesEnabled : DEFAULTS.cuesEnabled,
      verbosity: s.verbosity || DEFAULTS.verbosity
    };

    // Apply to modules
    VoiceInput.setSilenceTimeout(_settings.silenceTimeout);
    VoiceInput.setDoneWords([_settings.doneWord]);
    VoiceOutput.setTTSEnabled(_settings.ttsEnabled);
    VoiceOutput.setCuesEnabled(_settings.cuesEnabled);
  }

  function saveSettings() {
    try {
      localStorage.setItem('voice_settings', JSON.stringify(_settings));
    } catch (e) { /* ignore */ }
    // Apply immediately
    VoiceInput.setSilenceTimeout(_settings.silenceTimeout);
    VoiceInput.setDoneWords([_settings.doneWord]);
    VoiceOutput.setTTSEnabled(_settings.ttsEnabled);
    VoiceOutput.setCuesEnabled(_settings.cuesEnabled);
  }

  function getSetting(key) { return _settings[key]; }

  function setSetting(key, value) {
    _settings[key] = value;
    saveSettings();
  }

  // --- Screen management ---

  function showScreen(name) {
    _currentScreen = name;
    var screens = document.querySelectorAll('.screen');
    for (var i = 0; i < screens.length; i++) {
      screens[i].classList.toggle('active', screens[i].id === 'screen-' + name);
    }
    _updateConnectionIndicator();
  }

  function getCurrentScreen() { return _currentScreen; }

  // --- Agent list (tasks 2.20, 2.23, 2.24) ---

  function _renderAgentList(agents) {
    _agents = agents || [];
    var list = document.getElementById('agent-list');
    if (!list) return;

    if (_agents.length === 0) {
      list.innerHTML = '<div class="empty-state">No active agents</div>';
      return;
    }

    var html = '';
    for (var i = 0; i < _agents.length; i++) {
      var a = _agents[i];
      var stateClass = 'state-' + a.state;
      var needsInput = a.awaiting_input ? '<span class="needs-input">Needs Input</span>' : '';
      html += '<div class="agent-card ' + stateClass + '" data-agent-id="' + a.agent_id + '">'
        + '<div class="agent-header">'
        + '<span class="agent-project">' + _esc(a.project) + '</span>'
        + '<span class="agent-state ' + stateClass + '">' + _esc(a.state) + '</span>'
        + '</div>'
        + '<div class="agent-body">'
        + (a.summary ? '<div class="agent-summary">' + _esc(a.summary) + '</div>' : '')
        + needsInput
        + '<div class="agent-ago">' + _esc(a.last_activity_ago) + '</div>'
        + '</div>'
        + '</div>';
    }
    list.innerHTML = html;

    // Bind click handlers for agent selection
    var cards = list.querySelectorAll('.agent-card');
    for (var j = 0; j < cards.length; j++) {
      cards[j].addEventListener('click', _onAgentCardClick);
    }
  }

  function _onAgentCardClick(e) {
    var card = e.currentTarget;
    var id = parseInt(card.getAttribute('data-agent-id'), 10);
    _selectAgent(id);
  }

  function _selectAgent(id) {
    _targetAgentId = id;
    var agent = null;
    for (var i = 0; i < _agents.length; i++) {
      if (_agents[i].agent_id === id) { agent = _agents[i]; break; }
    }

    if (agent && agent.awaiting_input) {
      // Load question for this agent
      _loadQuestion(id);
    } else {
      _showListeningScreen(agent);
    }
  }

  // Auto-targeting (task 2.23)
  function _autoTarget() {
    var awaiting = [];
    for (var i = 0; i < _agents.length; i++) {
      if (_agents[i].awaiting_input) awaiting.push(_agents[i]);
    }
    if (awaiting.length === 1) {
      _targetAgentId = awaiting[0].agent_id;
      return awaiting[0];
    }
    return null;
  }

  // --- Listening / Command mode (task 2.21) ---

  function _showListeningScreen(agent) {
    var el = document.getElementById('listening-target');
    if (el && agent) el.textContent = agent.project;
    showScreen('listening');
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
      showScreen('question');
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
          html += '<button class="option-btn" data-label="' + _esc(opt.label) + '">'
            + '<strong>' + _esc(opt.label) + '</strong>'
            + (opt.description ? '<br><span class="option-desc">' + _esc(opt.description) + '</span>' : '')
            + '</button>';
        }
        optionsEl.innerHTML = html;

        var btns = optionsEl.querySelectorAll('.option-btn');
        for (var j = 0; j < btns.length; j++) {
          btns[j].addEventListener('click', function () {
            _sendCommand(this.getAttribute('data-label'));
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
    _targetAgentId = agentId;
    _chatRenderedTurnIds.clear();
    _chatHasMore = false;
    _chatLoadingMore = false;
    _chatOldestTurnId = null;
    _chatAgentEnded = false;
    var messagesEl = document.getElementById('chat-messages');
    if (messagesEl) messagesEl.innerHTML = '';

    VoiceAPI.getTranscript(agentId).then(function (data) {
      var nameEl = document.getElementById('chat-agent-name');
      var projEl = document.getElementById('chat-project-name');
      if (nameEl) nameEl.textContent = data.agent_name || 'Agent';
      if (projEl) projEl.textContent = data.project || '';

      _chatAgentState = data.agent_state;
      _chatHasMore = data.has_more || false;
      _chatAgentEnded = data.agent_ended || false;
      _renderTranscriptTurns(data);
      _scrollChatToBottom();
      _updateTypingIndicator();
      _updateEndedAgentUI();
      _updateLoadMoreIndicator();
    }).catch(function () {
      var nameEl = document.getElementById('chat-agent-name');
      if (nameEl) nameEl.textContent = 'Agent ' + agentId;
    });

    showScreen('chat');
  }

  function _loadOlderMessages() {
    if (_chatLoadingMore || !_chatHasMore || !_chatOldestTurnId) return;
    _chatLoadingMore = true;
    _updateLoadMoreIndicator();

    var messagesEl = document.getElementById('chat-messages');
    var prevScrollHeight = messagesEl ? messagesEl.scrollHeight : 0;

    VoiceAPI.getTranscript(_targetAgentId, { before: _chatOldestTurnId, limit: 50 }).then(function (data) {
      _chatHasMore = data.has_more || false;
      var turns = data.turns || [];
      if (turns.length > 0) {
        // Prepend older turns at top
        _prependTranscriptTurns(turns);
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
    } else if (!_chatHasMore && _chatOldestTurnId) {
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

  function _renderTranscriptTurns(data) {
    var turns = data.turns || [];
    var grouped = _groupTurns(turns);
    for (var i = 0; i < grouped.length; i++) {
      var item = grouped[i];
      var prev = i > 0 ? grouped[i - 1] : null;
      if (item.type === 'separator') {
        _renderTaskSeparator(item);
      } else {
        _renderChatBubble(item, prev);
      }
    }
  }

  function _prependTranscriptTurns(turns) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;

    var grouped = _groupTurns(turns);
    // Create a fragment with all elements, then prepend
    var frag = document.createDocumentFragment();
    for (var i = 0; i < grouped.length; i++) {
      var item = grouped[i];
      var prev = i > 0 ? grouped[i - 1] : null;
      if (item.type === 'separator') {
        var sepEl = _createTaskSeparatorEl(item);
        frag.appendChild(sepEl);
      } else {
        var bubbleEl = _createBubbleEl(item, prev);
        if (bubbleEl) frag.appendChild(bubbleEl);
      }
    }
    // Insert before load-more indicator or at top
    var loadMore = document.getElementById('chat-load-more');
    if (loadMore && loadMore.nextSibling) {
      messagesEl.insertBefore(frag, loadMore.nextSibling);
    } else {
      messagesEl.insertBefore(frag, messagesEl.firstChild);
    }
  }

  function _groupTurns(turns) {
    // Group consecutive agent turns within 2s into single items,
    // insert task separators between task boundaries
    var result = [];
    var currentGroup = null;
    var lastTaskId = null;

    for (var i = 0; i < turns.length; i++) {
      var turn = turns[i];

      // Track oldest turn ID for pagination
      if (!_chatOldestTurnId || turn.id < _chatOldestTurnId) {
        _chatOldestTurnId = turn.id;
      }

      // Task boundary separator
      if (turn.task_id && lastTaskId && turn.task_id !== lastTaskId) {
        // Flush current group
        if (currentGroup) { result.push(currentGroup); currentGroup = null; }
        result.push({
          type: 'separator',
          task_instruction: turn.task_instruction || 'New task',
          task_id: turn.task_id
        });
      }
      lastTaskId = turn.task_id;

      var isUser = turn.actor === 'user';
      if (isUser) {
        // User turns always standalone — flush any active group
        if (currentGroup) { result.push(currentGroup); currentGroup = null; }
        result.push(turn);
        continue;
      }

      // Agent turn — check if it should be grouped with previous
      if (currentGroup && _shouldGroup(currentGroup, turn)) {
        // Append text to group
        var newText = turn.text || turn.summary || '';
        if (newText) {
          currentGroup.groupedTexts.push(newText);
          currentGroup.text = currentGroup.groupedTexts.join('\n');
        }
        currentGroup.groupedIds.push(turn.id);
        // Keep latest timestamp
        currentGroup.timestamp = turn.timestamp || currentGroup.timestamp;
      } else {
        // Flush previous group and start new one
        if (currentGroup) result.push(currentGroup);
        currentGroup = Object.assign({}, turn);
        currentGroup.groupedTexts = [turn.text || turn.summary || ''];
        currentGroup.groupedIds = [turn.id];
      }
    }
    // Flush final group
    if (currentGroup) result.push(currentGroup);

    return result;
  }

  function _shouldGroup(group, turn) {
    // Only group same-intent agent turns within 2 seconds
    if (group.actor !== 'agent' || turn.actor !== 'agent') return false;
    if (group.intent !== turn.intent) return false;
    if (!group.timestamp || !turn.timestamp) return false;
    var gap = new Date(turn.timestamp) - new Date(group.timestamp);
    return gap <= 2000;
  }

  function _renderTaskSeparator(item) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    messagesEl.appendChild(_createTaskSeparatorEl(item));
  }

  function _createTaskSeparatorEl(item) {
    var sep = document.createElement('div');
    sep.className = 'chat-task-separator';
    sep.innerHTML = '<span>' + _esc(item.task_instruction) + '</span>';
    return sep;
  }

  function _renderChatBubble(turn, prevTurn) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    var el = _createBubbleEl(turn, prevTurn);
    if (el) messagesEl.appendChild(el);
  }

  function _createBubbleEl(turn, prevTurn) {
    // Check all IDs in a group
    var ids = turn.groupedIds || [turn.id];
    var allRendered = true;
    for (var k = 0; k < ids.length; k++) {
      if (!_chatRenderedTurnIds.has(ids[k])) { allRendered = false; break; }
    }
    if (allRendered) return null;
    for (var k2 = 0; k2 < ids.length; k2++) {
      _chatRenderedTurnIds.add(ids[k2]);
    }

    var frag = document.createDocumentFragment();

    // Timestamp separator — show if first message or >5 min gap
    if (turn.timestamp) {
      var showTimestamp = false;
      if (!prevTurn || prevTurn.type === 'separator') {
        showTimestamp = true;
      } else if (prevTurn.timestamp) {
        var gap = new Date(turn.timestamp) - new Date(prevTurn.timestamp);
        if (gap > 5 * 60 * 1000) showTimestamp = true;
      }
      if (showTimestamp) {
        var tsEl = document.createElement('div');
        tsEl.className = 'chat-timestamp';
        tsEl.textContent = _formatChatTime(turn.timestamp);
        frag.appendChild(tsEl);
      }
    }

    var bubble = document.createElement('div');
    var isUser = turn.actor === 'user';
    var isGrouped = turn.groupedTexts && turn.groupedTexts.length > 1;
    bubble.className = 'chat-bubble ' + (isUser ? 'user' : 'agent') + (isGrouped ? ' grouped' : '');
    bubble.setAttribute('data-turn-id', turn.id);

    var html = '';

    // Intent label for non-obvious intents
    if (turn.intent === 'question') {
      html += '<div class="bubble-intent">Question</div>';
    } else if (turn.intent === 'completion') {
      html += '<div class="bubble-intent">Completed</div>';
    } else if (turn.intent === 'command') {
      html += '<div class="bubble-intent">Command</div>';
    }

    // Text content — fallback chain: text -> summary -> (empty)
    var displayText = turn.text || '';
    if (!displayText && turn.summary) {
      displayText = turn.summary;
    }
    if (!isUser && turn.summary && !turn.text) {
      displayText = turn.summary;
    }
    if (displayText) {
      if (isGrouped) {
        // Render grouped texts with separators
        html += '<div class="bubble-text grouped-text">';
        for (var g = 0; g < turn.groupedTexts.length; g++) {
          if (g > 0) html += '<div class="group-divider"></div>';
          html += '<div>' + _esc(turn.groupedTexts[g]) + '</div>';
        }
        html += '</div>';
      } else {
        html += '<div class="bubble-text">' + _esc(displayText) + '</div>';
      }
    }

    // Question options inside the bubble
    if (turn.intent === 'question') {
      var opts = turn.question_options;
      if (!opts && turn.tool_input) {
        var questions = turn.tool_input.questions;
        if (questions && questions.length > 0 && questions[0].options) {
          opts = questions[0].options;
        }
      }
      if (opts && opts.length > 0) {
        html += '<div class="bubble-options">';
        for (var i = 0; i < opts.length; i++) {
          var opt = opts[i];
          html += '<button class="bubble-option-btn" data-label="' + _esc(opt.label) + '">'
            + _esc(opt.label)
            + (opt.description ? '<div class="bubble-option-desc">' + _esc(opt.description) + '</div>' : '')
            + '</button>';
        }
        html += '</div>';
      }
    }

    bubble.innerHTML = html;

    // Bind option button clicks
    var optBtns = bubble.querySelectorAll('.bubble-option-btn');
    for (var j = 0; j < optBtns.length; j++) {
      optBtns[j].addEventListener('click', function () {
        _sendChatCommand(this.getAttribute('data-label'));
      });
    }

    frag.appendChild(bubble);
    return frag;
  }

  function _formatChatTime(isoStr) {
    var d = new Date(isoStr);
    var now = new Date();
    var hours = d.getHours();
    var minutes = d.getMinutes();
    var ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    var timeStr = hours + ':' + (minutes < 10 ? '0' : '') + minutes + ' ' + ampm;

    // Same day? Just show time.
    if (d.toDateString() === now.toDateString()) {
      return timeStr;
    }
    // Yesterday
    var yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) {
      return 'Yesterday ' + timeStr;
    }
    // This week (within 7 days) — show day-of-week
    var weekAgo = new Date(now);
    weekAgo.setDate(weekAgo.getDate() - 6);
    if (d >= weekAgo) {
      var days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      return days[d.getDay()] + ' ' + timeStr;
    }
    // Older — show date
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ', ' + timeStr;
  }

  function _scrollChatToBottom() {
    var messagesEl = document.getElementById('chat-messages');
    if (messagesEl) {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    }
  }

  function _updateTypingIndicator() {
    var typingEl = document.getElementById('chat-typing');
    if (!typingEl) return;
    var isProcessing = _chatAgentState === 'processing' || _chatAgentState === 'commanded';
    typingEl.style.display = isProcessing ? 'block' : 'none';
    if (isProcessing) _scrollChatToBottom();
  }

  function _sendChatCommand(text) {
    if (!text || !text.trim()) return;

    // Add user bubble immediately
    var now = new Date().toISOString();
    var fakeTurn = {
      id: 'pending-' + Date.now(),
      actor: 'user',
      intent: 'answer',
      text: text.trim(),
      timestamp: now
    };

    var messagesEl = document.getElementById('chat-messages');
    var lastBubble = messagesEl ? messagesEl.querySelector('.chat-bubble:last-child') : null;
    var prevTurn = null;
    if (lastBubble) {
      prevTurn = { timestamp: now }; // skip timestamp for immediate send
    }
    _renderChatBubble(fakeTurn, prevTurn);
    _scrollChatToBottom();

    // Clear input
    var input = document.getElementById('chat-text-input');
    if (input) input.value = '';

    // Show typing indicator (agent will be processing)
    _chatAgentState = 'processing';
    _updateTypingIndicator();

    VoiceAPI.sendCommand(text.trim(), _targetAgentId).then(function () {
      // Command sent — SSE will update state
    }).catch(function (err) {
      // Show error as system message
      var errBubble = document.createElement('div');
      errBubble.className = 'chat-bubble agent';
      errBubble.innerHTML = '<div class="bubble-intent">Error</div><div class="bubble-text">' + _esc(err.error || 'Send failed') + '</div>';
      if (messagesEl) messagesEl.appendChild(errBubble);
      _chatAgentState = 'idle';
      _updateTypingIndicator();
      _scrollChatToBottom();
    });
  }

  function _handleChatSSE(data) {
    if (_currentScreen !== 'chat') return;

    var agentId = data.agent_id || data.id;
    if (parseInt(agentId, 10) !== parseInt(_targetAgentId, 10)) return;

    var newState = data.new_state || data.state;
    if (newState) {
      _chatAgentState = newState;
      _updateTypingIndicator();
    }

    // Check for ended agent
    if (data.agent_ended || newState === 'ended') {
      _chatAgentEnded = true;
      _updateEndedAgentUI();
    }

    // Fetch only new turns since last rendered
    var newestRendered = 0;
    _chatRenderedTurnIds.forEach(function (id) {
      if (typeof id === 'number' && id > newestRendered) newestRendered = id;
    });

    // Fetch recent turns (no cursor = latest)
    VoiceAPI.getTranscript(_targetAgentId).then(function (resp) {
      var turns = resp.turns || [];
      // Filter to only truly new turns
      var newTurns = turns.filter(function (t) { return !_chatRenderedTurnIds.has(t.id); });
      if (newTurns.length > 0) {
        var grouped = _groupTurns(newTurns);
        var messagesEl = document.getElementById('chat-messages');
        for (var i = 0; i < grouped.length; i++) {
          var item = grouped[i];
          var prev = i > 0 ? grouped[i - 1] : null;
          if (item.type === 'separator') {
            _renderTaskSeparator(item);
          } else {
            _renderChatBubble(item, prev);
          }
        }
      }
      if (resp.agent_state) {
        _chatAgentState = resp.agent_state;
        _updateTypingIndicator();
      }
      if (resp.agent_ended) {
        _chatAgentEnded = true;
        _updateEndedAgentUI();
      }
      _scrollChatToBottom();
    }).catch(function () { /* ignore */ });
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
      setTimeout(function () { _refreshAgents(); showScreen('agents'); }, 1500);
    }).catch(function (err) {
      VoiceOutput.playCue('error');
      if (status) status.textContent = 'Error: ' + (err.error || 'Send failed');
    });
  }

  // --- SSE event handling ---

  function _handleAgentUpdate(data) {
    // Update chat screen if active
    _handleChatSSE(data);

    // Re-fetch agent list on any update
    _refreshAgents();

    // Play cue if an agent transitions to awaiting_input
    if (data && data.new_state === 'awaiting_input') {
      VoiceOutput.playCue('needs-input');
    }
  }

  function _refreshAgents() {
    VoiceAPI.getSessions(_settings.verbosity).then(function (data) {
      _renderAgentList(data.agents || []);
      // Apply server auto_target setting if user hasn't overridden locally
      if (data.settings && data.settings.auto_target !== undefined) {
        var stored = null;
        try {
          var raw = localStorage.getItem('voice_settings');
          if (raw) stored = JSON.parse(raw);
        } catch (e) { /* ignore */ }
        if (!stored || stored.autoTarget === undefined) {
          _settings.autoTarget = data.settings.auto_target;
        }
      }
    }).catch(function () { /* ignore */ });
  }

  // --- Connection indicator (task 2.18) ---

  function _updateConnectionIndicator() {
    var el = document.getElementById('connection-status');
    if (!el) return;
    var state = VoiceAPI.getConnectionState();
    el.className = 'connection-dot ' + state;
    el.title = state;
  }

  // --- Escape HTML ---

  function _esc(s) {
    if (!s) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(s));
    return div.innerHTML;
  }

  // --- Initialization ---

  function init() {
    loadSettings();

    // Detect agent_id URL param (from dashboard "Chat" link)
    var urlParams = new URLSearchParams(window.location.search);
    var paramAgentId = urlParams.get('agent_id');

    // When agent_id param is present, use current origin as server
    // (user navigated here intentionally from dashboard or LAN link)
    if (paramAgentId && (!_settings.serverUrl || !_settings.token)) {
      _settings.serverUrl = window.location.origin;
      _settings.token = 'lan';
    }

    // Localhost: skip setup, use current origin as server URL
    if (_isLocalhost && (!_settings.serverUrl || !_settings.token)) {
      _settings.serverUrl = window.location.origin;
      _settings.token = 'localhost';
    }

    // Check if we have credentials
    if (!_settings.serverUrl || !_settings.token) {
      showScreen('setup');
      return;
    }

    // Initialize API
    VoiceAPI.init(_settings.serverUrl, _settings.token);

    // Wire up speech input callbacks
    VoiceInput.onResult(function (text) {
      if (_currentScreen === 'chat') {
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
      var btn = document.getElementById('mic-btn');
      if (btn) btn.classList.toggle('active', listening);
      var chatMic = document.getElementById('chat-mic-btn');
      if (chatMic) chatMic.classList.toggle('active', listening);
    });

    // Wire up SSE
    VoiceAPI.onConnectionChange(_updateConnectionIndicator);
    VoiceAPI.onAgentUpdate(_handleAgentUpdate);
    VoiceAPI.connectSSE();

    // Play ready cue
    VoiceOutput.playCue('ready');

    // If agent_id param present, go directly to chat screen
    if (paramAgentId) {
      _showChatScreen(parseInt(paramAgentId, 10));
      return;
    }

    // Load agents and show list
    _refreshAgents();
    showScreen('agents');
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
          setSetting('serverUrl', url);
          setSetting('token', token);
          init();
        }
      });
    }

    // Mic button
    var micBtn = document.getElementById('mic-btn');
    if (micBtn) {
      micBtn.addEventListener('click', function () {
        VoiceOutput.initAudio();
        if (VoiceInput.isListening()) {
          _stopListening();
        } else {
          // Auto-target if enabled
          if (_settings.autoTarget) {
            var auto = _autoTarget();
            if (auto) {
              _showListeningScreen(auto);
            }
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

    // Settings button
    var settingsBtn = document.getElementById('settings-btn');
    if (settingsBtn) {
      settingsBtn.addEventListener('click', function () {
        _populateSettingsForm();
        showScreen('settings');
      });
    }

    // Settings form (task 2.26)
    var settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
      settingsForm.addEventListener('submit', function (e) {
        e.preventDefault();
        _applySettingsForm();
        showScreen('agents');
      });
    }

    // Chat input form
    var chatForm = document.getElementById('chat-input-form');
    if (chatForm) {
      chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var input = document.getElementById('chat-text-input');
        if (input && input.value.trim()) {
          _sendChatCommand(input.value);
        }
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

    // Scroll-up pagination for chat history
    var chatMessages = document.getElementById('chat-messages');
    if (chatMessages) {
      chatMessages.addEventListener('scroll', function () {
        if (chatMessages.scrollTop < 50) {
          _loadOlderMessages();
        }
      });
    }

    // Chat back button
    var chatBackBtn = document.querySelector('.chat-back-btn');
    if (chatBackBtn) {
      chatBackBtn.addEventListener('click', function () {
        // If opened from dashboard (agent_id param), go back to dashboard
        var urlParams = new URLSearchParams(window.location.search);
        if (urlParams.get('agent_id') && document.referrer) {
          window.history.back();
        } else {
          showScreen('agents');
        }
      });
    }

    // Back buttons (existing screens)
    var backBtns = document.querySelectorAll('.back-btn');
    for (var i = 0; i < backBtns.length; i++) {
      backBtns[i].addEventListener('click', function () {
        showScreen('agents');
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

  function _populateSettingsForm() {
    var el;
    el = document.getElementById('setting-silence');
    if (el) el.value = _settings.silenceTimeout;
    var display = document.getElementById('silence-value');
    if (display) display.textContent = _settings.silenceTimeout + 'ms';

    el = document.getElementById('setting-doneword');
    if (el) el.value = _settings.doneWord;

    el = document.getElementById('setting-autotarget');
    if (el) el.checked = _settings.autoTarget;

    el = document.getElementById('setting-tts');
    if (el) el.checked = _settings.ttsEnabled;

    el = document.getElementById('setting-cues');
    if (el) el.checked = _settings.cuesEnabled;

    el = document.getElementById('setting-verbosity');
    if (el) el.value = _settings.verbosity;

    el = document.getElementById('setting-url');
    if (el) el.value = _settings.serverUrl;

    el = document.getElementById('setting-token');
    if (el) el.value = _settings.token;
  }

  function _applySettingsForm() {
    var el;
    el = document.getElementById('setting-silence');
    if (el) setSetting('silenceTimeout', parseInt(el.value, 10));

    el = document.getElementById('setting-doneword');
    if (el) setSetting('doneWord', el.value);

    el = document.getElementById('setting-autotarget');
    if (el) setSetting('autoTarget', el.checked);

    el = document.getElementById('setting-tts');
    if (el) setSetting('ttsEnabled', el.checked);

    el = document.getElementById('setting-cues');
    if (el) setSetting('cuesEnabled', el.checked);

    el = document.getElementById('setting-verbosity');
    if (el) setSetting('verbosity', el.value);

    el = document.getElementById('setting-url');
    if (el) setSetting('serverUrl', el.value.trim());

    el = document.getElementById('setting-token');
    if (el) setSetting('token', el.value.trim());

    // Re-init API with new settings
    VoiceAPI.init(_settings.serverUrl, _settings.token);
  }

  return {
    init: init,
    bindEvents: bindEvents,
    loadSettings: loadSettings,
    saveSettings: saveSettings,
    getSetting: getSetting,
    setSetting: setSetting,
    showScreen: showScreen,
    getCurrentScreen: getCurrentScreen,
    _renderAgentList: _renderAgentList,
    _autoTarget: _autoTarget,
    _sendCommand: _sendCommand,
    _showChatScreen: _showChatScreen,
    _esc: _esc
  };
})();
