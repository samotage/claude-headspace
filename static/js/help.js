/**
 * Help system for Claude Headspace
 * Provides page-based documentation with search functionality
 */

(function() {
    'use strict';

    // State
    let helpState = {
        topics: [],
        searchIndex: [],
        currentTopic: null
    };

    // Make functions global
    window.searchHelp = searchHelp;
    window.loadHelpTopic = loadHelpTopic;
    window.openDocViewer = openDocViewer;
    window.closeDocViewer = closeDocViewer;

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initHelp);
    } else {
        initHelp();
    }

    function initHelp() {
        loadTopics();

        // Scroll to anchor on initial page load (after content renders)
        if (window.location.hash) {
            setTimeout(function() { scrollToAnchor(window.location.hash); }, 500);
        }

        // Focus search on / key
        document.addEventListener('keydown', function(e) {
            if (e.key === '/' && !isInputFocused()) {
                e.preventDefault();
                var searchInput = document.getElementById('help-search-input');
                if (searchInput) {
                    searchInput.focus();
                }
            }
        });
    }

    function isInputFocused() {
        var active = document.activeElement;
        if (!active) return false;
        var tag = active.tagName.toLowerCase();
        return tag === 'input' || tag === 'textarea' || active.isContentEditable;
    }

    async function loadTopics() {
        try {
            var response = await fetch('/api/help/topics');
            var data = await response.json();
            helpState.topics = data.topics || [];
            renderTOC(helpState.topics);
            buildSearchIndex();
        } catch (error) {
            console.error('Failed to load help topics:', error);
        }
    }

    function renderTOC(topics) {
        var toc = document.getElementById('help-toc');
        if (!toc) return;

        toc.innerHTML = topics.map(function(topic) {
            var esc = window.CHUtils.escapeHtml;
            var safeSlug = esc(topic.slug);
            var isActive = helpState.currentTopic === topic.slug;
            return '<a href="/help/' + safeSlug + '"' +
                   ' onclick="loadHelpTopic(\'' + safeSlug.replace(/'/g, '\\&#39;') + '\'); return false;"' +
                   ' class="block px-3 py-2 rounded text-sm ' +
                   (isActive
                       ? 'bg-cyan/20 text-cyan'
                       : 'text-secondary hover:text-primary hover:bg-hover') +
                   ' transition-colors"' +
                   ' data-topic="' + safeSlug + '">' +
                   esc(topic.title) +
                   '</a>';
        }).join('');
    }

    async function loadHelpTopic(slug) {
        try {
            var response = await fetch('/api/help/topics/' + slug);
            if (!response.ok) {
                throw new Error('Topic not found');
            }

            var data = await response.json();
            helpState.currentTopic = slug;

            // Render content
            var content = document.getElementById('help-content');
            if (content) {
                content.innerHTML = renderMarkdown(data.content);
            }

            // Update TOC active state
            renderTOC(helpState.topics);

            // Update URL without reload (preserve hash if present)
            if (window.history && window.history.replaceState) {
                var hash = window.location.hash || '';
                window.history.replaceState(null, '', '/help/' + slug + hash);
            }

            // Clear search
            var searchInput = document.getElementById('help-search-input');
            if (searchInput) {
                searchInput.value = '';
            }

            // Scroll to anchor if present
            if (window.location.hash) {
                setTimeout(function() { scrollToAnchor(window.location.hash); }, 100);
            }

        } catch (error) {
            console.error('Failed to load topic:', error);
            var content = document.getElementById('help-content');
            if (content) {
                content.innerHTML = '<div class="text-red text-center py-8">Failed to load topic</div>';
            }
        }
    }

    async function buildSearchIndex() {
        try {
            var response = await fetch('/api/help/search');
            var data = await response.json();
            helpState.searchIndex = data.topics || [];
        } catch (error) {
            console.error('Failed to build search index:', error);
        }
    }

    function searchHelp(query) {
        query = query.toLowerCase().trim();

        if (!query) {
            // Show normal TOC
            renderTOC(helpState.topics);
            return;
        }

        // Search through topics
        var results = helpState.searchIndex
            .filter(function(topic) {
                var titleMatch = topic.title.toLowerCase().includes(query);
                var contentMatch = topic.content.toLowerCase().includes(query);
                return titleMatch || contentMatch;
            })
            .map(function(topic) {
                return {
                    slug: topic.slug,
                    title: topic.title,
                    excerpt: extractSearchExcerpt(topic.content, query)
                };
            });

        renderSearchResults(results, query);
    }

    function extractSearchExcerpt(content, query) {
        var lowerContent = content.toLowerCase();
        var index = lowerContent.indexOf(query);
        if (index === -1) return '';

        var start = Math.max(0, index - 40);
        var end = Math.min(content.length, index + query.length + 60);
        var excerpt = content.slice(start, end);

        if (start > 0) excerpt = '...' + excerpt;
        if (end < content.length) excerpt = excerpt + '...';

        return excerpt;
    }

    function renderSearchResults(results, query) {
        var toc = document.getElementById('help-toc');
        if (!toc) return;

        if (results.length === 0) {
            toc.innerHTML = '<div class="px-3 py-4 text-muted text-sm">No results found</div>';
            return;
        }

        toc.innerHTML =
            '<div class="px-3 py-2 text-xs text-muted border-b border-border mb-2">' +
                results.length + ' result' + (results.length === 1 ? '' : 's') +
            '</div>' +
            results.map(function(result) {
                var esc = window.CHUtils.escapeHtml;
                var safeSlug = esc(result.slug);
                return '<a href="/help/' + safeSlug + '"' +
                       ' onclick="loadHelpTopic(\'' + safeSlug.replace(/'/g, '\\&#39;') + '\'); return false;"' +
                       ' class="block px-3 py-2 rounded text-sm text-secondary hover:text-primary hover:bg-hover transition-colors">' +
                       '<div class="font-medium">' + highlightMatch(esc(result.title), query) + '</div>' +
                       (result.excerpt ? '<div class="text-xs text-muted mt-1 line-clamp-2">' + highlightMatch(esc(result.excerpt), query) + '</div>' : '') +
                       '</a>';
            }).join('');
    }

    function highlightMatch(text, query) {
        if (!query) return text;
        var regex = new RegExp('(' + escapeRegex(query) + ')', 'gi');
        return text.replace(regex, '<mark class="bg-cyan/30 text-primary">$1</mark>');
    }

    function escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function slugify(text) {
        return text.toLowerCase()
            .replace(/[^a-z0-9\s-]/g, '')
            .replace(/\s+/g, '-')
            .replace(/-+/g, '-')
            .trim();
    }

    function scrollToAnchor(hash) {
        if (!hash) return;
        var id = hash.replace('#', '');
        var el = document.getElementById(id);
        if (!el) return;
        el.scrollIntoView({ behavior: 'smooth', block: 'start' });
        // Brief highlight
        el.style.transition = 'background-color 0.3s ease';
        el.style.backgroundColor = 'rgba(86, 212, 221, 0.15)';
        el.style.borderRadius = '4px';
        el.style.padding = '2px 6px';
        el.style.marginLeft = '-6px';
        setTimeout(function() {
            el.style.backgroundColor = 'transparent';
            setTimeout(function() {
                el.style.transition = '';
                el.style.borderRadius = '';
                el.style.padding = '';
                el.style.marginLeft = '';
            }, 300);
        }, 2000);
    }

    function renderMarkdown(markdown) {
        var html = CHUtils.renderMarkdown(markdown, {
            headerIds: true,
            copyButtons: true,
            linkHandler: function(text, url) {
                if (url.startsWith('doc:')) {
                    var docId = url.slice(4);
                    return '<a href="#" onclick="openDocViewer(\'' + CHUtils.escapeHtml(docId) + '\'); return false;" class="inline-flex items-center gap-1 text-cyan hover:underline cursor-pointer">' +
                        '<svg class="w-4 h-4 inline" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>' +
                        text + '</a>';
                } else if (!url.startsWith('http') && !url.startsWith('#')) {
                    // Internal link - navigate to help topic
                    return '<a href="/help/' + CHUtils.escapeHtml(url) + '" onclick="loadHelpTopic(\'' + CHUtils.escapeHtml(url) + '\'); return false;" class="text-cyan hover:underline">' + text + '</a>';
                }
                return null; // Fall through to default link handling
            }
        });
        return '<div class="prose prose-invert max-w-none">' + html + '</div>';
    }

    // Document viewer modal functions
    async function openDocViewer(docId) {
        var modal = document.getElementById('doc-viewer-modal');
        if (!modal) return;

        // Show modal with loading state
        modal.classList.remove('hidden');
        document.body.style.overflow = 'hidden';

        var titleEl = document.getElementById('doc-viewer-title');
        var contentEl = document.getElementById('doc-viewer-content');
        if (titleEl) titleEl.textContent = 'Loading...';
        if (contentEl) contentEl.innerHTML = '<div class="text-muted text-center py-8">Loading...</div>';

        try {
            var response = await fetch('/api/help/' + docId);
            if (!response.ok) {
                throw new Error('Document not found');
            }
            var data = await response.json();

            if (titleEl) titleEl.textContent = data.title || 'Document';
            if (contentEl) contentEl.innerHTML = renderMarkdown(data.content);
        } catch (error) {
            console.error('Failed to load document:', error);
            if (contentEl) {
                contentEl.innerHTML = '<div class="text-red text-center py-8">Failed to load document</div>';
            }
        }
    }

    function closeDocViewer() {
        var modal = document.getElementById('doc-viewer-modal');
        if (modal) {
            modal.classList.add('hidden');
            document.body.style.overflow = '';
        }
    }

    // Close doc viewer on Escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            var modal = document.getElementById('doc-viewer-modal');
            if (modal && !modal.classList.contains('hidden')) {
                closeDocViewer();
            }
        }
    });
})();
