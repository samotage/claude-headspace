/* VoiceLayout — screen management, layout mode, FAB, hamburger, menu dispatch.
 *
 * Reads/writes VoiceState for screen, layout, FAB, and hamburger state.
 * Uses callbacks for dependencies on modules not yet extracted.
 */
window.VoiceLayout = (function () {
  'use strict';

  // Callbacks wired by VoiceApp.init
  var _onScreenChange = null;       // called on every showScreen (timer cleanup, connection indicator, highlight)
  var _onMenuAction = null;         // called from _handleMenuAction for project-picker/voice
  var _highlightSelected = null;    // highlight selected agent in sidebar

  function setScreenChangeHandler(fn) { _onScreenChange = fn; }
  function setMenuHandler(fn) { _onMenuAction = fn; }
  function setHighlightHandler(fn) { _highlightSelected = fn; }

  // ---- Layout mode detection ----

  function isPortrait() {
    return window.matchMedia('(orientation: portrait)').matches;
  }

  function shouldUseStackedLayout() {
    var w = window.innerWidth;
    if (w < 768) return true;
    if (isPortrait() && w < 1024) return true;
    return false;
  }

  function detectLayoutMode() {
    var newMode = shouldUseStackedLayout() ? 'stacked' : 'split';
    if (newMode !== VoiceState.layoutMode) {
      VoiceState.layoutMode = newMode;
      closeFab();
      closeHamburger();
      document.body.classList.remove('layout-stacked', 'layout-split');
      document.body.classList.add('layout-' + VoiceState.layoutMode);
      applyLayoutMode();
    }
  }

  function initLayoutMode() {
    VoiceState.layoutMode = shouldUseStackedLayout() ? 'stacked' : 'split';
    document.body.classList.add('layout-' + VoiceState.layoutMode);
    repositionStatePill();
  }

  function applyLayoutMode() {
    if (VoiceState.currentScreen === 'setup') return;
    applyScreenVisibility(VoiceState.currentScreen);
    repositionStatePill();
    if (_highlightSelected) _highlightSelected();
  }

  // Move the state pill into chat-header-info on mobile so it sits below the name,
  // and back to header-slot on desktop so it stays in the header row.
  function repositionStatePill() {
    var pill = document.getElementById('chat-state-pill');
    if (!pill) return;
    var headerInfo = document.querySelector('.chat-header-info');
    var headerSlot = document.getElementById('header-agent-slot');
    if (!headerInfo || !headerSlot) return;
    if (VoiceState.layoutMode === 'stacked') {
      // Insert right after chat-agent-name, not at the end
      var agentName = document.getElementById('chat-agent-name');
      if (agentName && pill.parentElement !== headerInfo) {
        agentName.insertAdjacentElement('afterend', pill);
      } else if (pill.parentElement !== headerInfo) {
        headerInfo.insertBefore(pill, headerInfo.firstChild);
      }
    } else {
      // Restore to header-slot, before the kebab button
      var kebab = document.getElementById('agent-chat-kebab-btn');
      if (pill.parentElement !== headerSlot) headerSlot.insertBefore(pill, kebab);
    }
  }

  // ---- Screen management ----

  function showScreen(name) {
    VoiceState.currentScreen = name;

    // Notify VoiceApp for timer cleanup, connection indicator, highlight
    if (_onScreenChange) _onScreenChange(name);

    if (name === 'setup') {
      var setupEl = document.getElementById('screen-setup');
      var layoutEl = document.getElementById('app-layout');
      if (setupEl) setupEl.classList.add('active');
      if (layoutEl) layoutEl.style.display = 'none';
      return;
    }

    var setupEl2 = document.getElementById('screen-setup');
    if (setupEl2) setupEl2.classList.remove('active');

    applyScreenVisibility(name);
    updateMainHeaderVisibility(name);
    if (_highlightSelected) _highlightSelected();
  }

  function updateMainHeaderVisibility(name) {
    var agentSlot = document.getElementById('header-agent-slot');
    var channelSlot = document.getElementById('header-channel-slot');
    var backBtn = document.querySelector('#main-header .chat-back-btn');

    var showAgent = (name === 'chat');
    var showChannel = (name === 'channel-chat');

    if (agentSlot) agentSlot.style.display = showAgent ? 'flex' : 'none';
    if (channelSlot) channelSlot.style.display = showChannel ? 'flex' : 'none';
    if (backBtn) backBtn.style.display = (showAgent || showChannel) ? '' : 'none';
  }

  function applyScreenVisibility(name) {
    var sidebar = document.getElementById('sidebar');
    var mainPanel = document.getElementById('main-panel');
    var emptyEl = document.getElementById('main-panel-empty');

    var screens = mainPanel ? mainPanel.querySelectorAll('.screen') : [];
    for (var i = 0; i < screens.length; i++) {
      screens[i].classList.remove('active');
    }
    if (emptyEl) emptyEl.classList.remove('show-empty');

    if (VoiceState.layoutMode === 'split') {
      if (sidebar) sidebar.classList.remove('show-sidebar');
      if (mainPanel) mainPanel.classList.remove('show-main');

      if (name === 'agents') {
        if (emptyEl && !VoiceState.targetAgentId) {
          emptyEl.classList.add('show-empty');
        } else if (VoiceState.targetAgentId) {
          var chatEl = document.getElementById('screen-chat');
          if (chatEl) chatEl.classList.add('active');
        }
      } else {
        var screenEl = document.getElementById('screen-' + name);
        if (screenEl) screenEl.classList.add('active');
      }
    } else {
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

  function getCurrentScreen() { return VoiceState.currentScreen; }

  // ---- FAB (split mode) ----

  function openFab() {
    if (VoiceState.fabOpen) return;
    VoiceState.fabOpen = true;
    if (VoiceState.fabCloseTimer) { clearTimeout(VoiceState.fabCloseTimer); VoiceState.fabCloseTimer = null; }
    var el = document.getElementById('fab-container');
    if (el) {
      el.classList.remove('closing');
      el.classList.add('open');
    }
  }

  function closeFab() {
    if (!VoiceState.fabOpen) return;
    VoiceState.fabOpen = false;
    var el = document.getElementById('fab-container');
    if (el) {
      el.classList.remove('open');
      el.classList.add('closing');
      if (VoiceState.fabCloseTimer) clearTimeout(VoiceState.fabCloseTimer);
      VoiceState.fabCloseTimer = setTimeout(function () {
        el.classList.remove('closing');
        VoiceState.fabCloseTimer = null;
      }, 200);
    }
  }

  function toggleFab() {
    if (VoiceState.fabOpen) { closeFab(); } else { openFab(); }
  }

  // ---- Hamburger (stacked mode) ----

  function openHamburger() {
    if (VoiceState.hamburgerOpen) return;
    VoiceState.hamburgerOpen = true;
    var dd = document.getElementById('hamburger-dropdown');
    var bd = document.getElementById('hamburger-backdrop');
    if (dd) dd.classList.add('open');
    if (bd) bd.classList.add('open');
  }

  function closeHamburger() {
    if (!VoiceState.hamburgerOpen) return;
    VoiceState.hamburgerOpen = false;
    var dd = document.getElementById('hamburger-dropdown');
    var bd = document.getElementById('hamburger-backdrop');
    if (dd) dd.classList.remove('open');
    if (bd) bd.classList.remove('open');
  }

  // ---- Menu action dispatcher ----

  function handleMenuAction(action) {
    closeFab();
    closeHamburger();
    if (action === 'settings') {
      VoiceSettings.openSettings();
    } else if (_onMenuAction) {
      _onMenuAction(action);
    }
  }

  return {
    // Layout
    initLayoutMode: initLayoutMode,
    detectLayoutMode: detectLayoutMode,
    applyLayoutMode: applyLayoutMode,
    repositionStatePill: repositionStatePill,
    // Screen
    showScreen: showScreen,
    getCurrentScreen: getCurrentScreen,
    applyScreenVisibility: applyScreenVisibility,
    updateMainHeaderVisibility: updateMainHeaderVisibility,
    // FAB
    openFab: openFab,
    closeFab: closeFab,
    toggleFab: toggleFab,
    // Hamburger
    openHamburger: openHamburger,
    closeHamburger: closeHamburger,
    // Menu
    handleMenuAction: handleMenuAction,
    // Callback wiring
    setScreenChangeHandler: setScreenChangeHandler,
    setMenuHandler: setMenuHandler,
    setHighlightHandler: setHighlightHandler
  };
})();
