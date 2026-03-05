/* Voice Chat Renderer — thin wrapper over ChatBubbles.
 * Keeps VoiceState side effects, dedup, ordering, transcript rendering,
 * lightbox, and attention banners. Delegates bubble creation to ChatBubbles.
 */
window.VoiceChatRenderer = (function () {
  'use strict';

  var _onOptionSelect = null;
  var _onNavigateToBanner = null;

  function setOptionSelectHandler(fn) { _onOptionSelect = fn; }
  function setNavigateToBannerHandler(fn) { _onNavigateToBanner = fn; }

  // --- Pass-throughs to ChatBubbles for backward compat ---

  function esc(s) { return ChatBubbles.esc(s); }
  function renderMd(text) { return ChatBubbles.renderMd(text); }
  function formatChatTime(isoStr) { return ChatBubbles.formatChatTime(isoStr); }

  // --- Image Lightbox ---

  function openImageLightbox(url, alt) {
    var lb = document.getElementById('image-lightbox');
    var img = document.getElementById('lightbox-img');
    if (!lb || !img) return;
    img.src = url;
    img.alt = alt || 'Image';
    lb.style.display = 'flex';
  }

  function closeImageLightbox() {
    var lb = document.getElementById('image-lightbox');
    var img = document.getElementById('lightbox-img');
    if (!lb) return;
    lb.style.display = 'none';
    if (img) img.src = '';
  }

  // Self-invoking lightbox init
  (function initImageLightbox() {
    document.addEventListener('click', function (e) {
      var lb = document.getElementById('image-lightbox');
      if (!lb || lb.style.display === 'none') return;
      if (e.target.classList.contains('image-lightbox-backdrop') ||
          e.target.classList.contains('image-lightbox-close')) {
        closeImageLightbox();
      }
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') closeImageLightbox();
    });
  })();

  // --- Turn grouping ---

  function groupTurns(turns) {
    var result = [];
    var currentGroup = null;
    var lastCommandId = null;

    for (var i = 0; i < turns.length; i++) {
      var turn = turns[i];

      if (turn.type === 'command_boundary') {
        if (currentGroup) { result.push(currentGroup); currentGroup = null; }
        result.push({
          type: 'separator',
          command_instruction: turn.command_instruction || 'New command',
          command_id: turn.command_id,
          has_turns: false
        });
        lastCommandId = turn.command_id;
        continue;
      }

      // Track oldest turn ID for pagination
      if (!VoiceState.chatOldestTurnId || turn.id < VoiceState.chatOldestTurnId) {
        VoiceState.chatOldestTurnId = turn.id;
      }

      if (turn.command_id && lastCommandId && turn.command_id !== lastCommandId) {
        if (currentGroup) { result.push(currentGroup); currentGroup = null; }
        result.push({
          type: 'separator',
          command_instruction: turn.command_instruction || 'New command',
          command_id: turn.command_id
        });
      }
      lastCommandId = turn.command_id;

      var isUser = turn.actor === 'user';
      if (isUser) {
        if (currentGroup) { result.push(currentGroup); currentGroup = null; }
        result.push(turn);
        continue;
      }

      if (currentGroup && shouldGroup(currentGroup, turn)) {
        var newText = turn.text || turn.summary || '';
        if (newText) {
          currentGroup.groupedTexts.push(newText);
          currentGroup.text = currentGroup.groupedTexts.join('\n');
        }
        currentGroup.groupedIds.push(turn.id);
        currentGroup.timestamp = turn.timestamp || currentGroup.timestamp;
      } else {
        if (currentGroup) result.push(currentGroup);
        currentGroup = Object.assign({}, turn);
        currentGroup.groupedTexts = [turn.text || turn.summary || ''];
        currentGroup.groupedIds = [turn.id];
      }
    }
    if (currentGroup) result.push(currentGroup);
    return result;
  }

  function shouldGroup(group, turn) {
    if (group.actor !== 'agent' || turn.actor !== 'agent') return false;
    if (group.intent !== turn.intent) return false;
    if (!group.timestamp || !turn.timestamp) return false;
    var gap = new Date(turn.timestamp) - new Date(group.timestamp);
    return gap <= 2000;
  }

  // --- Command separators ---

  function createCommandSeparatorEl(item) {
    return ChatBubbles.createCommandSeparator(
      item.command_instruction,
      item.command_id,
      item.has_turns
    );
  }

  function renderCommandSeparator(item) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    messagesEl.appendChild(createCommandSeparatorEl(item));
  }

  function maybeInsertCommandSeparator(turn) {
    if (!turn.command_id) return;
    if (VoiceState.chatLastCommandId && turn.command_id !== VoiceState.chatLastCommandId) {
      var messagesEl = document.getElementById('chat-messages');
      if (messagesEl && !messagesEl.querySelector('.chat-command-separator[data-command-id="' + turn.command_id + '"]')) {
        var sepEl = createCommandSeparatorEl({
          command_instruction: turn.command_instruction || 'New command',
          command_id: turn.command_id
        });
        messagesEl.appendChild(sepEl);
      }
    }
    VoiceState.chatLastCommandId = turn.command_id;
  }

  // --- Bubble ordering ---

  function insertBubbleOrdered(messagesEl, el) {
    var bubbleChild = el.querySelector ? el.querySelector('.chat-bubble[data-timestamp]') : null;
    var ts = bubbleChild ? bubbleChild.getAttribute('data-timestamp') : null;
    if (!ts) {
      messagesEl.appendChild(el);
      return;
    }
    var tsDate = new Date(ts);
    var existing = messagesEl.querySelectorAll('.chat-bubble[data-timestamp]');
    for (var i = existing.length - 1; i >= 0; i--) {
      var existingTs = new Date(existing[i].getAttribute('data-timestamp'));
      if (existingTs <= tsDate) {
        var next = existing[i].nextSibling;
        if (next) {
          messagesEl.insertBefore(el, next);
        } else {
          messagesEl.appendChild(el);
        }
        return;
      }
    }
    var loadMore = document.getElementById('chat-load-more');
    if (loadMore && loadMore.nextSibling) {
      messagesEl.insertBefore(el, loadMore.nextSibling);
    } else if (messagesEl.firstChild) {
      messagesEl.insertBefore(el, messagesEl.firstChild);
    } else {
      messagesEl.appendChild(el);
    }
  }

  function reorderBubble(bubble) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl || !bubble.parentNode) return;
    var ts = bubble.getAttribute('data-timestamp');
    if (!ts) return;
    var tsDate = new Date(ts);

    var prev = bubble.previousElementSibling;
    var next = bubble.nextElementSibling;

    var prevOk = true;
    var nextOk = true;
    if (prev && prev.classList.contains('chat-bubble') && prev.getAttribute('data-timestamp')) {
      prevOk = new Date(prev.getAttribute('data-timestamp')) <= tsDate;
    }
    if (next && next.classList.contains('chat-bubble') && next.getAttribute('data-timestamp')) {
      nextOk = new Date(next.getAttribute('data-timestamp')) >= tsDate;
    }

    if (prevOk && nextOk) return;

    bubble.parentNode.removeChild(bubble);
    insertBubbleOrdered(messagesEl, bubble);
  }

  // --- Map turn -> normalized msg for ChatBubbles ---

  function _turnToMsg(turn) {
    // Text fallback chain: text -> summary -> (empty)
    var displayText = turn.text || '';
    if (!displayText && turn.summary) displayText = turn.summary;
    if (turn.actor !== 'user' && turn.summary && !turn.text) displayText = turn.summary;

    return {
      id: turn.id,
      actor: turn.actor === 'user' ? 'user' : 'agent',
      intent: turn.intent,
      text: displayText,
      timestamp: turn.timestamp,
      commandId: turn.command_id,
      fileMetadata: turn.file_metadata,
      toolInput: turn.tool_input,
      questionOptions: turn.question_options,
      groupedTexts: turn.groupedTexts,
      groupedIds: turn.groupedIds
    };
  }

  function _bubbleOptions() {
    return {
      onOptionSelect: function (idx, label, bubble) {
        if (_onOptionSelect) _onOptionSelect(idx, label, bubble);
      },
      onMultiSubmit: function (answers, container, submitBtn) {
        fetch('/api/respond/' + VoiceState.targetAgentId, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mode: 'multi_select', answers: answers })
        }).then(function (resp) {
          return resp.json();
        }).then(function (data) {
          if (data.status === 'ok') {
            container.classList.add('answered');
            container.querySelectorAll('button').forEach(function (b) { b.disabled = true; });
            submitBtn.textContent = 'Submitted';
          } else {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Submit All';
          }
        }).catch(function () {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Submit All';
        });
      },
      onImageClick: function (url, alt) {
        openImageLightbox(url, alt);
      }
    };
  }

  // --- Bubble rendering ---

  function renderChatBubble(turn, prevTurn, forceRender) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    var el = createBubbleEl(turn, prevTurn, forceRender);
    if (el) insertBubbleOrdered(messagesEl, el);
  }

  function createBubbleEl(turn, prevTurn, forceRender) {
    // DOM-based dedup
    var container = document.getElementById('chat-messages');
    if (container && container.querySelector('[data-turn-id="' + turn.id + '"]')) {
      if (!forceRender) return null;
    }
    // Track max turn ID for scroll state and gap recovery
    var numId = typeof turn.id === 'number' ? turn.id : parseInt(turn.id, 10);
    if (!isNaN(numId) && numId > VoiceState.lastSeenTurnId) VoiceState.lastSeenTurnId = numId;
    var ids = turn.groupedIds || [];
    for (var k2 = 0; k2 < ids.length; k2++) {
      var gid = typeof ids[k2] === 'number' ? ids[k2] : parseInt(ids[k2], 10);
      if (!isNaN(gid) && gid > VoiceState.lastSeenTurnId) VoiceState.lastSeenTurnId = gid;
    }

    // Determine timestamp visibility
    var showTimestamp = false;
    if (turn.timestamp) {
      if (!prevTurn || prevTurn.type === 'separator') {
        showTimestamp = true;
      } else if (prevTurn.timestamp) {
        var gap = new Date(turn.timestamp) - new Date(prevTurn.timestamp);
        if (gap > 5 * 60 * 1000) showTimestamp = true;
      }
    }

    var msg = _turnToMsg(turn);
    var opts = _bubbleOptions();
    opts.showTimestamp = showTimestamp;

    return ChatBubbles.createBubble(msg, opts);
  }

  // --- Transcript rendering ---

  function renderTranscriptTurns(data) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    var turns = data.turns || [];
    var grouped = groupTurns(turns);
    var frag = document.createDocumentFragment();
    for (var i = 0; i < grouped.length; i++) {
      var item = grouped[i];
      var prev = i > 0 ? grouped[i - 1] : null;
      if (item.type === 'separator') {
        frag.appendChild(createCommandSeparatorEl(item));
        VoiceState.chatLastCommandId = item.command_id;
      } else {
        var bubbleEl = createBubbleEl(item, prev);
        if (bubbleEl) frag.appendChild(bubbleEl);
        if (item.command_id) VoiceState.chatLastCommandId = item.command_id;
      }
    }
    messagesEl.appendChild(frag);
  }

  function prependTranscriptTurns(turns) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;

    var grouped = groupTurns(turns);
    var frag = document.createDocumentFragment();
    for (var i = 0; i < grouped.length; i++) {
      var item = grouped[i];
      var prev = i > 0 ? grouped[i - 1] : null;
      if (item.type === 'separator') {
        frag.appendChild(createCommandSeparatorEl(item));
      } else {
        var bubbleEl = createBubbleEl(item, prev);
        if (bubbleEl) frag.appendChild(bubbleEl);
      }
    }
    var loadMore = document.getElementById('chat-load-more');
    if (loadMore && loadMore.nextSibling) {
      messagesEl.insertBefore(frag, loadMore.nextSibling);
    } else {
      messagesEl.insertBefore(frag, messagesEl.firstChild);
    }
  }

  // --- Attention banners ---

  function renderAttentionBanners() {
    var container = document.getElementById('attention-banners');
    if (!container) return;

    var bannerAgents = [];
    var keys = Object.keys(VoiceState.otherAgentStates);
    for (var i = 0; i < keys.length; i++) {
      var agentId = keys[i];
      var info = VoiceState.otherAgentStates[agentId];
      if (info.state === 'awaiting_input') {
        bannerAgents.push({ id: agentId, info: info });
      }
    }

    if (bannerAgents.length === 0) {
      container.innerHTML = '';
      return;
    }

    var html = '';
    for (var j = 0; j < bannerAgents.length; j++) {
      var ba = bannerAgents[j];
      var text = ba.info.command_instruction || 'Needs input';
      var bannerHeroHtml;
      if (ba.info.persona_name) {
        bannerHeroHtml = '<span class="agent-hero">' + esc(ba.info.persona_name) + '</span>';
      } else {
        bannerHeroHtml = '<span class="agent-hero">' + esc(ba.info.hero_chars) + '</span>'
          + '<span class="agent-hero-trail">' + esc(ba.info.hero_trail) + '</span>';
      }
      html += '<div class="attention-banner" data-agent-id="' + ba.id + '">'
        + '<div class="attention-banner-hero">'
        + bannerHeroHtml
        + '</div>'
        + '<div class="attention-banner-text">' + esc(text) + '</div>'
        + '<div class="attention-banner-arrow">&#8250;</div>'
        + '</div>';
    }
    container.innerHTML = html;

    var banners = container.querySelectorAll('.attention-banner');
    for (var k = 0; k < banners.length; k++) {
      banners[k].addEventListener('click', function () {
        var id = parseInt(this.getAttribute('data-agent-id'), 10);
        if (_onNavigateToBanner) _onNavigateToBanner(id);
      });
    }
  }

  // --- Inject options into existing bubble (recapture fallback) ---

  function injectOptionsIntoBubble(turnId, options, safetyClass) {
    var bubble = document.querySelector('[data-turn-id="' + turnId + '"]');
    if (!bubble) return false;
    if (bubble.querySelector('.bubble-options') || bubble.querySelector('.bubble-multi-question')) return false;

    var html = '<div class="bubble-options">';
    for (var i = 0; i < options.length; i++) {
      var opt = options[i];
      html += '<button class="bubble-option-btn' + (safetyClass || '') + '" data-opt-idx="' + i + '" data-label="' + esc(opt.label) + '">'
        + esc(opt.label)
        + (opt.description ? '<div class="bubble-option-desc">' + esc(opt.description) + '</div>' : '')
        + '</button>';
    }
    html += '</div>';

    var bubbleText = bubble.querySelector('.bubble-text');
    if (bubbleText) {
      bubbleText.insertAdjacentHTML('afterend', html);
    } else {
      bubble.insertAdjacentHTML('beforeend', html);
    }

    var optBtns = bubble.querySelectorAll('.bubble-option-btn');
    for (var j = 0; j < optBtns.length; j++) {
      optBtns[j].addEventListener('click', function () {
        var idx = parseInt(this.getAttribute('data-opt-idx'), 10);
        var label = this.getAttribute('data-label');
        if (_onOptionSelect) _onOptionSelect(idx, label, bubble);
      });
    }
    return true;
  }

  // --- Public API ---

  return {
    setOptionSelectHandler: setOptionSelectHandler,
    setNavigateToBannerHandler: setNavigateToBannerHandler,
    esc: esc,
    renderMd: renderMd,
    formatChatTime: formatChatTime,
    openImageLightbox: openImageLightbox,
    closeImageLightbox: closeImageLightbox,
    groupTurns: groupTurns,
    shouldGroup: shouldGroup,
    createCommandSeparatorEl: createCommandSeparatorEl,
    renderCommandSeparator: renderCommandSeparator,
    maybeInsertCommandSeparator: maybeInsertCommandSeparator,
    insertBubbleOrdered: insertBubbleOrdered,
    reorderBubble: reorderBubble,
    renderChatBubble: renderChatBubble,
    createBubbleEl: createBubbleEl,
    renderTranscriptTurns: renderTranscriptTurns,
    prependTranscriptTurns: prependTranscriptTurns,
    renderAttentionBanners: renderAttentionBanners,
    injectOptionsIntoBubble: injectOptionsIntoBubble
  };
})();
