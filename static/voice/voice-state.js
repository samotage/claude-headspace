/* VoiceState — shared mutable state for all voice modules.
 *
 * All 40+ state variables live here, exposed via getters/setters on the
 * return object.  Getters ensure live reads from the closure (a plain
 * `var x = VoiceState.foo` at module-load time would capture null forever).
 *
 * Nothing else should declare mutable state that crosses module boundaries.
 */
window.VoiceState = (function () {
  'use strict';

  // ---- Settings defaults ----
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

  // ---- Agents & Navigation ----
  var _agents = [];
  var _endedAgents = [];
  var _targetAgentId = null;
  var _navStack = [];
  var _otherAgentStates = {};
  var _pendingNewAgentProject = null;

  // ---- Screen & Layout ----
  var _currentScreen = 'setup';
  var _layoutMode = 'stacked';
  var SPLIT_BREAKPOINT = 768;

  // ---- UI Overlays ----
  var _fabOpen = false;
  var _hamburgerOpen = false;
  var _projectPickerOpen = false;
  var _allProjects = [];
  var _fabCloseTimer = null;

  // ---- Chat Session ----
  var _lastSeenTurnId = 0;
  var _chatPendingUserSends = [];
  var PENDING_SEND_TTL_MS = 10000;
  var _chatAgentState = null;
  var _chatAgentStateLabel = null;
  var _chatHasMore = false;
  var _chatLoadingMore = false;
  var _chatOldestTurnId = null;
  var _chatAgentEnded = false;
  var _chatLastCommandId = null;

  // ---- Timers & Guards ----
  var _chatSyncTimer = null;
  var _responseCatchUpTimers = [];
  var _fetchDebounceTimer = null;
  var _fetchInFlight = false;

  // ---- Scroll & Pills ----
  var _agentScrollState = {};
  var _newMessagesPillVisible = false;
  var _newMessagesFirstTurnId = null;

  // ---- File Upload ----
  var _pendingAttachment = null;
  var _pendingBlobUrl = null;

  // ---- Connection ----
  var _previousConnectionState = 'disconnected';
  var _connectionLostTimer = null;
  var _connectionLostShown = false;

  // ---- File Upload Constants ----
  var ALLOWED_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/gif', 'image/webp'];
  var ALLOWED_MIME_TYPES = [
    'image/png', 'image/jpeg', 'image/gif', 'image/webp',
    'application/pdf',
    'text/plain', 'text/markdown', 'text/x-python', 'text/javascript',
    'text/html', 'text/css', 'text/csv', 'text/yaml',
    'application/json', 'application/x-yaml',
  ];
  var ALLOWED_EXTENSIONS = [
    'png', 'jpg', 'jpeg', 'gif', 'webp', 'pdf',
    'txt', 'md', 'py', 'js', 'ts', 'json', 'yaml', 'yml',
    'html', 'css', 'rb', 'sh', 'sql', 'csv', 'log'
  ];
  var MAX_FILE_SIZE = 10 * 1024 * 1024;

  // ---- Computed Constants ----
  var _isLocalhost = (location.hostname === 'localhost' || location.hostname === '127.0.0.1' || location.hostname === '::1');
  var _isTrustedNetwork = _isLocalhost
    || /^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.|100\.)/.test(location.hostname)
    || /\.ts\.net$/.test(location.hostname);

  // ---- State Labels ----
  var _STATE_LABELS = {
    idle: 'Idle',
    commanded: 'Command received',
    processing: 'Processing\u2026',
    awaiting_input: 'Input needed',
    complete: 'Complete',
    timed_out: 'Timed out'
  };

  // ---- Atomic reset for chat session state ----
  function resetChatState() {
    _lastSeenTurnId = 0;
    _chatPendingUserSends = [];
    _chatAgentState = null;
    _chatAgentStateLabel = null;
    _chatHasMore = false;
    _chatLoadingMore = false;
    _chatOldestTurnId = null;
    _chatAgentEnded = false;
    _chatLastCommandId = null;
    _chatSyncTimer = null;
    _newMessagesPillVisible = false;
    _newMessagesFirstTurnId = null;
  }

  // ---- Public API (getters/setters for live reads) ----
  return {
    // Constants (read-only)
    get DEFAULTS() { return DEFAULTS; },
    get SPLIT_BREAKPOINT() { return SPLIT_BREAKPOINT; },
    get PENDING_SEND_TTL_MS() { return PENDING_SEND_TTL_MS; },
    get ALLOWED_IMAGE_TYPES() { return ALLOWED_IMAGE_TYPES; },
    get ALLOWED_MIME_TYPES() { return ALLOWED_MIME_TYPES; },
    get ALLOWED_EXTENSIONS() { return ALLOWED_EXTENSIONS; },
    get MAX_FILE_SIZE() { return MAX_FILE_SIZE; },
    get STATE_LABELS() { return _STATE_LABELS; },
    get isLocalhost() { return _isLocalhost; },
    get isTrustedNetwork() { return _isTrustedNetwork; },

    // Settings
    get settings() { return _settings; },
    set settings(v) { _settings = v; },

    // Agents & Navigation
    get agents() { return _agents; },
    set agents(v) { _agents = v; },
    get endedAgents() { return _endedAgents; },
    set endedAgents(v) { _endedAgents = v; },
    get targetAgentId() { return _targetAgentId; },
    set targetAgentId(v) { _targetAgentId = v; },
    get navStack() { return _navStack; },
    set navStack(v) { _navStack = v; },
    get otherAgentStates() { return _otherAgentStates; },
    set otherAgentStates(v) { _otherAgentStates = v; },
    get pendingNewAgentProject() { return _pendingNewAgentProject; },
    set pendingNewAgentProject(v) { _pendingNewAgentProject = v; },

    // Screen & Layout
    get currentScreen() { return _currentScreen; },
    set currentScreen(v) { _currentScreen = v; },
    get layoutMode() { return _layoutMode; },
    set layoutMode(v) { _layoutMode = v; },

    // UI Overlays
    get fabOpen() { return _fabOpen; },
    set fabOpen(v) { _fabOpen = v; },
    get hamburgerOpen() { return _hamburgerOpen; },
    set hamburgerOpen(v) { _hamburgerOpen = v; },
    get projectPickerOpen() { return _projectPickerOpen; },
    set projectPickerOpen(v) { _projectPickerOpen = v; },
    get allProjects() { return _allProjects; },
    set allProjects(v) { _allProjects = v; },
    get fabCloseTimer() { return _fabCloseTimer; },
    set fabCloseTimer(v) { _fabCloseTimer = v; },

    // Chat Session
    get lastSeenTurnId() { return _lastSeenTurnId; },
    set lastSeenTurnId(v) { _lastSeenTurnId = v; },
    get chatPendingUserSends() { return _chatPendingUserSends; },
    set chatPendingUserSends(v) { _chatPendingUserSends = v; },
    get chatAgentState() { return _chatAgentState; },
    set chatAgentState(v) { _chatAgentState = v; },
    get chatAgentStateLabel() { return _chatAgentStateLabel; },
    set chatAgentStateLabel(v) { _chatAgentStateLabel = v; },
    get chatHasMore() { return _chatHasMore; },
    set chatHasMore(v) { _chatHasMore = v; },
    get chatLoadingMore() { return _chatLoadingMore; },
    set chatLoadingMore(v) { _chatLoadingMore = v; },
    get chatOldestTurnId() { return _chatOldestTurnId; },
    set chatOldestTurnId(v) { _chatOldestTurnId = v; },
    get chatAgentEnded() { return _chatAgentEnded; },
    set chatAgentEnded(v) { _chatAgentEnded = v; },
    get chatLastCommandId() { return _chatLastCommandId; },
    set chatLastCommandId(v) { _chatLastCommandId = v; },

    // Timers & Guards
    get chatSyncTimer() { return _chatSyncTimer; },
    set chatSyncTimer(v) { _chatSyncTimer = v; },
    get responseCatchUpTimers() { return _responseCatchUpTimers; },
    set responseCatchUpTimers(v) { _responseCatchUpTimers = v; },
    get fetchDebounceTimer() { return _fetchDebounceTimer; },
    set fetchDebounceTimer(v) { _fetchDebounceTimer = v; },
    get fetchInFlight() { return _fetchInFlight; },
    set fetchInFlight(v) { _fetchInFlight = v; },

    // Scroll & Pills
    get agentScrollState() { return _agentScrollState; },
    set agentScrollState(v) { _agentScrollState = v; },
    get newMessagesPillVisible() { return _newMessagesPillVisible; },
    set newMessagesPillVisible(v) { _newMessagesPillVisible = v; },
    get newMessagesFirstTurnId() { return _newMessagesFirstTurnId; },
    set newMessagesFirstTurnId(v) { _newMessagesFirstTurnId = v; },

    // File Upload
    get pendingAttachment() { return _pendingAttachment; },
    set pendingAttachment(v) { _pendingAttachment = v; },
    get pendingBlobUrl() { return _pendingBlobUrl; },
    set pendingBlobUrl(v) { _pendingBlobUrl = v; },

    // Connection
    get previousConnectionState() { return _previousConnectionState; },
    set previousConnectionState(v) { _previousConnectionState = v; },
    get connectionLostTimer() { return _connectionLostTimer; },
    set connectionLostTimer(v) { _connectionLostTimer = v; },
    get connectionLostShown() { return _connectionLostShown; },
    set connectionLostShown(v) { _connectionLostShown = v; },

    // Methods
    resetChatState: resetChatState
  };
})();
