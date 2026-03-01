/**
 * Embed SSE — Server-Sent Events connection scoped to a single agent.
 *
 * Connects to the existing /api/events/stream endpoint with agent_id filter.
 * Handles reconnection with exponential backoff.
 */
window.EmbedSSE = (function () {
  'use strict';

  var _config = null;
  var _callbacks = null;
  var _eventSource = null;
  var _reconnectTimer = null;
  var _reconnectDelay = 1000;
  var _maxReconnectDelay = 30000;
  var _lastEventId = null;

  /**
   * Initialise SSE connection.
   * @param {Object} config - EMBED_CONFIG
   * @param {Object} callbacks - Event handlers: onTurnCreated, onCardRefresh, onStateChange, onAgentEnded, onConnected, onError
   */
  function init(config, callbacks) {
    _config = config;
    _callbacks = callbacks;
    connect();
  }

  function connect() {
    if (_eventSource) {
      _eventSource.close();
      _eventSource = null;
    }

    var url = _config.applicationUrl + '/api/events/stream?agent_id=' + _config.agentId;
    if (_lastEventId) {
      url += '&last_event_id=' + _lastEventId;
    }

    try {
      _eventSource = new EventSource(url);
    } catch (e) {
      console.error('EventSource creation failed:', e);
      scheduleReconnect();
      return;
    }

    _eventSource.onopen = function () {
      _reconnectDelay = 1000;
      if (_callbacks.onConnected) _callbacks.onConnected();
    };

    _eventSource.onerror = function () {
      console.warn('SSE connection error, scheduling reconnect');
      _eventSource.close();
      _eventSource = null;
      if (_callbacks.onError) _callbacks.onError();
      scheduleReconnect();
    };

    // Listen for named events
    _eventSource.addEventListener('turn_created', handleEvent);
    _eventSource.addEventListener('card_refresh', handleEvent);
    _eventSource.addEventListener('state_transition', handleEvent);
    _eventSource.addEventListener('turn_updated', handleEvent);
    _eventSource.addEventListener('agent_ended', handleEvent);
  }

  function handleEvent(event) {
    var data;
    try {
      data = JSON.parse(event.data);
    } catch (e) {
      return;
    }

    // Track event ID for reconnection replay
    if (event.lastEventId) {
      _lastEventId = event.lastEventId;
    }

    // Filter to our agent
    var eventAgentId = data.agent_id || data.id;
    if (eventAgentId && parseInt(eventAgentId, 10) !== _config.agentId) return;

    switch (event.type) {
      case 'turn_created':
        if (_callbacks.onTurnCreated) _callbacks.onTurnCreated(data);
        break;
      case 'card_refresh':
        if (_callbacks.onCardRefresh) _callbacks.onCardRefresh(data);
        break;
      case 'state_transition':
        if (_callbacks.onStateChange) _callbacks.onStateChange(data);
        break;
      case 'turn_updated':
        if (_callbacks.onTurnUpdated) _callbacks.onTurnUpdated(data);
        break;
      case 'agent_ended':
        if (_callbacks.onAgentEnded) _callbacks.onAgentEnded(data);
        break;
    }
  }

  function scheduleReconnect() {
    if (_reconnectTimer) return;
    _reconnectTimer = setTimeout(function () {
      _reconnectTimer = null;
      connect();
    }, _reconnectDelay);
    // Exponential backoff
    _reconnectDelay = Math.min(_reconnectDelay * 2, _maxReconnectDelay);
  }

  function disconnect() {
    if (_reconnectTimer) {
      clearTimeout(_reconnectTimer);
      _reconnectTimer = null;
    }
    if (_eventSource) {
      _eventSource.close();
      _eventSource = null;
    }
  }

  return {
    init: init,
    disconnect: disconnect,
  };
})();
