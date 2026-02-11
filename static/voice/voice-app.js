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
    verbosity: 'normal',
    fontSize: 15
  };

  var _settings = {};
  var _agents = [];
  var _targetAgentId = null;
  var _currentScreen = 'setup'; // setup | agents | listening | question | chat | settings
  var _chatRenderedTurnIds = new Set();
  var _chatPendingUserTexts = new Set(); // texts sent from chat, awaiting real turn
  var _chatAgentState = null;
  var _chatHasMore = false;
  var _chatLoadingMore = false;
  var _chatOldestTurnId = null;
  var _chatAgentEnded = false;
  var _isLocalhost = (location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.hostname === '::1');
  var _settingsReturnScreen = 'agents'; // track where settings was opened from
  var _navStack = [];           // Stack of agent IDs for back navigation
  var _otherAgentStates = {};   // Map: agentId -> {hero_chars, hero_trail, task_instruction, state, project_name}

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
      verbosity: s.verbosity || DEFAULTS.verbosity,
      fontSize: s.fontSize || DEFAULTS.fontSize
    };

    // Apply to modules
    VoiceInput.setSilenceTimeout(_settings.silenceTimeout);
    VoiceInput.setDoneWords([_settings.doneWord]);
    VoiceOutput.setTTSEnabled(_settings.ttsEnabled);
    VoiceOutput.setCuesEnabled(_settings.cuesEnabled);
    _applyFontSize();
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

  function _applyFontSize() {
    document.documentElement.style.setProperty('--chat-font-size', _settings.fontSize + 'px');
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

  function _returnFromSettings() {
    var target = _settingsReturnScreen || 'agents';
    if (target === 'chat') {
      showScreen('chat');
      _scrollChatToBottom();
    } else {
      _refreshAgents();
      showScreen('agents');
    }
  }

  // --- Agent list (tasks 2.20, 2.23, 2.24) ---

  function _renderAgentList(agents) {
    _agents = agents || [];
    var list = document.getElementById('agent-list');
    if (!list) return;

    if (_agents.length === 0) {
      list.innerHTML = '<div class="empty-state">No active agents</div>';
      return;
    }

    // Group agents by project
    var projectGroups = {};
    var projectOrder = [];
    for (var i = 0; i < _agents.length; i++) {
      var proj = _agents[i].project || 'unknown';
      if (!projectGroups[proj]) {
        projectGroups[proj] = [];
        projectOrder.push(proj);
      }
      projectGroups[proj].push(_agents[i]);
    }

    var html = '';
    for (var p = 0; p < projectOrder.length; p++) {
      var projName = projectOrder[p];
      var group = projectGroups[projName];

      html += '<div class="project-group">'
        + '<div class="project-group-header">'
        + '<span class="project-group-name">' + _esc(projName) + '</span>'
        + '<button class="project-kebab-btn" data-project="' + _esc(projName) + '" title="Project actions">&#8942;</button>'
        + '<div class="project-kebab-menu" data-project="' + _esc(projName) + '">'
        + '<button class="kebab-menu-item project-add-agent" data-project="' + _esc(projName) + '">Add agent</button>'
        + '</div>'
        + '</div>'
        + '<div class="project-group-cards">';

      for (var j = 0; j < group.length; j++) {
        var a = group[j];
        var stateClass = 'state-' + (a.state || '').toLowerCase();
        var stateLabel = a.state_label || a.state || 'unknown';
        var heroChars = a.hero_chars || '';
        var heroTrail = a.hero_trail || '';

        // Task instruction line
        var instructionHtml = a.task_instruction
          ? '<div class="agent-instruction">' + _esc(a.task_instruction) + '</div>'
          : '';

        // Summary line (only if different from instruction)
        var summaryText = '';
        if (a.task_completion_summary) {
          summaryText = a.task_completion_summary;
        } else if (a.task_summary && a.task_summary !== a.task_instruction) {
          summaryText = a.task_summary;
        }
        var summaryHtml = summaryText
          ? '<div class="agent-summary">' + _esc(summaryText) + '</div>'
          : '';

        // Footer: turn count + last activity
        var footerParts = [];
        if (a.turn_count && a.turn_count > 0) {
          footerParts.push(a.turn_count + ' turn' + (a.turn_count !== 1 ? 's' : ''));
        }
        footerParts.push(a.last_activity_ago);

        html += '<div class="agent-card ' + stateClass + '" data-agent-id="' + a.agent_id + '">'
          + '<div class="agent-header">'
          + '<div class="agent-hero-id">'
          + '<span class="agent-hero">' + _esc(heroChars) + '</span>'
          + '<span class="agent-hero-trail">' + _esc(heroTrail) + '</span>'
          + '</div>'
          + '<div class="agent-header-actions">'
          + '<button class="agent-kebab-btn" data-agent-id="' + a.agent_id + '" title="Actions">&#8942;</button>'
          + '<div class="agent-kebab-menu" data-agent-id="' + a.agent_id + '">'
          + '<button class="kebab-menu-item agent-ctx-action" data-agent-id="' + a.agent_id + '">Fetch context</button>'
          + '<button class="kebab-menu-item agent-kill-action" data-agent-id="' + a.agent_id + '">Dismiss agent</button>'
          + '</div>'
          + '</div>'
          + '</div>'
          + '<div class="agent-body">'
          + instructionHtml
          + summaryHtml
          + '<div class="agent-ctx-display" id="ctx-display-' + a.agent_id + '"></div>'
          + '<div class="agent-ago">' + _esc(footerParts.join(' · ')) + '</div>'
          + '</div>'
          + '</div>';
      }

      html += '</div></div>';
    }
    list.innerHTML = html;

    // Bind click handlers for agent selection
    var cards = list.querySelectorAll('.agent-card');
    for (var j = 0; j < cards.length; j++) {
      cards[j].addEventListener('click', _onAgentCardClick);
    }

    // Bind kebab menu buttons
    var kebabBtns = list.querySelectorAll('.agent-kebab-btn');
    for (var c = 0; c < kebabBtns.length; c++) {
      kebabBtns[c].addEventListener('click', function (e) {
        e.stopPropagation();
        var agentId = this.getAttribute('data-agent-id');
        var menu = list.querySelector('.agent-kebab-menu[data-agent-id="' + agentId + '"]');
        // Close any other open menus
        var allMenus = list.querySelectorAll('.agent-kebab-menu.open');
        for (var m = 0; m < allMenus.length; m++) {
          if (allMenus[m] !== menu) allMenus[m].classList.remove('open');
        }
        if (menu) menu.classList.toggle('open');
      });
    }

    // Bind kebab menu actions
    var ctxActions = list.querySelectorAll('.agent-ctx-action');
    for (var ca = 0; ca < ctxActions.length; ca++) {
      ctxActions[ca].addEventListener('click', function (e) {
        e.stopPropagation();
        var agentId = parseInt(this.getAttribute('data-agent-id'), 10);
        _closeAllKebabMenus();
        _checkAgentContext(agentId);
      });
    }
    var killActions = list.querySelectorAll('.agent-kill-action');
    for (var ka = 0; ka < killActions.length; ka++) {
      killActions[ka].addEventListener('click', function (e) {
        e.stopPropagation();
        var agentId = parseInt(this.getAttribute('data-agent-id'), 10);
        _closeAllKebabMenus();
        _shutdownAgent(agentId);
      });
    }

    // Bind project kebab menu buttons
    var projKebabBtns = list.querySelectorAll('.project-kebab-btn');
    for (var pk = 0; pk < projKebabBtns.length; pk++) {
      projKebabBtns[pk].addEventListener('click', function (e) {
        e.stopPropagation();
        var projectName = this.getAttribute('data-project');
        var menu = list.querySelector('.project-kebab-menu[data-project="' + projectName + '"]');
        _closeAllKebabMenus();
        if (menu) menu.classList.toggle('open');
      });
    }

    // Bind project "Add agent" actions
    var addAgentActions = list.querySelectorAll('.project-add-agent');
    for (var aa = 0; aa < addAgentActions.length; aa++) {
      addAgentActions[aa].addEventListener('click', function (e) {
        e.stopPropagation();
        var projectName = this.getAttribute('data-project');
        _closeAllKebabMenus();
        _createAgentForProject(projectName);
      });
    }
  }

  function _closeAllKebabMenus() {
    var menus = document.querySelectorAll('.agent-kebab-menu.open, .project-kebab-menu.open');
    for (var i = 0; i < menus.length; i++) {
      menus[i].classList.remove('open');
    }
  }

  function _onAgentCardClick(e) {
    var card = e.currentTarget;
    var id = parseInt(card.getAttribute('data-agent-id'), 10);
    _selectAgent(id);
  }

  function _selectAgent(id) {
    _targetAgentId = id;
    _navStack = [];
    _showChatScreen(id);
  }

  function _checkAgentContext(agentId) {
    var display = document.getElementById('ctx-display-' + agentId);
    if (display) {
      display.textContent = 'Checking...';
      display.className = 'agent-ctx-display loading';
    }
    VoiceAPI.getAgentContext(agentId).then(function (data) {
      if (!display) return;
      if (data.available) {
        display.textContent = data.percent_used + '% used \u00B7 ' + data.remaining_tokens + ' remaining';
        display.className = 'agent-ctx-display available';
      } else {
        display.textContent = 'Context unavailable';
        display.className = 'agent-ctx-display unavailable';
      }
    }).catch(function () {
      if (display) {
        display.textContent = 'Error checking context';
        display.className = 'agent-ctx-display error';
      }
    });
  }

  function _shutdownAgent(agentId) {
    if (!confirm('Shut down this agent?')) return;
    VoiceAPI.shutdownAgent(agentId).then(function () {
      _refreshAgents();
    }).catch(function (err) {
      alert('Shutdown failed: ' + (err.error || 'unknown error'));
    });
  }

  function _createAgentForProject(projectName) {
    VoiceAPI.createAgent(projectName).then(function (data) {
      _refreshAgents();
    }).catch(function (err) {
      alert('Create failed: ' + (err.error || 'unknown error'));
    });
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
    _chatPendingUserTexts.clear();
    _chatHasMore = false;
    _chatLoadingMore = false;
    _chatOldestTurnId = null;
    _chatAgentEnded = false;
    var messagesEl = document.getElementById('chat-messages');
    if (messagesEl) messagesEl.innerHTML = '';
    var bannersEl = document.getElementById('attention-banners');
    if (bannersEl) bannersEl.innerHTML = '';

    // Fetch other agent states for attention banners
    VoiceAPI.getSessions().then(function (data) {
      var agents = data.agents || [];
      _otherAgentStates = {};
      for (var i = 0; i < agents.length; i++) {
        var a = agents[i];
        if (a.agent_id !== agentId) {
          _otherAgentStates[a.agent_id] = {
            hero_chars: a.hero_chars || '',
            hero_trail: a.hero_trail || '',
            task_instruction: a.task_instruction || '',
            state: (a.state || '').toLowerCase(),
            project_name: a.project || ''
          };
        }
      }
      _renderAttentionBanners();
    }).catch(function () { /* ignore */ });

    VoiceAPI.getTranscript(agentId).then(function (data) {
      var nameEl = document.getElementById('chat-agent-name');
      var projEl = document.getElementById('chat-project-name');
      var heroEl = document.getElementById('chat-hero');
      if (heroEl) {
        var hc = data.hero_chars || '';
        var ht = data.hero_trail || '';
        heroEl.innerHTML = '<span class="agent-hero">' + _esc(hc) + '</span><span class="agent-hero-trail">' + _esc(ht) + '</span>';
      }
      if (nameEl) nameEl.textContent = data.project || 'Agent';
      if (projEl) projEl.textContent = '';

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

  function _renderAttentionBanners() {
    var container = document.getElementById('attention-banners');
    if (!container) return;

    var bannerAgents = [];
    var keys = Object.keys(_otherAgentStates);
    for (var i = 0; i < keys.length; i++) {
      var agentId = keys[i];
      var info = _otherAgentStates[agentId];
      if (info.state === 'awaiting_input') {
        bannerAgents.push({ id: agentId, info: info });
      }
    }

    if (bannerAgents.length === 0) {
      container.innerHTML = '';
      return;
    }

    var html = '';
    for (var j = 0; j < bannerAgents.length; j++) {
      var ba = bannerAgents[j];
      var text = ba.info.task_instruction || 'Needs input';
      html += '<div class="attention-banner" data-agent-id="' + ba.id + '">'
        + '<div class="attention-banner-hero">'
        + '<span class="agent-hero">' + _esc(ba.info.hero_chars) + '</span>'
        + '<span class="agent-hero-trail">' + _esc(ba.info.hero_trail) + '</span>'
        + '</div>'
        + '<div class="attention-banner-text">' + _esc(text) + '</div>'
        + '<div class="attention-banner-arrow">&#8250;</div>'
        + '</div>';
    }
    container.innerHTML = html;

    var banners = container.querySelectorAll('.attention-banner');
    for (var k = 0; k < banners.length; k++) {
      banners[k].addEventListener('click', function () {
        var id = parseInt(this.getAttribute('data-agent-id'), 10);
        _navigateToAgentFromBanner(id);
      });
    }
  }

  function _navigateToAgentFromBanner(agentId) {
    _navStack.push(_targetAgentId);
    _showChatScreen(agentId);
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
    } else if (turn.intent === 'progress') {
      html += '<div class="bubble-intent progress-intent">Working</div>';
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
      var renderFn = isUser ? _esc : _renderMd;
      if (isGrouped) {
        // Render grouped texts with separators
        html += '<div class="bubble-text grouped-text">';
        for (var g = 0; g < turn.groupedTexts.length; g++) {
          if (g > 0) html += '<div class="group-divider"></div>';
          html += '<div>' + renderFn(turn.groupedTexts[g]) + '</div>';
        }
        html += '</div>';
      } else {
        html += '<div class="bubble-text">' + renderFn(displayText) + '</div>';
      }
    }

    // Question options inside the bubble
    if (turn.intent === 'question') {
      var opts = turn.question_options;
      var toolInput = turn.tool_input || {};
      var allQuestions = null;
      if (!opts && toolInput.questions) {
        var questions = toolInput.questions;
        if (questions && questions.length > 1) {
          // Multi-question: check if first element has 'options' (full question objects)
          if (questions[0].options) {
            allQuestions = questions;
          }
        } else if (questions && questions.length > 0 && questions[0].options) {
          opts = questions[0].options;
        }
      }
      // Also check if q_options itself is multi-question format
      if (!allQuestions && opts && opts.length > 0 && opts[0].options) {
        allQuestions = opts;
        opts = null;
      }
      // Extract safety for color-coding option buttons
      var bubbleSafety = toolInput.safety || '';
      var safetyClass = bubbleSafety ? ' safety-' + _esc(bubbleSafety) : '';

      if (allQuestions && allQuestions.length > 1) {
        // Multi-question bubble
        html += _renderMultiQuestionBubble(allQuestions, safetyClass, turn);
      } else if (opts && opts.length > 0) {
        html += '<div class="bubble-options">';
        for (var i = 0; i < opts.length; i++) {
          var opt = opts[i];
          html += '<button class="bubble-option-btn' + safetyClass + '" data-label="' + _esc(opt.label) + '">'
            + _esc(opt.label)
            + (opt.description ? '<div class="bubble-option-desc">' + _esc(opt.description) + '</div>' : '')
            + '</button>';
        }
        html += '</div>';
      }
    }

    bubble.innerHTML = html;

    // Bind option button clicks
    var multiContainer = bubble.querySelector('.bubble-multi-question');
    if (multiContainer) {
      _bindMultiQuestionBubble(multiContainer, bubble);
    } else {
      var optBtns = bubble.querySelectorAll('.bubble-option-btn');
      for (var j = 0; j < optBtns.length; j++) {
        optBtns[j].addEventListener('click', function () {
          _sendChatCommand(this.getAttribute('data-label'));
        });
      }
    }

    frag.appendChild(bubble);
    return frag;
  }

  function _renderMultiQuestionBubble(questions, safetyClass, turn) {
    var html = '<div class="bubble-multi-question">';
    for (var qi = 0; qi < questions.length; qi++) {
      var q = questions[qi];
      var isMulti = q.multiSelect === true;
      html += '<div class="bubble-question-section" data-q-idx="' + qi + '" data-multi="' + (isMulti ? '1' : '0') + '">';
      html += '<div class="bubble-question-header">' + _esc(q.header ? q.header + ': ' : '') + _esc(q.question || '') + '</div>';
      var qOpts = q.options || [];
      for (var oi = 0; oi < qOpts.length; oi++) {
        html += '<button class="bubble-option-btn' + safetyClass + '" data-q-idx="' + qi + '" data-opt-idx="' + oi + '">'
          + _esc(qOpts[oi].label)
          + (qOpts[oi].description ? '<div class="bubble-option-desc">' + _esc(qOpts[oi].description) + '</div>' : '')
          + '</button>';
      }
      html += '</div>';
    }
    html += '<button class="bubble-multi-submit" disabled>Submit All</button>';
    html += '</div>';
    return html;
  }

  function _bindMultiQuestionBubble(container, bubble) {
    var sections = container.querySelectorAll('.bubble-question-section');
    var selections = {};
    sections.forEach(function(sec) {
      var qi = parseInt(sec.getAttribute('data-q-idx'), 10);
      var isMulti = sec.getAttribute('data-multi') === '1';
      selections[qi] = isMulti ? new Set() : null;
    });

    var submitBtn = container.querySelector('.bubble-multi-submit');
    var questionCount = sections.length;

    container.querySelectorAll('.bubble-option-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        if (container.classList.contains('answered')) return;
        var qi = parseInt(btn.getAttribute('data-q-idx'), 10);
        var oi = parseInt(btn.getAttribute('data-opt-idx'), 10);
        var sec = container.querySelector('[data-q-idx="' + qi + '"].bubble-question-section');
        var isMulti = sec && sec.getAttribute('data-multi') === '1';

        if (isMulti) {
          if (selections[qi].has(oi)) {
            selections[qi].delete(oi);
            btn.classList.remove('bubble-option-selected');
          } else {
            selections[qi].add(oi);
            btn.classList.add('bubble-option-selected');
          }
        } else {
          // Radio: deselect siblings
          sec.querySelectorAll('.bubble-option-btn').forEach(function(s) {
            s.classList.remove('bubble-option-selected');
          });
          btn.classList.add('bubble-option-selected');
          selections[qi] = oi;
        }

        // Update submit button
        var allAnswered = true;
        for (var i = 0; i < questionCount; i++) {
          var m = container.querySelector('[data-q-idx="' + i + '"].bubble-question-section');
          var im = m && m.getAttribute('data-multi') === '1';
          if (im) {
            if (!selections[i] || selections[i].size === 0) { allAnswered = false; break; }
          } else {
            if (selections[i] === null || selections[i] === undefined) { allAnswered = false; break; }
          }
        }
        submitBtn.disabled = !allAnswered;
      });
    });

    submitBtn.addEventListener('click', function() {
      if (submitBtn.disabled || container.classList.contains('answered')) return;
      // Build answers
      var answers = [];
      for (var i = 0; i < questionCount; i++) {
        var sec = container.querySelector('[data-q-idx="' + i + '"].bubble-question-section');
        var isMulti = sec && sec.getAttribute('data-multi') === '1';
        if (isMulti) {
          answers.push({ option_indices: Array.from(selections[i]).sort() });
        } else {
          answers.push({ option_index: selections[i] });
        }
      }
      submitBtn.disabled = true;
      submitBtn.textContent = 'Sending...';

      fetch('/api/respond/' + _targetAgentId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'multi_select', answers: answers })
      }).then(function(resp) {
        return resp.json();
      }).then(function(data) {
        if (data.status === 'ok') {
          container.classList.add('answered');
          container.querySelectorAll('button').forEach(function(b) { b.disabled = true; });
          submitBtn.textContent = 'Submitted';
        } else {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Submit All';
        }
      }).catch(function() {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit All';
      });
    });
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
    var state = (_chatAgentState || '').toLowerCase();
    var isProcessing = state === 'processing' || state === 'commanded';
    typingEl.style.display = isProcessing ? 'block' : 'none';
    if (isProcessing) _scrollChatToBottom();
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
    _scrollChatToBottom();
  }

  function _sendChatCommand(text) {
    if (!text || !text.trim()) return;

    // Guard: if agent is not in a receptive state, don't send stale text.
    // The question may have been answered in the terminal.
    var state = (_chatAgentState || '').toLowerCase();
    if (state === 'processing' || state === 'commanded') {
      _showChatSystemMessage('Agent is processing \u2014 please wait.');
      return;
    }

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
    _chatPendingUserTexts.add(text.trim());
    _renderChatBubble(fakeTurn, prevTurn);
    _scrollChatToBottom();

    // Clear input and reset textarea height
    var input = document.getElementById('chat-text-input');
    if (input) {
      input.value = '';
      input.style.height = 'auto';
    }

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

    // Recover from false ended state: card_refresh with is_active clears ended
    if (data.is_active === true && _chatAgentEnded) {
      _chatAgentEnded = false;
      _updateEndedAgentUI();
    }

    // Check for ended agent
    if (data.agent_ended || (newState && newState.toLowerCase() === 'ended')) {
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
      // Filter to only truly new turns, dedup user echoes from chat send
      var newTurns = turns.filter(function (t) {
        if (_chatRenderedTurnIds.has(t.id)) return false;
        // Skip USER turns whose text matches a pending chat message (already shown as fake bubble)
        if (t.actor === 'user' && t.text && _chatPendingUserTexts.has(t.text.trim())) {
          _chatRenderedTurnIds.add(t.id); // mark as rendered so it won't appear later
          _chatPendingUserTexts.delete(t.text.trim());
          return false;
        }
        return true;
      });
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
      if (resp.agent_ended !== undefined) {
        var wasEnded = _chatAgentEnded;
        _chatAgentEnded = !!resp.agent_ended;
        if (_chatAgentEnded !== wasEnded) _updateEndedAgentUI();
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

  function _handleTurnCreated(data) {
    if (_currentScreen !== 'chat') return;
    if (!data || !data.agent_id) return;
    if (parseInt(data.agent_id, 10) !== parseInt(_targetAgentId, 10)) return;
    if (!data.text || !data.text.trim()) return;

    // Only handle agent turns directly — user turns are handled by
    // _handleChatSSE via transcript fetch (which includes echo dedup).
    // Processing user turns here would consume _chatPendingUserTexts
    // entries before the transcript-based dedup can use them.
    if (data.actor === 'user') return;

    // Build a turn-like object for direct rendering
    var turn = {
      id: data.turn_id || ('sse-' + Date.now()),
      actor: data.actor || 'agent',
      intent: data.intent || 'progress',
      text: data.text,
      timestamp: data.timestamp || new Date().toISOString(),
      tool_input: data.tool_input || null,
      question_text: data.text,
      question_options: null
    };

    // Extract question_options from tool_input for immediate rendering
    if (data.tool_input && data.tool_input.questions) {
      var q = data.tool_input.questions[0];
      if (q && q.options) {
        turn.question_options = q.options;
      }
    }

    // Skip if already rendered
    if (_chatRenderedTurnIds.has(turn.id)) return;

    _renderChatBubble(turn, null);
    _scrollChatToBottom();
  }

  function _handleAgentUpdate(data) {
    // Handle session_ended: remove from other agent states and re-render banners
    if (data._type === 'session_ended') {
      var endedId = data.agent_id || data.id;
      if (endedId && _otherAgentStates[endedId]) {
        delete _otherAgentStates[endedId];
        if (_currentScreen === 'chat') _renderAttentionBanners();
      }
    }

    // Update attention banners for non-target agents on chat screen
    if (_currentScreen === 'chat') {
      var agentId = data.agent_id || data.id;
      if (agentId && parseInt(agentId, 10) !== parseInt(_targetAgentId, 10)) {
        var newState = data.new_state || data.state;
        if (newState && _otherAgentStates[agentId]) {
          _otherAgentStates[agentId].state = newState.toLowerCase();
          if (data.task_instruction) _otherAgentStates[agentId].task_instruction = data.task_instruction;
          if (data.hero_chars) _otherAgentStates[agentId].hero_chars = data.hero_chars;
          if (data.hero_trail) _otherAgentStates[agentId].hero_trail = data.hero_trail;
          _renderAttentionBanners();
        } else if (newState && !_otherAgentStates[agentId]) {
          // New agent appeared via SSE — add it
          _otherAgentStates[agentId] = {
            hero_chars: data.hero_chars || '',
            hero_trail: data.hero_trail || '',
            task_instruction: data.task_instruction || '',
            state: newState.toLowerCase(),
            project_name: data.project || ''
          };
          _renderAttentionBanners();
        }
      }
    }

    // Sync state to chat if this is the target agent
    if (_currentScreen === 'chat' && _targetAgentId) {
      var updateAgentId = data.agent_id || data.id;
      if (parseInt(updateAgentId, 10) === parseInt(_targetAgentId, 10)) {
        var chatNewState = data.new_state || data.state;
        if (chatNewState) {
          var prevState = _chatAgentState;
          _chatAgentState = chatNewState;
          _updateTypingIndicator();

          // If state left AWAITING_INPUT, update question options to "answered"
          if (prevState && prevState.toLowerCase() === 'awaiting_input'
              && chatNewState.toLowerCase() !== 'awaiting_input') {
            _markAllQuestionsAnswered();
          }
        }
      }
    }

    // Update chat screen if active
    _handleChatSSE(data);

    // Polling fallback: if data is a sessions list (no agent_id), and chat
    // is active, check if the target agent's state changed
    if (!data.agent_id && !data.id && data.agents && _currentScreen === 'chat' && _targetAgentId) {
      for (var i = 0; i < data.agents.length; i++) {
        if (data.agents[i].agent_id === _targetAgentId) {
          var polledState = data.agents[i].state;
          if (polledState && polledState.toLowerCase() !== (_chatAgentState || '').toLowerCase()) {
            _chatAgentState = polledState;
            _updateTypingIndicator();
            // Fetch transcript to pick up any new turns
            VoiceAPI.getTranscript(_targetAgentId).then(function (resp) {
              var turns = resp.turns || [];
              var newTurns = turns.filter(function (t) { return !_chatRenderedTurnIds.has(t.id); });
              if (newTurns.length > 0) {
                var grouped = _groupTurns(newTurns);
                for (var j = 0; j < grouped.length; j++) {
                  var item = grouped[j];
                  var prev = j > 0 ? grouped[j - 1] : null;
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
              if (resp.agent_ended !== undefined) {
                var wasEnded = _chatAgentEnded;
                _chatAgentEnded = !!resp.agent_ended;
                if (_chatAgentEnded !== wasEnded) _updateEndedAgentUI();
              }
              _scrollChatToBottom();
            }).catch(function () { /* ignore */ });
          }
          break;
        }
      }
    }

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
      // Sync attention banners when on chat screen
      if (_currentScreen === 'chat' && _targetAgentId) {
        var agents = data.agents || [];
        _otherAgentStates = {};
        for (var i = 0; i < agents.length; i++) {
          var a = agents[i];
          if (a.agent_id !== _targetAgentId) {
            _otherAgentStates[a.agent_id] = {
              hero_chars: a.hero_chars || '',
              hero_trail: a.hero_trail || '',
              task_instruction: a.task_instruction || '',
              state: (a.state || '').toLowerCase(),
              project_name: a.project || ''
            };
          }
        }
        _renderAttentionBanners();
      }
    }).catch(function () { /* ignore */ });
  }

  // --- Connection indicator (task 2.18) ---

  var _previousConnectionState = 'disconnected';

  function _updateConnectionIndicator() {
    var el = document.getElementById('connection-status');
    if (!el) return;
    var state = VoiceAPI.getConnectionState();
    el.className = 'connection-dot ' + state;
    el.title = state;

    // On reconnect: catch up on any missed state by re-fetching
    if (state === 'connected' && _previousConnectionState !== 'connected') {
      _catchUpAfterReconnect();
      if (_currentScreen === 'chat') {
        _showChatSystemMessage('Reconnected');
      }
    }
    if (state === 'reconnecting' && _previousConnectionState === 'connected') {
      if (_currentScreen === 'chat') {
        _showChatSystemMessage('Connection lost \u2014 reconnecting\u2026');
      }
    }
    _previousConnectionState = state;
  }

  function _catchUpAfterReconnect() {
    // Always refresh agent list
    _refreshAgents();

    // If chat screen is active, re-fetch transcript to catch missed events
    if (_currentScreen === 'chat' && _targetAgentId) {
      VoiceAPI.getTranscript(_targetAgentId).then(function (resp) {
        var turns = resp.turns || [];
        var newTurns = turns.filter(function (t) {
          if (_chatRenderedTurnIds.has(t.id)) return false;
          if (t.actor === 'user' && t.text && _chatPendingUserTexts.has(t.text.trim())) {
            _chatRenderedTurnIds.add(t.id);
            _chatPendingUserTexts.delete(t.text.trim());
            return false;
          }
          return true;
        });
        if (newTurns.length > 0) {
          var grouped = _groupTurns(newTurns);
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
        if (resp.agent_ended !== undefined) {
          var wasEnded = _chatAgentEnded;
          _chatAgentEnded = !!resp.agent_ended;
          if (_chatAgentEnded !== wasEnded) _updateEndedAgentUI();
        }
        _scrollChatToBottom();
      }).catch(function () { /* ignore */ });
    }
  }

  // --- Escape HTML ---

  function _esc(s) {
    if (!s) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(s));
    return div.innerHTML;
  }

  // --- Lightweight markdown renderer for agent bubbles ---

  function _renderMd(text) {
    if (!text) return '';
    // Escape HTML first to prevent XSS
    var html = _esc(text);

    // Code blocks (``` ... ```)
    html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function(m, lang, code) {
      return '<pre class="md-code-block"><code>' + code.trim() + '</code></pre>';
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3 class="md-h3">$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2 class="md-h2">$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1 class="md-h1">$1</h1>');

    // Bold and italic
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Horizontal rules
    html = html.replace(/^---+$/gm, '<hr class="md-hr">');

    // Unordered lists
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    // Ordered lists
    html = html.replace(/^\d+\. (.+)$/gm, '<li class="md-ol-item">$1</li>');
    // Wrap consecutive list items
    html = html.replace(/(<li[^>]*>.*<\/li>\n?)+/g, function(match) {
      if (match.indexOf('md-ol-item') !== -1) {
        return '<ol class="md-ol">' + match + '</ol>';
      }
      return '<ul class="md-ul">' + match + '</ul>';
    });

    // Links
    html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(m, linkText, url) {
      if (!/^https?:\/\//i.test(url)) return _esc(linkText);
      return '<a href="' + url + '" class="md-link" target="_blank" rel="noopener">' + linkText + '</a>';
    });

    // Paragraphs (double newline)
    html = html.replace(/\n\n/g, '</p><p class="md-p">');
    html = '<p class="md-p">' + html + '</p>';
    html = html.replace(/<p class="md-p"><\/p>/g, '');

    // Single newlines -> <br> (within paragraphs, after other transforms)
    html = html.replace(/([^>])\n([^<])/g, '$1<br>$2');

    return html;
  }

  // --- Initialization ---

  function init() {
    loadSettings();

    // Close kebab menus on click outside
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.agent-kebab-btn') && !e.target.closest('.agent-kebab-menu')
          && !e.target.closest('.project-kebab-btn') && !e.target.closest('.project-kebab-menu')) {
        _closeAllKebabMenus();
      }
    });

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
    VoiceAPI.onTurnCreated(_handleTurnCreated);
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

    // Title link — navigate back to agent list
    var titleLink = document.getElementById('app-title-link');
    if (titleLink) {
      titleLink.addEventListener('click', function (e) {
        e.preventDefault();
        _refreshAgents();
        showScreen('agents');
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

    // Settings button — remember where we came from
    var settingsBtn = document.getElementById('settings-btn');
    if (settingsBtn) {
      settingsBtn.addEventListener('click', function () {
        _settingsReturnScreen = _currentScreen;
        _populateSettingsForm();
        showScreen('settings');
      });
    }

    // Settings form (task 2.26) — return to originating screen
    var settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
      settingsForm.addEventListener('submit', function (e) {
        e.preventDefault();
        _applySettingsForm();
        _returnFromSettings();
      });
    }

    // Chat input form + textarea auto-resize
    var chatForm = document.getElementById('chat-input-form');
    var chatInput = document.getElementById('chat-text-input');
    if (chatForm) {
      chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        if (chatInput && chatInput.value.trim()) {
          _sendChatCommand(chatInput.value);
          chatInput.style.height = 'auto';
        }
      });
    }
    if (chatInput) {
      // Auto-resize textarea as content grows
      chatInput.addEventListener('input', function () {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
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

    // Chat back button — pop nav stack or go to agent list
    var chatBackBtn = document.querySelector('.chat-back-btn');
    if (chatBackBtn) {
      chatBackBtn.addEventListener('click', function () {
        if (_navStack.length > 0) {
          var prevId = _navStack.pop();
          _showChatScreen(prevId);
        } else {
          _otherAgentStates = {};
          _refreshAgents();
          showScreen('agents');
        }
      });
    }

    // Back buttons (listening, question screens)
    var backBtns = document.querySelectorAll('.back-btn');
    for (var i = 0; i < backBtns.length; i++) {
      backBtns[i].addEventListener('click', function () {
        showScreen('agents');
      });
    }

    // Settings back button — contextual return
    var settingsBackBtn = document.querySelector('.settings-back-btn');
    if (settingsBackBtn) {
      settingsBackBtn.addEventListener('click', function () {
        _returnFromSettings();
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

  function _populateSettingsForm() {
    var el;

    el = document.getElementById('setting-fontsize');
    if (el) el.value = _settings.fontSize;
    var fsDisplay = document.getElementById('fontsize-value');
    if (fsDisplay) fsDisplay.textContent = _settings.fontSize + 'px';

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

    el = document.getElementById('setting-fontsize');
    if (el) setSetting('fontSize', parseInt(el.value, 10));
    _applyFontSize();

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
