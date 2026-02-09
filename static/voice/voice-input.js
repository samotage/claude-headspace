/* Voice Bridge speech input — SpeechRecognition wrapper */
window.VoiceInput = (function () {
  'use strict';

  var SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  var _recognition = null;
  var _listening = false;
  var _silenceTimeout = 800;
  var _silenceTimer = null;
  var _transcript = '';
  var _doneWords = ['send', 'over', 'done'];
  var _onResult = null;   // called with final text
  var _onPartial = null;  // called with interim text
  var _onStateChange = null; // called with true/false

  function isSupported() {
    return !!SpeechRecognition;
  }

  function setSilenceTimeout(ms) {
    ms = parseInt(ms, 10);
    if (ms >= 600 && ms <= 1200) _silenceTimeout = ms;
  }

  function getSilenceTimeout() { return _silenceTimeout; }

  function setDoneWords(words) {
    if (Array.isArray(words)) _doneWords = words;
  }

  function getDoneWords() { return _doneWords.slice(); }

  function onResult(fn) { _onResult = fn; }
  function onPartial(fn) { _onPartial = fn; }
  function onStateChange(fn) { _onStateChange = fn; }

  function _setListening(v) {
    _listening = v;
    if (_onStateChange) _onStateChange(v);
  }

  function _clearSilenceTimer() {
    if (_silenceTimer) { clearTimeout(_silenceTimer); _silenceTimer = null; }
  }

  function _finalize() {
    _clearSilenceTimer();
    var text = _transcript.trim();
    if (text && _onResult) _onResult(text);
    _transcript = '';
  }

  function _checkDoneWord(text) {
    var lower = text.toLowerCase().trim();
    for (var i = 0; i < _doneWords.length; i++) {
      var dw = _doneWords[i].toLowerCase();
      // Check if text ends with the done-word
      if (lower === dw || lower.endsWith(' ' + dw)) {
        // Strip done-word
        var stripped = text.trim();
        var re = new RegExp('\\s*' + dw + '\\s*$', 'i');
        stripped = stripped.replace(re, '').trim();
        return { matched: true, text: stripped };
      }
    }
    return { matched: false, text: text };
  }

  function _resetSilenceTimer() {
    _clearSilenceTimer();
    _silenceTimer = setTimeout(function () {
      _finalize();
      stop();
    }, _silenceTimeout);
  }

  function start() {
    if (_listening || !SpeechRecognition) return;

    _transcript = '';
    _recognition = new SpeechRecognition();
    _recognition.continuous = true;
    _recognition.interimResults = true;
    _recognition.lang = 'en-US';

    _recognition.onstart = function () {
      _setListening(true);
    };

    _recognition.onresult = function (event) {
      var interim = '';
      var finalText = '';

      for (var i = event.resultIndex; i < event.results.length; i++) {
        var result = event.results[i];
        if (result.isFinal) {
          finalText += result[0].transcript;
        } else {
          interim += result[0].transcript;
        }
      }

      if (finalText) {
        _transcript += finalText;

        // Check for done-word
        var check = _checkDoneWord(_transcript);
        if (check.matched) {
          _transcript = check.text;
          _clearSilenceTimer();
          _finalize();
          stop();
          return;
        }

        // Reset silence timer (debounce)
        _resetSilenceTimer();
      }

      if (interim && _onPartial) {
        _onPartial(_transcript + interim);
      } else if (_transcript && _onPartial) {
        _onPartial(_transcript);
      }
    };

    _recognition.onerror = function (event) {
      if (event.error === 'no-speech' || event.error === 'aborted') {
        // Not fatal
        return;
      }
      stop();
    };

    _recognition.onend = function () {
      // If still supposed to be listening but recognition ended (browser timeout),
      // finalize whatever we have
      if (_listening) {
        _finalize();
        _setListening(false);
      }
    };

    try {
      _recognition.start();
      _resetSilenceTimer();
    } catch (e) {
      _setListening(false);
    }
  }

  function stop() {
    _clearSilenceTimer();
    if (_recognition) {
      try { _recognition.stop(); } catch (e) { /* ignore */ }
      _recognition = null;
    }
    _setListening(false);
  }

  function abort() {
    _clearSilenceTimer();
    _transcript = '';
    if (_recognition) {
      try { _recognition.abort(); } catch (e) { /* ignore */ }
      _recognition = null;
    }
    _setListening(false);
  }

  function isListening() { return _listening; }

  return {
    isSupported: isSupported,
    setSilenceTimeout: setSilenceTimeout,
    getSilenceTimeout: getSilenceTimeout,
    setDoneWords: setDoneWords,
    getDoneWords: getDoneWords,
    onResult: onResult,
    onPartial: onPartial,
    onStateChange: onStateChange,
    start: start,
    stop: stop,
    abort: abort,
    isListening: isListening,
    _checkDoneWord: _checkDoneWord  // exposed for testing
  };
})();
