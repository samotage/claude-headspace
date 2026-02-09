/* Voice Bridge main app controller */
window.VoiceApp = (function () {
  'use strict';

  // --- Settings defaults ---
  var DEFAULTS = {
    serverUrl: '',
    token: '',
    silenceTimeout: 800,
    doneWord: 'send',
    ttsEnabled: true,
    cuesEnabled: true,
    verbosity: 'normal'
  };

  var _settings = {};
  var _agents = [];
  var _targetAgentId = null;
  var _currentScreen = 'setup'; // setup | agents | listening | question | settings

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

    // Check if we have credentials
    if (!_settings.serverUrl || !_settings.token) {
      showScreen('setup');
      return;
    }

    // Initialize API
    VoiceAPI.init(_settings.serverUrl, _settings.token);

    // Wire up speech input callbacks
    VoiceInput.onResult(function (text) {
      _sendCommand(text);
    });

    VoiceInput.onPartial(function (text) {
      var el = document.getElementById('live-transcript');
      if (el) el.textContent = text;
    });

    VoiceInput.onStateChange(function (listening) {
      var btn = document.getElementById('mic-btn');
      if (btn) btn.classList.toggle('active', listening);
    });

    // Wire up SSE
    VoiceAPI.onConnectionChange(_updateConnectionIndicator);
    VoiceAPI.onAgentUpdate(_handleAgentUpdate);
    VoiceAPI.connectSSE();

    // Play ready cue
    VoiceOutput.playCue('ready');

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
          // Auto-target if possible
          var auto = _autoTarget();
          if (auto) {
            _showListeningScreen(auto);
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

    // Back buttons
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
    _esc: _esc
  };
})();
