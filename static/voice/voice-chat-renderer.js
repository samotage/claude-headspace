/* Voice Chat Renderer — bubble creation, transcript rendering, lightbox, and attention banners */
window.VoiceChatRenderer = (function () {
  'use strict';

  var _onOptionSelect = null;
  var _onNavigateToBanner = null;

  function setOptionSelectHandler(fn) { _onOptionSelect = fn; }
  function setNavigateToBannerHandler(fn) { _onNavigateToBanner = fn; }

  // --- HTML escape ---

  function esc(s) {
    if (!s) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(s));
    return div.innerHTML;
  }

  // --- Markdown renderer for agent bubbles (delegates to marked.js via CHUtils) ---

  function renderMd(text) {
    return CHUtils.renderMarkdown(text);
  }

  // --- Time formatting ---

  function formatChatTime(isoStr) {
    var d = new Date(isoStr);
    var now = new Date();
    var hours = d.getHours();
    var minutes = d.getMinutes();
    var ampm = hours >= 12 ? 'PM' : 'AM';
    hours = hours % 12 || 12;
    var timeStr = hours + ':' + (minutes < 10 ? '0' : '') + minutes + ' ' + ampm;

    // Same day? Just show time.
    if (d.toDateString() === now.toDateString()) {
      return timeStr;
    }
    // Yesterday
    var yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) {
      return 'Yesterday ' + timeStr;
    }
    // This week (within 7 days) — show day-of-week
    var weekAgo = new Date(now);
    weekAgo.setDate(weekAgo.getDate() - 6);
    if (d >= weekAgo) {
      var days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      return days[d.getDay()] + ' ' + timeStr;
    }
    // Older — show date
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ', ' + timeStr;
  }

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
    // Group consecutive agent turns within 2s into single items,
    // insert command separators between command boundaries
    var result = [];
    var currentGroup = null;
    var lastCommandId = null;

    for (var i = 0; i < turns.length; i++) {
      var turn = turns[i];

      // Synthetic command boundary from backend (command with no turns)
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

      // Command boundary separator
      if (turn.command_id && lastCommandId && turn.command_id !== lastCommandId) {
        // Flush current group
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
        // User turns always standalone — flush any active group
        if (currentGroup) { result.push(currentGroup); currentGroup = null; }
        result.push(turn);
        continue;
      }

      // Agent turn — check if it should be grouped with previous
      if (currentGroup && shouldGroup(currentGroup, turn)) {
        // Append text to group
        var newText = turn.text || turn.summary || '';
        if (newText) {
          currentGroup.groupedTexts.push(newText);
          currentGroup.text = currentGroup.groupedTexts.join('\n');
        }
        currentGroup.groupedIds.push(turn.id);
        // Keep latest timestamp
        currentGroup.timestamp = turn.timestamp || currentGroup.timestamp;
      } else {
        // Flush previous group and start new one
        if (currentGroup) result.push(currentGroup);
        currentGroup = Object.assign({}, turn);
        currentGroup.groupedTexts = [turn.text || turn.summary || ''];
        currentGroup.groupedIds = [turn.id];
      }
    }
    // Flush final group
    if (currentGroup) result.push(currentGroup);

    return result;
  }

  function shouldGroup(group, turn) {
    // Only group same-intent agent turns within 2 seconds
    if (group.actor !== 'agent' || turn.actor !== 'agent') return false;
    if (group.intent !== turn.intent) return false;
    if (!group.timestamp || !turn.timestamp) return false;
    var gap = new Date(turn.timestamp) - new Date(group.timestamp);
    return gap <= 2000;
  }

  // --- Command separators ---

  function createCommandSeparatorEl(item) {
    var sep = document.createElement('div');
    sep.className = 'chat-command-separator';
    if (item.command_id) sep.setAttribute('data-command-id', item.command_id);
    var label = esc(item.command_instruction);
    if (item.has_turns === false) {
      label += ' <span class="separator-no-activity">(no captured activity)</span>';
    }
    sep.innerHTML = '<span>' + label + '</span>';
    return sep;
  }

  function renderCommandSeparator(item) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    messagesEl.appendChild(createCommandSeparatorEl(item));
  }

  /**
   * Check if a turn crosses a command boundary and insert a separator if needed.
   * Updates VoiceState.chatLastCommandId. Call this BEFORE rendering the turn bubble.
   */
  function maybeInsertCommandSeparator(turn) {
    if (!turn.command_id) return;
    if (VoiceState.chatLastCommandId && turn.command_id !== VoiceState.chatLastCommandId) {
      // Check if a separator for this command already exists in DOM
      var messagesEl = document.getElementById('chat-messages');
      if (messagesEl && !messagesEl.querySelector('.chat-command-separator[data-command-id="' + turn.command_id + '"]')) {
        var sepEl = createCommandSeparatorEl({
          command_instruction: turn.command_instruction || 'New command',
          command_id: turn.command_id
        });
        // Append at end — separators appear in real-time as new commands arrive
        messagesEl.appendChild(sepEl);
      }
    }
    VoiceState.chatLastCommandId = turn.command_id;
  }

  // --- Bubble ordering ---

  /**
   * Insert a bubble element (or fragment) at the correct chronological
   * position based on data-timestamp. Walks backwards through existing
   * bubbles to find the insertion point.
   *
   * @param {Element} messagesEl - The chat messages container
   * @param {Element|DocumentFragment} el - Bubble element or fragment containing one
   */
  function insertBubbleOrdered(messagesEl, el) {
    // Extract timestamp: fragments don't have getAttribute, so find the bubble child
    var bubbleChild = el.querySelector ? el.querySelector('.chat-bubble[data-timestamp]') : null;
    var ts = bubbleChild ? bubbleChild.getAttribute('data-timestamp') : null;
    if (!ts) {
      // No timestamp — append at end as fallback
      messagesEl.appendChild(el);
      return;
    }
    var tsDate = new Date(ts);
    // Walk backwards through existing timestamped bubbles
    var existing = messagesEl.querySelectorAll('.chat-bubble[data-timestamp]');
    for (var i = existing.length - 1; i >= 0; i--) {
      var existingTs = new Date(existing[i].getAttribute('data-timestamp'));
      if (existingTs <= tsDate) {
        // Insert after this element (before its next sibling)
        var next = existing[i].nextSibling;
        if (next) {
          messagesEl.insertBefore(el, next);
        } else {
          messagesEl.appendChild(el);
        }
        return;
      }
    }
    // Oldest element — insert at the very beginning (after any load-more indicator)
    var loadMore = document.getElementById('chat-load-more');
    if (loadMore && loadMore.nextSibling) {
      messagesEl.insertBefore(el, loadMore.nextSibling);
    } else if (messagesEl.firstChild) {
      messagesEl.insertBefore(el, messagesEl.firstChild);
    } else {
      messagesEl.appendChild(el);
    }
  }

  /**
   * Reorder a bubble in the DOM if its timestamp has changed.
   * Checks if the bubble is already in the correct position relative
   * to its siblings; if not, removes and re-inserts it.
   */
  function reorderBubble(bubble) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl || !bubble.parentNode) return;
    var ts = bubble.getAttribute('data-timestamp');
    if (!ts) return;
    var tsDate = new Date(ts);

    // Check if position is correct: previous sibling (if any) should have ts <= ours,
    // next sibling (if any) should have ts >= ours
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

    if (prevOk && nextOk) return; // Already in correct position

    // Remove and re-insert at correct position
    bubble.parentNode.removeChild(bubble);
    insertBubbleOrdered(messagesEl, bubble);
  }

  // --- Bubble rendering ---

  function renderChatBubble(turn, prevTurn, forceRender) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    var el = createBubbleEl(turn, prevTurn, forceRender);
    if (el) insertBubbleOrdered(messagesEl, el);
  }

  function createBubbleEl(turn, prevTurn, forceRender) {
    // DOM-based dedup: check if this turn is already rendered
    var container = document.getElementById('chat-messages');
    if (container && container.querySelector('[data-turn-id="' + turn.id + '"]')) {
      if (!forceRender) return null;
    }
    // Track max turn ID for scroll state and gap recovery
    var numId = typeof turn.id === 'number' ? turn.id : parseInt(turn.id, 10);
    if (!isNaN(numId) && numId > VoiceState.lastSeenTurnId) VoiceState.lastSeenTurnId = numId;
    // Track grouped IDs too
    var ids = turn.groupedIds || [];
    for (var k2 = 0; k2 < ids.length; k2++) {
      var gid = typeof ids[k2] === 'number' ? ids[k2] : parseInt(ids[k2], 10);
      if (!isNaN(gid) && gid > VoiceState.lastSeenTurnId) VoiceState.lastSeenTurnId = gid;
    }

    var frag = document.createDocumentFragment();

    // Timestamp separator — show if first message or >5 min gap
    if (turn.timestamp) {
      var showTimestamp = false;
      if (!prevTurn || prevTurn.type === 'separator') {
        showTimestamp = true;
      } else if (prevTurn.timestamp) {
        var gap = new Date(turn.timestamp) - new Date(prevTurn.timestamp);
        if (gap > 5 * 60 * 1000) showTimestamp = true;
      }
      if (showTimestamp) {
        var tsEl = document.createElement('div');
        tsEl.className = 'chat-timestamp';
        tsEl.textContent = formatChatTime(turn.timestamp);
        frag.appendChild(tsEl);
      }
    }

    var bubble = document.createElement('div');
    var isUser = turn.actor === 'user';
    var isGrouped = turn.groupedTexts && turn.groupedTexts.length > 1;
    bubble.className = 'chat-bubble ' + (isUser ? 'user' : 'agent') + (isGrouped ? ' grouped' : '');
    bubble.setAttribute('data-turn-id', turn.id);
    bubble.setAttribute('data-timestamp', turn.timestamp || new Date().toISOString());
    if (turn.command_id) bubble.setAttribute('data-command-id', turn.command_id);

    var html = '';

    // Intent label for non-obvious intents
    if (turn.intent === 'question') {
      html += '<div class="bubble-intent">Question</div>';
    } else if (turn.intent === 'completion') {
      html += '<div class="bubble-intent">Completed</div>';
    } else if (turn.intent === 'command') {
      html += '<div class="bubble-intent">Command</div>';
    } else if (turn.intent === 'progress') {
      html += '<div class="bubble-intent progress-intent">Working</div>';
    }

    // Text content — fallback chain: text -> summary -> (empty)
    var displayText = turn.text || '';
    if (!displayText && turn.summary) {
      displayText = turn.summary;
    }
    if (!isUser && turn.summary && !turn.text) {
      displayText = turn.summary;
    }
    if (displayText) {
      var renderFn = isUser ? esc : renderMd;
      if (isGrouped) {
        // Render grouped texts with separators
        html += '<div class="bubble-text grouped-text">';
        for (var g = 0; g < turn.groupedTexts.length; g++) {
          if (g > 0) html += '<div class="group-divider"></div>';
          html += '<div>' + renderFn(turn.groupedTexts[g]) + '</div>';
        }
        html += '</div>';
      } else {
        html += '<div class="bubble-text">' + renderFn(displayText) + '</div>';
      }
    }

    // File attachment rendering
    if (turn.file_metadata) {
      var fm = turn.file_metadata;
      if (fm.file_type === 'image') {
        var imgUrl = fm._localPreviewUrl || fm.serving_url || '';
        if (imgUrl) {
          html += '<div class="bubble-file-image" data-full-url="' + esc(imgUrl) + '">'
            + '<img src="' + esc(imgUrl) + '" alt="' + esc(fm.original_filename || 'Image') + '" loading="lazy">'
            + '</div>';
        }
      } else {
        var cardUrl = fm.serving_url || '#';
        html += '<a class="bubble-file-card" href="' + esc(cardUrl) + '" target="_blank" rel="noopener">'
          + '<span class="file-card-icon">' + VoiceFileUpload.getFileTypeIcon(fm.original_filename || '') + '</span>'
          + '<div class="file-card-info">'
          + '<div class="file-card-name">' + esc(fm.original_filename || 'File') + '</div>'
          + '<div class="file-card-size">' + VoiceFileUpload.formatFileSize(fm.file_size || 0) + '</div>'
          + '</div></a>';
      }
    }

    // Plan content — render collapsible plan above question options
    if (turn.intent === 'question') {
      var toolInput = turn.tool_input || {};
      if (toolInput.plan_content) {
        html += '<div class="bubble-plan-content">';
        html += '<details open>';
        html += '<summary class="plan-toggle">Plan Details'
          + (toolInput.plan_file_path ? ' <span class="plan-file-path">' + esc(toolInput.plan_file_path.split('/').pop()) + '</span>' : '')
          + '</summary>';
        html += '<div class="plan-body">' + renderMd(toolInput.plan_content) + '</div>';
        html += '</details>';
        html += '</div>';
      }
    }

    // Question options inside the bubble
    if (turn.intent === 'question') {
      var opts = turn.question_options;
      var toolInput = turn.tool_input || {};
      var allQuestions = null;
      // Check if this question has already been answered
      var isAlreadyAnswered = (toolInput.status === 'complete');
      if (!opts && toolInput.questions) {
        var questions = toolInput.questions;
        if (questions && questions.length > 1) {
          // Multi-question: check if first element has 'options' (full question objects)
          if (questions[0].options) {
            allQuestions = questions;
          }
        } else if (questions && questions.length > 0 && questions[0].options) {
          opts = questions[0].options;
        }
      }
      // Also check if q_options itself is multi-question format
      if (!allQuestions && opts && opts.length > 0 && opts[0].options) {
        allQuestions = opts;
        opts = null;
      }
      // Extract safety for color-coding option buttons
      var bubbleSafety = toolInput.safety || '';
      var safetyClass = bubbleSafety ? ' safety-' + esc(bubbleSafety) : '';

      if (allQuestions && allQuestions.length > 1) {
        // Multi-question bubble
        html += renderMultiQuestionBubble(allQuestions, safetyClass, turn);
      } else if (opts && opts.length > 0) {
        html += '<div class="bubble-options' + (isAlreadyAnswered ? ' answered' : '') + '">';
        for (var i = 0; i < opts.length; i++) {
          var opt = opts[i];
          html += '<button class="bubble-option-btn' + safetyClass + '" data-opt-idx="' + i + '" data-label="' + esc(opt.label) + '"'
            + (isAlreadyAnswered ? ' disabled' : '')
            + '>'
            + esc(opt.label)
            + (opt.description ? '<div class="bubble-option-desc">' + esc(opt.description) + '</div>' : '')
            + '</button>';
        }
        html += '</div>';
      }
    }

    // Copy button for agent bubbles with text content
    if (!isUser && displayText) {
      bubble.setAttribute('data-raw-md', displayText);
      html = '<button class="bubble-copy-btn" aria-label="Copy markdown" title="Copy">'
        + '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
        + '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/>'
        + '<path d="M10.5 5.5V3.5a1.5 1.5 0 0 0-1.5-1.5H3.5A1.5 1.5 0 0 0 2 3.5V9a1.5 1.5 0 0 0 1.5 1.5h2"/>'
        + '</svg>'
        + '</button>' + html;
    }

    bubble.innerHTML = html;

    // Bind copy button click
    var copyBtn = bubble.querySelector('.bubble-copy-btn');
    if (copyBtn) {
      copyBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var rawMd = bubble.getAttribute('data-raw-md');
        if (!rawMd) return;
        navigator.clipboard.writeText(rawMd).then(function () {
          copyBtn.classList.add('copied');
          copyBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
            + '<polyline points="3.5 8.5 6.5 11.5 12.5 4.5"/>'
            + '</svg>';
          setTimeout(function () {
            copyBtn.classList.remove('copied');
            copyBtn.innerHTML = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
              + '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/>'
              + '<path d="M10.5 5.5V3.5a1.5 1.5 0 0 0-1.5-1.5H3.5A1.5 1.5 0 0 0 2 3.5V9a1.5 1.5 0 0 0 1.5 1.5h2"/>'
              + '</svg>';
          }, 1500);
        }).catch(function (err) { console.warn('Clipboard copy failed:', err); });
      });
    }

    // Bind image thumbnail click -> open in lightbox
    var imgThumb = bubble.querySelector('.bubble-file-image');
    if (imgThumb) {
      imgThumb.addEventListener('click', function () {
        var url = this.getAttribute('data-full-url');
        var alt = (this.querySelector('img') || {}).alt || 'Image';
        if (url) openImageLightbox(url, alt);
      });
    }

    // Bind option button clicks
    var multiContainer = bubble.querySelector('.bubble-multi-question');
    if (multiContainer) {
      bindMultiQuestionBubble(multiContainer, bubble);
    } else {
      var optBtns = bubble.querySelectorAll('.bubble-option-btn');
      for (var j = 0; j < optBtns.length; j++) {
        optBtns[j].addEventListener('click', function () {
          var idx = parseInt(this.getAttribute('data-opt-idx'), 10);
          var label = this.getAttribute('data-label');
          if (_onOptionSelect) _onOptionSelect(idx, label, bubble);
        });
      }
    }

    frag.appendChild(bubble);
    return frag;
  }

  // --- Multi-question rendering ---

  function renderMultiQuestionBubble(questions, safetyClass, turn) {
    var toolInput = turn.tool_input || {};
    var isAlreadyAnswered = (toolInput.status === 'complete');
    var answeredClass = isAlreadyAnswered ? ' answered' : '';
    var html = '<div class="bubble-multi-question' + answeredClass + '">';
    for (var qi = 0; qi < questions.length; qi++) {
      var q = questions[qi];
      var isMulti = q.multiSelect === true;
      html += '<div class="bubble-question-section" data-q-idx="' + qi + '" data-multi="' + (isMulti ? '1' : '0') + '">';
      html += '<div class="bubble-question-header">' + esc(q.header ? q.header + ': ' : '') + esc(q.question || '') + '</div>';
      var qOpts = q.options || [];
      for (var oi = 0; oi < qOpts.length; oi++) {
        html += '<button class="bubble-option-btn' + safetyClass + '" data-q-idx="' + qi + '" data-opt-idx="' + oi + '"'
          + (isAlreadyAnswered ? ' disabled' : '')
          + '>'
          + esc(qOpts[oi].label)
          + (qOpts[oi].description ? '<div class="bubble-option-desc">' + esc(qOpts[oi].description) + '</div>' : '')
          + '</button>';
      }
      html += '</div>';
    }
    html += '<button class="bubble-multi-submit" disabled>Submit All</button>';
    html += '</div>';
    return html;
  }

  function bindMultiQuestionBubble(container, bubble) {
    var sections = container.querySelectorAll('.bubble-question-section');
    var selections = {};
    sections.forEach(function(sec) {
      var qi = parseInt(sec.getAttribute('data-q-idx'), 10);
      var isMulti = sec.getAttribute('data-multi') === '1';
      selections[qi] = isMulti ? new Set() : null;
    });

    var submitBtn = container.querySelector('.bubble-multi-submit');
    var questionCount = sections.length;

    container.querySelectorAll('.bubble-option-btn').forEach(function(btn) {
      btn.addEventListener('click', function() {
        if (container.classList.contains('answered')) return;
        var qi = parseInt(btn.getAttribute('data-q-idx'), 10);
        var oi = parseInt(btn.getAttribute('data-opt-idx'), 10);
        var sec = container.querySelector('[data-q-idx="' + qi + '"].bubble-question-section');
        var isMulti = sec && sec.getAttribute('data-multi') === '1';

        if (isMulti) {
          if (selections[qi].has(oi)) {
            selections[qi].delete(oi);
            btn.classList.remove('bubble-option-selected');
          } else {
            selections[qi].add(oi);
            btn.classList.add('bubble-option-selected');
          }
        } else {
          // Radio: deselect siblings
          sec.querySelectorAll('.bubble-option-btn').forEach(function(s) {
            s.classList.remove('bubble-option-selected');
          });
          btn.classList.add('bubble-option-selected');
          selections[qi] = oi;
        }

        // Update submit button
        var allAnswered = true;
        for (var i = 0; i < questionCount; i++) {
          var m = container.querySelector('[data-q-idx="' + i + '"].bubble-question-section');
          var im = m && m.getAttribute('data-multi') === '1';
          if (im) {
            if (!selections[i] || selections[i].size === 0) { allAnswered = false; break; }
          } else {
            if (selections[i] === null || selections[i] === undefined) { allAnswered = false; break; }
          }
        }
        submitBtn.disabled = !allAnswered;
      });
    });

    submitBtn.addEventListener('click', function() {
      if (submitBtn.disabled || container.classList.contains('answered')) return;
      // Build answers
      var answers = [];
      for (var i = 0; i < questionCount; i++) {
        var sec = container.querySelector('[data-q-idx="' + i + '"].bubble-question-section');
        var isMulti = sec && sec.getAttribute('data-multi') === '1';
        if (isMulti) {
          answers.push({ option_indices: Array.from(selections[i]).sort() });
        } else {
          answers.push({ option_index: selections[i] });
        }
      }
      submitBtn.disabled = true;
      submitBtn.textContent = 'Sending...';

      fetch('/api/respond/' + VoiceState.targetAgentId, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ mode: 'multi_select', answers: answers })
      }).then(function(resp) {
        return resp.json();
      }).then(function(data) {
        if (data.status === 'ok') {
          container.classList.add('answered');
          container.querySelectorAll('button').forEach(function(b) { b.disabled = true; });
          submitBtn.textContent = 'Submitted';
        } else {
          submitBtn.disabled = false;
          submitBtn.textContent = 'Submit All';
        }
      }).catch(function() {
        submitBtn.disabled = false;
        submitBtn.textContent = 'Submit All';
      });
    });
  }

  // --- Transcript rendering ---

  function renderTranscriptTurns(data) {
    var messagesEl = document.getElementById('chat-messages');
    if (!messagesEl) return;
    var turns = data.turns || [];
    var grouped = groupTurns(turns);
    // Use a document fragment with sequential appends (NOT insertBubbleOrdered)
    // because groupTurns already returns items in correct chronological order.
    // Using insertBubbleOrdered here would push separators to the end since
    // it only considers .chat-bubble[data-timestamp] elements for positioning.
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
    // Create a fragment with all elements, then prepend
    var frag = document.createDocumentFragment();
    for (var i = 0; i < grouped.length; i++) {
      var item = grouped[i];
      var prev = i > 0 ? grouped[i - 1] : null;
      if (item.type === 'separator') {
        var sepEl = createCommandSeparatorEl(item);
        frag.appendChild(sepEl);
      } else {
        var bubbleEl = createBubbleEl(item, prev);
        if (bubbleEl) frag.appendChild(bubbleEl);
      }
    }
    // Insert before load-more indicator or at top
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
    // Don't inject if options already present
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

    // Insert before the closing div of bubble-text's parent
    var bubbleText = bubble.querySelector('.bubble-text');
    if (bubbleText) {
      bubbleText.insertAdjacentHTML('afterend', html);
    } else {
      bubble.insertAdjacentHTML('beforeend', html);
    }

    // Bind click handlers
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
    renderMultiQuestionBubble: renderMultiQuestionBubble,
    bindMultiQuestionBubble: bindMultiQuestionBubble,
    renderTranscriptTurns: renderTranscriptTurns,
    prependTranscriptTurns: prependTranscriptTurns,
    renderAttentionBanners: renderAttentionBanners,
    injectOptionsIntoBubble: injectOptionsIntoBubble
  };
})();
