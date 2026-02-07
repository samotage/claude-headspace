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
     * Render markdown text to safe HTML.
     * Consolidated from project_show.js, help.js, and brain-reboot.js.
     * Handles: headers, bold, italic, code blocks, inline code, links,
     * unordered/ordered lists, horizontal rules, tables, paragraphs.
     * All generated links are validated against a protocol whitelist.
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

        // Strip HTML comments
        text = text.replace(/<!--[\s\S]*?-->/g, '');

        // Escape HTML first to prevent XSS
        var html = escapeHtml(text);

        // Code blocks (triple backtick) — must be processed before inline patterns
        html = html.replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
            var trimmed = code.trim();
            if (options.copyButtons) {
                var id = 'code-' + Math.random().toString(36).slice(2, 9);
                return '<div class="code-block-wrapper" style="position:relative; margin: 1rem 0;">' +
                    '<button onclick="CHUtils.copyCodeBlock(\'' + id + '\')" ' +
                        'class="code-copy-btn" title="Copy to clipboard" aria-label="Copy code">' +
                        'Copy</button>' +
                    '<pre class="bg-surface rounded p-3 text-xs overflow-x-auto"><code id="' + id + '">' + trimmed + '</code></pre>' +
                    '</div>';
            }
            return '<pre class="bg-surface rounded p-3 text-xs overflow-x-auto"><code>' + trimmed + '</code></pre>';
        });

        // Inline code
        html = html.replace(/`([^`]+)`/g, '<code class="bg-surface px-1 rounded text-xs">$1</code>');

        // Headers (with optional id attributes for anchor linking)
        if (options.headerIds) {
            html = html.replace(/^### (.+)$/gm, function(m, title) {
                var id = _slugify(title);
                return '<h3 id="' + id + '" class="text-base font-semibold text-primary mt-4 mb-2">' + title + '</h3>';
            });
            html = html.replace(/^## (.+)$/gm, function(m, title) {
                var id = _slugify(title);
                return '<h2 id="' + id + '" class="text-lg font-bold text-primary mt-4 mb-2">' + title + '</h2>';
            });
            html = html.replace(/^# (.+)$/gm, function(m, title) {
                var id = _slugify(title);
                return '<h1 id="' + id + '" class="text-xl font-bold text-primary mt-4 mb-2">' + title + '</h1>';
            });
        } else {
            html = html.replace(/^### (.+)$/gm, '<h3 class="text-base font-semibold text-primary mt-4 mb-2">$1</h3>');
            html = html.replace(/^## (.+)$/gm, '<h2 class="text-lg font-bold text-primary mt-4 mb-2">$1</h2>');
            html = html.replace(/^# (.+)$/gm, '<h1 class="text-xl font-bold text-primary mt-4 mb-2">$1</h1>');
        }

        // Bold and italic
        html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
        html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

        // Horizontal rules
        html = html.replace(/^---+$/gm, '<hr class="border-border my-4">');

        // Unordered lists
        html = html.replace(/^- (.+)$/gm, '<li class="ml-4">$1</li>');

        // Ordered lists
        html = html.replace(/^\d+\. (.+)$/gm, '<li class="ml-4 list-decimal">$1</li>');

        // Wrap consecutive list items
        html = html.replace(/(<li[^>]*>.*<\/li>\n?)+/g, function(match) {
            if (match.indexOf('list-decimal') !== -1) {
                return '<ol class="list-decimal list-inside mb-2">' + match + '</ol>';
            }
            return '<ul class="list-disc mb-2">' + match + '</ul>';
        });

        // Links — with URL validation for XSS prevention
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(match, linkText, url) {
            // Custom link handler (for doc: links, internal help links, etc.)
            if (options.linkHandler) {
                var custom = options.linkHandler(linkText, url);
                if (custom != null) return custom;
            }
            // Validate URL protocol
            if (!isSafeUrl(url)) {
                return escapeHtml(linkText);
            }
            return '<a href="' + escapeHtml(url) + '" class="text-cyan hover:underline" target="_blank" rel="noopener">' + linkText + '</a>';
        });

        // Tables (simple support)
        html = html.replace(/^\|(.+)\|$/gm, function(match, content) {
            var cells = content.split('|').map(function(c) { return c.trim(); });
            return '<tr class="border-b border-border">' +
                cells.map(function(c) {
                    if (/^[-:]+$/.test(c)) return '';
                    return '<td class="px-3 py-2 text-secondary">' + c + '</td>';
                }).join('') +
                '</tr>';
        });

        // Wrap tables
        html = html.replace(/(<tr[^>]*>.*<\/tr>)+/g, function(match) {
            return '<table class="w-full my-4 border border-border">' + match + '</table>';
        });

        // Line breaks (double newline -> paragraph)
        html = html.replace(/\n\n/g, '</p><p class="mb-2">');
        html = '<p class="mb-2">' + html + '</p>';

        // Clean up empty paragraphs
        html = html.replace(/<p class="mb-2"><\/p>/g, '');

        return html;
    }

    /**
     * Slugify text for use as an HTML id attribute.
     * @param {string} text
     * @returns {string}
     */
    function _slugify(text) {
        // The text is already HTML-escaped at this point, so we decode entities first
        var decoded = text.replace(/&amp;/g, '&').replace(/&lt;/g, '<').replace(/&gt;/g, '>').replace(/&quot;/g, '"');
        return decoded.toLowerCase()
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

    // Export to global namespace
    window.CHUtils = {
        escapeHtml: escapeHtml,
        isSafeUrl: isSafeUrl,
        renderMarkdown: renderMarkdown,
        copyCodeBlock: copyCodeBlock,
        apiFetch: apiFetch,
        fillHourlyGaps: fillHourlyGaps,
        aggregateByDay: aggregateByDay,
        weightedAvgTime: weightedAvgTime,
        sumTurns: sumTurns,
        sumFrustrationHistory: sumFrustrationHistory
    };
})();
