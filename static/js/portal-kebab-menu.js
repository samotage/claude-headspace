/**
 * Portal Kebab Menu — shared menu component rendered on document.body.
 *
 * Extracts the kebab menu from the agent card DOM into an independent portal
 * element. SSE events can freely mutate the card without breaking the menu.
 *
 * Follows the ConfirmDialog lazy-create pattern: one shared DOM element,
 * reused for every menu open.
 *
 * Usage:
 *   PortalKebabMenu.open(triggerButton, {
 *       agentId: 123,
 *       actions: [
 *           { id: 'chat', label: 'Chat', icon: '<svg ...>' },
 *           'divider',
 *           { id: 'dismiss', label: 'Dismiss agent', icon: '<svg ...>', className: 'kill-action' },
 *       ],
 *       onAction: function(actionId, agentId) { ... }
 *   });
 *   PortalKebabMenu.close();
 *   PortalKebabMenu.isOpen();
 */
(function(global) {
    'use strict';

    var menuEl = null;
    var _isOpen = false;
    var _agentId = null;
    var _onAction = null;
    var _triggerBtn = null;

    // SVG icon strings shared by dashboard and voice consumers
    var ICONS = {
        chat: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M2 13h1l7-7-1-1-7 7zm9.5-9.5 1 1m-2-2 1.44-1.44a.7.7 0 0 1 1 0l1 1a.7.7 0 0 1 0 1L12.5 4.5"/></svg>',
        dismiss: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3 3l10 10M13 3L3 13"/></svg>',
        attach: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="4" width="12" height="9" rx="1"/><path d="M5 4V3a3 3 0 0 1 6 0v1"/></svg>',
        context: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.5"/><path d="M8 5v3.5L10.5 10"/></svg>',
        info: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="8" cy="8" r="5.5"/><path d="M8 5.5v4"/><circle cx="8" cy="11.5" r="0.5" fill="currentColor" stroke="none"/></svg>',
        reconcile: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M1 8a7 7 0 0 1 13.4-2.8M15 8a7 7 0 0 1-13.4 2.8"/><path d="M14.4 1v4.2h-4.2M1.6 15v-4.2h4.2"/></svg>',
        handoff: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M5 2v12M11 2v12"/><path d="M5 8h6"/><path d="M1 5l4 3-4 3"/><path d="M15 5l-4 3 4 3"/></svg>',
        revive: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M8 1v6M5 4l3-3 3 3"/><path d="M2 8a6 6 0 1 0 12 0"/></svg>',
        addMember: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="6" cy="5" r="3"/><path d="M2 14c0-2.8 1.8-4 4-4s4 1.2 4 4"/><path d="M12 5v4M10 7h4"/></svg>',
        complete: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M3.5 8.5l3 3 6-7"/></svg>',
        archive: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="2" y="2" width="12" height="4" rx="1"/><path d="M3 6v7a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V6"/><path d="M6.5 9h3"/></svg>',
        copySlug: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="5" width="8" height="8" rx="1"/><path d="M3 11V3a1 1 0 0 1 1-1h8"/></svg>',
        leave: '<svg class="kebab-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M6 2H3a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/><path d="M10 11l3-3-3-3"/><path d="M13 8H6"/></svg>'
    };

    function ensureDOM() {
        if (menuEl) return;
        menuEl = document.createElement('div');
        menuEl.id = 'portal-kebab-menu';
        menuEl.setAttribute('role', 'menu');
        document.body.appendChild(menuEl);

        // Delegated click + touchend on the portal element
        menuEl.addEventListener('click', _handleAction);
        menuEl.addEventListener('touchend', _handleAction);
    }

    function _handleAction(e) {
        var item = e.target.closest('.portal-kebab-item');
        if (!item) return;
        e.preventDefault();
        e.stopPropagation();
        var actionId = item.getAttribute('data-action');
        if (actionId && _onAction && _agentId != null) {
            var callback = _onAction;
            var agentId = _agentId;
            close();
            callback(actionId, agentId);
        }
    }

    function _buildMenuHTML(actions) {
        var html = '';
        for (var i = 0; i < actions.length; i++) {
            var action = actions[i];
            if (action === 'divider') {
                html += '<div class="portal-kebab-divider"></div>';
                continue;
            }
            var cls = 'portal-kebab-item';
            if (action.className) cls += ' ' + action.className;
            html += '<button class="' + cls + '" data-action="' + action.id + '" role="menuitem">';
            if (action.icon) html += action.icon;
            html += '<span>' + action.label + '</span>';
            html += '</button>';
        }
        return html;
    }

    function _position(btn) {
        if (!menuEl || !btn) return;
        var rect = btn.getBoundingClientRect();
        var menuRect = menuEl.getBoundingClientRect();
        var vw = window.innerWidth;
        var vh = window.innerHeight;

        // Default: below-right of button
        var top = rect.bottom + 6;
        var left = rect.right - menuRect.width;

        // Flip upward if near viewport bottom
        if (top + menuRect.height > vh - 8) {
            top = rect.top - menuRect.height - 6;
            if (top < 8) top = 8;
        }

        // Keep within left edge
        if (left < 8) left = 8;
        // Keep within right edge
        if (left + menuRect.width > vw - 8) {
            left = vw - menuRect.width - 8;
        }

        menuEl.style.top = top + 'px';
        menuEl.style.left = left + 'px';
    }

    function open(triggerButton, opts) {
        ensureDOM();
        if (_isOpen) close();

        _agentId = opts.agentId;
        _onAction = opts.onAction;
        _triggerBtn = triggerButton;

        menuEl.innerHTML = _buildMenuHTML(opts.actions);
        menuEl.classList.add('open');
        _isOpen = true;

        // Update trigger button aria
        if (_triggerBtn) _triggerBtn.setAttribute('aria-expanded', 'true');

        // Position after making visible (need rendered dimensions)
        _position(_triggerBtn);

        // Bind close-on-outside listeners
        setTimeout(function() {
            document.addEventListener('click', _onClickOutside, true);
            document.addEventListener('touchstart', _onTouchOutside, { passive: true });
            document.addEventListener('keydown', _onEscape);
            window.addEventListener('resize', _onResize);
            window.addEventListener('scroll', _onScroll, true);
        }, 0);
    }

    function close() {
        if (!_isOpen) return;
        _isOpen = false;
        if (menuEl) {
            menuEl.classList.remove('open');
            menuEl.innerHTML = '';
        }

        // Reset trigger button aria
        if (_triggerBtn) {
            _triggerBtn.setAttribute('aria-expanded', 'false');
            _triggerBtn = null;
        }

        _agentId = null;
        _onAction = null;

        // Unbind listeners
        document.removeEventListener('click', _onClickOutside, true);
        document.removeEventListener('touchstart', _onTouchOutside);
        document.removeEventListener('keydown', _onEscape);
        window.removeEventListener('resize', _onResize);
        window.removeEventListener('scroll', _onScroll, true);

        // Execute any deferred SSE reload now that menu is closed
        if (global._sseReloadDeferred) {
            setTimeout(function() {
                if (!global._sseReloadDeferred) return;
                if (typeof ConfirmDialog !== 'undefined' && ConfirmDialog.isOpen()) return;
                var active = document.activeElement;
                if (active && active.closest && active.closest('.respond-widget')) return;
                var deferred = global._sseReloadDeferred;
                global._sseReloadDeferred = null;
                deferred();
            }, 0);
        }
    }

    function _onClickOutside(e) {
        if (!_isOpen) return;
        if (menuEl && menuEl.contains(e.target)) return;
        // Allow clicking the same trigger button to toggle
        if (_triggerBtn && _triggerBtn.contains(e.target)) return;
        close();
    }

    function _onTouchOutside(e) {
        if (!_isOpen) return;
        if (menuEl && menuEl.contains(e.target)) return;
        if (_triggerBtn && _triggerBtn.contains(e.target)) return;
        close();
    }

    function _onEscape(e) {
        if (e.key === 'Escape' && _isOpen) {
            e.stopPropagation();
            close();
        }
    }

    function _onResize() {
        if (_isOpen && _triggerBtn) _position(_triggerBtn);
    }

    function _onScroll() {
        if (_isOpen) close();
    }

    // Export
    global.PortalKebabMenu = {
        open: open,
        close: close,
        isOpen: function() { return _isOpen; },
        ICONS: ICONS
    };

})(typeof window !== 'undefined' ? window : this);
