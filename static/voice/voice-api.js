/* Voice Bridge API client — HTTP + SSE + Bearer auth */
window.VoiceAPI = (function () {
  'use strict';

  let _baseUrl = '';
  let _token = '';
  let _sse = null;
  let _sseRetryDelay = 1000;
  const SSE_MAX_DELAY = 30000;
  const FETCH_TIMEOUT_MS = 30000;
  const UPLOAD_TIMEOUT_MS = 60000;
  let _pollTimer = null;
  let _reconnectTimer = null;  // Guard against stacked reconnects
  let _connectionState = 'disconnected'; // connected | reconnecting | disconnected
  let _onConnectionChange = null;
  let _onAgentUpdate = null;
  let _onTurnCreated = null;
  let _onGap = null;

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
  function onGap(fn) { _onGap = fn; }

  // --- HTTP helpers ---

  function _fetch(path, opts) {
    opts = opts || {};
    opts.headers = _headers();

    // Add AbortController timeout for all fetch calls
    var controller = new AbortController();
    var timeoutId = setTimeout(function () { controller.abort(); }, FETCH_TIMEOUT_MS);
    opts.signal = controller.signal;

    return fetch(_baseUrl + path, opts).then(function (r) {
      clearTimeout(timeoutId);
      if (!r.ok) return r.json().then(function (b) { return Promise.reject(b); });
      return r.json();
    }).catch(function (err) {
      clearTimeout(timeoutId);
      if (err.name === 'AbortError') {
        return Promise.reject({ error: 'Request timed out' });
      }
      return Promise.reject(err);
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

  function createAgent(projectIdOrName) {
    var body = {};
    if (typeof projectIdOrName === 'number') {
      body.project_id = projectIdOrName;
    } else {
      body.project_name = projectIdOrName;
    }
    return _fetch('/api/voice/agents/create', { method: 'POST', body: JSON.stringify(body) });
  }

  function shutdownAgent(agentId) {
    return _fetch('/api/voice/agents/' + agentId + '/shutdown', { method: 'POST' });
  }

  function getAgentContext(agentId) {
    return _fetch('/api/voice/agents/' + agentId + '/context');
  }

  /**
   * Upload a file to share with an agent.
   * Uses XMLHttpRequest for upload progress events.
   *
   * @param {number} agentId - Target agent ID
   * @param {File} file - File object to upload
   * @param {string} [text] - Optional text to send with the file
   * @param {function} [onProgress] - Progress callback: fn(percent)
   * @returns {Promise<object>} - Response data with file_metadata
   */
  function uploadFile(agentId, file, text, onProgress) {
    return new Promise(function (resolve, reject) {
      var xhr = new XMLHttpRequest();
      var formData = new FormData();
      formData.append('file', file);
      if (text) formData.append('text', text);

      xhr.open('POST', _baseUrl + '/api/voice/agents/' + agentId + '/upload');
      if (_token) xhr.setRequestHeader('Authorization', 'Bearer ' + _token);

      // Timeout for upload requests (Finding 9)
      xhr.timeout = UPLOAD_TIMEOUT_MS;

      xhr.upload.onprogress = function (e) {
        if (e.lengthComputable && onProgress) {
          var pct = Math.round((e.loaded / e.total) * 100);
          onProgress(pct);
        }
      };

      xhr.onload = function () {
        try {
          var data = JSON.parse(xhr.responseText);
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(data);
          } else {
            reject(data);
          }
        } catch (e) {
          reject({ error: 'Parse error' });
        }
      };

      xhr.onerror = function () {
        reject({ error: 'Network error' });
      };

      xhr.ontimeout = function () {
        reject({ error: 'Upload timed out' });
      };

      xhr.send(formData);
    });
  }

  // --- SSE ---

  function connectSSE() {
    if (_sse) _sse.close();
    _stopPolling();
    _clearReconnectTimer();

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

    _sse.addEventListener('state_changed', function (e) {
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

    _sse.addEventListener('session_ended', function (e) {
      try {
        var data = JSON.parse(e.data);
        data._type = 'session_ended';
        if (_onAgentUpdate) _onAgentUpdate(data);
      } catch (err) { /* ignore */ }
    });

    _sse.addEventListener('session_created', function (e) {
      try {
        var data = JSON.parse(e.data);
        data._type = 'session_created';
        if (_onAgentUpdate) _onAgentUpdate(data);
      } catch (err) { /* ignore */ }
    });

    // Gap event: server detected dropped events for this client
    _sse.addEventListener('gap', function (e) {
      try {
        var data = JSON.parse(e.data);
        if (_onGap) _onGap(data);
      } catch (err) { /* ignore */ }
    });

    _sse.onerror = function () {
      _sse.close();
      _sse = null;
      _setConnection('reconnecting');
      _startPolling();

      // Guard against stacked reconnect timers: clear any existing
      // timer before scheduling a new one.
      _clearReconnectTimer();
      _sseRetryDelay = Math.min(_sseRetryDelay * 2, SSE_MAX_DELAY);
      _reconnectTimer = setTimeout(connectSSE, _sseRetryDelay);
    };
  }

  function _clearReconnectTimer() {
    if (_reconnectTimer) {
      clearTimeout(_reconnectTimer);
      _reconnectTimer = null;
    }
  }

  function disconnectSSE() {
    _clearReconnectTimer();
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

  function focusAgent(agentId) {
    return _fetch('/api/focus/' + agentId, { method: 'POST' });
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
    onGap: onGap,
    getSessions: getSessions,
    sendCommand: sendCommand,
    getOutput: getOutput,
    getQuestion: getQuestion,
    getTranscript: getTranscript,
    createAgent: createAgent,
    shutdownAgent: shutdownAgent,
    getAgentContext: getAgentContext,
    uploadFile: uploadFile,
    connectSSE: connectSSE,
    disconnectSSE: disconnectSSE,
    focusAgent: focusAgent
  };
})();
