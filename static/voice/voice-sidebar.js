/* VoiceSidebar — agent list rendering, project picker, agent CRUD, kebab menus,
 * agent highlighting, and sidebar refresh logic.
 *
 * Reads/writes VoiceState for agents, targetAgentId, pendingNewAgentProject,
 * projectPickerOpen, allProjects, endedAgents, otherAgentStates, etc.
 * Uses a callback for agent selection (wired by VoiceApp.init).
 */
window.VoiceSidebar = (function () {
  'use strict';

  // Callback wired by VoiceApp.init
  var _onAgentSelected = null;   // called when an agent card is clicked/selected (agentId)

  function setAgentSelectedHandler(fn) { _onAgentSelected = fn; }

  // --- Project Picker ---

  function openProjectPicker() {
    VoiceState.projectPickerOpen = true;
    var bd = document.getElementById('project-picker-backdrop');
    var pk = document.getElementById('project-picker');
    var search = document.getElementById('project-picker-search');
    if (bd) bd.classList.add('open');
    if (pk) pk.classList.add('open');
    if (search) { search.value = ''; search.focus(); }
    fetchProjects();
  }

  function closeProjectPicker() {
    VoiceState.projectPickerOpen = false;
    var bd = document.getElementById('project-picker-backdrop');
    var pk = document.getElementById('project-picker');
    if (bd) bd.classList.remove('open');
    if (pk) pk.classList.remove('open');
  }

  function fetchProjects() {
    var list = document.getElementById('project-picker-list');
    if (list) list.innerHTML = '<div class="project-picker-empty">Loading\u2026</div>';
    VoiceAPI.getProjects().then(function (data) {
      VoiceState.allProjects = Array.isArray(data) ? data : [];
      renderProjectList(VoiceState.allProjects);
    }).catch(function () {
      VoiceState.allProjects = [];
      if (list) list.innerHTML = '<div class="project-picker-empty">Failed to load projects</div>';
    });
  }

  function renderProjectList(projects) {
    var list = document.getElementById('project-picker-list');
    if (!list) return;

    if (!projects || projects.length === 0) {
      list.innerHTML = '<div class="project-picker-empty">No projects found</div>';
      return;
    }

    // Sort alphabetically by name
    var sorted = projects.slice().sort(function (a, b) {
      return (a.name || '').localeCompare(b.name || '');
    });

    var html = '<div class="project-picker-grid">';
    for (var i = 0; i < sorted.length; i++) {
      var p = sorted[i];
      var count = p.agent_count || 0;
      var badgeClass = count === 0 ? 'project-picker-cell-badge zero' : 'project-picker-cell-badge';
      var shortPath = (p.path || '').replace(/^\/Users\/[^/]+\//, '~/');
      html += '<div class="project-picker-cell" data-project-name="' + VoiceChatRenderer.esc(p.name) + '"'
        + ' title="' + VoiceChatRenderer.esc(shortPath) + '">'
        + '<div class="project-picker-cell-name">' + VoiceChatRenderer.esc(p.name) + '</div>'
        + '<span class="' + badgeClass + '">' + count + ' agent' + (count !== 1 ? 's' : '') + '</span>'
        + '</div>';
    }
    html += '</div>';
    list.innerHTML = html;

    // Bind click handlers
    var rows = list.querySelectorAll('.project-picker-cell');
    for (var r = 0; r < rows.length; r++) {
      rows[r].addEventListener('click', function () {
        var name = this.getAttribute('data-project-name');
        onProjectPicked(this, name);
      });
    }
  }

  function filterProjectList(query) {
    if (!query) {
      renderProjectList(VoiceState.allProjects);
      return;
    }
    var q = query.toLowerCase();
    var filtered = VoiceState.allProjects.filter(function (p) {
      return (p.name || '').toLowerCase().indexOf(q) !== -1;
    });
    renderProjectList(filtered);
  }

  function onProjectPicked(rowEl, projectName) {
    if (rowEl) rowEl.classList.add('creating');
    closeProjectPicker();
    createAgentForProject(projectName);
  }

  // --- Agent highlighting in sidebar ---

  function highlightSelectedAgent() {
    var cards = document.querySelectorAll('.agent-card');
    for (var i = 0; i < cards.length; i++) {
      var id = parseInt(cards[i].getAttribute('data-agent-id'), 10);
      cards[i].classList.toggle('selected', id === VoiceState.targetAgentId && VoiceState.layoutMode === 'split');
    }
  }

  // --- Agent list ---

  function renderAgentList(agents, endedAgents) {
    // Detect newly appeared agents before overwriting agents
    var oldIds = {};
    var currentAgents = VoiceState.agents;
    for (var oi = 0; oi < currentAgents.length; oi++) {
      oldIds[currentAgents[oi].agent_id] = true;
    }

    VoiceState.agents = agents || [];
    var list = document.getElementById('agent-list');
    if (!list) return;

    // Auto-select a newly created agent when it first appears
    if (VoiceState.pendingNewAgentProject) {
      var agentsArr = VoiceState.agents;
      for (var ni = 0; ni < agentsArr.length; ni++) {
        var a = agentsArr[ni];
        if (!oldIds[a.agent_id] && (a.project || '').toLowerCase() === VoiceState.pendingNewAgentProject.toLowerCase()) {
          var newAgentId = a.agent_id;
          VoiceState.pendingNewAgentProject = null;
          // Defer selection until after render completes
          setTimeout(function () { selectAgent(newAgentId); }, 0);
          break;
        }
      }
    }

    // Save scroll position before re-render
    var sidebar = document.getElementById('sidebar');
    var savedScroll = sidebar ? sidebar.scrollTop : 0;

    // Group ended agents by project
    var endedByProject = {};
    if (endedAgents && endedAgents.length) {
      for (var ei = 0; ei < endedAgents.length; ei++) {
        var ep = endedAgents[ei].project || 'unknown';
        if (!endedByProject[ep]) endedByProject[ep] = [];
        endedByProject[ep].push(endedAgents[ei]);
      }
    }

    var hasEnded = Object.keys(endedByProject).length > 0;

    if (VoiceState.agents.length === 0 && !hasEnded) {
      list.innerHTML = '<div class="empty-state">No active agents</div>';
      return;
    }

    // Group agents by project, newest first within each group
    var projectGroups = {};
    var projectOrder = [];
    var agentsList = VoiceState.agents;
    for (var i = 0; i < agentsList.length; i++) {
      var proj = agentsList[i].project || 'unknown';
      if (!projectGroups[proj]) {
        projectGroups[proj] = [];
        projectOrder.push(proj);
      }
      projectGroups[proj].push(agentsList[i]);
    }
    // Add projects that only have ended agents
    for (var endedProj in endedByProject) {
      if (!projectGroups[endedProj]) {
        projectGroups[endedProj] = [];
        projectOrder.push(endedProj);
      }
    }
    // Sort project groups alphabetically (case-insensitive)
    projectOrder.sort(function (a, b) {
      return a.toLowerCase().localeCompare(b.toLowerCase());
    });
    // Sort each group: newest agent first (by started_at descending)
    for (var si = 0; si < projectOrder.length; si++) {
      projectGroups[projectOrder[si]].sort(function (a, b) {
        var aTime = a.started_at ? new Date(a.started_at).getTime() : 0;
        var bTime = b.started_at ? new Date(b.started_at).getTime() : 0;
        return bTime - aTime;
      });
    }

    // Helper to build a single agent card's HTML
    function buildCardHtml(a, isEnded) {
      var stateClass = isEnded ? 'state-ended' : 'state-' + (a.state || '').toLowerCase();
      var stateLabel = isEnded ? 'Ended' : (a.state_label || a.state || 'unknown');
      var heroChars = a.hero_chars || '';
      var heroTrail = a.hero_trail || '';

      var instructionHtml = a.command_instruction
        ? '<div class="agent-instruction">' + VoiceChatRenderer.esc(a.command_instruction) + '</div>'
        : '';

      var summaryText = '';
      if (a.command_completion_summary) {
        summaryText = a.command_completion_summary;
      } else if (a.command_summary && a.command_summary !== a.command_instruction) {
        summaryText = a.command_summary;
      }
      var summaryHtml = summaryText
        ? '<div class="agent-summary">' + VoiceChatRenderer.esc(summaryText) + '</div>'
        : '';

      // Context usage display
      var ctxHtml = '';
      if (a.context && a.context.percent_used != null) {
        var pct = a.context.percent_used;
        var ctxClass = 'ctx-normal';
        if (pct >= 75) ctxClass = 'ctx-high';
        else if (pct >= 65) ctxClass = 'ctx-warning';
        ctxHtml = '<span class="agent-ctx-inline ' + ctxClass + '">'
          + pct + '% \u00b7 ' + (a.context.remaining_tokens || '?') + ' rem</span>';
      }

      var footerParts = [];
      if (a.turn_count && a.turn_count > 0) {
        footerParts.push(a.turn_count + ' turn' + (a.turn_count !== 1 ? 's' : ''));
      }
      if (isEnded && a.ended_at) {
        var endedDate = new Date(a.ended_at);
        var endedElapsed = (Date.now() - endedDate.getTime()) / 1000;
        if (endedElapsed < 60) footerParts.push('ended ' + Math.floor(endedElapsed) + 's ago');
        else if (endedElapsed < 3600) footerParts.push('ended ' + Math.floor(endedElapsed / 60) + 'm ago');
        else footerParts.push('ended ' + Math.floor(endedElapsed / 3600) + 'h ago');
      } else {
        footerParts.push(a.last_activity_ago);
      }

      var selectedClass = (VoiceState.layoutMode === 'split' && a.agent_id === VoiceState.targetAgentId) ? ' selected' : '';
      var endedClass = isEnded ? ' ended' : '';

      // Kebab button only — menu rendered via portal
      var kebabBtnDataAttrs = ' data-agent-id="' + a.agent_id + '"'
        + ' data-persona-name="' + VoiceChatRenderer.esc(a.persona_name || '') + '"'
        + ' data-is-ended="' + (isEnded ? 'true' : 'false') + '"';

      // Persona name replaces hero chars when available
      var heroHtml;
      if (a.persona_name) {
        var roleSuffix = a.persona_role ? ' <span class="agent-hero-trail">' + VoiceChatRenderer.esc(a.persona_role) + '</span>' : '';
        heroHtml = '<span class="agent-hero">' + VoiceChatRenderer.esc(a.persona_name) + '</span>' + roleSuffix;
      } else {
        heroHtml = '<span class="agent-hero">' + VoiceChatRenderer.esc(heroChars) + '</span>'
          + '<span class="agent-hero-trail">' + VoiceChatRenderer.esc(heroTrail) + '</span>';
      }

      return '<div class="agent-card ' + stateClass + selectedClass + endedClass + '" data-agent-id="' + a.agent_id + '">'
        + '<div class="agent-header">'
        + '<a class="agent-card-link" href="/voice?agent_id=' + a.agent_id + '">'
        + '<div class="agent-hero-id">'
        + heroHtml
        + '</div>'
        + '</a>'
        + '<div class="agent-header-actions">'
        + '<span class="agent-state ' + stateClass + '">' + VoiceChatRenderer.esc(stateLabel) + '</span>'
        + '<button class="agent-kebab-btn"' + kebabBtnDataAttrs + ' title="Actions">&#8942;</button>'
        + '</div>'
        + '</div>'
        + '<a class="agent-card-link" href="/voice?agent_id=' + a.agent_id + '">'
        + '<div class="agent-body">'
        + instructionHtml
        + summaryHtml
        + '<div class="agent-ago">' + VoiceChatRenderer.esc(footerParts.join(' \u00b7 ')) + (ctxHtml ? ' ' + ctxHtml : '') + '</div>'
        + '</div>'
        + '</a>'
        + '</div>';
    }

    // Update total active agent count in sidebar header
    var totalCountEl = document.getElementById('total-agent-count');
    if (totalCountEl) {
      var totalActive = VoiceState.agents.length;
      totalCountEl.textContent = '(' + totalActive + ')';
    }

    var html = '';
    for (var p = 0; p < projectOrder.length; p++) {
      var projName = projectOrder[p];
      var group = projectGroups[projName];
      var endedGroup = endedByProject[projName] || [];

      var activeCount = group.length;
      html += '<div class="project-group" data-project="' + VoiceChatRenderer.esc(projName) + '">'
        + '<div class="project-group-header">'
        + '<span class="project-group-name">' + VoiceChatRenderer.esc(projName) + ' (' + activeCount + ')</span>'
        + '<button class="project-kebab-btn" data-project="' + VoiceChatRenderer.esc(projName) + '" title="Project actions">&#8942;</button>'
        + '<div class="project-kebab-menu" data-project="' + VoiceChatRenderer.esc(projName) + '">'
        + '<button class="kebab-menu-item project-add-agent" data-project="' + VoiceChatRenderer.esc(projName) + '">'
        + '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 3v10M3 8h10"/></svg>'
        + '<span>Add agent</span></button>'
        + '</div>'
        + '</div>'
        + '<div class="project-group-cards">';

      // Active agents
      for (var j = 0; j < group.length; j++) {
        html += buildCardHtml(group[j], false);
      }

      // Ended agents (sorted by started_at descending, with divider if there are active agents above)
      if (endedGroup.length > 0) {
        endedGroup.sort(function (a, b) {
          var aTime = a.started_at ? new Date(a.started_at).getTime() : 0;
          var bTime = b.started_at ? new Date(b.started_at).getTime() : 0;
          return bTime - aTime;
        });
        if (group.length > 0) {
          html += '<div class="ended-divider"></div>';
        }
        for (var ej = 0; ej < endedGroup.length; ej++) {
          html += buildCardHtml(endedGroup[ej], true);
        }
      }

      html += '</div></div>';
    }
    list.innerHTML = html;

    // Restore scroll position
    if (sidebar) sidebar.scrollTop = savedScroll;

    // Bind click handlers for agent selection
    var cards = list.querySelectorAll('.agent-card');
    for (var j = 0; j < cards.length; j++) {
      cards[j].addEventListener('click', onAgentCardClick);
    }
    // Prevent default on card links for regular clicks (SPA navigation),
    // but allow right-click / cmd+click to open in new tab natively
    var cardLinks = list.querySelectorAll('.agent-card-link');
    for (var cl = 0; cl < cardLinks.length; cl++) {
      cardLinks[cl].addEventListener('click', function (e) {
        e.preventDefault();
      });
    }

    // Bind kebab menu buttons — open portal menu
    var kebabBtns = list.querySelectorAll('.agent-kebab-btn');
    for (var c = 0; c < kebabBtns.length; c++) {
      kebabBtns[c].addEventListener('click', function (e) {
        e.stopPropagation();
        if (typeof PortalKebabMenu !== 'undefined' && PortalKebabMenu.isOpen()) {
          PortalKebabMenu.close();
          return;
        }
        var btn = this;
        var agentId = parseInt(btn.getAttribute('data-agent-id'), 10);
        if (typeof PortalKebabMenu !== 'undefined') {
          PortalKebabMenu.open(btn, {
            agentId: agentId,
            actions: _buildVoiceActions(btn),
            onAction: _handleVoiceAction
          });
        }
      });
    }
    // Bind project kebab menu buttons
    var projKebabBtns = list.querySelectorAll('.project-kebab-btn');
    for (var pk = 0; pk < projKebabBtns.length; pk++) {
      projKebabBtns[pk].addEventListener('click', function (e) {
        e.stopPropagation();
        var projectName = this.getAttribute('data-project');
        var menu = list.querySelector('.project-kebab-menu[data-project="' + projectName + '"]');
        closeAllKebabMenus();
        if (menu) menu.classList.toggle('open');
      });
    }

    // Bind project "Add agent" actions
    var addAgentActions = list.querySelectorAll('.project-add-agent');
    for (var aa = 0; aa < addAgentActions.length; aa++) {
      addAgentActions[aa].addEventListener('click', function (e) {
        e.stopPropagation();
        var projectName = this.getAttribute('data-project');
        closeAllKebabMenus();
        createAgentForProject(projectName);
      });
    }
  }

  // --- Kebab menus ---

  function closeAllKebabMenus() {
    // Close portal menu (agent kebabs)
    if (typeof PortalKebabMenu !== 'undefined') PortalKebabMenu.close();
    // Close project kebabs (still inline — no SSE mutation problem)
    var projMenus = document.querySelectorAll('.project-kebab-menu.open');
    for (var i = 0; i < projMenus.length; i++) {
      projMenus[i].classList.remove('open');
    }
  }

  // --- Agent card click handler (private) ---

  function onAgentCardClick(e) {
    // Guard: on touch devices the browser retargets the synthesised click
    // to .agent-header-actions when the dropdown extends beyond its layout
    // box, so we must also block clicks originating from that wrapper.
    if (e.target.closest('.agent-kebab-btn')
        || e.target.closest('.agent-header-actions')) {
      return;
    }
    var card = e.currentTarget;
    var id = parseInt(card.getAttribute('data-agent-id'), 10);
    selectAgent(id);
  }

  // --- Agent selection ---

  function selectAgent(id) {
    VoiceState.navStack = [];
    if (_onAgentSelected) {
      _onAgentSelected(id);
    }
  }

  // --- Context check (private) ---

  function checkAgentContext(agentId) {
    // API persists context to agent record and broadcasts card_refresh via SSE
    VoiceAPI.getAgentContext(agentId).then(function (data) {
      if (!data.available) {
        console.warn('Context unavailable for agent ' + agentId + ': ' + (data.reason || 'unknown'));
      }
    }).catch(function () {
      console.error('Error checking context for agent ' + agentId);
    });
  }

  // --- Deselect agent if it's the one currently being viewed ---

  function deselectIfTarget(agentId) {
    if (parseInt(VoiceState.targetAgentId, 10) === agentId) {
      VoiceState.targetAgentId = null;
      VoiceState.chatAgentEnded = false;
      VoiceLayout.showScreen('agents');
    }
  }

  // --- Download transcript (private) ---

  function _downloadAgentTranscript(agentId) {
    showToast('Preparing transcript\u2026');
    window.open('/api/agents/' + agentId + '/transcript', '_blank');
  }

  // --- Portal kebab menu action builders ---

  function _buildVoiceActions(btn) {
    var I = (typeof PortalKebabMenu !== 'undefined') ? PortalKebabMenu.ICONS : {};
    var isEnded = btn.getAttribute('data-is-ended') === 'true';

    if (isEnded) {
      return [
        { id: 'download-transcript', label: 'Download Transcript', icon: I.download || '' },
        { id: 'context', label: 'Fetch context', icon: I.context || '' },
        'divider',
        { id: 'revive', label: 'Revive', icon: I.revive || '' }
      ];
    }

    var actions = [
      { id: 'download-transcript', label: 'Download Transcript', icon: I.download || '' },
      { id: 'context', label: 'Fetch context', icon: I.context || '' }
    ];
    if (btn.getAttribute('data-persona-name')) {
      actions.push({ id: 'handoff', label: 'Handoff', icon: I.handoff || '', className: 'handoff-action' });
    }
    actions.push('divider');
    actions.push({ id: 'dismiss', label: 'Dismiss agent', icon: I.dismiss || '', className: 'kill-action' });
    return actions;
  }

  function _handleVoiceAction(actionId, agentId) {
    switch (actionId) {
      case 'download-transcript':
        _downloadAgentTranscript(agentId);
        break;
      case 'context':
        checkAgentContext(agentId);
        break;
      case 'dismiss':
        shutdownAgent(agentId);
        break;
      case 'handoff':
        handoffAgent(agentId);
        break;
      case 'revive':
        CHUtils.apiFetch('/api/agents/' + agentId + '/revive', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({}) })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (data.error) { showToast('Revival failed: ' + data.error); }
            else { showToast('Revival initiated'); refreshAgents(); }
          })
          .catch(function () { showToast('Revival failed'); });
        break;
    }
  }

  // --- Shutdown agent (private) ---

  function shutdownAgent(agentId) {
    if (typeof ConfirmDialog !== 'undefined') {
      ConfirmDialog.show(
        'Shut down agent?',
        'This will send /exit to the agent.',
        { confirmText: 'Shut down', cancelText: 'Cancel' }
      ).then(function (confirmed) {
        if (!confirmed) return;
        VoiceAPI.shutdownAgent(agentId).then(function () {
          deselectIfTarget(agentId);
          refreshAgents();
        }).catch(function (err) {
          if (window.Toast) {
            Toast.error('Shutdown failed', err.error || 'unknown error');
          } else {
            alert('Shutdown failed: ' + (err.error || 'unknown error'));
          }
        });
      });
    } else {
      if (!confirm('Shut down this agent?')) return;
      VoiceAPI.shutdownAgent(agentId).then(function () {
        deselectIfTarget(agentId);
        refreshAgents();
      }).catch(function (err) {
        alert('Shutdown failed: ' + (err.error || 'unknown error'));
      });
    }
  }

  // --- Handoff agent (private) ---

  function handoffAgent(agentId) {
    if (typeof ConfirmDialog !== 'undefined') {
      ConfirmDialog.show(
        'Handoff agent?',
        'The agent will write a handoff document and a successor agent will be created with the same persona. The current agent will remain alive.',
        { confirmText: 'Handoff', cancelText: 'Cancel' }
      ).then(function (confirmed) {
        if (!confirmed) return;
        _doHandoff(agentId);
      });
    } else {
      if (!confirm('Handoff this agent to a successor?')) return;
      _doHandoff(agentId);
    }
  }

  function _doHandoff(agentId) {
    CHUtils.apiFetch('/api/agents/' + agentId + '/handoff', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ reason: 'manual' })
    }).then(function (res) {
      return res.json().then(function (data) {
        if (res.ok) {
          showToast(data.message || 'Handoff initiated — agent writing handoff document');
        } else {
          showToast('Handoff failed: ' + (data.error || 'unknown error'));
        }
      });
    }).catch(function () {
      showToast('Handoff failed');
    });
  }

  // --- Create agent for project ---

  function createAgentForProject(projectName) {
    // Fetch personas; if any exist, show persona picker before creating
    VoiceAPI.getActivePersonas().then(function (data) {
      var personas = Array.isArray(data) ? data : (data && data.personas) ? data.personas : [];
      if (personas.length === 0) {
        _doCreateAgent(projectName, null);
      } else {
        showPersonaPicker(projectName, personas);
      }
    }).catch(function () {
      _doCreateAgent(projectName, null);
    });
  }

  function _doCreateAgent(projectName, personaSlug) {
    VoiceState.pendingNewAgentProject = projectName;
    showPendingAgentPlaceholder(projectName);
    VoiceAPI.createAgent(projectName, personaSlug).then(function (data) {
      showToast('Agent starting\u2026');
      refreshAgents();
    }).catch(function (err) {
      VoiceState.pendingNewAgentProject = null;
      removePendingAgentPlaceholder();
      if (window.Toast) {
        Toast.error('Create failed', err.error || 'unknown error');
      } else {
        alert('Create failed: ' + (err.error || 'unknown error'));
      }
    });
  }

  // --- Persona Picker ---

  var _pendingPersonaProject = null;

  function showPersonaPicker(projectName, personas) {
    _pendingPersonaProject = projectName;
    var bd = document.getElementById('persona-picker-backdrop');
    var pk = document.getElementById('persona-picker');
    if (bd) bd.classList.add('open');
    if (pk) pk.classList.add('open');
    renderPersonaList(personas);
  }

  function closePersonaPicker() {
    _pendingPersonaProject = null;
    var bd = document.getElementById('persona-picker-backdrop');
    var pk = document.getElementById('persona-picker');
    if (bd) bd.classList.remove('open');
    if (pk) pk.classList.remove('open');
  }

  function renderPersonaList(personas) {
    var list = document.getElementById('persona-picker-list');
    if (!list) return;

    // "No persona" default option (full width, above grid)
    var html = '<div class="persona-picker-row persona-picker-default" data-persona-slug="">'
      + '<div class="persona-picker-info">'
      + '<div class="persona-picker-name">No persona (default)</div>'
      + '<div class="persona-picker-desc">Standard Claude agent without persona</div>'
      + '</div>'
      + '</div>';

    // Sort personas by role then name
    var sorted = personas.slice().sort(function(a, b) {
      var ra = (a.role || 'other').toLowerCase();
      var rb = (b.role || 'other').toLowerCase();
      if (ra < rb) return -1;
      if (ra > rb) return 1;
      var na = (a.name || '').toLowerCase();
      var nb = (b.name || '').toLowerCase();
      if (na < nb) return -1;
      if (na > nb) return 1;
      return 0;
    });

    // Two-column grid of persona cells
    html += '<div class="persona-picker-grid">';
    for (var i = 0; i < sorted.length; i++) {
      var persona = sorted[i];
      var desc = persona.description || '';
      var role = persona.role || 'Other';
      html += '<div class="persona-picker-cell" data-persona-slug="' + VoiceChatRenderer.esc(persona.slug) + '"'
        + (desc ? ' title="' + VoiceChatRenderer.esc(desc) + '"' : '') + '>'
        + '<div class="persona-picker-cell-role">' + VoiceChatRenderer.esc(role) + '</div>'
        + '<div class="persona-picker-cell-name">' + VoiceChatRenderer.esc(persona.name) + '</div>'
        + '</div>';
    }
    html += '</div>';
    list.innerHTML = html;

    // Bind click handlers for default row and grid cells
    var clickables = list.querySelectorAll('.persona-picker-row, .persona-picker-cell');
    for (var k = 0; k < clickables.length; k++) {
      clickables[k].addEventListener('click', function () {
        var slug = this.getAttribute('data-persona-slug') || null;
        var projName = _pendingPersonaProject;
        closePersonaPicker();
        if (projName) _doCreateAgent(projName, slug);
      });
    }
  }

  // --- Pending agent placeholder (private) ---

  function showPendingAgentPlaceholder(projectName) {
    var list = document.getElementById('agent-list');
    if (!list) return;
    // Find the project group matching this project
    var groups = list.querySelectorAll('.project-group');
    var targetGroup = null;
    for (var i = 0; i < groups.length; i++) {
      var proj = groups[i].getAttribute('data-project');
      if (proj && proj.toLowerCase() === projectName.toLowerCase()) {
        targetGroup = groups[i];
        break;
      }
    }
    // If no matching group exists (project has 0 agents), create a temporary one
    if (!targetGroup) {
      targetGroup = document.createElement('div');
      targetGroup.className = 'project-group';
      targetGroup.id = 'pending-project-group';
      targetGroup.setAttribute('data-project', projectName);
      targetGroup.innerHTML = '<div class="project-group-header">'
        + '<span class="project-group-name">' + VoiceChatRenderer.esc(projectName) + ' (0)</span>'
        + '</div>'
        + '<div class="project-group-cards"></div>';
      list.prepend(targetGroup);
    }
    // Remove any existing placeholder
    removePendingAgentPlaceholder();
    // Append placeholder card
    var cardsContainer = targetGroup.querySelector('.project-group-cards');
    if (!cardsContainer) return;
    var placeholder = document.createElement('div');
    placeholder.className = 'agent-card agent-card-pending';
    placeholder.id = 'pending-agent-placeholder';
    placeholder.innerHTML = '<div class="agent-header">'
      + '<div class="agent-hero-id">'
      + '<span class="agent-hero">\u2026</span>'
      + '</div>'
      + '</div>'
      + '<div class="agent-body">'
      + '<div class="agent-instruction pending-pulse">Starting agent\u2026</div>'
      + '</div>';
    cardsContainer.prepend(placeholder);
  }

  function removePendingAgentPlaceholder() {
    var el = document.getElementById('pending-agent-placeholder');
    if (el) el.remove();
    // Also remove the temporary project group if it was created
    var tempGroup = document.getElementById('pending-project-group');
    if (tempGroup) tempGroup.remove();
  }

  // --- Toast (private) ---

  function showToast(message) {
    // Lightweight inline toast for voice app (no dependency on dashboard Toast)
    var existing = document.getElementById('voice-toast');
    if (existing) existing.remove();
    var toast = document.createElement('div');
    toast.id = 'voice-toast';
    toast.className = 'voice-toast';
    toast.textContent = message;
    document.body.appendChild(toast);
    // Trigger animation
    requestAnimationFrame(function () {
      toast.classList.add('show');
    });
    setTimeout(function () {
      toast.classList.remove('show');
      setTimeout(function () { toast.remove(); }, 300);
    }, 3000);
  }

  // --- Auto-targeting ---

  function autoTarget() {
    var agents = VoiceState.agents;
    var awaiting = [];
    for (var i = 0; i < agents.length; i++) {
      if (agents[i].awaiting_input) awaiting.push(agents[i]);
    }
    if (awaiting.length === 1) {
      VoiceState.targetAgentId = awaiting[0].agent_id;
      return awaiting[0];
    }
    return null;
  }

  // --- Refresh agents ---

  function refreshAgents() {
    // Fetch channels in parallel (non-blocking — failure is fine)
    VoiceAPI.getChannels().then(function (channels) {
      channels = Array.isArray(channels) ? channels : [];
      // Only keep active/pending channels
      var active = [];
      for (var ci = 0; ci < channels.length; ci++) {
        if (channels[ci].status === 'active' || channels[ci].status === 'pending') {
          // Merge into VoiceState.channels preserving SSE-updated last_sender/last_preview
          var existing = null;
          for (var ei = 0; ei < VoiceState.channels.length; ei++) {
            if (VoiceState.channels[ei].slug === channels[ci].slug) {
              existing = VoiceState.channels[ei];
              break;
            }
          }
          if (existing) {
            existing.name = channels[ci].name || existing.name;
            existing.status = channels[ci].status || existing.status;
            existing.channel_type = channels[ci].channel_type || existing.channel_type;
            active.push(existing);
          } else {
            active.push({
              slug: channels[ci].slug,
              name: channels[ci].name || channels[ci].slug,
              status: channels[ci].status,
              channel_type: channels[ci].channel_type || 'workshop',
              last_sender: null,
              last_preview: null,
              last_message_at: channels[ci].created_at || null
            });
          }
        }
      }
      VoiceState.channels = active;
      // Fetch members for uncached channels (non-blocking)
      for (var mi = 0; mi < active.length; mi++) {
        (function (slug) {
          if (!VoiceState.channelMembersBySlug[slug]) {
            VoiceAPI.getChannelMembers(slug).then(function (data) {
              VoiceState.channelMembersBySlug[slug] = Array.isArray(data) ? data : (data.members || []);
              renderChannelList(); // re-render with initials
            }).catch(function () { /* ignore */ });
          }
        })(active[mi].slug);
      }
      renderChannelList();
    }).catch(function () { /* ignore */ });

    VoiceAPI.getSessions(VoiceState.settings.verbosity, VoiceState.settings.showEndedAgents).then(function (data) {
      VoiceState.endedAgents = data.ended_agents || [];
      renderAgentList(data.agents || [], VoiceState.endedAgents);
      // Apply server auto_target setting if user hasn't overridden locally
      if (data.settings && data.settings.auto_target !== undefined) {
        var stored = null;
        try {
          var raw = localStorage.getItem('voice_settings');
          if (raw) stored = JSON.parse(raw);
        } catch (e) { /* ignore */ }
        if (!stored || stored.autoTarget === undefined) {
          VoiceState.settings.autoTarget = data.settings.auto_target;
        }
      }
      // Sync attention banners when on chat screen
      if (VoiceState.currentScreen === 'chat' && VoiceState.targetAgentId) {
        var agents = data.agents || [];
        VoiceState.otherAgentStates = {};
        for (var i = 0; i < agents.length; i++) {
          var a = agents[i];
          if (a.agent_id !== VoiceState.targetAgentId) {
            VoiceState.otherAgentStates[a.agent_id] = {
              hero_chars: a.hero_chars || '',
              hero_trail: a.hero_trail || '',
              command_instruction: a.command_instruction || '',
              state: (a.state || '').toLowerCase(),
              project_name: a.project || '',
              persona_name: a.persona_name || '',
              persona_role: a.persona_role || ''
            };
          }
        }
        VoiceChatRenderer.renderAttentionBanners();
      }
    }).catch(function () { /* ignore */ });
  }

  // --- Channel section rendering ---

  function renderChannelList() {
    var channels = VoiceState.channels || [];
    var container = document.getElementById('channel-list');

    // Create container if it doesn't exist yet
    if (!container) {
      var sidebar = document.getElementById('sidebar');
      if (!sidebar) return;
      container = document.createElement('div');
      container.id = 'channel-list';
      container.className = 'channel-list-section';
      // Insert channels at the top of the sidebar (before agent-list)
      var agentList = document.getElementById('agent-list');
      if (agentList) {
        sidebar.insertBefore(container, agentList);
      } else {
        sidebar.appendChild(container);
      }
    }

    // Filter to active/pending channels only
    var active = [];
    for (var i = 0; i < channels.length; i++) {
      if (channels[i].status === 'active' || channels[i].status === 'pending') {
        active.push(channels[i]);
      }
    }

    // Sort by most recent message
    active.sort(function (a, b) {
      var aTime = a.last_message_at ? new Date(a.last_message_at).getTime() : 0;
      var bTime = b.last_message_at ? new Date(b.last_message_at).getTime() : 0;
      return bTime - aTime;
    });

    var html = '<div class="channel-section-header">'
      + '<span class="channel-section-title">Channels (' + active.length + ')</span>'
      + '<button class="channel-create-btn" title="Create channel">+</button>'
      + '</div>';

    for (var ci = 0; ci < active.length; ci++) {
      var ch = active[ci];
      var statusClass = 'channel-status-' + (ch.status || 'pending');
      var isUnread = VoiceState.unreadChannelSlugs[ch.slug];
      var unreadClass = isUnread ? ' channel-card-unread' : '';
      var agoText = '';
      if (ch.last_message_at) {
        var elapsed = (Date.now() - new Date(ch.last_message_at).getTime()) / 1000;
        if (elapsed < 60) agoText = Math.floor(elapsed) + 's ago';
        else if (elapsed < 3600) agoText = Math.floor(elapsed / 60) + 'm ago';
        else agoText = Math.floor(elapsed / 3600) + 'h ago';
      }

      // Member initials
      var membersHtml = '';
      var members = VoiceState.channelMembersBySlug[ch.slug];
      if (members && members.length > 0) {
        membersHtml = '<div class="channel-members">';
        var maxShow = 4;
        for (var mi = 0; mi < Math.min(members.length, maxShow); mi++) {
          var name = members[mi].persona_name || members[mi].name || '?';
          var initial = name.charAt(0).toUpperCase();
          membersHtml += '<span class="channel-member-initial" title="' + _esc(name) + '">' + initial + '</span>';
        }
        if (members.length > maxShow) {
          membersHtml += '<span class="channel-member-more">+' + (members.length - maxShow) + '</span>';
        }
        membersHtml += '</div>';
      }

      var previewHtml = '';
      if (ch.last_sender && ch.last_preview) {
        previewHtml = '<div class="channel-preview">'
          + '<span class="channel-sender">' + _esc(ch.last_sender) + ':</span> '
          + '<span class="channel-content-preview">' + _esc(ch.last_preview) + '</span>'
          + '</div>';
      }

      html += '<div class="channel-card' + unreadClass + '" data-channel-slug="' + _esc(ch.slug) + '">'
        + '<a class="channel-card-link" href="/voice?channel=' + encodeURIComponent(ch.slug) + '">'
        + '<div class="channel-header">'
        + '<span class="channel-name">#' + _esc(ch.slug) + '</span>'
        + '<span class="channel-status ' + statusClass + '">' + _esc(ch.status || 'pending') + '</span>'
        + '</div>'
        + membersHtml
        + previewHtml
        + (agoText ? '<div class="channel-ago">' + agoText + '</div>' : '')
        + '</a>'
        + '</div>';
    }

    container.innerHTML = html;

    // Bind click handlers for channel cards
    var cards = container.querySelectorAll('.channel-card');
    for (var k = 0; k < cards.length; k++) {
      cards[k].addEventListener('click', function () {
        var slug = this.getAttribute('data-channel-slug');
        onChannelCardClick(slug);
      });
    }
    // Prevent default on card links for regular clicks (SPA navigation),
    // but allow right-click / cmd+click to open in new tab natively
    var channelLinks = container.querySelectorAll('.channel-card-link');
    for (var cl = 0; cl < channelLinks.length; cl++) {
      channelLinks[cl].addEventListener('click', function (e) {
        e.preventDefault();
      });
    }

    // Bind create channel button
    var createBtn = container.querySelector('.channel-create-btn');
    if (createBtn) {
      createBtn.addEventListener('click', function (e) {
        e.stopPropagation();
        openChannelPicker();
      });
    }
  }

  function onChannelCardClick(slug) {
    delete VoiceState.unreadChannelSlugs[slug];
    VoiceChannelChat.showChannelChatScreen(slug);
  }

  // --- Create Channel Bottom Sheet ---

  function openChannelPicker() {
    VoiceState.channelPickerOpen = true;
    var bd = document.getElementById('channel-picker-backdrop');
    var pk = document.getElementById('channel-picker');
    if (bd) bd.classList.add('open');
    if (pk) pk.classList.add('open');
    // Reset form
    var nameInput = document.getElementById('channel-name-input');
    var typeSelect = document.getElementById('channel-type-select');
    if (nameInput) { nameInput.value = ''; nameInput.focus(); }
    if (typeSelect) typeSelect.selectedIndex = 0;
    // Clone-replace submit button to prevent stale listeners
    var submitBtn = document.getElementById('channel-create-submit');
    if (submitBtn) {
      var newBtn = submitBtn.cloneNode(true);
      submitBtn.parentNode.replaceChild(newBtn, submitBtn);
      newBtn.addEventListener('click', function () { _submitCreateChannel(); });
    }
    // Enter key on name input submits
    if (nameInput) {
      nameInput.onkeydown = function (e) {
        if (e.key === 'Enter') { e.preventDefault(); _submitCreateChannel(); }
      };
    }
    // Fetch available members
    VoiceAPI.getAvailableMembers().then(function (data) {
      _renderMemberCheckboxes(data.projects || data);
    }).catch(function () {
      var list = document.getElementById('channel-member-list');
      if (list) list.innerHTML = '<div class="channel-picker-empty">Could not load members</div>';
    });
  }

  function closeChannelPicker() {
    VoiceState.channelPickerOpen = false;
    var bd = document.getElementById('channel-picker-backdrop');
    var pk = document.getElementById('channel-picker');
    if (bd) bd.classList.remove('open');
    if (pk) pk.classList.remove('open');
  }

  function _renderMemberCheckboxes(projects) {
    var list = document.getElementById('channel-member-list');
    if (!list) return;

    // projects can be an array of { project_name, agents: [{agent_id, persona_name, persona_slug}] }
    // or a flat array of agents
    if (!projects || (Array.isArray(projects) && projects.length === 0)) {
      list.innerHTML = '<div class="channel-picker-empty">No agents available</div>';
      return;
    }

    var html = '';
    if (Array.isArray(projects) && projects[0] && projects[0].project_name) {
      // Grouped by project
      for (var pi = 0; pi < projects.length; pi++) {
        var proj = projects[pi];
        var agents = proj.agents || [];
        if (agents.length === 0) continue;
        html += '<div class="channel-member-project">' + _esc(proj.project_name) + '</div>';
        for (var ai = 0; ai < agents.length; ai++) {
          var a = agents[ai];
          var label = a.persona_name || ('Agent #' + a.agent_id);
          var role = a.persona_role || '';
          html += '<label class="channel-member-option">'
            + '<input type="checkbox" value="' + a.agent_id + '">'
            + '<span class="channel-member-label">' + _esc(label)
            + (role ? ' <span class="channel-member-role">' + _esc(role) + '</span>' : '')
            + '</span></label>';
        }
      }
    } else if (Array.isArray(projects)) {
      // Flat array
      for (var fi = 0; fi < projects.length; fi++) {
        var f = projects[fi];
        var fLabel = f.persona_name || f.name || ('Agent #' + f.agent_id);
        html += '<label class="channel-member-option">'
          + '<input type="checkbox" value="' + (f.agent_id || f.id) + '">'
          + '<span class="channel-member-label">' + _esc(fLabel) + '</span></label>';
      }
    }

    list.innerHTML = html || '<div class="channel-picker-empty">No agents available</div>';
  }

  function _submitCreateChannel() {
    var nameInput = document.getElementById('channel-name-input');
    var typeSelect = document.getElementById('channel-type-select');
    var name = nameInput ? nameInput.value.trim() : '';
    var channelType = typeSelect ? typeSelect.value : 'workshop';

    if (!name) {
      if (nameInput) nameInput.focus();
      return;
    }

    // Collect checked members
    var checkboxes = document.querySelectorAll('#channel-member-list input[type="checkbox"]:checked');
    var members = [];
    for (var i = 0; i < checkboxes.length; i++) {
      members.push(parseInt(checkboxes[i].value, 10));
    }

    var submitBtn = document.getElementById('channel-create-submit');
    if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = 'Creating...'; }

    VoiceAPI.createChannel(name, channelType, members).then(function () {
      closeChannelPicker();
      showToast('Channel created');
      refreshAgents();
    }).catch(function (err) {
      if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = 'Create'; }
      showToast('Failed: ' + (err.error || 'unknown error'));
    });
  }

  // Use VoiceChatRenderer.esc for HTML escaping (always available on voice page)
  function _esc(str) {
    return VoiceChatRenderer.esc(str);
  }

  // --- Public API ---

  return {
    setAgentSelectedHandler: setAgentSelectedHandler,
    highlightSelectedAgent: highlightSelectedAgent,
    renderAgentList: renderAgentList,
    renderChannelList: renderChannelList,
    closeAllKebabMenus: closeAllKebabMenus,
    selectAgent: selectAgent,
    autoTarget: autoTarget,
    createAgentForProject: createAgentForProject,
    refreshAgents: refreshAgents,
    openProjectPicker: openProjectPicker,
    closeProjectPicker: closeProjectPicker,
    closePersonaPicker: closePersonaPicker,
    filterProjectList: filterProjectList,
    openChannelPicker: openChannelPicker,
    closeChannelPicker: closeChannelPicker,
    showToast: showToast,
    deselectIfTarget: deselectIfTarget
  };
})();
