/* Voice Bridge main app controller */
window.VoiceApp = (function () {
  'use strict';

  // --- Voice from FAB/hamburger ---

  function _triggerVoiceFromMenu() {
    VoiceOutput.initAudio();
    if (VoiceInput.isListening()) {
      _stopListening();
      return;
    }
    if (VoiceState.settings.autoTarget) {
      var auto = VoiceSidebar.autoTarget();
      if (auto) { _showListeningScreen(auto); }
    }
    if (!VoiceState.targetAgentId) {
      var agentStatus = document.getElementById('agent-status-message');
      if (agentStatus) {
        agentStatus.textContent = 'Select an agent first';
        setTimeout(function () { agentStatus.textContent = ''; }, 2000);
      }
      return;
    }
    _startListening();
  }

  // --- Listening / Command mode ---

  function _showListeningScreen(agent) {
    var el = document.getElementById('listening-target');
    if (el && agent) el.textContent = agent.project;
    VoiceLayout.showScreen('listening');
  }

  function _startListening() {
    VoiceOutput.initAudio(); // unlock audio context on user gesture
    VoiceInput.start();
  }

  function _stopListening() {
    VoiceInput.stop();
  }

  // --- Question / Response mode ---

  function _loadQuestion(agentId) {
    VoiceAPI.getQuestion(agentId).then(function (data) {
      _renderQuestion(data);
      VoiceLayout.showScreen('question');
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
          html += '<button class="option-btn" data-label="' + VoiceChatRenderer.esc(opt.label) + '" data-opt-idx="' + i + '">'
            + '<strong>' + VoiceChatRenderer.esc(opt.label) + '</strong>'
            + (opt.description ? '<br><span class="option-desc">' + VoiceChatRenderer.esc(opt.description) + '</span>' : '')
            + '</button>';
        }
        optionsEl.innerHTML = html;

        var btns = optionsEl.querySelectorAll('.option-btn');
        for (var j = 0; j < btns.length; j++) {
          btns[j].addEventListener('click', function () {
            var idx = parseInt(this.getAttribute('data-opt-idx'), 10);
            VoiceChatController.sendSelect(idx);
          });
        }
      }
    } else {
      // Free-text question
      if (optionsEl) optionsEl.style.display = 'none';
      if (freeEl) freeEl.style.display = 'block';
    }
  }

  // --- Initialization ---

  function init() {
    // Wire callbacks before loading settings
    VoiceSettings.setRefreshAgentsHandler(VoiceSidebar.refreshAgents);
    VoiceLayout.setScreenChangeHandler(function (name) {
      if (name !== 'chat') { document.title = 'Claude Chat'; }
      VoiceSSEHandler.updateConnectionIndicator();
    });
    VoiceLayout.setHighlightHandler(VoiceSidebar.highlightSelectedAgent);
    VoiceLayout.setMenuHandler(function (action) {
      if (action === 'new-chat') {
        VoiceSidebar.openProjectPicker();
      } else if (action === 'voice') {
        _triggerVoiceFromMenu();
      } else if (action === 'close') {
        window.location.href = '/';
      }
    });
    VoiceChatRenderer.setOptionSelectHandler(VoiceChatController.sendChatSelect);
    VoiceChatRenderer.setNavigateToBannerHandler(VoiceChatController.navigateToAgentFromBanner);
    VoiceSidebar.setAgentSelectedHandler(function (id) { VoiceChatController.showChatScreen(id); });
    VoiceSSEHandler.setUpdateTypingHandler(VoiceChatController.updateTypingIndicator);
    VoiceSSEHandler.setUpdateStatePillHandler(VoiceChatController.updateChatStatePill);
    VoiceSSEHandler.setUpdateEndedUIHandler(VoiceChatController.updateEndedAgentUI);
    VoiceSSEHandler.setScrollChatHandler(function (nearOnly) {
      if (nearOnly) { VoiceChatController.scrollChatToBottomIfNear(); } else { VoiceChatController.scrollChatToBottom(); }
    });
    VoiceSSEHandler.setMarkQuestionsHandler(VoiceChatController.markAllQuestionsAnswered);
    VoiceSSEHandler.setShowSystemMessageHandler(VoiceChatController.showChatSystemMessage);
    VoiceSettings.loadSettings();

    // Initialize layout mode
    VoiceLayout.initLayoutMode();

    // Listen for resize and orientation to switch layout modes
    var _resizeTimer = null;
    window.addEventListener('resize', function () {
      clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(VoiceLayout.detectLayoutMode, 100);
    });
    window.addEventListener('orientationchange', function () {
      clearTimeout(_resizeTimer);
      _resizeTimer = setTimeout(VoiceLayout.detectLayoutMode, 100);
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
        VoiceSidebar.closeAllKebabMenus();
      }
    }
    document.addEventListener('click', _handleCloseKebabs);
    document.addEventListener('touchstart', _handleCloseKebabs, { passive: true });

    // Detect agent_id URL param (from dashboard "Chat" link)
    var urlParams = new URLSearchParams(window.location.search);
    var paramAgentId = urlParams.get('agent_id');

    // Trusted network (localhost, LAN, Tailscale): skip setup, use current origin
    if (VoiceState.isTrustedNetwork && (!VoiceState.settings.serverUrl || !VoiceState.settings.token)) {
      VoiceState.settings.serverUrl = window.location.origin;
      VoiceState.settings.token = VoiceState.isLocalhost ? 'localhost' : 'lan';
      VoiceSettings.saveSettings();
    }

    // Check if we have credentials
    if (!VoiceState.settings.serverUrl || !VoiceState.settings.token) {
      VoiceLayout.showScreen('setup');
      return;
    }

    // Initialize API
    VoiceAPI.init(VoiceState.settings.serverUrl, VoiceState.settings.token);

    // Wire up speech input callbacks
    VoiceInput.onResult(function (text) {
      if (VoiceState.currentScreen === 'chat') {
        VoiceChatController.sendChatCommand(text);
      } else {
        VoiceChatController.sendCommand(text);
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
    VoiceAPI.onConnectionChange(VoiceSSEHandler.updateConnectionIndicator);
    VoiceAPI.onAgentUpdate(VoiceSSEHandler.handleAgentUpdate);
    VoiceAPI.onTurnCreated(VoiceSSEHandler.handleTurnCreated);
    VoiceAPI.onTurnUpdated(VoiceSSEHandler.handleTurnUpdated);
    VoiceAPI.onGap(VoiceSSEHandler.handleGap);
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
      VoiceSidebar.refreshAgents();
      if (VoiceState.currentScreen === 'chat' && VoiceState.targetAgentId) {
        VoiceSSEHandler.fetchTranscriptForChat();
      }
    });

    // Play ready cue
    VoiceOutput.playCue('ready');

    // If agent_id param present, go directly to chat screen
    if (paramAgentId) {
      VoiceChatController.showChatScreen(parseInt(paramAgentId, 10));
      return;
    }

    // Load agents and show list
    VoiceSidebar.refreshAgents();
    VoiceLayout.showScreen('agents');
  }

  // --- Event binding ---

  function bindEvents() {
    // Setup form
    var setupForm = document.getElementById('setup-form');
    if (setupForm) {
      setupForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var url = document.getElementById('setup-url').value.trim();
        var token = document.getElementById('setup-token').value.trim();
        if (url && token) {
          VoiceSettings.setSetting('serverUrl', url);
          VoiceSettings.setSetting('token', token);
          init();
        }
      });
    }

    // Title link — navigate back to agent list (or show sidebar in split mode)
    var titleLink = document.getElementById('app-title-link');
    if (titleLink) {
      titleLink.addEventListener('click', function (e) {
        e.preventDefault();
        if (VoiceState.currentScreen === 'chat' && VoiceState.targetAgentId) {
          VoiceChatController.saveScrollState(VoiceState.targetAgentId);
        }
        VoiceSidebar.refreshAgents();
        VoiceLayout.showScreen('agents');
      });
    }

    // Text input fallback
    var textForm = document.getElementById('text-form');
    if (textForm) {
      textForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var input = document.getElementById('text-input');
        if (input && input.value.trim()) {
          VoiceChatController.sendCommand(input.value);
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
          VoiceChatController.sendCommand(input.value);
          input.value = '';
        }
      });
    }

    // --- FAB (split mode) ---
    var fabBtn = document.getElementById('fab-btn');
    if (fabBtn) {
      fabBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        VoiceLayout.toggleFab();
      });
    }
    var fabBackdrop = document.getElementById('fab-backdrop');
    if (fabBackdrop) {
      fabBackdrop.addEventListener('click', function () { VoiceLayout.closeFab(); });
    }
    // FAB menu items
    var fabItems = document.querySelectorAll('.fab-menu-item');
    for (var fi = 0; fi < fabItems.length; fi++) {
      fabItems[fi].addEventListener('click', function (e) {
        e.stopPropagation();
        VoiceLayout.handleMenuAction(this.getAttribute('data-action'));
      });
    }

    // --- Hamburger (stacked mode) ---
    var hamburgerBtn = document.getElementById('hamburger-btn');
    if (hamburgerBtn) {
      hamburgerBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        if (VoiceState.hamburgerOpen) { VoiceLayout.closeHamburger(); } else { VoiceLayout.openHamburger(); }
      });
    }
    var hamburgerBackdrop = document.getElementById('hamburger-backdrop');
    if (hamburgerBackdrop) {
      hamburgerBackdrop.addEventListener('click', function () { VoiceLayout.closeHamburger(); });
    }
    var hamburgerItems = document.querySelectorAll('.hamburger-item');
    for (var hi = 0; hi < hamburgerItems.length; hi++) {
      hamburgerItems[hi].addEventListener('click', function () {
        VoiceLayout.handleMenuAction(this.getAttribute('data-action'));
      });
    }

    // --- Project Picker ---
    var pickerClose = document.getElementById('project-picker-close');
    if (pickerClose) {
      pickerClose.addEventListener('click', function () { VoiceSidebar.closeProjectPicker(); });
    }
    var pickerBackdrop = document.getElementById('project-picker-backdrop');
    if (pickerBackdrop) {
      pickerBackdrop.addEventListener('click', function () { VoiceSidebar.closeProjectPicker(); });
    }
    var pickerSearch = document.getElementById('project-picker-search');
    if (pickerSearch) {
      pickerSearch.addEventListener('input', function () {
        VoiceSidebar.filterProjectList(this.value.trim());
      });
    }

    // --- Escape key handler ---
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        if (VoiceState.projectPickerOpen) { VoiceSidebar.closeProjectPicker(); e.preventDefault(); return; }
        if (VoiceState.fabOpen) { VoiceLayout.closeFab(); e.preventDefault(); return; }
        if (VoiceState.hamburgerOpen) { VoiceLayout.closeHamburger(); e.preventDefault(); return; }
      }
    });

    // Close FAB on outside click
    document.addEventListener('click', function (e) {
      if (VoiceState.fabOpen && !e.target.closest('.fab-container')) {
        VoiceLayout.closeFab();
      }
    });

    // Settings close button
    var settingsCloseBtn = document.getElementById('settings-close-btn');
    if (settingsCloseBtn) {
      settingsCloseBtn.addEventListener('click', function () {
        VoiceSettings.closeSettings();
      });
    }

    // Settings overlay click — close
    var settingsOverlay = document.getElementById('settings-overlay');
    if (settingsOverlay) {
      settingsOverlay.addEventListener('click', function () {
        VoiceSettings.closeSettings();
      });
    }

    // Settings form — save and close
    var settingsForm = document.getElementById('settings-form');
    if (settingsForm) {
      settingsForm.addEventListener('submit', function (e) {
        e.preventDefault();
        VoiceSettings.applySettingsForm();
        VoiceSettings.closeSettings();
      });
    }

    // Chat input form + textarea auto-resize
    var chatForm = document.getElementById('chat-input-form');
    var chatInput = document.getElementById('chat-text-input');
    if (chatForm) {
      chatForm.addEventListener('submit', function (e) {
        e.preventDefault();
        var hasText = chatInput && chatInput.value.trim();
        var hasFile = !!VoiceState.pendingAttachment;
        if (hasText || hasFile) {
          VoiceChatController.sendChatWithAttachment(chatInput ? chatInput.value : '');
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
          VoiceChatController.loadOlderMessages();
        }
        // Auto-dismiss new messages pill when user scrolls to the first new message
        if (VoiceState.newMessagesPillVisible && VoiceState.newMessagesFirstTurnId) {
          var bubble = document.querySelector('[data-turn-id="' + VoiceState.newMessagesFirstTurnId + '"]');
          if (bubble) {
            var containerRect = chatMessages.getBoundingClientRect();
            var bubbleRect = bubble.getBoundingClientRect();
            if (bubbleRect.top < containerRect.bottom) {
              VoiceChatController.dismissNewMessagesPill();
            }
          }
        }
      });
    }

    // Chat header focus link — click to attach (tmux) or focus (iTerm)
    var chatFocusLink = document.getElementById('chat-focus-link');
    if (chatFocusLink) {
      chatFocusLink.addEventListener('click', function () {
        if (VoiceState.targetAgentId) {
          var tmuxSession = this.getAttribute('data-tmux-session');
          if (tmuxSession) {
            VoiceAPI.attachAgent(VoiceState.targetAgentId).catch(function (err) {
              console.warn('Attach failed:', err);
            });
          } else {
            VoiceAPI.focusAgent(VoiceState.targetAgentId).catch(function (err) {
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
        if (VoiceState.navStack.length > 0) {
          var prevId = VoiceState.navStack.pop();
          VoiceChatController.showChatScreen(prevId);
        } else {
          VoiceChatController.saveScrollState(VoiceState.targetAgentId);
          VoiceState.otherAgentStates = {};
          VoiceSidebar.refreshAgents();
          VoiceLayout.showScreen('agents');
        }
      });
    }

    // Back buttons (listening, question screens)
    var backBtns = document.querySelectorAll('.back-btn');
    for (var i = 0; i < backBtns.length; i++) {
      backBtns[i].addEventListener('click', function () {
        if (VoiceState.layoutMode === 'split') {
          // In split mode, back from listening/question goes to chat or agents
          if (VoiceState.targetAgentId) {
            VoiceChatController.showChatScreen(VoiceState.targetAgentId);
          } else {
            VoiceLayout.showScreen('agents');
          }
        } else {
          VoiceLayout.showScreen('agents');
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
        VoiceSettings.setSetting('theme', theme);
        VoiceSettings.applyTheme();
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

  return {
    init: init,
    bindEvents: bindEvents
  };
})();
