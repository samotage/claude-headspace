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

    // Sort: projects with active agents first, then alphabetical
    var sorted = projects.slice().sort(function (a, b) {
      var aCount = a.agent_count || 0;
      var bCount = b.agent_count || 0;
      if (aCount > 0 && bCount === 0) return -1;
      if (aCount === 0 && bCount > 0) return 1;
      return (a.name || '').localeCompare(b.name || '');
    });

    var html = '';
    for (var i = 0; i < sorted.length; i++) {
      var p = sorted[i];
      var count = p.agent_count || 0;
      var badgeClass = count === 0 ? 'project-picker-badge zero' : 'project-picker-badge';
      var shortPath = (p.path || '').replace(/^\/Users\/[^/]+\//, '~/');
      html += '<div class="project-picker-row" data-project-name="' + VoiceChatRenderer.esc(p.name) + '">'
        + '<div class="project-picker-info">'
        + '<div class="project-picker-name">' + VoiceChatRenderer.esc(p.name) + '</div>'
        + '<div class="project-picker-path">' + VoiceChatRenderer.esc(shortPath) + '</div>'
        + '</div>'
        + '<span class="' + badgeClass + '">' + count + ' agent' + (count !== 1 ? 's' : '') + '</span>'
        + '</div>';
    }
    list.innerHTML = html;

    // Bind click handlers
    var rows = list.querySelectorAll('.project-picker-row');
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
    // Sort each group: newest agent first (highest agent_id)
    for (var si = 0; si < projectOrder.length; si++) {
      projectGroups[projectOrder[si]].sort(function (a, b) {
        return b.agent_id - a.agent_id;
      });
    }

    // Helper to build a single agent card's HTML
    function buildCardHtml(a, isEnded) {
      var stateClass = isEnded ? 'state-ended' : 'state-' + (a.state || '').toLowerCase();
      var stateLabel = isEnded ? 'Ended' : (a.state_label || a.state || 'unknown');
      var heroChars = a.hero_chars || '';
      var heroTrail = a.hero_trail || '';

      var instructionHtml = a.task_instruction
        ? '<div class="agent-instruction">' + VoiceChatRenderer.esc(a.task_instruction) + '</div>'
        : '';

      var summaryText = '';
      if (a.task_completion_summary) {
        summaryText = a.task_completion_summary;
      } else if (a.task_summary && a.task_summary !== a.task_instruction) {
        summaryText = a.task_summary;
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

      // Kebab menu: ended agents only get "Fetch context"
      var kebabMenuHtml;
      if (isEnded) {
        kebabMenuHtml = '<div class="agent-kebab-menu" data-agent-id="' + a.agent_id + '">'
          + '<button class="kebab-menu-item agent-ctx-action" data-agent-id="' + a.agent_id + '">'
          + '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.5"/><path d="M8 5v3.5L10.5 10"/></svg>'
          + '<span>Fetch context</span></button>'
          + '</div>';
      } else {
        kebabMenuHtml = '<div class="agent-kebab-menu" data-agent-id="' + a.agent_id + '">'
          + '<button class="kebab-menu-item agent-ctx-action" data-agent-id="' + a.agent_id + '">'
          + '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.5"/><path d="M8 5v3.5L10.5 10"/></svg>'
          + '<span>Fetch context</span></button>'
          + '<div class="kebab-divider"></div>'
          + '<button class="kebab-menu-item agent-kill-action" data-agent-id="' + a.agent_id + '">'
          + '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l10 10M13 3L3 13"/></svg>'
          + '<span>Dismiss agent</span></button>'
          + '</div>';
      }

      return '<div class="agent-card ' + stateClass + selectedClass + endedClass + '" data-agent-id="' + a.agent_id + '">'
        + '<div class="agent-header">'
        + '<a class="agent-card-link" href="/voice?agent_id=' + a.agent_id + '">'
        + '<div class="agent-hero-id">'
        + '<span class="agent-hero">' + VoiceChatRenderer.esc(heroChars) + '</span>'
        + '<span class="agent-hero-trail">' + VoiceChatRenderer.esc(heroTrail) + '</span>'
        + '</div>'
        + '</a>'
        + '<div class="agent-header-actions">'
        + '<span class="agent-state ' + stateClass + '">' + VoiceChatRenderer.esc(stateLabel) + '</span>'
        + '<button class="agent-kebab-btn" data-agent-id="' + a.agent_id + '" title="Actions">&#8942;</button>'
        + kebabMenuHtml
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

    var html = '';
    for (var p = 0; p < projectOrder.length; p++) {
      var projName = projectOrder[p];
      var group = projectGroups[projName];
      var endedGroup = endedByProject[projName] || [];

      html += '<div class="project-group">'
        + '<div class="project-group-header">'
        + '<span class="project-group-name">' + VoiceChatRenderer.esc(projName) + '</span>'
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

      // Ended agents (with divider if there are active agents above)
      if (endedGroup.length > 0) {
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

    // Bind kebab menu buttons
    var kebabBtns = list.querySelectorAll('.agent-kebab-btn');
    for (var c = 0; c < kebabBtns.length; c++) {
      kebabBtns[c].addEventListener('click', function (e) {
        e.stopPropagation();
        var agentId = this.getAttribute('data-agent-id');
        var menu = list.querySelector('.agent-kebab-menu[data-agent-id="' + agentId + '"]');
        // Close any other open menus
        var allMenus = list.querySelectorAll('.agent-kebab-menu.open');
        for (var m = 0; m < allMenus.length; m++) {
          if (allMenus[m] !== menu) allMenus[m].classList.remove('open');
        }
        if (menu) menu.classList.toggle('open');
      });
    }

    // Bind kebab menu actions
    var ctxActions = list.querySelectorAll('.agent-ctx-action');
    for (var ca = 0; ca < ctxActions.length; ca++) {
      ctxActions[ca].addEventListener('click', function (e) {
        e.stopPropagation();
        var agentId = parseInt(this.getAttribute('data-agent-id'), 10);
        closeAllKebabMenus();
        checkAgentContext(agentId);
      });
    }
    var killActions = list.querySelectorAll('.agent-kill-action');
    for (var ka = 0; ka < killActions.length; ka++) {
      killActions[ka].addEventListener('click', function (e) {
        e.stopPropagation();
        var agentId = parseInt(this.getAttribute('data-agent-id'), 10);
        closeAllKebabMenus();
        shutdownAgent(agentId);
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
    var menus = document.querySelectorAll('.agent-kebab-menu.open, .project-kebab-menu.open');
    for (var i = 0; i < menus.length; i++) {
      menus[i].classList.remove('open');
    }
  }

  // --- Agent card click handler (private) ---

  function onAgentCardClick(e) {
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
        refreshAgents();
      }).catch(function (err) {
        alert('Shutdown failed: ' + (err.error || 'unknown error'));
      });
    }
  }

  // --- Create agent for project ---

  function createAgentForProject(projectName) {
    VoiceState.pendingNewAgentProject = projectName;
    showPendingAgentPlaceholder(projectName);
    VoiceAPI.createAgent(projectName).then(function (data) {
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

  // --- Pending agent placeholder (private) ---

  function showPendingAgentPlaceholder(projectName) {
    var list = document.getElementById('agent-list');
    if (!list) return;
    // Find the project group matching this project
    var groups = list.querySelectorAll('.project-group');
    var targetGroup = null;
    for (var i = 0; i < groups.length; i++) {
      var nameEl = groups[i].querySelector('.project-group-name');
      if (nameEl && nameEl.textContent.trim().toLowerCase() === projectName.toLowerCase()) {
        targetGroup = groups[i];
        break;
      }
    }
    // If no matching group exists (project has 0 agents), create a temporary one
    if (!targetGroup) {
      targetGroup = document.createElement('div');
      targetGroup.className = 'project-group';
      targetGroup.id = 'pending-project-group';
      targetGroup.innerHTML = '<div class="project-group-header">'
        + '<span class="project-group-name">' + VoiceChatRenderer.esc(projectName) + '</span>'
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
              task_instruction: a.task_instruction || '',
              state: (a.state || '').toLowerCase(),
              project_name: a.project || ''
            };
          }
        }
        VoiceChatRenderer.renderAttentionBanners();
      }
    }).catch(function () { /* ignore */ });
  }

  // --- Public API ---

  return {
    setAgentSelectedHandler: setAgentSelectedHandler,
    highlightSelectedAgent: highlightSelectedAgent,
    renderAgentList: renderAgentList,
    closeAllKebabMenus: closeAllKebabMenus,
    selectAgent: selectAgent,
    autoTarget: autoTarget,
    createAgentForProject: createAgentForProject,
    refreshAgents: refreshAgents,
    openProjectPicker: openProjectPicker,
    closeProjectPicker: closeProjectPicker,
    filterProjectList: filterProjectList,
    showToast: showToast
  };
})();
