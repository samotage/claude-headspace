/**
 * ChatBubbles — shared pure rendering module for chat message bubbles.
 *
 * Given a normalized message object, returns a DOM element. No side effects,
 * no state tracking, no DOM insertion. Each consumer maps its data into the
 * normalized shape and handles its own plumbing (SSE, dedup, scroll, etc.).
 *
 * Dependencies: CHUtils (window.CHUtils) for renderMarkdown / escapeHtml.
 *
 * Normalized message shape:
 *   { id, actor ('user'|'agent'|'system'), senderName, senderType ('operator'|'agent'|'system'),
 *     intent, text, timestamp, commandId, fileMetadata, toolInput, questionOptions,
 *     groupedTexts, groupedIds }
 *
 * Options:
 *   { showSenderName, showCopyButton (default true), showIntentBadge (default true),
 *     showTimestamp, onOptionSelect, onMultiSubmit, onImageClick }
 */
window.ChatBubbles = (function () {
  'use strict';

  // --- HTML escape ---

  function esc(s) {
    if (!s) return '';
    var div = document.createElement('div');
    div.appendChild(document.createTextNode(s));
    return div.innerHTML;
  }

  // --- Markdown renderer (delegates to CHUtils.renderMarkdown) ---

  function renderMd(text) {
    // Extract COMMAND COMPLETE footer before markdown rendering.
    // marked treats "text\n---" as a setext heading (<h2>).
    var ccMatch = text.match(
      /\n---\n(COMMAND COMPLETE\s*[—–-])\s*(.*)(\n---\s*$|\s*$)/
    );
    if (ccMatch) {
      text = text.substring(0, ccMatch.index);
    }
    var html = CHUtils.renderMarkdown(text);
    if (ccMatch) {
      html += '<hr><p class="command-complete-footer"><strong>' + esc(ccMatch[1]) + '</strong> '
            + esc(ccMatch[2]) + '</p>';
      if (ccMatch[3] && ccMatch[3].trim()) html += '<hr>';
    }
    return html;
  }

  // --- Strip COMMAND COMPLETE footer from copied text ---

  function stripCommandComplete(text) {
    return text.replace(/\n---\nCOMMAND COMPLETE\s*[—–-].*$/s, '').trimEnd();
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

    if (d.toDateString() === now.toDateString()) return timeStr;

    var yesterday = new Date(now);
    yesterday.setDate(yesterday.getDate() - 1);
    if (d.toDateString() === yesterday.toDateString()) return 'Yesterday ' + timeStr;

    var weekAgo = new Date(now);
    weekAgo.setDate(weekAgo.getDate() - 6);
    if (d >= weekAgo) {
      var days = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
      return days[d.getDay()] + ' ' + timeStr;
    }
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) + ', ' + timeStr;
  }

  function formatRelativeTime(date) {
    if (!(date instanceof Date)) date = new Date(date);
    var diff = (Date.now() - date.getTime()) / 1000;
    if (diff < 60) return 'just now';
    if (diff < 3600) return Math.floor(diff / 60) + 'm ago';
    if (diff < 86400) return Math.floor(diff / 3600) + 'h ago';
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  // --- File utilities ---

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  function getFileTypeIcon(filename) {
    var ext = (filename || '').split('.').pop().toLowerCase();
    var icons = {
      pdf: '\uD83D\uDCC4', txt: '\uD83D\uDCDD', md: '\uD83D\uDCDD',
      py: '\uD83D\uDC0D', js: '\uD83D\uDCDC', ts: '\uD83D\uDCDC',
      json: '{ }', yaml: '\u2699\uFE0F', yml: '\u2699\uFE0F',
      html: '\uD83C\uDF10', css: '\uD83C\uDFA8',
      png: '\uD83D\uDDBC', jpg: '\uD83D\uDDBC', jpeg: '\uD83D\uDDBC',
      gif: '\uD83D\uDDBC', svg: '\uD83D\uDDBC', webp: '\uD83D\uDDBC'
    };
    return icons[ext] || '\uD83D\uDCC1';
  }

  // --- Copy button SVG ---

  var COPY_ICON_SVG = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">'
    + '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/>'
    + '<path d="M10.5 5.5V3.5a1.5 1.5 0 0 0-1.5-1.5H3.5A1.5 1.5 0 0 0 2 3.5V9a1.5 1.5 0 0 0 1.5 1.5h2"/>'
    + '</svg>';

  var CHECK_ICON_SVG = '<svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    + '<polyline points="3.5 8.5 6.5 11.5 12.5 4.5"/>'
    + '</svg>';

  // --- Time separator ---

  function createTimeSeparator(timeStr) {
    var el = document.createElement('div');
    el.className = 'chat-timestamp';
    el.textContent = timeStr;
    return el;
  }

  // --- Command separator ---

  function createCommandSeparator(instruction, commandId, hasTurns) {
    var sep = document.createElement('div');
    sep.className = 'chat-command-separator';
    if (commandId) sep.setAttribute('data-command-id', commandId);
    var label = esc(instruction);
    if (hasTurns === false) {
      label += ' <span class="separator-no-activity">(no captured activity)</span>';
    }
    sep.innerHTML = '<span>' + label + '</span>';
    return sep;
  }

  // --- Multi-question rendering ---

  function _renderMultiQuestionHtml(questions, safetyClass, isAlreadyAnswered) {
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

  function _bindMultiQuestionBubble(container, onMultiSubmit) {
    var sections = container.querySelectorAll('.bubble-question-section');
    var selections = {};
    sections.forEach(function (sec) {
      var qi = parseInt(sec.getAttribute('data-q-idx'), 10);
      var isMulti = sec.getAttribute('data-multi') === '1';
      selections[qi] = isMulti ? new Set() : null;
    });

    var submitBtn = container.querySelector('.bubble-multi-submit');
    var questionCount = sections.length;

    container.querySelectorAll('.bubble-option-btn').forEach(function (btn) {
      btn.addEventListener('click', function () {
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
          sec.querySelectorAll('.bubble-option-btn').forEach(function (s) {
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

    submitBtn.addEventListener('click', function () {
      if (submitBtn.disabled || container.classList.contains('answered')) return;
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

      if (onMultiSubmit) {
        onMultiSubmit(answers, container, submitBtn);
      }
    });
  }

  // --- Core bubble creation ---

  /**
   * createBubble(msg, options) -> DocumentFragment
   *
   * @param {object} msg — normalized message
   * @param {object} [options]
   * @returns {DocumentFragment}
   */
  function createBubble(msg, options) {
    options = options || {};
    var showCopyButton = options.showCopyButton !== false;
    var showIntentBadge = options.showIntentBadge !== false;

    var frag = document.createDocumentFragment();

    // Timestamp separator (when showTimestamp is explicitly provided)
    if (options.showTimestamp && msg.timestamp) {
      frag.appendChild(createTimeSeparator(formatChatTime(msg.timestamp)));
    }

    var isUser = msg.actor === 'user';
    var isSystem = msg.actor === 'system';
    var isAgent = !isUser && !isSystem;
    var isGrouped = msg.groupedTexts && msg.groupedTexts.length > 1;

    var bubble = document.createElement('div');

    if (isSystem) {
      bubble.className = 'chat-bubble system';
    } else {
      bubble.className = 'chat-bubble ' + (isUser ? 'user' : 'agent') + (isGrouped ? ' grouped' : '');
    }

    if (msg.id) bubble.setAttribute('data-turn-id', msg.id);
    bubble.setAttribute('data-timestamp', msg.timestamp || new Date().toISOString());
    if (msg.commandId) bubble.setAttribute('data-command-id', msg.commandId);

    // System messages: just text, no extras
    if (isSystem) {
      bubble.textContent = msg.text || '';
      frag.appendChild(bubble);
      return frag;
    }

    var html = '';

    // Sender name (for channel chat)
    if (options.showSenderName && msg.senderName) {
      var senderClass = 'bubble-sender';
      if (msg.senderType === 'operator') senderClass += ' bubble-sender-operator';
      else if (msg.senderType === 'agent') senderClass += ' bubble-sender-agent';
      html += '<div class="' + senderClass + '">' + esc(msg.senderName) + '</div>';
    }

    // Intent badge
    if (showIntentBadge && msg.intent) {
      if (msg.intent === 'question') {
        html += '<div class="bubble-intent">Question</div>';
      } else if (msg.intent === 'completion') {
        html += '<div class="bubble-intent">Completed</div>';
      } else if (msg.intent === 'command') {
        html += '<div class="bubble-intent">Command</div>';
      } else if (msg.intent === 'progress') {
        html += '<div class="bubble-intent progress-intent">Working</div>';
      }
    }

    // Text content
    var displayText = msg.text || '';
    if (displayText) {
      var renderFn = isUser ? esc : renderMd;
      if (isGrouped) {
        html += '<div class="bubble-text grouped-text">';
        for (var g = 0; g < msg.groupedTexts.length; g++) {
          if (g > 0) html += '<div class="group-divider"></div>';
          html += '<div>' + renderFn(msg.groupedTexts[g]) + '</div>';
        }
        html += '</div>';
      } else {
        html += '<div class="bubble-text">' + renderFn(displayText) + '</div>';
      }
    }

    // File attachment
    if (msg.fileMetadata) {
      var fm = msg.fileMetadata;
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
          + '<span class="file-card-icon">' + getFileTypeIcon(fm.original_filename || '') + '</span>'
          + '<div class="file-card-info">'
          + '<div class="file-card-name">' + esc(fm.original_filename || 'File') + '</div>'
          + '<div class="file-card-size">' + formatFileSize(fm.file_size || 0) + '</div>'
          + '</div></a>';
      }
    }

    // Plan content (collapsible)
    if (msg.intent === 'question') {
      var toolInput = msg.toolInput || {};
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

    // Question options
    if (msg.intent === 'question') {
      var toolInput2 = msg.toolInput || {};
      var opts = msg.questionOptions;
      var allQuestions = null;
      var isAlreadyAnswered = (toolInput2.status === 'complete');

      if (!opts && toolInput2.questions) {
        var questions = toolInput2.questions;
        if (questions && questions.length > 1) {
          if (questions[0].options) allQuestions = questions;
        } else if (questions && questions.length > 0 && questions[0].options) {
          opts = questions[0].options;
        }
      }
      if (!allQuestions && opts && opts.length > 0 && opts[0].options) {
        allQuestions = opts;
        opts = null;
      }

      var bubbleSafety = toolInput2.safety || '';
      var safetyClass = bubbleSafety ? ' safety-' + esc(bubbleSafety) : '';

      if (allQuestions && allQuestions.length > 1) {
        html += _renderMultiQuestionHtml(allQuestions, safetyClass, isAlreadyAnswered);
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

    // Copy button (prepended so it floats top-right)
    if (showCopyButton && displayText) {
      bubble.setAttribute('data-raw-md', stripCommandComplete(displayText));
      var copyLabel = isUser ? 'Copy text' : 'Copy markdown';
      html = '<button class="bubble-copy-btn" aria-label="' + copyLabel + '" title="Copy">'
        + COPY_ICON_SVG + '</button>' + html;
    }

    bubble.innerHTML = html;

    // --- Event binding ---

    // Copy button
    var copyBtn = bubble.querySelector('.bubble-copy-btn');
    if (copyBtn) {
      copyBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        var rawMd = bubble.getAttribute('data-raw-md');
        if (!rawMd) return;
        navigator.clipboard.writeText(rawMd).then(function () {
          copyBtn.classList.add('copied');
          copyBtn.innerHTML = CHECK_ICON_SVG;
          setTimeout(function () {
            copyBtn.classList.remove('copied');
            copyBtn.innerHTML = COPY_ICON_SVG;
          }, 1500);
        }).catch(function (err) { console.warn('Clipboard copy failed:', err); });
      });
    }

    // Image thumbnail click
    var imgThumb = bubble.querySelector('.bubble-file-image');
    if (imgThumb) {
      imgThumb.addEventListener('click', function () {
        var url = this.getAttribute('data-full-url');
        var alt = (this.querySelector('img') || {}).alt || 'Image';
        if (options.onImageClick) {
          options.onImageClick(url, alt);
        }
      });
    }

    // Multi-question
    var multiContainer = bubble.querySelector('.bubble-multi-question');
    if (multiContainer) {
      _bindMultiQuestionBubble(multiContainer, options.onMultiSubmit);
    } else {
      // Single-question option buttons
      var optBtns = bubble.querySelectorAll('.bubble-option-btn');
      for (var j = 0; j < optBtns.length; j++) {
        optBtns[j].addEventListener('click', function () {
          var idx = parseInt(this.getAttribute('data-opt-idx'), 10);
          var label = this.getAttribute('data-label');
          if (options.onOptionSelect) options.onOptionSelect(idx, label, bubble);
        });
      }
    }

    frag.appendChild(bubble);
    return frag;
  }

  // --- Public API ---

  return {
    createBubble: createBubble,
    createTimeSeparator: createTimeSeparator,
    createCommandSeparator: createCommandSeparator,
    renderMd: renderMd,
    esc: esc,
    stripCommandComplete: stripCommandComplete,
    formatChatTime: formatChatTime,
    formatRelativeTime: formatRelativeTime,
    formatFileSize: formatFileSize,
    getFileTypeIcon: getFileTypeIcon
  };
})();
