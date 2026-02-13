/**
 * Shared utility functions for Claude Headspace frontend.
 *
 * Loaded in base.html before all other scripts.
 * Access via window.CHUtils namespace.
 */
(function() {
    'use strict';

    var _escapeDiv = document.createElement('div');

    // Protocol whitelist for URL validation (XSS prevention)
    var SAFE_PROTOCOLS = ['http:', 'https:'];

    /**
     * Escape HTML special characters to prevent XSS.
     * Uses DOM textContent/innerHTML for correctness.
     *
     * @param {string} text - Raw text to escape
     * @returns {string} HTML-safe string
     */
    function escapeHtml(text) {
        if (text == null) return '';
        _escapeDiv.textContent = String(text);
        return _escapeDiv.innerHTML;
    }

    /**
     * Validate a URL is safe for use in href attributes.
     * Only allows http:, https:, and fragment (#) URLs.
     *
     * @param {string} url - URL to validate
     * @returns {boolean} true if safe
     */
    function isSafeUrl(url) {
        if (!url) return false;
        var trimmed = url.trim();
        if (trimmed.startsWith('#')) return true;
        try {
            var parsed = new URL(trimmed, window.location.origin);
            return SAFE_PROTOCOLS.indexOf(parsed.protocol) !== -1;
        } catch (e) {
            return false;
        }
    }

    /**
     * Render markdown text to safe HTML using marked.js + DOMPurify.
     * Handles all CommonMark/GFM syntax including proper ordered lists,
     * tables, code blocks, and nested structures.
     *
     * @param {string} text - Raw markdown text
     * @param {Object} [options] - Rendering options
     * @param {boolean} [options.headerIds] - Generate id attributes on headers for anchor linking
     * @param {boolean} [options.copyButtons] - Add copy buttons to code blocks
     * @param {Function} [options.linkHandler] - Custom link handler(text, url) returning HTML string or null
     * @returns {string} Safe HTML string
     */
    function renderMarkdown(text, options) {
        if (!text) return '';
        options = options || {};

        // Strip HTML comments before parsing
        text = text.replace(/<!--[\s\S]*?-->/g, '');

        var renderer = new marked.Renderer();

        renderer.code = function(token) {
            var code = escapeHtml(token.text);
            if (options.copyButtons) {
                var id = 'code-' + Math.random().toString(36).slice(2, 9);
                return '<div class="code-block-wrapper" style="position:relative; margin: 1rem 0;">' +
                    '<button onclick="CHUtils.copyCodeBlock(\'' + id + '\')" ' +
                        'class="code-copy-btn" title="Copy to clipboard" aria-label="Copy code">' +
                        'Copy</button>' +
                    '<pre class="bg-surface rounded p-3 text-xs overflow-x-auto"><code id="' + id + '">' + code + '</code></pre>' +
                    '</div>';
            }
            return '<pre class="bg-surface rounded p-3 text-xs overflow-x-auto"><code>' + code + '</code></pre>';
        };

        renderer.heading = function(token) {
            var tag = 'h' + token.depth;
            var idAttr = '';
            if (options.headerIds) {
                idAttr = ' id="' + _slugify(token.text) + '"';
            }
            return '<' + tag + idAttr + '>' + this.parser.parseInline(token.tokens) + '</' + tag + '>';
        };

        renderer.link = function(token) {
            var href = token.href;
            var linkText = this.parser.parseInline(token.tokens);

            // Custom link handler (for doc: links, internal help links, etc.)
            if (options.linkHandler) {
                var custom = options.linkHandler(linkText, href);
                if (custom != null) return custom;
            }
            // Validate URL protocol
            if (!isSafeUrl(href)) {
                return escapeHtml(token.text);
            }
            return '<a href="' + escapeHtml(href) + '" target="_blank" rel="noopener">' + linkText + '</a>';
        };

        renderer.list = function(token) {
            var tag = token.ordered ? 'ol' : 'ul';
            var startAttr = (token.ordered && token.start != null && token.start !== 1)
                ? ' start="' + token.start + '"'
                : '';
            var body = '';
            for (var i = 0; i < token.items.length; i++) {
                body += this.listitem(token.items[i]);
            }
            return '<' + tag + startAttr + '>\n' + body + '</' + tag + '>\n';
        };

        var rawHtml = marked.parse(text, { renderer: renderer, breaks: true, gfm: true });

        // Merge consecutive <ol> fragments that marked creates from loose list items
        rawHtml = rawHtml.replace(/<\/ol>\s*<ol(?:\s+start="\d+")?>/g, '');

        return DOMPurify.sanitize(rawHtml, {
            ADD_TAGS: ['details', 'summary'],
            ADD_ATTR: ['target', 'rel', 'id', 'onclick', 'aria-label']
        });
    }

    /**
     * Slugify text for use as an HTML id attribute.
     * @param {string} text
     * @returns {string}
     */
    function _slugify(text) {
        return text.toLowerCase()
            .replace(/[^a-z0-9\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .trim();
    }

    /**
     * Copy a code block's content to clipboard.
     * Used by renderMarkdown's copyButtons option.
     *
     * @param {string} id - The id of the code element
     */
    function copyCodeBlock(id) {
        var codeEl = document.getElementById(id);
        if (!codeEl) return;

        var text = codeEl.textContent;
        navigator.clipboard.writeText(text).then(function() {
            var container = codeEl.closest('.code-block-wrapper');
            var btn = container ? container.querySelector('.code-copy-btn') : null;
            if (btn) {
                var original = btn.textContent;
                btn.textContent = 'Copied!';
                btn.style.color = '#22d3ee';
                setTimeout(function() {
                    btn.textContent = original;
                    btn.style.color = '';
                }, 1500);
            }
        }).catch(function(err) { console.warn('Clipboard copy failed:', err); });
    }

    /**
     * Fetch wrapper that adds CSRF token to destructive requests.
     * Reads token from <meta name="csrf-token"> tag.
     * Automatically adds Content-Type: application/json for requests with a body.
     *
     * @param {string} url - Request URL
     * @param {Object} [options] - fetch() options
     * @returns {Promise<Response>}
     */
    function apiFetch(url, options) {
        options = options || {};
        var method = (options.method || 'GET').toUpperCase();

        // Clone headers to avoid mutating caller's object
        var headers = {};
        if (options.headers) {
            if (options.headers instanceof Headers) {
                options.headers.forEach(function(value, key) {
                    headers[key] = value;
                });
            } else {
                Object.keys(options.headers).forEach(function(key) {
                    headers[key] = options.headers[key];
                });
            }
        }

        // Add CSRF token for state-changing methods
        if (method === 'POST' || method === 'PUT' || method === 'DELETE' || method === 'PATCH') {
            var meta = document.querySelector('meta[name="csrf-token"]');
            if (meta) {
                headers['X-CSRF-Token'] = meta.getAttribute('content');
            }
        }

        options.headers = headers;
        return fetch(url, options);
    }

    // ── Shared metric/aggregation helpers ──
    // Extracted from activity.js, project_show.js, dashboard-sse.js

    /**
     * Fill hourly gaps in a time-series history array.
     * Inserts zero-valued entries for missing hours between first and last entry.
     *
     * @param {Array} history - Array of {bucket_start, turn_count, ...} objects
     * @returns {Array} History with gaps filled
     */
    function fillHourlyGaps(history) {
        if (history.length < 2) return history;
        var bucketMap = {};
        history.forEach(function(h) {
            var d = new Date(h.bucket_start);
            var key = d.getFullYear() + '-' +
                String(d.getMonth() + 1).padStart(2, '0') + '-' +
                String(d.getDate()).padStart(2, '0') + 'T' +
                String(d.getHours()).padStart(2, '0');
            bucketMap[key] = h;
        });
        var first = new Date(history[0].bucket_start);
        var last = new Date(history[history.length - 1].bucket_start);
        first.setMinutes(0, 0, 0);
        last.setMinutes(0, 0, 0);
        var result = [];
        var cursor = new Date(first);
        while (cursor <= last) {
            var key = cursor.getFullYear() + '-' +
                String(cursor.getMonth() + 1).padStart(2, '0') + '-' +
                String(cursor.getDate()).padStart(2, '0') + 'T' +
                String(cursor.getHours()).padStart(2, '0');
            if (bucketMap[key]) {
                result.push(bucketMap[key]);
            } else {
                result.push({
                    bucket_start: cursor.toISOString(),
                    turn_count: 0,
                    avg_turn_time_seconds: null,
                    active_agents: null,
                    total_frustration: null,
                    frustration_turn_count: null,
                    max_frustration: null
                });
            }
            cursor = new Date(cursor.getTime() + 3600000);
        }
        return result;
    }

    /**
     * Aggregate hourly history entries by day.
     *
     * @param {Array} history - Array of hourly history entries
     * @returns {Array} Aggregated daily entries
     */
    function aggregateByDay(history) {
        var dayMap = {};
        history.forEach(function(h) {
            var d = new Date(h.bucket_start);
            var key = d.toLocaleDateString('en-CA');
            if (!dayMap[key]) {
                dayMap[key] = { date: d, turn_count: 0, total_frustration: 0, frustration_turn_count: 0, max_frustration: null, bucket_start: h.bucket_start };
            }
            dayMap[key].turn_count += h.turn_count;
            if (h.total_frustration != null) dayMap[key].total_frustration += h.total_frustration;
            if (h.frustration_turn_count != null) dayMap[key].frustration_turn_count += h.frustration_turn_count;
            var bucketMax = h.max_frustration != null ? h.max_frustration : null;
            if (bucketMax != null) {
                dayMap[key].max_frustration = dayMap[key].max_frustration != null
                    ? Math.max(dayMap[key].max_frustration, bucketMax)
                    : bucketMax;
            }
        });
        return Object.keys(dayMap).sort().map(function(k) {
            var entry = dayMap[k];
            if (entry.total_frustration === 0) entry.total_frustration = null;
            if (entry.frustration_turn_count === 0) entry.frustration_turn_count = null;
            return entry;
        });
    }

    /**
     * Compute weighted average turn time across history buckets.
     *
     * @param {Array} history - Array of history entries
     * @returns {number|null} Weighted average in seconds, or null if insufficient data
     */
    function weightedAvgTime(history) {
        var totalTime = 0, totalPairs = 0;
        if (history) {
            history.forEach(function(h) {
                if (h.avg_turn_time_seconds != null && h.turn_count >= 2) {
                    var pairs = h.turn_count - 1;
                    totalTime += h.avg_turn_time_seconds * pairs;
                    totalPairs += pairs;
                }
            });
        }
        return totalPairs > 0 ? totalTime / totalPairs : null;
    }

    /**
     * Sum turn_count across history entries.
     *
     * @param {Array} history - Array of history entries
     * @returns {number} Total turns
     */
    function sumTurns(history) {
        var total = 0;
        if (history) history.forEach(function(h) { total += (h.turn_count || 0); });
        return total;
    }

    /**
     * Sum frustration totals and turn counts across history entries.
     *
     * @param {Array} history - Array of history entries
     * @returns {{total: number, turns: number}} Frustration sums
     */
    function sumFrustrationHistory(history) {
        var total = 0, turns = 0;
        if (history) {
            history.forEach(function(h) {
                if (h.total_frustration != null) total += h.total_frustration;
                if (h.frustration_turn_count != null) turns += h.frustration_turn_count;
            });
        }
        return { total: total, turns: turns };
    }

    /**
     * Generate styled hero identity HTML markup.
     * Reusable component for the agent-hero + agent-hero-trail pattern
     * used across dashboard cards, kanban, logging, activity, and dialogs.
     *
     * @param {string} chars - Hero characters (e.g. "a4")
     * @param {string} trail - Trail characters (e.g. "6efe68")
     * @param {Object} [opts] - Options
     * @param {string} [opts.heroClass] - Extra classes for .agent-hero span
     * @param {string} [opts.trailClass] - Extra classes for .agent-hero-trail span
     * @returns {string} Safe HTML string
     */
    function heroHTML(chars, trail, opts) {
        opts = opts || {};
        var hClass = 'agent-hero' + (opts.heroClass ? ' ' + opts.heroClass : '');
        var tClass = 'agent-hero-trail' + (opts.trailClass ? ' ' + opts.trailClass : '');
        return '<span class="' + hClass + '">' + escapeHtml(chars) +
               '</span><span class="' + tClass + '">' + escapeHtml(trail) + '</span>';
    }

    // Global unhandled promise rejection handler
    window.addEventListener('unhandledrejection', function(event) {
        console.error('Unhandled promise rejection:', event.reason);
    });

    // Export to global namespace
    window.CHUtils = {
        escapeHtml: escapeHtml,
        isSafeUrl: isSafeUrl,
        renderMarkdown: renderMarkdown,
        copyCodeBlock: copyCodeBlock,
        apiFetch: apiFetch,
        heroHTML: heroHTML,
        fillHourlyGaps: fillHourlyGaps,
        aggregateByDay: aggregateByDay,
        weightedAvgTime: weightedAvgTime,
        sumTurns: sumTurns,
        sumFrustrationHistory: sumFrustrationHistory
    };
})();
