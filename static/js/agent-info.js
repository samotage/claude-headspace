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

                // Update hero chars in header
                var short = data.identity.session_uuid_short || '';
                var heroChars = document.getElementById('agent-info-hero-chars');
                var heroTrail = document.getElementById('agent-info-hero-trail');
                if (heroChars) heroChars.textContent = short.slice(0, 2);
                if (heroTrail) heroTrail.textContent = short.slice(2);

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
        var tasks = data.tasks || [];

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

        // --- Task History Section ---
        var taskTextLines = [];
        taskTextLines.push('## Task History (' + tasks.length + ')');
        for (var tti = 0; tti < tasks.length; tti++) {
            var tt = tasks[tti];
            taskTextLines.push('');
            taskTextLines.push('### #' + tt.id + ' [' + tt.state + '] ' + (tt.instruction || 'No instruction'));
            taskTextLines.push('- **Turns:** ' + tt.turn_count);
            if (tt.completion_summary) taskTextLines.push('- **Summary:** ' + tt.completion_summary);
            taskTextLines.push('- **Started:** ' + formatTimestampPlain(tt.started_at) + (tt.completed_at ? ' \u2014 **Completed:** ' + formatTimestampPlain(tt.completed_at) : ''));
            var ttTurns = tt.turns || [];
            if (ttTurns.length > 0) {
                taskTextLines.push('');
                taskTextLines.push('| ID | Actor | Intent | Time | Frust. |');
                taskTextLines.push('|----|-------|--------|------|--------|');
                for (var tui = 0; tui < ttTurns.length; tui++) {
                    var tu = ttTurns[tui];
                    var frustVal = (tu.frustration_score !== null && tu.frustration_score !== undefined) ? tu.frustration_score : '\u2014';
                    taskTextLines.push('| ' + tu.id + ' | ' + tu.actor + ' | ' + tu.intent + ' | ' + formatTimestampPlain(tu.timestamp) + ' | ' + frustVal + ' |');
                    var tuDisplay = tu.text || tu.summary;
                    if (tuDisplay) taskTextLines.push('| | *' + tuDisplay + '* ||||');
                }
            }
        }
        var taskText = taskTextLines.length > 1 ? taskTextLines.join('\n') : 'No tasks recorded';

        html += '<div class="agent-info-section">';
        html += '<div class="agent-info-section-title"><span>Task History (' + tasks.length + ')</span>' + sectionCopyBtn(taskText) + '</div>';
        if (tasks.length === 0) {
            html += '<p class="text-muted text-sm italic">No tasks recorded</p>';
        } else {
            for (var ti = 0; ti < tasks.length; ti++) {
                var task = tasks[ti];
                html += '<details class="agent-info-task-details">';
                html += '<summary class="agent-info-task-header">';
                html += '<span class="text-muted text-[10px] font-mono">#' + task.id + '</span> ';
                html += stateBadge(task.state) + ' ';
                html += '<span class="text-secondary text-xs">' + esc(task.instruction || 'No instruction') + '</span>';
                html += '<span class="text-muted text-[10px] ml-auto">' + task.turn_count + ' turn' + (task.turn_count !== 1 ? 's' : '') + '</span>';
                html += '</summary>';

                // Task detail
                html += '<div class="agent-info-task-body">';
                if (task.completion_summary) {
                    html += '<div class="text-green text-xs italic mb-2">' + esc(task.completion_summary) + '</div>';
                }
                html += '<div class="text-muted text-[10px] mb-1">';
                html += 'Started: ' + formatTimestamp(task.started_at);
                if (task.completed_at) html += ' &mdash; Completed: ' + formatTimestamp(task.completed_at);
                html += '</div>';

                // Turns table
                var turns = task.turns || [];
                if (turns.length > 0) {
                    html += '<div class="text-muted text-[10px] font-mono uppercase mt-2 mb-1">Turns (' + turns.length + ')</div>';
                    html += '<table class="agent-info-turn-table">';
                    html += '<thead><tr><th>ID</th><th>Actor</th><th>Intent</th><th>Time</th><th>Frust.</th></tr></thead>';
                    html += '<tbody>';
                    for (var ui = 0; ui < turns.length; ui++) {
                        var turn = turns[ui];
                        var actorClass = turn.actor === 'user' ? 'text-amber' : 'text-cyan';
                        var frustCell = '';
                        if (turn.frustration_score !== null && turn.frustration_score !== undefined) {
                            var fC = turn.frustration_score <= 3 ? 'text-green' : turn.frustration_score <= 6 ? 'text-amber' : 'text-red';
                            frustCell = '<span class="' + fC + '">' + turn.frustration_score + '</span>';
                        } else {
                            frustCell = '<span class="text-muted">\u2014</span>';
                        }
                        html += '<tr>';
                        html += '<td class="text-muted">' + turn.id + '</td>';
                        html += '<td class="' + actorClass + '">' + esc(turn.actor) + '</td>';
                        html += '<td>' + esc(turn.intent) + '</td>';
                        html += '<td>' + formatTimestamp(turn.timestamp) + '</td>';
                        html += '<td>' + frustCell + '</td>';
                        html += '</tr>';
                        var turnDisplay = turn.text || turn.summary;
                        if (turnDisplay) {
                            var turnShown = turnDisplay.length > 200 ? turnDisplay.substring(0, 200) + '...' : turnDisplay;
                            html += '<tr class="agent-info-turn-summary-row"><td></td><td colspan="4" class="text-muted text-[10px] italic">' + esc(turnShown) + '</td></tr>';
                        }
                    }
                    html += '</tbody></table>';
                } else {
                    html += '<p class="text-muted text-[10px] italic">No turns</p>';
                }

                html += '</div>'; // task-body
                html += '</details>';
            }
        }
        html += '</div>';

        contentEl.innerHTML = html;

        // Attach click handlers for section copy buttons
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
