/**
 * Card Text Tooltip — shows full text for truncated card lines.
 *
 * Desktop: hover over truncated .command-instruction or .command-summary to reveal.
 *          Click also works (pins the tooltip until click-away).
 * Touch:   tap truncated text to show; tap elsewhere to dismiss.
 *
 * Uses clone-based measurement for reliable truncation detection with
 * -webkit-line-clamp (scrollHeight is unreliable when line-clamp is active).
 * Uses mouseover/mouseout for event delegation (mouseenter doesn't bubble).
 */
(function() {
    var tooltip = null;
    var activeEl = null;
    var isTouch = false;
    var shownByHover = false; // true if tooltip was opened via hover
    var pinned = false;       // true if tooltip was pinned by click

    function ensureTooltip() {
        if (tooltip) return tooltip;
        tooltip = document.createElement('div');
        tooltip.className = 'card-text-tooltip';
        tooltip.style.display = 'none';
        document.body.appendChild(tooltip);
        return tooltip;
    }

    /**
     * Reliable truncation detection: clones the element without line-clamp
     * and compares the unclamped height to the clamped height.
     */
    function isTruncated(el) {
        // Fast path: if scrollHeight clearly exceeds clientHeight
        if (el.scrollHeight > el.clientHeight + 1) return true;

        // Clone-based measurement for -webkit-line-clamp elements
        var clone = el.cloneNode(true);
        clone.style.cssText =
            'position:absolute;visibility:hidden;pointer-events:none;' +
            'width:' + el.clientWidth + 'px;' +
            'display:block;-webkit-line-clamp:unset;' +
            '-webkit-box-orient:unset;max-height:none;overflow:visible;';
        el.parentNode.appendChild(clone);
        var fullHeight = clone.scrollHeight;
        clone.remove();
        return fullHeight > el.clientHeight + 1;
    }

    /**
     * Mark elements that are currently truncated with a CSS class
     * so we can show a pointer cursor hint.
     */
    function markTruncated(el) {
        if (isTruncated(el)) {
            el.classList.add('is-truncated');
        } else {
            el.classList.remove('is-truncated');
        }
    }

    function showTooltip(el) {
        if (!isTruncated(el)) return;

        ensureTooltip();
        tooltip.textContent = el.textContent;
        tooltip.style.display = 'block';

        // Position relative to the element
        var rect = el.getBoundingClientRect();
        var vw = window.innerWidth;
        var vh = window.innerHeight;

        // Start below the element
        var top = rect.bottom + 6;
        var left = rect.left;
        var width = Math.min(rect.width, 480);

        // Measure tooltip
        tooltip.style.left = left + 'px';
        tooltip.style.top = top + 'px';
        tooltip.style.maxWidth = width + 'px';

        // Re-measure after positioning to check overflow
        var tipRect = tooltip.getBoundingClientRect();

        // If it goes below viewport, show above instead
        if (tipRect.bottom > vh - 8) {
            top = rect.top - tipRect.height - 6;
            if (top < 8) top = 8;
            tooltip.style.top = top + 'px';
        }

        // If it goes off right edge, shift left
        if (tipRect.right > vw - 8) {
            left = vw - tipRect.width - 8;
            if (left < 8) left = 8;
            tooltip.style.left = left + 'px';
        }

        activeEl = el;
    }

    function hideTooltip() {
        if (tooltip) tooltip.style.display = 'none';
        activeEl = null;
        shownByHover = false;
        pinned = false;
    }

    // Detect touch capability
    window.addEventListener('touchstart', function() {
        isTouch = true;
    }, { once: true, passive: true });

    // --- Desktop: mouseover/mouseout (bubble, unlike mouseenter/mouseleave) ---
    // Uses page-level delegation — single listeners on document, not per-element.
    // This is intentional to avoid listener accumulation on dynamically-rendered cards.

    document.addEventListener('mouseover', function(e) {
        if (isTouch) return;
        var el = e.target.closest('.command-instruction, .command-summary');
        if (el) {
            if (activeEl === el) return; // already showing for this element
            if (pinned) return; // don't replace a pinned tooltip
            if (isTruncated(el)) {
                hideTooltip();
                showTooltip(el);
                shownByHover = true;
            }
        } else if (!pinned) {
            // Mouse moved off a tracked element
            if (tooltip && tooltip.contains(e.target)) return;
            if (activeEl) {
                hideTooltip();
            }
        }
    });

    document.addEventListener('mouseout', function(e) {
        if (isTouch || pinned) return;
        var el = e.target.closest('.command-instruction, .command-summary');
        if (!el && !(tooltip && (e.target === tooltip || tooltip.contains(e.target)))) return;

        var related = e.relatedTarget;
        // If moving to the tooltip, keep it open
        if (tooltip && (related === tooltip || tooltip.contains(related))) return;
        // If still within the source element, ignore
        if (activeEl && (related === activeEl || activeEl.contains(related))) return;

        hideTooltip();
    });

    // --- Click: pin on desktop, toggle on touch ---

    document.addEventListener('click', function(e) {
        var el = e.target.closest('.command-instruction, .command-summary');
        if (el && isTruncated(el)) {
            if (pinned && activeEl === el) {
                // Clicking a pinned tooltip's source: unpin and hide
                hideTooltip();
            } else if (activeEl === el && shownByHover) {
                // Clicking while hover-shown: pin it so it stays on mouse-away
                pinned = true;
                shownByHover = false;
            } else {
                // Show (or switch to different element)
                hideTooltip();
                showTooltip(el);
                pinned = isTouch; // pin on touch (no hover to maintain it)
                shownByHover = false;
            }
            return;
        }
        // Click on tooltip itself — keep it
        if (tooltip && tooltip.contains(e.target)) return;
        // Click elsewhere — dismiss
        if (activeEl) hideTooltip();
    });

    // Dismiss on scroll (tooltip position becomes stale)
    window.addEventListener('scroll', function() {
        if (activeEl) hideTooltip();
    }, { passive: true });

    // Dismiss on resize
    window.addEventListener('resize', function() {
        if (activeEl) hideTooltip();
    });

    // Expose a refresh function for SSE handlers to call after text updates
    window.CardTooltip = {
        refresh: function(el) {
            if (el) markTruncated(el);
        },
        refreshAll: function() {
            document.querySelectorAll('.command-instruction, .command-summary').forEach(markTruncated);
        }
    };

    // Initial mark on page load
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            window.CardTooltip.refreshAll();
        });
    } else {
        window.CardTooltip.refreshAll();
    }
})();
