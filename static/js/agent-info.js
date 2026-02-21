/**
 * Agent Info slider-pane modal.
 * Fetches and displays comprehensive debug info for an agent.
 */

(function() {
    'use strict';

    var state = {
        agentId: null,
        isOpen: false,
        data: null
    };

    function open(agentId) {
        state.agentId = agentId;
        state.isOpen = true;
        state.data = null;

        var backdrop = document.getElementById('agent-info-backdrop');
        var slider = document.getElementById('agent-info-slider');
        if (!slider) return;

        // Show slider
        if (backdrop) backdrop.classList.add('active');
        slider.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Loading state
        var contentEl = document.getElementById('agent-info-content');
        if (contentEl) {
            contentEl.innerHTML = '<p class="text-muted italic">Loading agent info...</p>';
        }

        var statusEl = document.getElementById('agent-info-status');
        if (statusEl) statusEl.textContent = '';

        // Add escape key listener
        document.addEventListener('keydown', keyHandler);

        // Fetch agent info
        CHUtils.apiFetch('/api/agents/' + agentId + '/info')
            .then(function(response) {
                if (!response.ok) {
                    return response.json().then(function(data) {
                        throw new Error(data.error || 'Failed to load agent info');
                    });
                }
                return response.json();
            })
            .then(function(data) {
                state.data = data;

                // Update hero in header — persona name or UUID
                var heroChars = document.getElementById('agent-info-hero-chars');
                var heroTrail = document.getElementById('agent-info-hero-trail');
                if (data.persona && data.persona.name) {
                    if (heroChars) heroChars.textContent = data.persona.name;
                    if (heroTrail) heroTrail.textContent = data.persona.role ? ' \u2014 ' + data.persona.role : '';
                } else {
                    var short = data.identity.session_uuid_short || '';
                    if (heroChars) heroChars.textContent = short.slice(0, 2);
                    if (heroTrail) heroTrail.textContent = short.slice(2);
                }

                render(contentEl, data);

                if (statusEl) {
                    statusEl.textContent = 'Agent #' + data.identity.id;
                }
            })
            .catch(function(err) {
                if (contentEl) {
                    contentEl.innerHTML = '<p class="text-red text-sm">Error: ' + CHUtils.escapeHtml(err.message) + '</p>';
                }
            });
    }

    function close() {
        var backdrop = document.getElementById('agent-info-backdrop');
        var slider = document.getElementById('agent-info-slider');
        if (backdrop) backdrop.classList.remove('active');
        if (slider) slider.classList.remove('active');
        document.body.style.overflow = '';
        state.isOpen = false;
        document.removeEventListener('keydown', keyHandler);
    }

    function keyHandler(e) {
        if (e.key === 'Escape' && state.isOpen) {
            close();
        }
    }

    function copyToClipboard(text, btnEl) {
        navigator.clipboard.writeText(text).then(function() {
            if (btnEl) {
                var original = btnEl.textContent;
                btnEl.textContent = 'Copied!';
                btnEl.classList.add('agent-info-copy-success');
                setTimeout(function() {
                    btnEl.textContent = original;
                    btnEl.classList.remove('agent-info-copy-success');
                }, 1500);
            }
        }).catch(function() {
            if (btnEl) {
                btnEl.textContent = 'Failed';
                setTimeout(function() {
                    btnEl.textContent = 'Copy';
                }, 1500);
            }
        });
    }

    function esc(str) {
        return CHUtils.escapeHtml(str || '');
    }

    /**
     * Build a section-level copy button that copies plain text for the section.
     * sectionId is used to store the text in a lookup for the onclick handler.
     */
    var sectionTexts = {};
    var sectionCounter = 0;

    function sectionCopyBtn(plainText) {
        var sid = 'sec_' + (sectionCounter++);
        sectionTexts[sid] = plainText;
        return '<button class="agent-info-copy-btn" data-section-id="' + sid + '">Copy</button>';
    }

    function formatTimestamp(isoStr) {
        if (!isoStr) return '<span class="text-muted">\u2014</span>';
        try {
            return new Date(isoStr).toLocaleString();
        } catch (e) {
            return esc(isoStr);
        }
    }

    function formatTimestampPlain(isoStr) {
        if (!isoStr) return '\u2014';
        try {
            return new Date(isoStr).toLocaleString();
        } catch (e) {
            return isoStr;
        }
    }

    function stateBadge(stateVal) {
        var colors = {
            'idle': 'bg-green/20 text-green',
            'commanded': 'bg-amber/20 text-amber',
            'processing': 'bg-blue/20 text-blue',
            'awaiting_input': 'bg-amber/20 text-amber',
            'complete': 'bg-green/20 text-green',
            'IDLE': 'bg-green/20 text-green',
            'COMMANDED': 'bg-amber/20 text-amber',
            'PROCESSING': 'bg-blue/20 text-blue',
            'AWAITING_INPUT': 'bg-amber/20 text-amber',
            'COMPLETE': 'bg-green/20 text-green',
            'TIMED_OUT': 'bg-red/20 text-red'
        };
        var cls = colors[stateVal] || 'bg-muted/20 text-muted';
        return '<span class="inline-block px-1.5 py-0.5 text-[10px] font-mono font-medium rounded ' + cls + '">' + esc(stateVal) + '</span>';
    }

    function render(contentEl, data) {
        if (!contentEl || !data) return;

        // Reset section copy state
        sectionTexts = {};
        sectionCounter = 0;

        var html = '';
        var id = data.identity;
        var proj = data.project;
        var life = data.lifecycle;
        var pri = data.priority;
        var hs = data.headspace;
        var commands = data.commands || [];

        // --- Persona Section (only when agent has persona) ---
        var per = data.persona;
        if (per) {
            var personaText = [
                '## Persona',
                '- **Name:** ' + per.name,
                '- **Role:** ' + (per.role || '\u2014'),
                '- **Status:** ' + (per.status || '\u2014'),
                '- **Slug:** ' + (per.slug || '\u2014')
            ].join('\n');

            html += '<div class="agent-info-section">';
            html += '<div class="agent-info-section-title"><span>Persona</span>' + sectionCopyBtn(personaText) + '</div>';
            html += row('Name', '<span class="text-cyan">' + esc(per.name) + '</span>');
            html += row('Role', esc(per.role || '\u2014'));
            html += row('Status', per.status === 'active' ? '<span class="text-green">' + esc(per.status) + '</span>' : esc(per.status || '\u2014'));
            html += row('Slug', esc(per.slug || '\u2014'));
            html += '</div>';
        }

        // --- Identity Section ---
        var identityText = [
            '## Identity',
            '- **Agent ID:** #' + id.id,
            '- **Session UUID:** `' + id.session_uuid + '`',
            '- **Claude Session:** ' + (id.claude_session_id || '\u2014'),
            '- **tmux Pane:** ' + (id.tmux_pane_id || '\u2014'),
            '- **tmux Session:** ' + (id.tmux_session_name || '\u2014'),
            '- **tmux Alive:** ' + (id.tmux_pane_alive ? 'Yes' : 'No'),
            '- **Bridge:** ' + (id.bridge_available ? 'Connected' : 'Disconnected'),
            '- **iTerm Pane:** ' + (id.iterm_pane_id || '\u2014'),
            '- **Transcript:** ' + (id.transcript_path || '\u2014')
        ].join('\n');

        html += '<div class="agent-info-section">';
        html += '<div class="agent-info-section-title"><span>Identity</span>' + sectionCopyBtn(identityText) + '</div>';
        html += row('Agent ID', '#' + id.id);
        html += row('Session UUID', '<span class="text-cyan">' + esc(id.session_uuid) + '</span>');
        html += row('Claude Session', esc(id.claude_session_id || '\u2014'));
        html += row('tmux Pane', esc(id.tmux_pane_id || '\u2014'));
        html += row('tmux Session', (id.tmux_session_name ? '<span class="text-green">' + esc(id.tmux_session_name) + '</span>' : '<span class="text-muted">\u2014</span>'));
        html += row('tmux Alive', id.tmux_pane_alive ? '<span class="text-green">Yes</span>' : '<span class="text-red">No</span>');
        html += row('Bridge', id.bridge_available ? '<span class="text-green">Connected</span>' : '<span class="text-muted">Disconnected</span>');
        html += row('iTerm Pane', esc(id.iterm_pane_id || '\u2014'));
        html += row('Transcript', esc(id.transcript_path || '\u2014'));
        html += '</div>';

        // --- Project Section ---
        var projectText = '';
        if (proj) {
            projectText = [
                '## Project',
                '- **Name:** ' + proj.name,
                '- **Path:** `' + proj.path + '`',
                '- **Branch:** ' + (proj.current_branch || '\u2014'),
                '- **GitHub:** ' + (proj.github_repo || '\u2014')
            ].join('\n');
        } else {
            projectText = '## Project\nNo project linked';
        }

        html += '<div class="agent-info-section">';
        html += '<div class="agent-info-section-title"><span>Project</span>' + sectionCopyBtn(projectText) + '</div>';
        if (proj) {
            html += row('Name', '<a href="/projects/' + esc(proj.slug) + '" class="text-cyan hover:underline">' + esc(proj.name) + '</a>');
            html += row('Path', esc(proj.path));
            html += row('Branch', esc(proj.current_branch || '\u2014'));
            html += row('GitHub', proj.github_repo ? '<span class="text-secondary">' + esc(proj.github_repo) + '</span>' : '<span class="text-muted">\u2014</span>');
        } else {
            html += '<p class="text-muted text-sm italic">No project linked</p>';
        }
        html += '</div>';

        // --- Lifecycle Section ---
        var lifecycleText = [
            '## Lifecycle',
            '- **State:** ' + life.current_state,
            '- **Active:** ' + (life.is_active ? 'Yes' : 'No'),
            '- **Uptime:** ' + (life.uptime || '\u2014'),
            '- **Started:** ' + formatTimestampPlain(life.started_at),
            '- **Last Seen:** ' + formatTimestampPlain(life.last_seen_at),
            '- **Ended:** ' + formatTimestampPlain(life.ended_at)
        ].join('\n');

        html += '<div class="agent-info-section">';
        html += '<div class="agent-info-section-title"><span>Lifecycle</span>' + sectionCopyBtn(lifecycleText) + '</div>';
        html += row('State', stateBadge(life.current_state));
        html += row('Active', life.is_active ? '<span class="text-green">Yes</span>' : '<span class="text-muted">No</span>');
        html += row('Uptime', esc(life.uptime || '\u2014'));
        html += row('Started', formatTimestamp(life.started_at));
        html += row('Last Seen', formatTimestamp(life.last_seen_at));
        html += row('Ended', life.ended_at ? formatTimestamp(life.ended_at) : '<span class="text-muted">\u2014</span>');
        html += '</div>';

        // --- Priority Section ---
        var priorityText = [
            '## Priority',
            '- **Score:** ' + (pri.score !== null ? pri.score : '\u2014'),
            '- **Reason:** ' + (pri.reason || '\u2014'),
            '- **Updated:** ' + formatTimestampPlain(pri.updated_at)
        ].join('\n');

        html += '<div class="agent-info-section">';
        html += '<div class="agent-info-section-title"><span>Priority</span>' + sectionCopyBtn(priorityText) + '</div>';
        html += row('Score', pri.score !== null ? '<span class="font-medium">' + pri.score + '</span>' : '<span class="text-muted">\u2014</span>');
        html += row('Reason', esc(pri.reason || '\u2014'));
        html += row('Updated', formatTimestamp(pri.updated_at));
        html += '</div>';

        // --- Headspace Section ---
        var headspaceTextLines = [];
        headspaceTextLines.push('## Headspace');
        if (hs) {
            headspaceTextLines.push('- **State:** ' + hs.state);
            headspaceTextLines.push('- **Frustration (10):** ' + (hs.frustration_rolling_10 !== null ? Number(hs.frustration_rolling_10).toFixed(1) : '\u2014'));
            headspaceTextLines.push('- **Frustration (30m):** ' + (hs.frustration_rolling_30min !== null ? Number(hs.frustration_rolling_30min).toFixed(1) : '\u2014'));
            headspaceTextLines.push('- **Frustration (3h):** ' + (hs.frustration_rolling_3hr !== null ? Number(hs.frustration_rolling_3hr).toFixed(1) : '\u2014'));
            headspaceTextLines.push('- **Flow State:** ' + (hs.is_flow_state ? 'Active' + (hs.flow_duration_minutes ? ' (' + hs.flow_duration_minutes + 'm)' : '') : 'No'));
            headspaceTextLines.push('- **Turn Rate:** ' + (hs.turn_rate_per_hour !== null ? Number(hs.turn_rate_per_hour).toFixed(1) + '/hr' : '\u2014'));
        } else {
            headspaceTextLines.push('No headspace data');
        }
        var fScores = data.frustration_scores || [];
        if (fScores.length > 0) {
            headspaceTextLines.push('- **Recent Frustration:** ' + fScores.slice(0, 20).map(function(f) { return f.score; }).join(', '));
        }
        var headspaceText = headspaceTextLines.join('\n');

        html += '<div class="agent-info-section">';
        html += '<div class="agent-info-section-title"><span>Headspace</span>' + sectionCopyBtn(headspaceText) + '</div>';
        if (hs) {
            var hsStateColors = { green: 'text-green', yellow: 'text-amber', red: 'text-red' };
            var hsStateClass = hsStateColors[hs.state] || 'text-muted';
            html += row('State', '<span class="' + hsStateClass + ' font-medium uppercase">' + esc(hs.state) + '</span>');
            html += row('Frustration (10)', hs.frustration_rolling_10 !== null ? Number(hs.frustration_rolling_10).toFixed(1) : '\u2014');
            html += row('Frustration (30m)', hs.frustration_rolling_30min !== null ? Number(hs.frustration_rolling_30min).toFixed(1) : '\u2014');
            html += row('Frustration (3h)', hs.frustration_rolling_3hr !== null ? Number(hs.frustration_rolling_3hr).toFixed(1) : '\u2014');
            html += row('Flow State', hs.is_flow_state ? '<span class="text-green">Active</span>' + (hs.flow_duration_minutes ? ' (' + hs.flow_duration_minutes + 'm)' : '') : '<span class="text-muted">No</span>');
            html += row('Turn Rate', hs.turn_rate_per_hour !== null ? Number(hs.turn_rate_per_hour).toFixed(1) + '/hr' : '\u2014');
        } else {
            html += '<p class="text-muted text-sm italic">No headspace data</p>';
        }

        // Recent frustration scores
        if (fScores.length > 0) {
            html += '<div class="mt-3 mb-1"><span class="text-muted text-xs font-mono uppercase">Recent Frustration</span></div>';
            html += '<div class="flex flex-wrap gap-1">';
            for (var fi = 0; fi < Math.min(fScores.length, 20); fi++) {
                var fs = fScores[fi];
                var fColor = fs.score <= 3 ? 'bg-green/20 text-green' : fs.score <= 6 ? 'bg-amber/20 text-amber' : 'bg-red/20 text-red';
                html += '<span class="inline-block px-1 py-0.5 text-[10px] font-mono rounded ' + fColor + '" title="' + esc(fs.timestamp) + '">' + fs.score + '</span>';
            }
            html += '</div>';
        }
        html += '</div>';

        // --- Command History Section ---
        var commandTextLines = [];
        commandTextLines.push('## Command History (' + commands.length + ')');
        for (var tti = 0; tti < commands.length; tti++) {
            var tt = commands[tti];
            commandTextLines.push('');
            commandTextLines.push('### #' + tt.id + ' [' + tt.state + '] ' + (tt.instruction || 'No instruction'));
            commandTextLines.push('- **Turns:** ' + tt.turn_count);
            if (tt.completion_summary) commandTextLines.push('- **Summary:** ' + tt.completion_summary);
            commandTextLines.push('- **Started:** ' + formatTimestampPlain(tt.started_at) + (tt.completed_at ? ' \u2014 **Completed:** ' + formatTimestampPlain(tt.completed_at) : ''));
            var ttTurns = tt.turns || [];
            if (ttTurns.length > 0) {
                commandTextLines.push('');
                for (var tui = 0; tui < ttTurns.length; tui++) {
                    var tu = ttTurns[tui];
                    var frustVal = (tu.frustration_score !== null && tu.frustration_score !== undefined) ? tu.frustration_score : '\u2014';
                    commandTextLines.push('**' + tu.actor.toUpperCase() + '** [' + tu.intent + '] ' + formatTimestampPlain(tu.timestamp) + (frustVal !== '\u2014' ? ' F:' + frustVal : ''));
                    if (tu.text) commandTextLines.push(tu.text);
                    else if (tu.summary) commandTextLines.push('*' + tu.summary + '*');
                    commandTextLines.push('');
                }
            }
        }
        var commandText = commandTextLines.length > 1 ? commandTextLines.join('\n') : 'No commands recorded';

        html += '<div class="agent-info-section">';
        html += '<div class="agent-info-section-title"><span>Command History (' + commands.length + ')</span>' + sectionCopyBtn(commandText) + '</div>';
        if (commands.length === 0) {
            html += '<p class="text-muted text-sm italic">No commands recorded</p>';
        } else {
            for (var ti = 0; ti < commands.length; ti++) {
                var command = commands[ti];
                html += '<details class="agent-info-command-details">';
                html += '<summary class="agent-info-command-header">';
                html += '<span class="text-muted text-[10px] font-mono">#' + command.id + '</span> ';
                html += stateBadge(command.state) + ' ';
                html += '<span class="text-secondary text-xs">' + esc(command.instruction || 'No instruction') + '</span>';
                html += '<span class="text-muted text-[10px] ml-auto">' + command.turn_count + ' turn' + (command.turn_count !== 1 ? 's' : '') + '</span>';
                html += '</summary>';

                // Command detail
                html += '<div class="agent-info-command-body">';
                if (command.completion_summary) {
                    html += '<div class="text-green text-xs italic mb-2">' + esc(command.completion_summary) + '</div>';
                }
                html += '<div class="text-muted text-[10px] mb-1">';
                html += 'Started: ' + formatTimestamp(command.started_at);
                if (command.completed_at) html += ' &mdash; Completed: ' + formatTimestamp(command.completed_at);
                html += '</div>';

                // Turns — conversation blocks
                var turns = command.turns || [];
                if (turns.length > 0) {
                    html += '<div class="text-muted text-[10px] font-mono uppercase mt-2 mb-1">Turns (' + turns.length + ')</div>';
                    html += '<div class="agent-info-turn-blocks">';
                    for (var ui = 0; ui < turns.length; ui++) {
                        var turn = turns[ui];
                        var actorClass = turn.actor === 'user' ? 'text-amber' : 'text-cyan';
                        var frustBadge = '';
                        if (turn.frustration_score !== null && turn.frustration_score !== undefined) {
                            var fC = turn.frustration_score <= 3 ? 'text-green' : turn.frustration_score <= 6 ? 'text-amber' : 'text-red';
                            frustBadge = '<span class="' + fC + ' text-[10px]">F:' + turn.frustration_score + '</span>';
                        }
                        html += '<div class="agent-info-turn-block">';
                        // Header row
                        html += '<div class="flex items-center gap-1.5 flex-wrap">';
                        html += '<span class="text-muted text-[9px] font-mono">#' + turn.id + '</span>';
                        html += '<span class="text-[10px] font-medium px-1 py-0.5 rounded ' + actorClass + ' bg-surface">' + esc(turn.actor.toUpperCase()) + '</span>';
                        html += '<span class="text-[10px] text-muted">' + esc(turn.intent) + '</span>';
                        if (frustBadge) html += frustBadge;
                        html += '<span class="text-[10px] text-muted ml-auto">' + formatTimestamp(turn.timestamp) + '</span>';
                        html += '</div>';
                        // Primary content: turn text
                        var turnText = turn.text || '';
                        var turnSummary = turn.summary || '';
                        if (turnText) {
                            var displayText = turnText.length > 300 ? turnText.substring(0, 300) + '...' : turnText;
                            var textElId = 'ai-turn-text-' + turn.id;
                            html += '<div class="agent-info-turn-text whitespace-pre-line" id="' + textElId + '">' + esc(displayText) + '</div>';
                            if (turnText.length > 300) {
                                html += '<button type="button" class="ai-turn-view-full text-[10px] text-cyan hover:underline" data-turn-idx="' + ui + '" data-command-idx="' + ti + '" data-text-id="' + textElId + '">View full</button>';
                            }
                            // Annotation: summary below text if different
                            if (turnSummary && turnSummary !== turnText && turnSummary !== turnText.substring(0, turnSummary.length)) {
                                html += '<div class="agent-info-turn-annotation">' + esc(turnSummary) + '</div>';
                            }
                        } else if (turnSummary) {
                            // Fallback: show summary as primary when no text
                            html += '<div class="agent-info-turn-text">' + esc(turnSummary) + '</div>';
                        }
                        html += '</div>';
                    }
                    html += '</div>';
                } else {
                    html += '<p class="text-muted text-[10px] italic">No turns</p>';
                }

                html += '</div>'; // command-body
                html += '</details>';
            }
        }
        html += '</div>';

        contentEl.innerHTML = html;

        // Attach click handlers for section copy buttons.
        // These don't accumulate because contentEl.innerHTML replaces all prior content.
        var copyBtns = contentEl.querySelectorAll('.agent-info-copy-btn[data-section-id]');
        for (var ci = 0; ci < copyBtns.length; ci++) {
            copyBtns[ci].addEventListener('click', function(e) {
                e.stopPropagation();
                var btn = e.currentTarget;
                var sid = btn.getAttribute('data-section-id');
                var text = sectionTexts[sid];
                if (text) copyToClipboard(text, btn);
            });
        }

        // Attach View full toggle handlers for turn text
        var viewFullBtns = contentEl.querySelectorAll('.ai-turn-view-full');
        for (var vfi = 0; vfi < viewFullBtns.length; vfi++) {
            viewFullBtns[vfi].addEventListener('click', function(e) {
                e.stopPropagation();
                var btn = e.currentTarget;
                var commandIdx = parseInt(btn.getAttribute('data-command-idx'), 10);
                var turnIdx = parseInt(btn.getAttribute('data-turn-idx'), 10);
                var textElId = btn.getAttribute('data-text-id');
                var textEl = document.getElementById(textElId);
                if (!textEl) return;
                var fullText = (commands[commandIdx] && commands[commandIdx].turns && commands[commandIdx].turns[turnIdx])
                    ? commands[commandIdx].turns[turnIdx].text || '' : '';
                var expanded = btn.getAttribute('data-expanded') === '1';
                if (expanded) {
                    textEl.textContent = fullText.substring(0, 300) + '...';
                    btn.textContent = 'View full';
                    btn.setAttribute('data-expanded', '0');
                } else {
                    textEl.textContent = fullText;
                    btn.textContent = 'Collapse';
                    btn.setAttribute('data-expanded', '1');
                }
            });
        }
    }

    function row(label, valueHtml) {
        return '<div class="agent-info-row">' +
            '<span class="agent-info-label">' + label + '</span>' +
            '<span class="agent-info-value">' + valueHtml + '</span>' +
            '</div>';
    }

    // Export
    window.AgentInfo = {
        open: open,
        close: close,
        copy: copyToClipboard
    };

})();
