/* Voice Bridge API client — HTTP + SSE + Bearer auth */
window.VoiceAPI = (function () {
  'use strict';

  let _baseUrl = '';
  let _token = '';
  let _sse = null;
  let _sseRetryDelay = 1000;
  const SSE_MAX_DELAY = 30000;
  let _pollTimer = null;
  let _connectionState = 'disconnected'; // connected | reconnecting | disconnected
  let _onConnectionChange = null;
  let _onAgentUpdate = null;
  let _onTurnCreated = null;

  function init(baseUrl, token) {
    _baseUrl = baseUrl.replace(/\/+$/, '');
    _token = token;
  }

  function getToken() { return _token; }
  function setToken(t) { _token = t; }
  function getBaseUrl() { return _baseUrl; }

  function _headers() {
    var h = { 'Content-Type': 'application/json' };
    if (_token) h['Authorization'] = 'Bearer ' + _token;
    return h;
  }

  function _setConnection(state) {
    if (state !== _connectionState) {
      _connectionState = state;
      if (_onConnectionChange) _onConnectionChange(state);
    }
  }

  function getConnectionState() { return _connectionState; }
  function onConnectionChange(fn) { _onConnectionChange = fn; }
  function onAgentUpdate(fn) { _onAgentUpdate = fn; }
  function onTurnCreated(fn) { _onTurnCreated = fn; }

  // --- HTTP helpers ---

  function _fetch(path, opts) {
    opts = opts || {};
    opts.headers = _headers();
    return fetch(_baseUrl + path, opts).then(function (r) {
      if (!r.ok) return r.json().then(function (b) { return Promise.reject(b); });
      return r.json();
    });
  }

  function getSessions(verbosity) {
    var q = verbosity ? '?verbosity=' + verbosity : '';
    return _fetch('/api/voice/sessions' + q);
  }

  function sendCommand(text, agentId) {
    var body = { text: text };
    if (agentId) body.agent_id = agentId;
    return _fetch('/api/voice/command', { method: 'POST', body: JSON.stringify(body) });
  }

  function getOutput(agentId, verbosity) {
    var q = verbosity ? '?verbosity=' + verbosity : '';
    return _fetch('/api/voice/agents/' + agentId + '/output' + q);
  }

  function getQuestion(agentId) {
    return _fetch('/api/voice/agents/' + agentId + '/question');
  }

  function getTranscript(agentId, options) {
    var params = [];
    if (options) {
      if (options.before) params.push('before=' + options.before);
      if (options.limit) params.push('limit=' + options.limit);
    }
    var q = params.length ? '?' + params.join('&') : '';
    return _fetch('/api/voice/agents/' + agentId + '/transcript' + q);
  }

  // --- SSE ---

  function connectSSE() {
    if (_sse) _sse.close();
    _stopPolling();

    var url = _baseUrl + '/api/events/stream';
    try {
      _sse = new EventSource(url);
    } catch (e) {
      _setConnection('disconnected');
      _startPolling();
      return;
    }

    _sse.onopen = function () {
      _sseRetryDelay = 1000;
      _setConnection('connected');
      _stopPolling();
    };

    _sse.addEventListener('card_refresh', function (e) {
      try {
        var data = JSON.parse(e.data);
        if (_onAgentUpdate) _onAgentUpdate(data);
      } catch (err) { /* ignore parse errors */ }
    });

    _sse.addEventListener('state_transition', function (e) {
      try {
        var data = JSON.parse(e.data);
        if (_onAgentUpdate) _onAgentUpdate(data);
      } catch (err) { /* ignore */ }
    });

    _sse.addEventListener('turn_created', function (e) {
      try {
        var data = JSON.parse(e.data);
        if (_onTurnCreated) _onTurnCreated(data);
      } catch (err) { /* ignore */ }
    });

    _sse.onerror = function () {
      _sse.close();
      _sse = null;
      _setConnection('reconnecting');
      _startPolling();
      _sseRetryDelay = Math.min(_sseRetryDelay * 2, SSE_MAX_DELAY);
      setTimeout(connectSSE, _sseRetryDelay);
    };
  }

  function disconnectSSE() {
    if (_sse) { _sse.close(); _sse = null; }
    _stopPolling();
    _setConnection('disconnected');
  }

  function _startPolling() {
    if (_pollTimer) return;
    _pollTimer = setInterval(function () {
      getSessions().then(function (data) {
        if (_onAgentUpdate) _onAgentUpdate(data);
      }).catch(function () { /* ignore */ });
    }, 5000);
  }

  function _stopPolling() {
    if (_pollTimer) { clearInterval(_pollTimer); _pollTimer = null; }
  }

  return {
    init: init,
    getToken: getToken,
    setToken: setToken,
    getBaseUrl: getBaseUrl,
    getConnectionState: getConnectionState,
    onConnectionChange: onConnectionChange,
    onAgentUpdate: onAgentUpdate,
    onTurnCreated: onTurnCreated,
    getSessions: getSessions,
    sendCommand: sendCommand,
    getOutput: getOutput,
    getQuestion: getQuestion,
    getTranscript: getTranscript,
    connectSSE: connectSSE,
    disconnectSSE: disconnectSSE
  };
})();
