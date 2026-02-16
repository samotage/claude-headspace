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
    fontSize: 15,
    theme: 'dark',
    showEndedAgents: false
  };

  var _settings = {};
  var _agents = [];
  var _endedAgents = [];
  var _targetAgentId = null;
  var _currentScreen = 'setup'; // setup | agents | listening | question | chat
  var _lastSeenTurnId = 0;
  var _chatPendingUserSends = [];  // {text, sentAt, fakeTurnId} — pending sends awaiting real turn
  var PENDING_SEND_TTL_MS = 10000; // 10s window for optimistic send confirmation
  var _chatAgentState = null;
  var _chatAgentStateLabel = null;
  var _chatHasMore = false;
  var _chatLoadingMore = false;
  var _chatOldestTurnId = null;
  var _chatAgentEnded = false;
  var _chatLastTaskId = null;  // Last rendered task ID — for inserting separators on task transitions
  // _chatTranscriptSeq kept for initial load guard only (stale navigation detection)
  var _chatSyncTimer = null;   // Periodic transcript sync timer (safety net)
  var _responseCatchUpTimers = []; // Aggressive post-send fetch timers
  var _isLocalhost = (location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.hostname === '::1');
  var _isTrustedNetwork = _isLocalhost
    || /^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|100\.)/.test(location.hostname)
    || /\.ts\.net$/.test(location.hostname);
  var _navStack = [];           // Stack of agent IDs for back navigation
  var _otherAgentStates = {};   // Map: agentId -> {hero_chars, hero_trail, task_instruction, state, project_name}
  var _pendingAttachment = null; // File object pending upload
  var _pendingBlobUrl = null;    // Blob URL for image preview (revoke on clear)
  var _pendingNewAgentProject = null; // Project name when awaiting a newly created agent to appear

  // Per-agent scroll position memory (in-memory, dies with tab)
  var _agentScrollState = {};        // agentId -> { scrollTop, scrollHeight, lastTurnId }
  var _newMessagesPillVisible = false;
  var _newMessagesFirstTurnId = null;

  // Layout mode state
  var _layoutMode = 'stacked'; // 'stacked' | 'split'
  var SPLIT_BREAKPOINT = 768;

  // FAB / Hamburger / Project Picker state
  var _fabOpen = false;
  var _hamburgerOpen = false;
  var _projectPickerOpen = false;
  var _allProjects = [];
  var _fabCloseTimer = null;

  // File upload constants now in VoiceState

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
      fontSize: s.fontSize || DEFAULTS.fontSize,
      theme: s.theme || DEFAULTS.theme,
      showEndedAgents: s.showEndedAgents !== undefined ? s.showEndedAgents : DEFAULTS.showEndedAgents
    };

    // Apply to modules
    VoiceInput.setSilenceTimeout(_settings.silenceTimeout);
    VoiceInput.setDoneWords([_settings.doneWord]);
    VoiceOutput.setTTSEnabled(_settings.ttsEnabled);
    VoiceOutput.setCuesEnabled(_settings.cuesEnabled);
    _applyFontSize();
    _applyTheme();
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

  function _applyTheme() {
    var theme = _settings.theme || 'dark';
    if (theme === 'dark') {
      document.documentElement.removeAttribute('data-theme');
    } else {
      document.documentElement.setAttribute('data-theme', theme);
    }
    var colors = { dark: '#0d1117', warm: '#f5f0e8', cool: '#fbfaf8' };
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta && colors[theme]) meta.setAttribute('content', colors[theme]);
  }

  // --- Layout mode detection ---

  function _isPortrait() {
    return window.matchMedia('(orientation: portrait)').matches;
  }

  function _shouldUseStackedLayout() {
    var w = window.innerWidth;
    if (w < 768) return true;   // Phone: always stacked
    if (_isPortrait() && w < 1024) return true;  // Tablet portrait: stacked
    return false;  // Desktop or tablet landscape: split
  }

  function _detectLayoutMode() {
    var newMode = _shouldUseStackedLayout() ? 'stacked' : 'split';
    if (newMode !== _layoutMode) {
      _layoutMode = newMode;
      _closeFab();
      _closeHamburger();
      document.body.classList.remove('layout-stacked', 'layout-split');
      document.body.classList.add('layout-' + _layoutMode);
      _applyLayoutMode();
    }
  }

  function _initLayoutMode() {
    _layoutMode = _shouldUseStackedLayout() ? 'stacked' : 'split';
    document.body.classList.add('layout-' + _layoutMode);
  }

  function _applyLayoutMode() {
    // Re-apply current screen visibility for the new layout mode
    if (_currentScreen === 'setup') return; // setup is outside app-layout
    _applyScreenVisibility(_currentScreen);
    _highlightSelectedAgent();
  }

  // --- Screen management ---

  function showScreen(name) {
    _currentScreen = name;
    // Stop chat sync timer when leaving chat screen
    if (name !== 'chat') { _stopChatSyncTimer(); _cancelResponseCatchUp(); document.title = 'Claude Chat'; }

    if (name === 'setup') {
      // Setup screen is outside app-layout, hide app-layout
      var setupEl = document.getElementById('screen-setup');
      var layoutEl = document.getElementById('app-layout');
      if (setupEl) setupEl.classList.add('active');
      if (layoutEl) layoutEl.style.display = 'none';
      _updateConnectionIndicator();
      return;
    }

    // Hide setup, show app-layout
    var setupEl2 = document.getElementById('screen-setup');
    if (setupEl2) setupEl2.classList.remove('active');

    _applyScreenVisibility(name);
    _updateMainHeaderVisibility(name);
    _updateConnectionIndicator();
    _highlightSelectedAgent();
  }

  function _updateMainHeaderVisibility(name) {
    var chatScreen = document.getElementById('screen-chat');
    var emptyEl = document.getElementById('main-panel-empty');
    var focusLink = document.getElementById('chat-focus-link');
    var statePill = document.getElementById('chat-state-pill');
    var showingChat = chatScreen && chatScreen.classList.contains('active');
    if (focusLink) focusLink.style.display = showingChat ? '' : 'none';
    if (statePill) statePill.style.display = showingChat ? '' : 'none';
  }

  function _applyScreenVisibility(name) {
    var sidebar = document.getElementById('sidebar');
    var mainPanel = document.getElementById('main-panel');
    var emptyEl = document.getElementById('main-panel-empty');

    // Hide all screens in main-panel
    var screens = mainPanel ? mainPanel.querySelectorAll('.screen') : [];
    for (var i = 0; i < screens.length; i++) {
      screens[i].classList.remove('active');
    }
    if (emptyEl) emptyEl.classList.remove('show-empty');

    if (_layoutMode === 'split') {
      // Split mode: sidebar always visible, main panel shows content
      if (sidebar) {
        sidebar.classList.remove('show-sidebar');
      }
      if (mainPanel) {
        mainPanel.classList.remove('show-main');
      }

      if (name === 'agents') {
        // Show empty placeholder in main panel (no agent selected yet)
        if (emptyEl && !_targetAgentId) {
          emptyEl.classList.add('show-empty');
        } else if (_targetAgentId) {
          // If an agent was selected, show the chat
          var chatEl = document.getElementById('screen-chat');
          if (chatEl) chatEl.classList.add('active');
        }
      } else {
        // Show the requested screen in main panel
        var screenEl = document.getElementById('screen-' + name);
        if (screenEl) screenEl.classList.add('active');
      }
    } else {
      // Stacked mode: show one panel at a time
      if (name === 'agents') {
        if (sidebar) sidebar.classList.add('show-sidebar');
        if (mainPanel) mainPanel.classList.remove('show-main');
      } else {
        if (sidebar) sidebar.classList.remove('show-sidebar');
        if (mainPanel) mainPanel.classList.add('show-main');
        var screenEl2 = document.getElementById('screen-' + name);
        if (screenEl2) screenEl2.classList.add('active');
      }
    }
  }

  function getCurrentScreen() { return _currentScreen; }

  // --- Settings slide-out panel ---

  function _openSettings() {
    _populateSettingsForm();
    var overlay = document.getElementById('settings-overlay');
    var panel = document.getElementById('settings-panel');
    if (overlay) overlay.classList.add('open');
    if (panel) panel.classList.add('open');
  }

  function _closeSettings() {
    var overlay = document.getElementById('settings-overlay');
    var panel = document.getElementById('settings-panel');
    if (overlay) overlay.classList.remove('open');
    if (panel) panel.classList.remove('open');
  }

  // --- FAB (split mode) ---

  function _openFab() {
    if (_fabOpen) return;
    _fabOpen = true;
    if (_fabCloseTimer) { clearTimeout(_fabCloseTimer); _fabCloseTimer = null; }
    var el = document.getElementById('fab-container');
    if (el) {
      el.classList.remove('closing');
      el.classList.add('open');
    }
  }

  function _closeFab() {
    if (!_fabOpen) return;
    _fabOpen = false;
    var el = document.getElementById('fab-container');
    if (el) {
      el.classList.remove('open');
      el.classList.add('closing');
      if (_fabCloseTimer) clearTimeout(_fabCloseTimer);
      _fabCloseTimer = setTimeout(function () {
        el.classList.remove('closing');
        _fabCloseTimer = null;
      }, 200);
    }
  }

  function _toggleFab() {
    if (_fabOpen) { _closeFab(); } else { _openFab(); }
  }

  // --- Hamburger (stacked mode) ---

  function _openHamburger() {
    if (_hamburgerOpen) return;
    _hamburgerOpen = true;
    var dd = document.getElementById('hamburger-dropdown');
    var bd = document.getElementById('hamburger-backdrop');
    if (dd) dd.classList.add('open');
    if (bd) bd.classList.add('open');
  }

  function _closeHamburger() {
    if (!_hamburgerOpen) return;
    _hamburgerOpen = false;
    var dd = document.getElementById('hamburger-dropdown');
    var bd = document.getElementById('hamburger-backdrop');
    if (dd) dd.classList.remove('open');
    if (bd) bd.classList.remove('open');
  }

  // --- Menu action dispatcher ---

  function _handleMenuAction(action) {
    _closeFab();
    _closeHamburger();
    if (action === 'new-chat') {
      _openProjectPicker();
    } else if (action === 'settings') {
      _openSettings();
    } else if (action === 'voice') {
      _triggerVoiceFromMenu();
    } else if (action === 'close') {
      window.location.href = '/';
    }
  }

  // --- Voice from FAB/hamburger ---

  function _triggerVoiceFromMenu() {
    VoiceOutput.initAudio();
    if (VoiceInput.isListening()) {
      _stopListening();
      return;
    }
    if (_settings.autoTarget) {
      var auto = _autoTarget();
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

  // --- Project Picker ---

  function _openProjectPicker() {
    _projectPickerOpen = true;
    var bd = document.getElementById('project-picker-backdrop');
    var pk = document.getElementById('project-picker');
    var search = document.getElementById('project-picker-search');
    if (bd) bd.classList.add('open');
    if (pk) pk.classList.add('open');
    if (search) { search.value = ''; search.focus(); }
    _fetchProjects();
  }

  function _closeProjectPicker() {
    _projectPickerOpen = false;
    var bd = document.getElementById('project-picker-backdrop');
    var pk = document.getElementById('project-picker');
    if (bd) bd.classList.remove('open');
    if (pk) pk.classList.remove('open');
  }

  function _fetchProjects() {
    var list = document.getElementById('project-picker-list');
    if (list) list.innerHTML = '<div class="project-picker-empty">Loading\u2026</div>';
    VoiceAPI.getProjects().then(function (data) {
      _allProjects = Array.isArray(data) ? data : [];
      _renderProjectList(_allProjects);
    }).catch(function () {
      _allProjects = [];
      if (list) list.innerHTML = '<div class="project-picker-empty">Failed to load projects</div>';
    });
  }

  function _renderProjectList(projects) {
    var list = document.getElementById('project-picker-list');
    if (!list) return;

    if (!projects || projects.length === 0) {
      list.innerHTML = '<div class="project-picker-empty">No projects found</div>';
      return;
    }

    // Sort: projects with active agents first, then alphabetical
    var sorted = projects.slice().sort(function (a, b) {
      var aCount = a.agent_count || 0;
      var bCount = b.agent_count || 0;
      if (aCount > 0 && bCount === 0) return -1;
      if (aCount === 0 && bCount > 0) return 1;
      return (a.name || '').localeCompare(b.name || '');
    });

    var html = '';
    for (var i = 0; i < sorted.length; i++) {
      var p = sorted[i];
      var count = p.agent_count || 0;
      var badgeClass = count === 0 ? 'project-picker-badge zero' : 'project-picker-badge';
      var shortPath = (p.path || '').replace(/^\/Users\/[^/]+\//, '~/');
      html += '<div class="project-picker-row" data-project-name="' + _esc(p.name) + '">'
        + '<div class="project-picker-info">'
        + '<div class="project-picker-name">' + _esc(p.name) + '</div>'
        + '<div class="project-picker-path">' + _esc(shortPath) + '</div>'
        + '</div>'
        + '<span class="' + badgeClass + '">' + count + ' agent' + (count !== 1 ? 's' : '') + '</span>'
        + '</div>';
    }
    list.innerHTML = html;

    // Bind click handlers
    var rows = list.querySelectorAll('.project-picker-row');
    for (var r = 0; r < rows.length; r++) {
      rows[r].addEventListener('click', function () {
        var name = this.getAttribute('data-project-name');
        _onProjectPicked(this, name);
      });
    }
  }

  function _filterProjectList(query) {
    if (!query) {
      _renderProjectList(_allProjects);
      return;
    }
    var q = query.toLowerCase();
    var filtered = _allProjects.filter(function (p) {
      return (p.name || '').toLowerCase().indexOf(q) !== -1;
    });
    _renderProjectList(filtered);
  }

  function _onProjectPicked(rowEl, projectName) {
    if (rowEl) rowEl.classList.add('creating');
    _closeProjectPicker();
    _createAgentForProject(projectName);
  }

  // --- Agent highlighting in sidebar ---

  function _highlightSelectedAgent() {
    var cards = document.querySelectorAll('.agent-card');
    for (var i = 0; i < cards.length; i++) {
      var id = parseInt(cards[i].getAttribute('data-agent-id'), 10);
      cards[i].classList.toggle('selected', id === _targetAgentId && _layoutMode === 'split');
    }
  }

  // --- Agent list (tasks 2.20, 2.23, 2.24) ---

  function _renderAgentList(agents, endedAgents) {
    // Detect newly appeared agents before overwriting _agents
    var oldIds = {};
    for (var oi = 0; oi < _agents.length; oi++) {
      oldIds[_agents[oi].agent_id] = true;
    }

    _agents = agents || [];
    var list = document.getElementById('agent-list');
    if (!list) return;

    // Auto-select a newly created agent when it first appears
    if (_pendingNewAgentProject) {
      for (var ni = 0; ni < _agents.length; ni++) {
        var a = _agents[ni];
        if (!oldIds[a.agent_id] && (a.project || '').toLowerCase() === _pendingNewAgentProject.toLowerCase()) {
          var newAgentId = a.agent_id;
          _pendingNewAgentProject = null;
          // Defer selection until after render completes
          setTimeout(function () { _selectAgent(newAgentId); }, 0);
          break;
        }
      }
    }

    // Save scroll position before re-render
    var sidebar = document.getElementById('sidebar');
    var savedScroll = sidebar ? sidebar.scrollTop : 0;

    // Group ended agents by project
    var endedByProject = {};
    if (endedAgents && endedAgents.length) {
      for (var ei = 0; ei < endedAgents.length; ei++) {
        var ep = endedAgents[ei].project || 'unknown';
        if (!endedByProject[ep]) endedByProject[ep] = [];
        endedByProject[ep].push(endedAgents[ei]);
      }
    }

    var hasEnded = Object.keys(endedByProject).length > 0;

    if (_agents.length === 0 && !hasEnded) {
      list.innerHTML = '<div class="empty-state">No active agents</div>';
      return;
    }

    // Group agents by project, newest first within each group
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
    // Add projects that only have ended agents
    for (var endedProj in endedByProject) {
      if (!projectGroups[endedProj]) {
        projectGroups[endedProj] = [];
        projectOrder.push(endedProj);
      }
    }
    // Sort each group: newest agent first (highest agent_id)
    for (var si = 0; si < projectOrder.length; si++) {
      projectGroups[projectOrder[si]].sort(function (a, b) {
        return b.agent_id - a.agent_id;
      });
    }

    // Helper to build a single agent card's HTML
    function _buildCardHtml(a, isEnded) {
      var stateClass = isEnded ? 'state-ended' : 'state-' + (a.state || '').toLowerCase();
      var stateLabel = isEnded ? 'Ended' : (a.state_label || a.state || 'unknown');
      var heroChars = a.hero_chars || '';
      var heroTrail = a.hero_trail || '';

      var instructionHtml = a.task_instruction
        ? '<div class="agent-instruction">' + _esc(a.task_instruction) + '</div>'
        : '';

      var summaryText = '';
      if (a.task_completion_summary) {
        summaryText = a.task_completion_summary;
      } else if (a.task_summary && a.task_summary !== a.task_instruction) {
        summaryText = a.task_summary;
      }
      var summaryHtml = summaryText
        ? '<div class="agent-summary">' + _esc(summaryText) + '</div>'
        : '';

      // Context usage display
      var ctxHtml = '';
      if (a.context && a.context.percent_used != null) {
        var pct = a.context.percent_used;
        var ctxClass = 'ctx-normal';
        if (pct >= 75) ctxClass = 'ctx-high';
        else if (pct >= 65) ctxClass = 'ctx-warning';
        ctxHtml = '<span class="agent-ctx-inline ' + ctxClass + '">'
          + pct + '% · ' + (a.context.remaining_tokens || '?') + ' rem</span>';
      }

      var footerParts = [];
      if (a.turn_count && a.turn_count > 0) {
        footerParts.push(a.turn_count + ' turn' + (a.turn_count !== 1 ? 's' : ''));
      }
      if (isEnded && a.ended_at) {
        var endedDate = new Date(a.ended_at);
        var endedElapsed = (Date.now() - endedDate.getTime()) / 1000;
        if (endedElapsed < 60) footerParts.push('ended ' + Math.floor(endedElapsed) + 's ago');
        else if (endedElapsed < 3600) footerParts.push('ended ' + Math.floor(endedElapsed / 60) + 'm ago');
        else footerParts.push('ended ' + Math.floor(endedElapsed / 3600) + 'h ago');
      } else {
        footerParts.push(a.last_activity_ago);
      }

      var selectedClass = (_layoutMode === 'split' && a.agent_id === _targetAgentId) ? ' selected' : '';
      var endedClass = isEnded ? ' ended' : '';

      // Kebab menu: ended agents only get "Fetch context"
      var kebabMenuHtml;
      if (isEnded) {
        kebabMenuHtml = '<div class="agent-kebab-menu" data-agent-id="' + a.agent_id + '">'
          + '<button class="kebab-menu-item agent-ctx-action" data-agent-id="' + a.agent_id + '">'
          + '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.5"/><path d="M8 5v3.5L10.5 10"/></svg>'
          + '<span>Fetch context</span></button>'
          + '</div>';
      } else {
        kebabMenuHtml = '<div class="agent-kebab-menu" data-agent-id="' + a.agent_id + '">'
          + '<button class="kebab-menu-item agent-ctx-action" data-agent-id="' + a.agent_id + '">'
          + '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.5"/><path d="M8 5v3.5L10.5 10"/></svg>'
          + '<span>Fetch context</span></button>'
          + '<div class="kebab-divider"></div>'
          + '<button class="kebab-menu-item agent-kill-action" data-agent-id="' + a.agent_id + '">'
          + '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l10 10M13 3L3 13"/></svg>'
          + '<span>Dismiss agent</span></button>'
          + '</div>';
      }

      return '<div class="agent-card ' + stateClass + selectedClass + endedClass + '" data-agent-id="' + a.agent_id + '">'
        + '<div class="agent-header">'
        + '<a class="agent-card-link" href="/voice?agent_id=' + a.agent_id + '">'
        + '<div class="agent-hero-id">'
        + '<span class="agent-hero">' + _esc(heroChars) + '</span>'
        + '<span class="agent-hero-trail">' + _esc(heroTrail) + '</span>'
        + '</div>'
        + '</a>'
        + '<div class="agent-header-actions">'
        + '<span class="agent-state ' + stateClass + '">' + _esc(stateLabel) + '</span>'
        + '<button class="agent-kebab-btn" data-agent-id="' + a.agent_id + '" title="Actions">&#8942;</button>'
        + kebabMenuHtml
        + '</div>'
        + '</div>'
        + '<a class="agent-card-link" href="/voice?agent_id=' + a.agent_id + '">'
        + '<div class="agent-body">'
        + instructionHtml
        + summaryHtml
        + '<div class="agent-ago">' + _esc(footerParts.join(' · ')) + (ctxHtml ? ' ' + ctxHtml : '') + '</div>'
        + '</div>'
        + '</a>'
        + '</div>';
    }

    var html = '';
    for (var p = 0; p < projectOrder.length; p++) {
      var projName = projectOrder[p];
      var group = projectGroups[projName];
      var endedGroup = endedByProject[projName] || [];

      html += '<div class="project-group">'
        + '<div class="project-group-header">'
        + '<span class="project-group-name">' + _esc(projName) + '</span>'
        + '<button class="project-kebab-btn" data-project="' + _esc(projName) + '" title="Project actions">&#8942;</button>'
        + '<div class="project-kebab-menu" data-project="' + _esc(projName) + '">'
        + '<button class="kebab-menu-item project-add-agent" data-project="' + _esc(projName) + '">'
        + '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3v10M3 8h10"/></svg>'
        + '<span>Add agent</span></button>'
        + '</div>'
        + '</div>'
        + '<div class="project-group-cards">';

      // Active agents
      for (var j = 0; j < group.length; j++) {
        html += _buildCardHtml(group[j], false);
      }

      // Ended agents (with divider if there are active agents above)
      if (endedGroup.length > 0) {
        if (group.length > 0) {
          html += '<div class="ended-divider"></div>';
        }
        for (var ej = 0; ej < endedGroup.length; ej++) {
          html += _buildCardHtml(endedGroup[ej], true);
        }
      }

      html += '</div></div>';
    }
    list.innerHTML = html;

    // Restore scroll position
    if (sidebar) sidebar.scrollTop = savedScroll;

    // Bind click handlers for agent selection
    var cards = list.querySelectorAll('.agent-card');
    for (var j = 0; j < cards.length; j++) {
      cards[j].addEventListener('click', _onAgentCardClick);
    }
    // Prevent default on card links for regular clicks (SPA navigation),
    // but allow right-click / cmd+click to open in new tab natively
    var cardLinks = list.querySelectorAll('.agent-card-link');
    for (var cl = 0; cl < cardLinks.length; cl++) {
      cardLinks[cl].addEventListener('click', function (e) {
        e.preventDefault();
      });
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
    _navStack = [];
    _showChatScreen(id);
  }

  function _checkAgentContext(agentId) {
    // API persists context to agent record and broadcasts card_refresh via SSE
    VoiceAPI.getAgentContext(agentId).then(function (data) {
      if (!data.available) {
        console.warn('Context unavailable for agent ' + agentId + ': ' + (data.reason || 'unknown'));
      }
    }).catch(function () {
      console.error('Error checking context for agent ' + agentId);
    });
  }

  function _shutdownAgent(agentId) {
    if (typeof ConfirmDialog !== 'undefined') {
      ConfirmDialog.show(
        'Shut down agent?',
        'This will send /exit to the agent.',
        { confirmText: 'Shut down', cancelText: 'Cancel' }
      ).then(function (confirmed) {
        if (!confirmed) return;
        VoiceAPI.shutdownAgent(agentId).then(function () {
          _refreshAgents();
        }).catch(function (err) {
          if (window.Toast) {
            Toast.error('Shutdown failed', err.error || 'unknown error');
          } else {
            alert('Shutdown failed: ' + (err.error || 'unknown error'));
          }
        });
      });
    } else {
      if (!confirm('Shut down this agent?')) return;
      VoiceAPI.shutdownAgent(agentId).then(function () {
        _refreshAgents();
      }).catch(function (err) {
        alert('Shutdown failed: ' + (err.error || 'unknown error'));
      });
    }
  }

  function _createAgentForProject(projectName) {
    _pendingNewAgentProject = projectName;
    _showPendingAgentPlaceholder(projectName);
    VoiceAPI.createAgent(projectName).then(function (data) {
      _showToast('Agent starting\u2026');
      _refreshAgents();
    }).catch(function (err) {
      _pendingNewAgentProject = null;
      _removePendingAgentPlaceholder();
      if (window.Toast) {
        Toast.error('Create failed', err.error || 'unknown error');
      } else {
        alert('Create failed: ' + (err.error || 'unknown error'));
      }
    });
  }

  function _showPendingAgentPlaceholder(projectName) {
    var list = document.getElementById('agent-list');
    if (!list) return;
    // Find the project group matching this project
    var groups = list.querySelectorAll('.project-group');
    var targetGroup = null;
    for (var i = 0; i < groups.length; i++) {
      var nameEl = groups[i].querySelector('.project-group-name');
      if (nameEl && nameEl.textContent.trim().toLowerCase() === projectName.toLowerCase()) {
        targetGroup = groups[i];
        break;
      }
    }
    // If no matching group exists (project has 0 agents), create a temporary one
    if (!targetGroup) {
      targetGroup = document.createElement('div');
      targetGroup.className = 'project-group';
      targetGroup.id = 'pending-project-group';
      targetGroup.innerHTML = '<div class="project-group-header">'
        + '<span class="project-group-name">' + _esc(projectName) + '</span>'
        + '</div>'
        + '<div class="project-group-cards"></div>';
      list.prepend(targetGroup);
    }
    // Remove any existing placeholder
    _removePendingAgentPlaceholder();
    // Append placeholder card
    var cardsContainer = targetGroup.querySelector('.project-group-cards');
    if (!cardsContainer) return;
    var placeholder = document.createElement('div');
    placeholder.className = 'agent-card agent-card-pending';
    placeholder.id = 'pending-agent-placeholder';
    placeholder.innerHTML = '<div class="agent-header">'
      + '<div class="agent-hero-id">'
      + '<span class="agent-hero">\u2026</span>'
      + '</div>'
      + '</div>'
      + '<div class="agent-body">'
      + '<div class="agent-instruction pending-pulse">Starting agent\u2026</div>'
      + '</div>';
    cardsContainer.prepend(placeholder);
  }

  function _removePendingAgentPlaceholder() {
    var el = document.getElementById('pending-agent-placeholder');
    if (el) el.remove();
    // Also remove the temporary project group if it was created
    var tempGroup = document.getElementById('pending-project-group');
    if (tempGroup) tempGroup.remove();
  }

  function _showToast(message) {
    // Lightweight inline toast for voice app (no dependency on dashboard Toast)
    var existing = document.getElementById('voice-toast');
    if (existing) existing.remove();
    var toast = document.createElement('div');
    toast.id = 'voice-toast';
    toast.className = 'voice-toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    // Trigger animation
    requestAnimationFrame(function () {
      toast.classList.add('show');
    });
    setTimeout(function () {
      toast.classList.remove('show');
      setTimeout(function () { toast.remove(); }, 300);
    }, 3000);
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
          html += '<button class="option-btn" data-label="' + _esc(opt.label) + '" data-opt-idx="' + i + '">'
            + '<strong>' + _esc(opt.label) + '</strong>'
            + (opt.description ? '<br><span class="option-desc">' + _esc(opt.description) + '</span>' : '')
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
    var focusLink = document.getElementById('chat-focus-link');
    if (focusLink) focusLink.setAttribute('data-agent-id', agentId);
    _lastSeenTurnId = 0;
    _chatPendingUserSends = [];
    _chatHasMore = false;
    _chatLoadingMore = false;
    _chatOldestTurnId = null;
    _chatAgentEnded = false;
    _chatLastTaskId = null;
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

    var initAgentId = agentId;
    VoiceAPI.getTranscript(agentId).then(function (data) {
      if (initAgentId !== _targetAgentId) return; // Stale response — user navigated away
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
      _renderTranscriptTurns(data);
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

    showScreen('chat');
    _highlightSelectedAgent();
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
        _chatLastTaskId = item.task_id;
      } else {
        _renderChatBubble(item, prev);
        if (item.task_id) _chatLastTaskId = item.task_id;
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

      // Synthetic task boundary from backend (task with no turns)
      if (turn.type === 'task_boundary') {
        if (currentGroup) { result.push(currentGroup); currentGroup = null; }
        result.push({
          type: 'separator',
          task_instruction: turn.task_instruction || 'New task',
          task_id: turn.task_id,
          has_turns: false
        });
        lastTaskId = turn.task_id;
        continue;
      }

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
    if (item.task_id) sep.setAttribute('data-task-id', item.task_id);
    var label = _esc(item.task_instruction);
    if (item.has_turns === false) {
      label += ' <span class="separator-no-activity">(no captured activity)</span>';
    }
    sep.innerHTML = '<span>' + label + '</span>';
    return sep;
  }

  /**
   * Check if a turn crosses a task boundary and insert a separator if needed.
   * Updates _chatLastTaskId. Call this BEFORE rendering the turn bubble.
   */
  function _maybeInsertTaskSeparator(turn) {
    if (!turn.task_id) return;
    if (_chatLastTaskId && turn.task_id !== _chatLastTaskId) {
      // Check if a separator for this task already exists in DOM
      var messagesEl = document.getElementById('chat-messages');
      if (messagesEl && !messagesEl.querySelector('.chat-task-separator[data-task-id="' + turn.task_id + '"]')) {
        var sepEl = _createTaskSeparatorEl({
          task_instruction: turn.task_instruction || 'New task',
          task_id: turn.task_id
        });
        // Append at end — separators appear in real-time as new tasks arrive
        messagesEl.appendChild(sepEl);
      }
    }
    _chatLastTaskId = turn.task_id;
  }

  /**
   * Insert a bubble element (or fragment) at the correct chronological
   * position based on data-timestamp. Walks backwards through existing
   * bubbles to find the insertion point.
   *
   * @param {Element} messagesEl - The chat messages container
   * @param {Element|DocumentFragment} el - Bubble element or fragment containing one
   */
  function _insertBubbleOrdered(messagesEl, el) {
    // Extract timestamp: fragments don't have getAttribute, so find the bubble child
    var bubbleChild = el.querySelector ? el.querySelector('.chat-bubble[data-timestamp]') : null;
    var ts = bubbleChild ? bubbleChild.getAttribute('data-timestamp') : null;
    if (!ts) {
      // No timestamp — append at end as fallback
      messagesEl.appendChild(el);
      return;
    }
    var tsDate = new Date(ts);
    // Walk backwards through existing timestamped bubbles
    var existing = messagesEl.querySelectorAll('.chat-bubble[data-timestamp]');
    for (var i = existing.length - 1; i >= 0; i--) {
      var existingTs = new Date(existing[i].getAttribute('data-timestamp'));
      if (existingTs <= tsDate) {
        // Insert after this element (before its next sibling)
        var next = existing[i].nextSibling;
        if (next) {
          messagesEl.insertBefore(el, next);
        } else {
          messagesEl.appendChild(el);
        }
        return;
      }
    }
    // Oldest element — insert at the very beginning (after any load-more indicator)
    var loadMore = document.getElementById('chat-load-more');
    if (loadMore && loadMore.nextSibling) {
      messagesEl.insertBefore(el, loadMore.nextSibling);
    } else if (messagesEl.firstChild) {
      messagesEl.insertBefore(el, messagesEl.firstChild);
    } else {
      messagesEl.appendChild(el);
    }
  }

  /**
   * Reorder a bubble in the DOM if its timestamp has changed.
   * Checks if the bubble is already in the correct position relative
   * to its siblings; if not, removes and re-inserts it.
   */
  function _reorderBubble(bubble) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl || !bubble.parentNode) return;
    var ts = bubble.getAttribute('data-timestamp');
    if (!ts) return;
    var tsDate = new Date(ts);

    // Check if position is correct: previous sibling (if any) should have ts <= ours,
    // next sibling (if any) should have ts >= ours
    var prev = bubble.previousElementSibling;
    var next = bubble.nextElementSibling;

    var prevOk = true;
    var nextOk = true;
    if (prev && prev.classList.contains('chat-bubble') && prev.getAttribute('data-timestamp')) {
      prevOk = new Date(prev.getAttribute('data-timestamp')) <= tsDate;
    }
    if (next && next.classList.contains('chat-bubble') && next.getAttribute('data-timestamp')) {
      nextOk = new Date(next.getAttribute('data-timestamp')) >= tsDate;
    }

    if (prevOk && nextOk) return; // Already in correct position

    // Remove and re-insert at correct position
    bubble.parentNode.removeChild(bubble);
    _insertBubbleOrdered(messagesEl, bubble);
  }

  function _renderChatBubble(turn, prevTurn, forceRender) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    var el = _createBubbleEl(turn, prevTurn, forceRender);
    if (el) _insertBubbleOrdered(messagesEl, el);
  }

  function _createBubbleEl(turn, prevTurn, forceRender) {
    // DOM-based dedup: check if this turn is already rendered
    var container = document.getElementById('chat-messages');
    if (container && container.querySelector('[data-turn-id="' + turn.id + '"]')) {
      if (!forceRender) return null;
    }
    // Track max turn ID for scroll state and gap recovery
    var numId = typeof turn.id === 'number' ? turn.id : parseInt(turn.id, 10);
    if (!isNaN(numId) && numId > _lastSeenTurnId) _lastSeenTurnId = numId;
    // Track grouped IDs too
    var ids = turn.groupedIds || [];
    for (var k2 = 0; k2 < ids.length; k2++) {
      var gid = typeof ids[k2] === 'number' ? ids[k2] : parseInt(ids[k2], 10);
      if (!isNaN(gid) && gid > _lastSeenTurnId) _lastSeenTurnId = gid;
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
    bubble.setAttribute('data-timestamp', turn.timestamp || new Date().toISOString());
    if (turn.task_id) bubble.setAttribute('data-task-id', turn.task_id);

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

    // File attachment rendering
    if (turn.file_metadata) {
      var fm = turn.file_metadata;
      if (fm.file_type === 'image') {
        var imgUrl = fm._localPreviewUrl || fm.serving_url || '';
        if (imgUrl) {
          html += '<div class="bubble-file-image" data-full-url="' + _esc(imgUrl) + '">'
            + '<img src="' + _esc(imgUrl) + '" alt="' + _esc(fm.original_filename || 'Image') + '" loading="lazy">'
            + '</div>';
        }
      } else {
        var cardUrl = fm.serving_url || '#';
        html += '<a class="bubble-file-card" href="' + _esc(cardUrl) + '" target="_blank" rel="noopener">'
          + '<span class="file-card-icon">' + _getFileTypeIcon(fm.original_filename || '') + '</span>'
          + '<div class="file-card-info">'
          + '<div class="file-card-name">' + _esc(fm.original_filename || 'File') + '</div>'
          + '<div class="file-card-size">' + _formatFileSize(fm.file_size || 0) + '</div>'
          + '</div></a>';
      }
    }

    // Plan content — render collapsible plan above question options
    if (turn.intent === 'question') {
      var toolInput = turn.tool_input || {};
      if (toolInput.plan_content) {
        html += '<div class="bubble-plan-content">';
        html += '<details open>';
        html += '<summary class="plan-toggle">Plan Details'
          + (toolInput.plan_file_path ? ' <span class="plan-file-path">' + _esc(toolInput.plan_file_path.split('/').pop()) + '</span>' : '')
          + '</summary>';
        html += '<div class="plan-body">' + _renderMd(toolInput.plan_content) + '</div>';
        html += '</details>';
        html += '</div>';
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
          html += '<button class="bubble-option-btn' + safetyClass + '" data-opt-idx="' + i + '" data-label="' + _esc(opt.label) + '">'
            + _esc(opt.label)
            + (opt.description ? '<div class="bubble-option-desc">' + _esc(opt.description) + '</div>' : '')
            + '</button>';
        }
        html += '</div>';
      }
    }

    // Copy button for agent bubbles with text content
    if (!isUser && displayText) {
      bubble.setAttribute('data-raw-md', displayText);
      html = '<button class="bubble-copy-btn" aria-label="Copy markdown" title="Copy">'
        + '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        + '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/>'
        + '<path d="M10.5 5.5V3.5a1.5 1.5 0 0 0-1.5-1.5H3.5A1.5 1.5 0 0 0 2 3.5V9a1.5 1.5 0 0 0 1.5 1.5h2"/>'
        + '</svg>'
        + '</button>' + html;
    }

    bubble.innerHTML = html;

    // Bind copy button click
    var copyBtn = bubble.querySelector('.bubble-copy-btn');
    if (copyBtn) {
      copyBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var rawMd = bubble.getAttribute('data-raw-md');
        if (!rawMd) return;
        navigator.clipboard.writeText(rawMd).then(function () {
          copyBtn.classList.add('copied');
          copyBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            + '<polyline points="3.5 8.5 6.5 11.5 12.5 4.5"/>'
            + '</svg>';
          setTimeout(function () {
            copyBtn.classList.remove('copied');
            copyBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
              + '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/>'
              + '<path d="M10.5 5.5V3.5a1.5 1.5 0 0 0-1.5-1.5H3.5A1.5 1.5 0 0 0 2 3.5V9a1.5 1.5 0 0 0 1.5 1.5h2"/>'
              + '</svg>';
          }, 1500);
        }).catch(function (err) { console.warn('Clipboard copy failed:', err); });
      });
    }

    // Bind image thumbnail click -> open in lightbox
    var imgThumb = bubble.querySelector('.bubble-file-image');
    if (imgThumb) {
      imgThumb.addEventListener('click', function () {
        var url = this.getAttribute('data-full-url');
        var alt = (this.querySelector('img') || {}).alt || 'Image';
        if (url) _openImageLightbox(url, alt);
      });
    }

    // Bind option button clicks
    var multiContainer = bubble.querySelector('.bubble-multi-question');
    if (multiContainer) {
      _bindMultiQuestionBubble(multiContainer, bubble);
    } else {
      var optBtns = bubble.querySelectorAll('.bubble-option-btn');
      for (var j = 0; j < optBtns.length; j++) {
        optBtns[j].addEventListener('click', function () {
          var idx = parseInt(this.getAttribute('data-opt-idx'), 10);
          var label = this.getAttribute('data-label');
          _sendChatSelect(idx, label, bubble);
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
      lastTurnId: _lastSeenTurnId
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
    _renderChatBubble(fakeTurn, prevTurn);
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
      errBubble.innerHTML = '<div class="bubble-intent">Error</div><div class="bubble-text">' + _esc(err.error || 'Send failed') + '</div>';
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
      errBubble.innerHTML = '<div class="bubble-intent">Error</div><div class="bubble-text">' + _esc(err.error || 'Select failed') + '</div>';
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
    if (_currentScreen !== 'chat') return;

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
      setTimeout(function () { _refreshAgents(); showScreen('agents'); }, 1500);
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
      setTimeout(function () { _refreshAgents(); showScreen('agents'); }, 1500);
    }).catch(function (err) {
      VoiceOutput.playCue('error');
      if (status) status.textContent = 'Error: ' + (err.error || 'Select failed');
    });
  }

  // --- SSE event handling ---

  function _handleGap(data) {
    // Server detected dropped events — do a full refresh to catch up
    _refreshAgents();
    if (_currentScreen === 'chat' && _targetAgentId) {
      _fetchTranscriptForChat();
    }
  }

  function _handleTurnUpdated(data) {
    if (_currentScreen !== 'chat') return;
    if (!data || !data.agent_id) return;
    if (parseInt(data.agent_id, 10) !== parseInt(_targetAgentId, 10)) return;

    if (data.update_type === 'timestamp_correction' && data.turn_id) {
      var bubble = document.querySelector('[data-turn-id="' + data.turn_id + '"]');
      if (bubble && data.timestamp) {
        bubble.setAttribute('data-timestamp', data.timestamp);
        _reorderBubble(bubble);
      }
    }
  }

  function _handleTurnCreated(data) {
    if (_currentScreen !== 'chat') return;
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
    _maybeInsertTaskSeparator(turn);

    _renderChatBubble(turn, null, isTerminalIntent);
    _scrollChatToBottomIfNear();
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
    if (!data.agent_id && !data.id && data.agents && _currentScreen === 'chat' && _targetAgentId) {
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
      window._sseReloadDeferred = function () { _refreshAgents(); };
    } else {
      _refreshAgents();
    }

    // Play cue if an agent transitions to awaiting_input
    if (data && data.new_state === 'awaiting_input') {
      VoiceOutput.playCue('needs-input');
    }
  }

  function _refreshAgents() {
    VoiceAPI.getSessions(_settings.verbosity, _settings.showEndedAgents).then(function (data) {
      _endedAgents = data.ended_agents || [];
      _renderAgentList(data.agents || [], _endedAgents);
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
      if (_connectionLostShown && _currentScreen === 'chat') {
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
            if (_currentScreen === 'chat') {
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
    _refreshAgents();

    // If chat screen is active, re-fetch transcript to catch missed events
    if (_currentScreen === 'chat' && _targetAgentId) {
      _fetchTranscriptForChat();

      // Deferred stops create turns 0.5-5s after the initial stop hook.
      // If we reconnected during that gap the first fetch finds nothing.
      // A second fetch 3s later catches those late-arriving turns.
      var deferredAgentId = _targetAgentId;
      setTimeout(function () {
        if (_currentScreen === 'chat' && _targetAgentId === deferredAgentId) {
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
            messagesContainer.appendChild(_createTaskSeparatorEl(t));
          }
          _chatLastTaskId = t.task_id;
          continue;
        }

        // Track max turn ID for gap recovery
        var numId = typeof t.id === 'number' ? t.id : parseInt(t.id, 10);
        if (!isNaN(numId) && numId > _lastSeenTurnId) _lastSeenTurnId = numId;

        // Check if this turn is already in the DOM
        var existingBubble = messagesContainer
          ? messagesContainer.querySelector('[data-turn-id="' + t.id + '"]')
          : null;

        if (existingBubble) {
          // Already rendered — update timestamp if changed, reorder if needed
          var currentTs = existingBubble.getAttribute('data-timestamp');
          if (t.timestamp && currentTs !== t.timestamp) {
            existingBubble.setAttribute('data-timestamp', t.timestamp);
            _reorderBubble(existingBubble);
          }
          // Still track task ID for boundary detection
          if (t.task_id) _chatLastTaskId = t.task_id;
        } else {
          // Insert task separator if this turn starts a new task
          _maybeInsertTaskSeparator(t);
          // Not in DOM — render at correct chronological position
          var prev = ti > 0 ? turns[ti - 1] : null;
          var forceTerminal = (t.intent === 'completion' || t.intent === 'end_of_task');
          _renderChatBubble(t, prev, forceTerminal);
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

  // --- Escape HTML ---

  // --- Image Lightbox ---

  function _openImageLightbox(url, alt) {
    var lb = document.getElementById('image-lightbox');
    var img = document.getElementById('lightbox-img');
    if (!lb || !img) return;
    img.src = url;
    img.alt = alt || 'Image';
    lb.style.display = 'flex';
  }

  function _closeImageLightbox() {
    var lb = document.getElementById('image-lightbox');
    var img = document.getElementById('lightbox-img');
    if (!lb) return;
    lb.style.display = 'none';
    if (img) img.src = '';
  }

  (function _initImageLightbox() {
    document.addEventListener('click', function (e) {
      var lb = document.getElementById('image-lightbox');
      if (!lb || lb.style.display === 'none') return;
      if (e.target.classList.contains('image-lightbox-backdrop') ||
          e.target.classList.contains('image-lightbox-close')) {
        _closeImageLightbox();
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') _closeImageLightbox();
    });
  })();

  function _esc(s) {
    if (!s) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(s));
    return div.innerHTML;
  }

  // --- Markdown renderer for agent bubbles (delegates to marked.js via CHUtils) ---

  function _renderMd(text) {
    return CHUtils.renderMarkdown(text);
  }

  // --- Initialization ---

  function init() {
    loadSettings();

    // Initialize layout mode
    _initLayoutMode();

    // Listen for resize and orientation to switch layout modes
    var _resizeTimer = null;
    window.addEventListener('resize', function () {
      clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(_detectLayoutMode, 100);
    });
    window.addEventListener('orientationchange', function () {
      clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(_detectLayoutMode, 100);
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
        _closeAllKebabMenus();
      }
    }
    document.addEventListener('click', _handleCloseKebabs);
    document.addEventListener('touchstart', _handleCloseKebabs, { passive: true });

    // Detect agent_id URL param (from dashboard "Chat" link)
    var urlParams = new URLSearchParams(window.location.search);
    var paramAgentId = urlParams.get('agent_id');

    // Trusted network (localhost, LAN, Tailscale): skip setup, use current origin
    if (_isTrustedNetwork && (!_settings.serverUrl || !_settings.token)) {
      _settings.serverUrl = window.location.origin;
      _settings.token = _isLocalhost ? 'localhost' : 'lan';
      saveSettings();
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
      _refreshAgents();
      if (_currentScreen === 'chat' && _targetAgentId) {
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

    // Title link — navigate back to agent list (or show sidebar in split mode)
    var titleLink = document.getElementById('app-title-link');
    if (titleLink) {
      titleLink.addEventListener('click', function (e) {
        e.preventDefault();
        if (_currentScreen === 'chat' && _targetAgentId) {
          _saveScrollState(_targetAgentId);
        }
        _refreshAgents();
        showScreen('agents');
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
        _toggleFab();
      });
    }
    var fabBackdrop = document.getElementById('fab-backdrop');
    if (fabBackdrop) {
      fabBackdrop.addEventListener('click', function () { _closeFab(); });
    }
    // FAB menu items
    var fabItems = document.querySelectorAll('.fab-menu-item');
    for (var fi = 0; fi < fabItems.length; fi++) {
      fabItems[fi].addEventListener('click', function (e) {
        e.stopPropagation();
        _handleMenuAction(this.getAttribute('data-action'));
      });
    }

    // --- Hamburger (stacked mode) ---
    var hamburgerBtn = document.getElementById('hamburger-btn');
    if (hamburgerBtn) {
      hamburgerBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (_hamburgerOpen) { _closeHamburger(); } else { _openHamburger(); }
      });
    }
    var hamburgerBackdrop = document.getElementById('hamburger-backdrop');
    if (hamburgerBackdrop) {
      hamburgerBackdrop.addEventListener('click', function () { _closeHamburger(); });
    }
    var hamburgerItems = document.querySelectorAll('.hamburger-item');
    for (var hi = 0; hi < hamburgerItems.length; hi++) {
      hamburgerItems[hi].addEventListener('click', function () {
        _handleMenuAction(this.getAttribute('data-action'));
      });
    }

    // --- Project Picker ---
    var pickerClose = document.getElementById('project-picker-close');
    if (pickerClose) {
      pickerClose.addEventListener('click', function () { _closeProjectPicker(); });
    }
    var pickerBackdrop = document.getElementById('project-picker-backdrop');
    if (pickerBackdrop) {
      pickerBackdrop.addEventListener('click', function () { _closeProjectPicker(); });
    }
    var pickerSearch = document.getElementById('project-picker-search');
    if (pickerSearch) {
      pickerSearch.addEventListener('input', function () {
        _filterProjectList(this.value.trim());
      });
    }

    // --- Escape key handler ---
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        if (_projectPickerOpen) { _closeProjectPicker(); e.preventDefault(); return; }
        if (_fabOpen) { _closeFab(); e.preventDefault(); return; }
        if (_hamburgerOpen) { _closeHamburger(); e.preventDefault(); return; }
      }
    });

    // Close FAB on outside click
    document.addEventListener('click', function (e) {
      if (_fabOpen && !e.target.closest('.fab-container')) {
        _closeFab();
      }
    });

    // Settings close button
    var settingsCloseBtn = document.getElementById('settings-close-btn');
    if (settingsCloseBtn) {
      settingsCloseBtn.addEventListener('click', function () {
        _closeSettings();
      });
    }

    // Settings overlay click — close
    var settingsOverlay = document.getElementById('settings-overlay');
    if (settingsOverlay) {
      settingsOverlay.addEventListener('click', function () {
        _closeSettings();
      });
    }

    // Settings form — save and close
    var settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
      settingsForm.addEventListener('submit', function (e) {
        e.preventDefault();
        _applySettingsForm();
        _closeSettings();
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
        if (_layoutMode === 'split') {
          // In split mode, back from listening/question goes to chat or agents
          if (_targetAgentId) {
            _showChatScreen(_targetAgentId);
          } else {
            showScreen('agents');
          }
        } else {
          showScreen('agents');
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
        setSetting('theme', theme);
        _applyTheme();
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

    // Theme chips
    var themeSelector = document.getElementById('theme-selector');
    if (themeSelector) {
      var chips = themeSelector.querySelectorAll('.theme-chip');
      for (var tc = 0; tc < chips.length; tc++) {
        chips[tc].classList.toggle('active', chips[tc].getAttribute('data-theme') === _settings.theme);
      }
    }

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

    el = document.getElementById('setting-ended');
    if (el) el.checked = _settings.showEndedAgents;

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

    el = document.getElementById('setting-ended');
    if (el) {
      var prev = _settings.showEndedAgents;
      setSetting('showEndedAgents', el.checked);
      if (el.checked !== prev) _refreshAgents();
    }

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
