/* VoiceSettings — settings persistence, form population, and theme/font application.
 *
 * Reads/writes VoiceState.settings. Calls VoiceInput/VoiceOutput/VoiceAPI
 * to propagate setting changes.
 */
window.VoiceSettings = (function () {
  'use strict';

  var _onRefreshAgents = null; // callback set by VoiceApp.init

  function setRefreshAgentsHandler(fn) { _onRefreshAgents = fn; }

  // ---- Persistence ----

  function loadSettings() {
    var DEFAULTS = VoiceState.DEFAULTS;
    var s = {};
    try {
      var stored = localStorage.getItem('voice_settings');
      if (stored) s = JSON.parse(stored);
    } catch (e) { /* ignore */ }

    VoiceState.settings = {
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
    VoiceInput.setSilenceTimeout(VoiceState.settings.silenceTimeout);
    VoiceInput.setDoneWords([VoiceState.settings.doneWord]);
    VoiceOutput.setTTSEnabled(VoiceState.settings.ttsEnabled);
    VoiceOutput.setCuesEnabled(VoiceState.settings.cuesEnabled);
    applyFontSize();
    applyTheme();
  }

  function saveSettings() {
    try {
      localStorage.setItem('voice_settings', JSON.stringify(VoiceState.settings));
    } catch (e) { /* ignore */ }
    // Apply immediately
    VoiceInput.setSilenceTimeout(VoiceState.settings.silenceTimeout);
    VoiceInput.setDoneWords([VoiceState.settings.doneWord]);
    VoiceOutput.setTTSEnabled(VoiceState.settings.ttsEnabled);
    VoiceOutput.setCuesEnabled(VoiceState.settings.cuesEnabled);
  }

  function getSetting(key) { return VoiceState.settings[key]; }

  function setSetting(key, value) {
    VoiceState.settings[key] = value;
    saveSettings();
  }

  // ---- Visual application ----

  function applyFontSize() {
    document.documentElement.style.setProperty('--chat-font-size', VoiceState.settings.fontSize + 'px');
  }

  function applyTheme() {
    var theme = VoiceState.settings.theme || 'dark';
    if (theme === 'dark') {
      document.documentElement.removeAttribute('data-theme');
    } else {
      document.documentElement.setAttribute('data-theme', theme);
    }
    var colors = { dark: '#0d1117', warm: '#f5f0e8', cool: '#fbfaf8' };
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta && colors[theme]) meta.setAttribute('content', colors[theme]);
  }

  // ---- Settings panel ----

  function openSettings() {
    populateSettingsForm();
    var overlay = document.getElementById('settings-overlay');
    var panel = document.getElementById('settings-panel');
    if (overlay) overlay.classList.add('open');
    if (panel) panel.classList.add('open');
  }

  function closeSettings() {
    var overlay = document.getElementById('settings-overlay');
    var panel = document.getElementById('settings-panel');
    if (overlay) overlay.classList.remove('open');
    if (panel) panel.classList.remove('open');
  }

  function populateSettingsForm() {
    var el;
    var _settings = VoiceState.settings;

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

  function applySettingsForm() {
    var el;

    el = document.getElementById('setting-fontsize');
    if (el) setSetting('fontSize', parseInt(el.value, 10));
    applyFontSize();

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
      var prev = VoiceState.settings.showEndedAgents;
      setSetting('showEndedAgents', el.checked);
      if (el.checked !== prev && _onRefreshAgents) _onRefreshAgents();
    }

    el = document.getElementById('setting-url');
    if (el) setSetting('serverUrl', el.value.trim());

    el = document.getElementById('setting-token');
    if (el) setSetting('token', el.value.trim());

    // Re-init API with new settings
    VoiceAPI.init(VoiceState.settings.serverUrl, VoiceState.settings.token);
  }

  return {
    loadSettings: loadSettings,
    saveSettings: saveSettings,
    getSetting: getSetting,
    setSetting: setSetting,
    applyFontSize: applyFontSize,
    applyTheme: applyTheme,
    openSettings: openSettings,
    closeSettings: closeSettings,
    populateSettingsForm: populateSettingsForm,
    applySettingsForm: applySettingsForm,
    setRefreshAgentsHandler: setRefreshAgentsHandler
  };
})();
