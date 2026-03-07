/* VoiceAgentInfo — slide-out agent info panel for voice chat.
 *
 * Fetches data from /api/agents/{id}/info and renders it in a
 * settings-style slide-out panel. Follows the same open/close
 * pattern as VoiceSettings.
 *
 * Each section has a Copy button that copies markdown-formatted
 * text to the clipboard (matching the dashboard agent info pattern).
 *
 * Dependencies:
 *   CHUtils.apiFetch — authenticated fetch wrapper
 */
window.VoiceAgentInfo = (function () {
  'use strict';

  // Section copy state — reset on each render
  var _sectionTexts = {};
  var _sectionCounter = 0;

  function open(agentId) {
    var overlay = document.getElementById('agent-info-overlay');
    var panel = document.getElementById('agent-info-panel');
    var content = document.getElementById('agent-info-content');
    var title = document.getElementById('agent-info-title');

    if (content) content.innerHTML = '<div class="agent-info-loading">Loading\u2026</div>';
    if (title) title.textContent = 'Agent Info';
    if (overlay) overlay.classList.add('open');
    if (panel) panel.classList.add('open');

    CHUtils.apiFetch('/api/agents/' + agentId + '/info')
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) {
          if (content) content.innerHTML = '<div class="agent-info-error">' + _esc(data.error) + '</div>';
          return;
        }
        _render(data, content, title);
      })
      .catch(function () {
        if (content) content.innerHTML = '<div class="agent-info-error">Failed to load agent info</div>';
      });
  }

  function close() {
    var overlay = document.getElementById('agent-info-overlay');
    var panel = document.getElementById('agent-info-panel');
    if (overlay) overlay.classList.remove('open');
    if (panel) panel.classList.remove('open');
  }

  // --- Copy to clipboard ---

  function _copyToClipboard(text, btnEl) {
    navigator.clipboard.writeText(text).then(function () {
      if (btnEl) {
        var original = btnEl.textContent;
        btnEl.textContent = 'Copied!';
        btnEl.classList.add('agent-info-copy-success');
        setTimeout(function () {
          btnEl.textContent = original;
          btnEl.classList.remove('agent-info-copy-success');
        }, 1500);
      }
    }).catch(function () {
      if (btnEl) {
        btnEl.textContent = 'Failed';
        setTimeout(function () { btnEl.textContent = 'Copy'; }, 1500);
      }
    });
  }

  function _sectionCopyBtn(plainText) {
    var sid = 'sec_' + (_sectionCounter++);
    _sectionTexts[sid] = plainText;
    return '<button class="agent-info-copy-btn" data-section-id="' + sid + '">Copy</button>';
  }

  function _wireCopyButtons(content) {
    var btns = content.querySelectorAll('.agent-info-copy-btn[data-section-id]');
    for (var i = 0; i < btns.length; i++) {
      btns[i].addEventListener('click', function (e) {
        e.stopPropagation();
        var btn = e.currentTarget;
        var sid = btn.getAttribute('data-section-id');
        var text = _sectionTexts[sid];
        if (text) _copyToClipboard(text, btn);
      });
    }
  }

  // --- Utility ---

  function _esc(str) {
    if (!str) return '';
    var d = document.createElement('div');
    d.textContent = str;
    return d.innerHTML;
  }

  function _timeAgo(isoStr) {
    if (!isoStr) return '\u2014';
    var diff = Date.now() - new Date(isoStr).getTime();
    var sec = Math.floor(diff / 1000);
    if (sec < 60) return sec + 's ago';
    var min = Math.floor(sec / 60);
    if (min < 60) return min + 'm ago';
    var hr = Math.floor(min / 60);
    if (hr < 24) return hr + 'h ago';
    var d = Math.floor(hr / 24);
    return d + 'd ago';
  }

  function _or(val, fallback) {
    return (val !== null && val !== undefined) ? val : (fallback || '\u2014');
  }

  // --- Section header with copy button ---

  function _sectionHeader(title, copyText) {
    return '<div class="agent-info-section-header"><h3>' + _esc(title) + '</h3>' + _sectionCopyBtn(copyText) + '</div>';
  }

  // --- Render ---

  function _render(data, content, titleEl) {
    // Reset copy state
    _sectionTexts = {};
    _sectionCounter = 0;

    var id = data.identity || {};
    var proj = data.project;
    var life = data.lifecycle || {};
    var prio = data.priority || {};
    var persona = data.persona;
    var headspace = data.headspace;
    var frustration = data.frustration_scores || [];
    var commands = data.commands || [];
    var guardrails = data.guardrails;

    // Update title with agent identity
    var heroName = persona ? persona.name : ('Agent #' + id.id);
    if (titleEl) titleEl.textContent = heroName;

    var html = '';

    // --- Identity section ---
    var identityText = '## Identity\n';
    identityText += '- **Agent ID:** #' + id.id + '\n';
    identityText += '- **Session UUID:** `' + (id.session_uuid || '') + '`\n';
    if (id.claude_session_id) identityText += '- **Claude Session:** ' + id.claude_session_id + '\n';
    if (persona) {
      identityText += '- **Persona:** ' + persona.name + '\n';
      if (persona.role) identityText += '- **Role:** ' + persona.role + '\n';
    }
    if (id.tmux_pane_id) {
      identityText += '- **Tmux:** ' + (id.tmux_session_name || id.tmux_pane_id) + ' (' + (id.tmux_pane_alive ? 'alive' : 'dead') + ')\n';
    }
    if (id.bridge_available) identityText += '- **Bridge:** available\n';
    if (id.claude_pid) identityText += '- **Claude PID:** ' + id.claude_pid + '\n';

    html += '<div class="agent-info-section">';
    html += _sectionHeader('Identity', identityText);
    html += _row('Agent ID', '#' + id.id);
    html += _row('Session UUID', '<span title="' + _esc(id.session_uuid) + '">' + _esc(id.session_uuid_short) + '</span>');
    if (persona) {
      html += _row('Persona', _esc(persona.name));
      if (persona.role) html += _row('Role', _esc(persona.role));
    }
    if (id.tmux_pane_id) {
      var tmuxLabel = _esc(id.tmux_session_name || id.tmux_pane_id);
      var aliveClass = id.tmux_pane_alive ? 'alive' : 'dead';
      var aliveLabel = id.tmux_pane_alive ? 'alive' : 'dead';
      html += _row('Tmux', tmuxLabel + ' <span class="agent-info-badge ' + aliveClass + '">' + aliveLabel + '</span>');
    }
    if (id.bridge_available) {
      html += _row('Bridge', '<span class="agent-info-badge alive">available</span>');
    }
    if (id.claude_pid) {
      html += _row('Claude PID', id.claude_pid);
    }
    html += '</div>';

    // --- Project section ---
    if (proj) {
      var projectText = '## Project\n';
      projectText += '- **Name:** ' + proj.name + '\n';
      if (proj.current_branch) projectText += '- **Branch:** ' + proj.current_branch + '\n';
      if (proj.path) projectText += '- **Path:** `' + proj.path + '`\n';

      html += '<div class="agent-info-section">';
      html += _sectionHeader('Project', projectText);
      html += _row('Name', _esc(proj.name));
      if (proj.current_branch) html += _row('Branch', _esc(proj.current_branch));
      if (proj.path) html += _row('Path', '<span style="font-size:11px">' + _esc(proj.path) + '</span>');
      html += '</div>';
    }

    // --- Lifecycle section ---
    var lifecycleText = '## Lifecycle\n';
    lifecycleText += '- **State:** ' + (life.current_state || 'unknown') + '\n';
    lifecycleText += '- **Status:** ' + (life.is_active ? 'Active' : 'Ended') + '\n';
    if (life.uptime) lifecycleText += '- **Uptime:** ' + life.uptime + '\n';
    if (life.started_at) lifecycleText += '- **Started:** ' + life.started_at + '\n';
    if (life.last_seen_at) lifecycleText += '- **Last seen:** ' + life.last_seen_at + '\n';
    if (life.ended_at) lifecycleText += '- **Ended:** ' + life.ended_at + '\n';

    html += '<div class="agent-info-section">';
    html += _sectionHeader('Lifecycle', lifecycleText);
    var stateKey = (life.current_state || '').toLowerCase();
    html += _row('State', '<span class="agent-info-value state-pill state-' + stateKey + '">' + _esc(life.current_state) + '</span>');
    var activeClass = life.is_active ? 'active' : 'ended';
    var activeLabel = life.is_active ? 'Active' : 'Ended';
    html += _row('Status', '<span class="agent-info-badge ' + activeClass + '">' + activeLabel + '</span>');
    if (life.uptime) html += _row('Uptime', _esc(life.uptime));
    html += _row('Started', _timeAgo(life.started_at));
    html += _row('Last seen', _timeAgo(life.last_seen_at));
    if (life.ended_at) html += _row('Ended', _timeAgo(life.ended_at));
    html += '</div>';

    // --- Priority section ---
    if (prio.score !== null && prio.score !== undefined) {
      var priorityText = '## Priority\n';
      priorityText += '- **Score:** ' + (prio.score || 0) + ' / 100\n';
      if (prio.reason) priorityText += '- **Reason:** ' + prio.reason + '\n';

      html += '<div class="agent-info-section">';
      html += _sectionHeader('Priority', priorityText);
      var score = prio.score || 0;
      var barColor = score > 70 ? 'var(--success, #73e0a0)' : score > 40 ? 'var(--accent, #e0b073)' : 'var(--text-muted, #888)';
      html += _row('Score', score + ' / 100');
      html += '<div class="agent-info-priority-bar"><div class="agent-info-priority-fill" style="width:' + score + '%;background:' + barColor + '"></div></div>';
      if (prio.reason) html += _row('Reason', '<span style="font-family:inherit;font-size:12px">' + _esc(prio.reason) + '</span>');
      html += '</div>';
    }

    // --- Headspace section ---
    if (headspace) {
      var headspaceText = '## Headspace\n';
      headspaceText += '- **State:** ' + (headspace.state || 'unknown') + '\n';
      if (headspace.is_flow_state) headspaceText += '- **Flow state:** yes' + (headspace.flow_duration_minutes ? ' (' + headspace.flow_duration_minutes + ' min)' : '') + '\n';
      if (headspace.frustration_rolling_10 !== null && headspace.frustration_rolling_10 !== undefined) headspaceText += '- **Frustration (10t):** ' + headspace.frustration_rolling_10.toFixed(1) + '\n';
      if (headspace.frustration_rolling_30min !== null && headspace.frustration_rolling_30min !== undefined) headspaceText += '- **Frustration (30m):** ' + headspace.frustration_rolling_30min.toFixed(1) + '\n';
      if (headspace.frustration_rolling_3hr !== null && headspace.frustration_rolling_3hr !== undefined) headspaceText += '- **Frustration (3hr):** ' + headspace.frustration_rolling_3hr.toFixed(1) + '\n';
      if (headspace.turn_rate_per_hour !== null && headspace.turn_rate_per_hour !== undefined) headspaceText += '- **Turn rate:** ' + headspace.turn_rate_per_hour.toFixed(1) + '/hr\n';

      html += '<div class="agent-info-section">';
      html += _sectionHeader('Headspace', headspaceText);
      var hsState = (headspace.state || 'green').toLowerCase();
      var hsColor = hsState === 'red' ? 'var(--error, #e07373)' : hsState === 'yellow' ? 'var(--accent, #e0b073)' : 'var(--success, #73e0a0)';
      html += _row('Alert', '<span style="color:' + hsColor + ';font-weight:600">\u25cf ' + _esc(headspace.state) + '</span>');
      if (headspace.is_flow_state) {
        html += _row('Flow state', '<span class="agent-info-badge alive">in flow</span>' + (headspace.flow_duration_minutes ? ' (' + headspace.flow_duration_minutes + ' min)' : ''));
      }
      if (headspace.frustration_rolling_10 !== null && headspace.frustration_rolling_10 !== undefined) {
        html += _row('Frustration (10t)', headspace.frustration_rolling_10.toFixed(1));
      }
      if (headspace.turn_rate_per_hour !== null && headspace.turn_rate_per_hour !== undefined) {
        html += _row('Turn rate', headspace.turn_rate_per_hour.toFixed(1) + '/hr');
      }
      html += '</div>';
    }

    // --- Frustration sparkline ---
    if (frustration.length > 0) {
      var frustrationText = '## Recent Frustration\n';
      for (var fi2 = 0; fi2 < frustration.length && fi2 < 20; fi2++) {
        frustrationText += '- Score: ' + frustration[fi2].score + ' (' + frustration[fi2].timestamp + ')\n';
      }

      html += '<div class="agent-info-section">';
      html += _sectionHeader('Recent Frustration', frustrationText);
      html += '<div class="agent-info-frustration-list">';
      for (var fi = 0; fi < frustration.length && fi < 20; fi++) {
        var fs = frustration[fi].score;
        var fc = fs >= 7 ? 'var(--error, #e07373)' : fs >= 4 ? 'var(--accent, #e0b073)' : 'var(--success, #73e0a0)';
        html += '<span class="agent-info-frustration-dot" style="background:' + fc + '" title="' + fs + '"></span>';
      }
      html += '</div></div>';
    }

    // --- Guardrails section ---
    if (guardrails) {
      var guardrailsText = '## Guardrails\n';
      guardrailsText += '- **Version hash:** ' + (guardrails.version_hash || 'unknown') + '\n';
      guardrailsText += '- **Status:** ' + (guardrails.stale ? 'stale' : 'current') + '\n';

      html += '<div class="agent-info-section">';
      html += _sectionHeader('Guardrails', guardrailsText);
      var staleLabel = guardrails.stale ? '<span class="agent-info-badge ended">stale</span>' : '<span class="agent-info-badge alive">current</span>';
      html += _row('Version', staleLabel);
      html += '</div>';
    }

    // --- Recent Commands ---
    var commandsText = '## Command History (' + commands.length + ')\n';
    for (var ci2 = 0; ci2 < commands.length && ci2 < 5; ci2++) {
      var c = commands[ci2];
      commandsText += '\n### #' + (ci2 + 1) + ' [' + c.state + '] ' + (c.instruction || 'No instruction') + '\n';
      commandsText += '- **Turns:** ' + c.turn_count + '\n';
      if (c.completion_summary) commandsText += '- **Summary:** ' + c.completion_summary + '\n';
      if (c.started_at) commandsText += '- **Started:** ' + c.started_at + '\n';
      if (c.completed_at) commandsText += '- **Completed:** ' + c.completed_at + '\n';
    }

    html += '<div class="agent-info-section">';
    html += _sectionHeader('Recent Commands', commandsText);
    if (commands.length === 0) {
      html += '<div class="agent-info-none">No commands recorded</div>';
    } else {
      html += '<ul class="agent-info-commands">';
      for (var ci = 0; ci < commands.length && ci < 5; ci++) {
        var cmd = commands[ci];
        html += '<li class="agent-info-command">';
        html += '<div class="agent-info-command-header">';
        html += '<span class="agent-info-command-state">' + _esc(cmd.state) + '</span>';
        html += '<span class="agent-info-command-meta">' + cmd.turn_count + ' turns &middot; ' + _timeAgo(cmd.started_at) + '</span>';
        html += '</div>';
        if (cmd.instruction) html += '<div class="agent-info-command-instruction">' + _esc(cmd.instruction.length > 120 ? cmd.instruction.substring(0, 120) + '\u2026' : cmd.instruction) + '</div>';
        if (cmd.completion_summary) html += '<div class="agent-info-command-summary">' + _esc(cmd.completion_summary.length > 100 ? cmd.completion_summary.substring(0, 100) + '\u2026' : cmd.completion_summary) + '</div>';
        html += '</li>';
      }
      html += '</ul>';
    }
    html += '</div>';

    if (content) {
      content.innerHTML = html;
      _wireCopyButtons(content);
    }
  }

  function _row(label, value) {
    return '<div class="agent-info-row"><span class="agent-info-label">' + _esc(label) + '</span><span class="agent-info-value">' + value + '</span></div>';
  }

  // --- Wire close handlers on DOMContentLoaded ---
  document.addEventListener('DOMContentLoaded', function () {
    var overlay = document.getElementById('agent-info-overlay');
    var closeBtn = document.getElementById('agent-info-close-btn');
    if (overlay) overlay.addEventListener('click', close);
    if (closeBtn) closeBtn.addEventListener('click', close);
  });

  return {
    open: open,
    close: close
  };
})();
