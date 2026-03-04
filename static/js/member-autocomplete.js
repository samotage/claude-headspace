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
    var _selected = [];         // [{ agent_id?, persona_slug?, persona_name, project_name?, role }, ...]
    var _highlightIdx = -1;     // keyboard nav index within visible items
    var _inputEl = null;
    var _dropdownEl = null;
    var _tagsEl = null;
    var _fallbackEl = null;     // text input fallback on API failure
    var _boundOnDocClick = null;
    var _isOpen = false;
    var _excludeAgentIds = {};  // { agentId: true } — agents to hide from dropdown
    var _excludePersonaSlugs = {};  // { slug: true } — personas to hide from dropdown

    var _escapeHtml = (global.CHUtils && global.CHUtils.escapeHtml) || function(str) {
        if (!str) return '';
        var div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    };

    // ── Public API ──────────────────────────────────────────

    function init(containerEl, options) {
        if (!containerEl) return;

        // Don't re-init if already set up on this container
        if (_container === containerEl && _inputEl) return;

        destroy();
        _container = containerEl;
        _selected = [];
        _highlightIdx = -1;
        _isOpen = false;

        // Build exclude sets from options
        _excludeAgentIds = {};
        _excludePersonaSlugs = {};
        if (options) {
            (options.excludeAgentIds || []).forEach(function(id) { _excludeAgentIds[id] = true; });
            (options.excludePersonaSlugs || []).forEach(function(s) { _excludePersonaSlugs[s] = true; });
        }

        // Build DOM skeleton
        _container.innerHTML = '';

        _tagsEl = document.createElement('div');
        _tagsEl.className = 'member-ac-tags';

        _inputEl = document.createElement('input');
        _inputEl.type = 'text';
        _inputEl.className = 'form-well w-full px-3 py-2 text-sm';
        _inputEl.placeholder = 'Search agents...';
        _inputEl.setAttribute('autocomplete', 'off');

        // Dropdown is appended to body (fixed position) to escape overflow clipping
        _dropdownEl = document.createElement('div');
        _dropdownEl.className = 'member-ac-dropdown';
        document.body.appendChild(_dropdownEl);

        _container.appendChild(_tagsEl);
        _container.appendChild(_inputEl);

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
        if (_fallbackEl) return [];
        return _selected.filter(function(s) { return s.agent_id; }).map(function(s) { return s.agent_id; });
    }

    function getSelectedPersonaSlugs() {
        if (_fallbackEl) return [];
        return _selected.filter(function(s) { return !s.agent_id && s.persona_slug; }).map(function(s) { return s.persona_slug; });
    }

    function getSelected() {
        if (_fallbackEl) return [];
        return _selected.slice();
    }

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
        _isOpen = false;
        if (_fallbackEl) _fallbackEl.value = '';
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
        // Remove dropdown from body
        if (_dropdownEl && _dropdownEl.parentNode) {
            _dropdownEl.parentNode.removeChild(_dropdownEl);
        }
        _container = null;
        _data = null;
        _selected = [];
        _inputEl = null;
        _dropdownEl = null;
        _tagsEl = null;
        _fallbackEl = null;
        _isOpen = false;
        _excludeAgentIds = {};
        _excludePersonaSlugs = {};
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
        // Remove body-appended dropdown
        if (_dropdownEl && _dropdownEl.parentNode) {
            _dropdownEl.parentNode.removeChild(_dropdownEl);
        }
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
        if (!_isOpen) {
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
        if (!_isOpen) return;
        // Close if click is outside both the container and the dropdown
        var inContainer = _container && _container.contains(e.target);
        var inDropdown = _dropdownEl && _dropdownEl.contains(e.target);
        if (!inContainer && !inDropdown) {
            _closeDropdown();
        }
    }

    // ── Dropdown Positioning & Rendering ─────────────────────

    function _positionDropdown() {
        if (!_inputEl || !_dropdownEl) return;
        var rect = _inputEl.getBoundingClientRect();
        _dropdownEl.style.position = 'fixed';
        _dropdownEl.style.top = (rect.bottom + 4) + 'px';
        _dropdownEl.style.left = rect.left + 'px';
        _dropdownEl.style.width = rect.width + 'px';
    }

    function _openDropdown() {
        if (!_dropdownEl) return;
        _positionDropdown();
        _dropdownEl.classList.add('open');
        _isOpen = true;
    }

    function _closeDropdown() {
        if (_dropdownEl) _dropdownEl.classList.remove('open');
        _highlightIdx = -1;
        _isOpen = false;
    }

    function _renderDropdown(query) {
        if (!_dropdownEl) return;
        _dropdownEl.innerHTML = '';

        if (!_data || (!_data.projects && !_data.personas)) {
            _dropdownEl.innerHTML = '<div class="member-ac-empty">No members available</div>';
            return;
        }

        var selectedIds = {};
        var selectedSlugs = {};
        _selected.forEach(function(s) {
            if (s.agent_id) selectedIds[s.agent_id] = true;
            if (s.persona_slug) selectedSlugs[s.persona_slug] = true;
        });

        var q = (query || '').toLowerCase();
        var hasResults = false;
        var itemIndex = 0;

        // Render agents grouped by project
        (_data.projects || []).forEach(function(project) {
            var matchingAgents = project.agents.filter(function(agent) {
                if (selectedIds[agent.agent_id]) return false;
                if (_excludeAgentIds[agent.agent_id]) return false;
                if (agent.persona_slug && _excludePersonaSlugs[agent.persona_slug]) return false;
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

                item.addEventListener('mousedown', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    _selectAgent({
                        agent_id: agent.agent_id,
                        persona_slug: agent.persona_slug,
                        persona_name: agent.persona_name,
                        project_name: project.project_name,
                        role: agent.role || ''
                    });
                });

                _dropdownEl.appendChild(item);
            });
        });

        // Render personas without active agents (e.g. operator)
        var matchingPersonas = (_data.personas || []).filter(function(p) {
            if (selectedSlugs[p.persona_slug]) return false;
            if (_excludePersonaSlugs[p.persona_slug]) return false;
            if (!q) return true;
            return (p.persona_name || '').toLowerCase().indexOf(q) !== -1 ||
                   (p.role || '').toLowerCase().indexOf(q) !== -1 ||
                   (p.persona_slug || '').toLowerCase().indexOf(q) !== -1;
        });

        if (matchingPersonas.length > 0) {
            hasResults = true;

            var header = document.createElement('div');
            header.className = 'member-ac-group-header';
            header.textContent = 'People';
            _dropdownEl.appendChild(header);

            matchingPersonas.forEach(function(p) {
                var item = document.createElement('button');
                item.type = 'button';
                item.className = 'member-ac-item';
                item.setAttribute('data-index', itemIndex++);
                item.innerHTML = '<span class="member-ac-item-name">' + _escapeHtml(p.persona_name) + '</span>' +
                                 '<span class="member-ac-item-role">' + _escapeHtml(p.role || '') + '</span>';

                item.addEventListener('mousedown', function(e) {
                    e.preventDefault();
                    e.stopPropagation();
                    _selectAgent({
                        persona_slug: p.persona_slug,
                        persona_name: p.persona_name,
                        role: p.role || ''
                    });
                });

                _dropdownEl.appendChild(item);
            });
        }

        if (!hasResults) {
            var empty = document.createElement('div');
            empty.className = 'member-ac-empty';
            empty.textContent = q ? 'No matches' : 'No members available';
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
        for (var i = 0; i < _selected.length; i++) {
            var s = _selected[i];
            if (agentInfo.agent_id && s.agent_id === agentInfo.agent_id) return;
            if (!agentInfo.agent_id && s.persona_slug === agentInfo.persona_slug) return;
        }
        _selected.push(agentInfo);
        _renderTags();
        if (_inputEl) _inputEl.value = '';
        _closeDropdown();
    }

    function _removeAgent(agentId, personaSlug) {
        _selected = _selected.filter(function(s) {
            if (agentId) return s.agent_id !== agentId;
            return s.persona_slug !== personaSlug;
        });
        _renderTags();
    }

    function _renderTags() {
        if (!_tagsEl) return;
        _tagsEl.innerHTML = '';

        _selected.forEach(function(member) {
            var tag = document.createElement('span');
            tag.className = 'member-ac-tag';
            var label = _escapeHtml(member.persona_name);
            if (member.project_name) {
                label += ' <span class="member-ac-tag-project">(' + _escapeHtml(member.project_name) + ')</span>';
            } else {
                label += ' <span class="member-ac-tag-project">(' + _escapeHtml(member.role || 'persona') + ')</span>';
            }
            tag.innerHTML = label;

            var removeBtn = document.createElement('button');
            removeBtn.type = 'button';
            removeBtn.className = 'member-ac-tag-remove';
            removeBtn.innerHTML = '&times;';
            removeBtn.setAttribute('aria-label', 'Remove ' + member.persona_name);
            removeBtn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                _removeAgent(member.agent_id, member.persona_slug);
            });

            tag.appendChild(removeBtn);
            _tagsEl.appendChild(tag);
        });
    }

    // ── Expose ──────────────────────────────────────────────

    global.MemberAutocomplete = {
        init: init,
        getSelectedAgentIds: getSelectedAgentIds,
        getSelectedPersonaSlugs: getSelectedPersonaSlugs,
        getSelected: getSelected,
        getFallbackMembers: getFallbackMembers,
        reset: reset,
        destroy: destroy,
    };

})(window);
