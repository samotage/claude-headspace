/* Voice Bridge speech output — TTS + audio cues */
window.VoiceOutput = (function () {
  'use strict';

  var _ttsEnabled = true;
  var _cuesEnabled = true;
  var _audioCtx = null;
  var _speaking = false;
  var _queue = [];

  // Audio cue definitions: [frequency, duration_ms, type]
  var CUES = {
    ready:       [660, 150, 'sine'],
    sent:        [880, 120, 'sine'],
    'needs-input': [440, 300, 'triangle'],
    error:       [220, 400, 'sawtooth']
  };

  function _getAudioCtx() {
    if (!_audioCtx) {
      var AC = window.AudioContext || window.webkitAudioContext;
      if (AC) _audioCtx = new AC();
    }
    return _audioCtx;
  }

  function initAudio() {
    // Must be called from a user gesture to unlock audio on iOS
    var ctx = _getAudioCtx();
    if (ctx && ctx.state === 'suspended') {
      ctx.resume();
    }
  }

  function isTTSEnabled() { return _ttsEnabled; }
  function isCuesEnabled() { return _cuesEnabled; }

  function setTTSEnabled(v) {
    _ttsEnabled = !!v;
    try { localStorage.setItem('voice_tts_enabled', _ttsEnabled ? '1' : '0'); } catch (e) { /* ignore */ }
    if (!_ttsEnabled) cancelSpeech();
  }

  function setCuesEnabled(v) {
    _cuesEnabled = !!v;
    try { localStorage.setItem('voice_cues_enabled', _cuesEnabled ? '1' : '0'); } catch (e) { /* ignore */ }
  }

  function loadSettings() {
    try {
      var tts = localStorage.getItem('voice_tts_enabled');
      if (tts !== null) _ttsEnabled = tts === '1';
      var cues = localStorage.getItem('voice_cues_enabled');
      if (cues !== null) _cuesEnabled = cues === '1';
    } catch (e) { /* ignore */ }
  }

  // --- Audio cues ---

  function playCue(name) {
    if (!_cuesEnabled) return;
    var def = CUES[name];
    if (!def) return;

    var ctx = _getAudioCtx();
    if (!ctx) return;

    var osc = ctx.createOscillator();
    var gain = ctx.createGain();
    osc.type = def[2];
    osc.frequency.value = def[0];
    gain.gain.value = 0.3;
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + def[1] / 1000);
  }

  // --- TTS ---

  function speak(text, onDone) {
    if (!_ttsEnabled || !window.speechSynthesis) {
      if (onDone) onDone();
      return;
    }

    var utt = new SpeechSynthesisUtterance(text);
    utt.rate = 1.0;
    utt.pitch = 1.0;

    utt.onend = function () {
      _speaking = false;
      _processQueue();
      if (onDone) onDone();
    };
    utt.onerror = function () {
      _speaking = false;
      _processQueue();
      if (onDone) onDone();
    };

    if (_speaking) {
      _queue.push({ text: text, onDone: onDone });
      return;
    }

    _speaking = true;
    window.speechSynthesis.speak(utt);
  }

  function _processQueue() {
    if (_queue.length === 0) return;
    var next = _queue.shift();
    speak(next.text, next.onDone);
  }

  function cancelSpeech() {
    _queue = [];
    _speaking = false;
    if (window.speechSynthesis) window.speechSynthesis.cancel();
  }

  function isSpeaking() { return _speaking; }

  // --- Structured response reading ---

  function speakResponse(voiceData) {
    if (!_ttsEnabled || !voiceData) return;

    // status_line first
    if (voiceData.status_line) {
      speak(voiceData.status_line);
    }

    // pause then results
    if (voiceData.results && voiceData.results.length > 0) {
      // Small pause via empty speak won't work; just chain them
      for (var i = 0; i < voiceData.results.length; i++) {
        speak(voiceData.results[i]);
      }
    }

    // next_action last
    if (voiceData.next_action && voiceData.next_action !== 'none') {
      speak(voiceData.next_action);
    }
  }

  // Load settings on init
  loadSettings();

  return {
    initAudio: initAudio,
    isTTSEnabled: isTTSEnabled,
    isCuesEnabled: isCuesEnabled,
    setTTSEnabled: setTTSEnabled,
    setCuesEnabled: setCuesEnabled,
    loadSettings: loadSettings,
    playCue: playCue,
    speak: speak,
    speakResponse: speakResponse,
    cancelSpeech: cancelSpeech,
    isSpeaking: isSpeaking
  };
})();
