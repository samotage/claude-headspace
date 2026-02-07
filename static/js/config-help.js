/**
 * Config help popover system for Claude Headspace
 * Provides clickable info icons with popovers for config fields and sections.
 */
(function() {
    'use strict';

    var activePopover = null;
    var activeIcon = null;
    var popoverEl = null;

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    function init() {
        createPopoverElement();
        bindIcons();
        bindDismissHandlers();
    }

    function createPopoverElement() {
        popoverEl = document.createElement('div');
        popoverEl.className = 'config-help-popover';
        popoverEl.setAttribute('role', 'tooltip');
        popoverEl.style.display = 'none';
        document.body.appendChild(popoverEl);
    }

    function bindIcons() {
        document.querySelectorAll('.config-help-icon').forEach(function(icon) {
            icon.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                togglePopover(this);
            });
            icon.addEventListener('keydown', function(e) {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    e.stopPropagation();
                    togglePopover(this);
                }
            });
        });
    }

    function bindDismissHandlers() {
        // Click outside
        document.addEventListener('click', function(e) {
            if (!activePopover) return;
            if (popoverEl.contains(e.target)) return;
            if (e.target.closest('.config-help-icon')) return;
            hidePopover();
        });

        // Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && activePopover) {
                hidePopover();
                if (activeIcon) activeIcon.focus();
            }
        });

        // Scroll/resize
        window.addEventListener('scroll', function() { if (activePopover) hidePopover(); }, true);
        window.addEventListener('resize', function() { if (activePopover) hidePopover(); });
    }

    function togglePopover(icon) {
        if (activeIcon === icon) {
            hidePopover();
            return;
        }
        showPopover(icon);
    }

    function showPopover(icon) {
        hidePopover();

        var helpType = icon.getAttribute('data-help-type');
        var html = '';

        if (helpType === 'section') {
            var sectionDesc = icon.getAttribute('data-section-description') || '';
            var sectionTitle = icon.getAttribute('data-section-title') || '';
            var helpUrl = icon.getAttribute('data-help-url') || '';

            html = '<div class="config-popover-title">' + escapeHtml(sectionTitle) + '</div>';
            if (sectionDesc) {
                html += '<div class="config-popover-desc">' + escapeHtml(sectionDesc) + '</div>';
            }
            if (helpUrl) {
                html += '<div class="config-popover-link"><a href="' + escapeHtml(helpUrl) + '">Learn more \u2192</a></div>';
            }
        } else {
            var fieldName = icon.getAttribute('data-field-name') || '';
            var helpText = icon.getAttribute('data-help-text') || '';
            var defaultVal = icon.getAttribute('data-default') || '';
            var minVal = icon.getAttribute('data-min');
            var maxVal = icon.getAttribute('data-max');
            var helpUrl = icon.getAttribute('data-help-url') || '';

            html = '<div class="config-popover-title">' + escapeHtml(fieldName.replace(/_/g, ' ').replace(/\./g, ' \u203a ')) + '</div>';
            if (helpText) {
                html += '<div class="config-popover-desc">' + escapeHtml(helpText) + '</div>';
            }
            html += '<div class="config-popover-meta">';
            if (defaultVal !== '') {
                html += '<span class="config-popover-default">Default: <strong>' + escapeHtml(defaultVal) + '</strong></span>';
            }
            if (minVal !== null && minVal !== '' && maxVal !== null && maxVal !== '') {
                html += '<span class="config-popover-range">Range: ' + escapeHtml(minVal) + '\u2013' + escapeHtml(maxVal) + '</span>';
            }
            html += '</div>';
            if (helpUrl) {
                html += '<div class="config-popover-link"><a href="' + escapeHtml(helpUrl) + '">Learn more \u2192</a></div>';
            }
        }

        popoverEl.innerHTML = html;
        popoverEl.style.display = 'block';

        positionPopover(icon);

        activePopover = popoverEl;
        activeIcon = icon;
        icon.setAttribute('aria-expanded', 'true');
    }

    function hidePopover() {
        if (!activePopover) return;
        popoverEl.style.display = 'none';
        popoverEl.innerHTML = '';
        if (activeIcon) {
            activeIcon.setAttribute('aria-expanded', 'false');
        }
        activePopover = null;
        activeIcon = null;
    }

    function positionPopover(icon) {
        var rect = icon.getBoundingClientRect();
        var popRect = popoverEl.getBoundingClientRect();
        var viewW = window.innerWidth;
        var viewH = window.innerHeight;

        // Try below the icon
        var top = rect.bottom + 8;
        var left = rect.left + (rect.width / 2) - (popRect.width / 2);

        // Flip above if near bottom
        if (top + popRect.height > viewH - 20) {
            top = rect.top - popRect.height - 8;
        }

        // Clamp horizontal
        if (left < 12) left = 12;
        if (left + popRect.width > viewW - 12) {
            left = viewW - popRect.width - 12;
        }

        // Clamp vertical
        if (top < 12) top = 12;

        popoverEl.style.top = top + 'px';
        popoverEl.style.left = left + 'px';
    }

    var escapeHtml = CHUtils.escapeHtml;
})();
