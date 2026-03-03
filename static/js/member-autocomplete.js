/**
 * Member Autocomplete Picker — search and select agents for channel membership.
 *
 * Fetches active agents grouped by project from /api/channels/available-members,
 * renders a tag-based picker with dropdown search, keyboard navigation, and
 * graceful degradation to text input on API failure.
 *
 * Public API:
 * - init(containerEl)          — attach autocomplete to a container element
 * - getSelectedAgentIds()      — return [agent_id, ...] for form submission
 * - reset()                    — clear selections and cached data
 * - destroy()                  — teardown event listeners
 */
(function(global) {
    'use strict';

    var _container = null;
    var _data = null;           // cached API response { projects: [...] }
    var _selected = [];         // [{ agent_id, persona_name, project_name, role }, ...]
    var _highlightIdx = -1;     // keyboard nav index within visible items
    var _inputEl = null;
    var _dropdownEl = null;
    var _tagsEl = null;
    var _fallbackEl = null;     // text input fallback on API failure
    var _boundOnDocClick = null;

    var _escapeHtml = (global.CHUtils && global.CHUtils.escapeHtml) || function(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    };

    // ── Public API ──────────────────────────────────────────

    function init(containerEl) {
        if (!containerEl) return;
        _container = containerEl;
        _selected = [];
        _highlightIdx = -1;

        // Build DOM skeleton
        _container.innerHTML = '';

        _tagsEl = document.createElement('div');
        _tagsEl.className = 'member-ac-tags';

        _inputEl = document.createElement('input');
        _inputEl.type = 'text';
        _inputEl.className = 'form-well w-full px-3 py-2 text-sm';
        _inputEl.placeholder = 'Search agents...';
        _inputEl.setAttribute('autocomplete', 'off');

        _dropdownEl = document.createElement('div');
        _dropdownEl.className = 'member-ac-dropdown';

        _container.appendChild(_tagsEl);
        _container.appendChild(_inputEl);
        _container.appendChild(_dropdownEl);

        // Event listeners
        _inputEl.addEventListener('focus', _onFocus);
        _inputEl.addEventListener('input', _onInput);
        _inputEl.addEventListener('keydown', _onKeydown);
        _boundOnDocClick = _onDocClick.bind(null);
        document.addEventListener('mousedown', _boundOnDocClick);

        // Fetch data
        _fetchData();
    }

    function getSelectedAgentIds() {
        // If in fallback mode, parse comma-separated slugs — but return empty
        // since fallback uses `members` field directly
        if (_fallbackEl) return [];
        return _selected.map(function(s) { return s.agent_id; });
    }

    /**
     * Return the fallback text value (comma-separated slugs) if in fallback mode.
     * Returns null if autocomplete is working normally.
     */
    function getFallbackMembers() {
        if (!_fallbackEl) return null;
        var val = _fallbackEl.value.trim();
        if (!val) return null;
        return val.split(',').map(function(s) { return s.trim(); }).filter(Boolean);
    }

    function reset() {
        _selected = [];
        _highlightIdx = -1;
        _data = null;
        if (_inputEl) _inputEl.value = '';
        if (_tagsEl) _tagsEl.innerHTML = '';
        if (_dropdownEl) {
            _dropdownEl.innerHTML = '';
            _dropdownEl.classList.remove('open');
        }
        if (_fallbackEl) _fallbackEl.value = '';
        // Re-fetch so dropdown is ready for next use
        _fetchData();
    }

    function destroy() {
        if (_inputEl) {
            _inputEl.removeEventListener('focus', _onFocus);
            _inputEl.removeEventListener('input', _onInput);
            _inputEl.removeEventListener('keydown', _onKeydown);
        }
        if (_boundOnDocClick) {
            document.removeEventListener('mousedown', _boundOnDocClick);
        }
        _container = null;
        _data = null;
        _selected = [];
        _inputEl = null;
        _dropdownEl = null;
        _tagsEl = null;
        _fallbackEl = null;
    }

    // ── Data Fetching ───────────────────────────────────────

    function _fetchData() {
        fetch('/api/channels/available-members')
            .then(function(r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function(data) {
                _data = data;
            })
            .catch(function(err) {
                console.error('MemberAutocomplete: failed to fetch available members:', err);
                _showFallback();
            });
    }

    function _showFallback() {
        if (!_container) return;
        _container.innerHTML = '';

        _fallbackEl = document.createElement('input');
        _fallbackEl.type = 'text';
        _fallbackEl.className = 'form-well w-full px-3 py-2 text-sm';
        _fallbackEl.placeholder = 'Comma-separated persona slugs (optional)';
        _fallbackEl.id = 'channel-create-members';

        var hint = document.createElement('span');
        hint.className = 'text-muted text-xs mt-1 block';
        hint.textContent = 'e.g. developer-con-1, tester-robbo-2';

        _container.appendChild(_fallbackEl);
        _container.appendChild(hint);

        _inputEl = null;
        _dropdownEl = null;
        _tagsEl = null;
    }

    // ── Event Handlers ──────────────────────────────────────

    function _onFocus() {
        _renderDropdown(_inputEl.value.trim());
        _openDropdown();
    }

    function _onInput() {
        _highlightIdx = -1;
        _renderDropdown(_inputEl.value.trim());
        _openDropdown();
    }

    function _onKeydown(e) {
        if (!_dropdownEl || !_dropdownEl.classList.contains('open')) {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                _renderDropdown(_inputEl.value.trim());
                _openDropdown();
                e.preventDefault();
            }
            return;
        }

        var items = _dropdownEl.querySelectorAll('.member-ac-item');
        var count = items.length;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            _highlightIdx = (_highlightIdx + 1) % count;
            _updateHighlight(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            _highlightIdx = (_highlightIdx - 1 + count) % count;
            _updateHighlight(items);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (_highlightIdx >= 0 && _highlightIdx < count) {
                items[_highlightIdx].click();
            }
        } else if (e.key === 'Escape') {
            e.preventDefault();
            _closeDropdown();
            _inputEl.blur();
        }
    }

    function _onDocClick(e) {
        if (_container && !_container.contains(e.target)) {
            _closeDropdown();
        }
    }

    // ── Dropdown Rendering ──────────────────────────────────

    function _openDropdown() {
        if (_dropdownEl) _dropdownEl.classList.add('open');
    }

    function _closeDropdown() {
        if (_dropdownEl) _dropdownEl.classList.remove('open');
        _highlightIdx = -1;
    }

    function _renderDropdown(query) {
        if (!_dropdownEl) return;
        _dropdownEl.innerHTML = '';

        if (!_data || !_data.projects) {
            _dropdownEl.innerHTML = '<div class="member-ac-empty">No active agents available</div>';
            return;
        }

        var selectedIds = {};
        _selected.forEach(function(s) { selectedIds[s.agent_id] = true; });

        var q = (query || '').toLowerCase();
        var hasResults = false;
        var itemIndex = 0;

        _data.projects.forEach(function(project) {
            var matchingAgents = project.agents.filter(function(agent) {
                if (selectedIds[agent.agent_id]) return false;
                if (!q) return true;
                return (agent.persona_name || '').toLowerCase().indexOf(q) !== -1 ||
                       (agent.role || '').toLowerCase().indexOf(q) !== -1 ||
                       (agent.persona_slug || '').toLowerCase().indexOf(q) !== -1;
            });

            if (matchingAgents.length === 0) return;
            hasResults = true;

            // Project header
            var header = document.createElement('div');
            header.className = 'member-ac-group-header';
            header.textContent = project.project_name;
            _dropdownEl.appendChild(header);

            // Agent items
            matchingAgents.forEach(function(agent) {
                var item = document.createElement('button');
                item.type = 'button';
                item.className = 'member-ac-item';
                item.setAttribute('data-index', itemIndex++);
                item.innerHTML = '<span class="member-ac-item-name">' + _escapeHtml(agent.persona_name) + '</span>' +
                                 '<span class="member-ac-item-role">' + _escapeHtml(agent.role || '') + '</span>';

                item.addEventListener('click', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    _selectAgent({
                        agent_id: agent.agent_id,
                        persona_name: agent.persona_name,
                        project_name: project.project_name,
                        role: agent.role || ''
                    });
                });

                _dropdownEl.appendChild(item);
            });
        });

        if (!hasResults) {
            var empty = document.createElement('div');
            empty.className = 'member-ac-empty';
            empty.textContent = q ? 'No matches' : 'No active agents available';
            _dropdownEl.appendChild(empty);
        }
    }

    function _updateHighlight(items) {
        items.forEach(function(item, i) {
            if (i === _highlightIdx) {
                item.classList.add('member-ac-highlight');
                item.scrollIntoView({ block: 'nearest' });
            } else {
                item.classList.remove('member-ac-highlight');
            }
        });
    }

    // ── Selection Management ────────────────────────────────

    function _selectAgent(agentInfo) {
        // Prevent duplicates
        for (var i = 0; i < _selected.length; i++) {
            if (_selected[i].agent_id === agentInfo.agent_id) return;
        }
        _selected.push(agentInfo);
        _renderTags();
        if (_inputEl) _inputEl.value = '';
        _closeDropdown();
        if (_inputEl) _inputEl.focus();
    }

    function _removeAgent(agentId) {
        _selected = _selected.filter(function(s) { return s.agent_id !== agentId; });
        _renderTags();
    }

    function _renderTags() {
        if (!_tagsEl) return;
        _tagsEl.innerHTML = '';

        _selected.forEach(function(agent) {
            var tag = document.createElement('span');
            tag.className = 'member-ac-tag';
            tag.innerHTML = _escapeHtml(agent.persona_name) +
                            ' <span class="member-ac-tag-project">(' + _escapeHtml(agent.project_name) + ')</span>';

            var removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'member-ac-tag-remove';
            removeBtn.innerHTML = '&times;';
            removeBtn.setAttribute('aria-label', 'Remove ' + agent.persona_name);
            removeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                _removeAgent(agent.agent_id);
            });

            tag.appendChild(removeBtn);
            _tagsEl.appendChild(tag);
        });
    }

    // ── Expose ──────────────────────────────────────────────

    global.MemberAutocomplete = {
        init: init,
        getSelectedAgentIds: getSelectedAgentIds,
        getFallbackMembers: getFallbackMembers,
        reset: reset,
        destroy: destroy,
    };

})(window);
