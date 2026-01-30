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

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initHelp);
    } else {
        initHelp();
    }

    function initHelp() {
        loadTopics();

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
            var isActive = helpState.currentTopic === topic.slug;
            return '<a href="/help/' + topic.slug + '"' +
                   ' onclick="loadHelpTopic(\'' + topic.slug + '\'); return false;"' +
                   ' class="block px-3 py-2 rounded text-sm ' +
                   (isActive
                       ? 'bg-cyan/20 text-cyan'
                       : 'text-secondary hover:text-primary hover:bg-hover') +
                   ' transition-colors"' +
                   ' data-topic="' + topic.slug + '">' +
                   escapeHtml(topic.title) +
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

            // Update URL without reload
            if (window.history && window.history.replaceState) {
                window.history.replaceState(null, '', '/help/' + slug);
            }

            // Clear search
            var searchInput = document.getElementById('help-search-input');
            if (searchInput) {
                searchInput.value = '';
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
                return '<a href="/help/' + result.slug + '"' +
                       ' onclick="loadHelpTopic(\'' + result.slug + '\'); return false;"' +
                       ' class="block px-3 py-2 rounded text-sm text-secondary hover:text-primary hover:bg-hover transition-colors">' +
                       '<div class="font-medium">' + highlightMatch(result.title, query) + '</div>' +
                       (result.excerpt ? '<div class="text-xs text-muted mt-1 line-clamp-2">' + highlightMatch(escapeHtml(result.excerpt), query) + '</div>' : '') +
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

    function escapeHtml(text) {
        var div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function renderMarkdown(markdown) {
        // Simple markdown to HTML rendering
        var html = markdown
            // Escape HTML first
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            // Code blocks (before other processing)
            .replace(/```(\w*)\n([\s\S]*?)```/g, function(match, lang, code) {
                return '<pre class="bg-surface rounded p-4 overflow-x-auto my-4"><code class="text-sm">' + code.trim() + '</code></pre>';
            })
            // Inline code
            .replace(/`([^`]+)`/g, '<code class="px-1.5 py-0.5 bg-surface rounded text-cyan text-sm">$1</code>')
            // Headers
            .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold text-primary mt-6 mb-2">$1</h3>')
            .replace(/^## (.+)$/gm, '<h2 class="text-xl font-bold text-primary mt-8 mb-3">$1</h2>')
            .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold text-primary mb-4">$1</h1>')
            // Bold and italic
            .replace(/\*\*([^*]+)\*\*/g, '<strong class="font-bold">$1</strong>')
            .replace(/\*([^*]+)\*/g, '<em class="italic">$1</em>')
            // Links
            .replace(/\[([^\]]+)\]\(([^)]+)\)/g, function(match, text, url) {
                if (url.startsWith('http')) {
                    return '<a href="' + url + '" target="_blank" rel="noopener" class="text-cyan hover:underline">' + text + '</a>';
                } else {
                    // Internal link - navigate to help topic
                    return '<a href="/help/' + url + '" onclick="loadHelpTopic(\'' + url + '\'); return false;" class="text-cyan hover:underline">' + text + '</a>';
                }
            })
            // Lists
            .replace(/^- (.+)$/gm, '<li class="ml-4 text-secondary">$1</li>')
            .replace(/^(\d+)\. (.+)$/gm, '<li class="ml-4 text-secondary list-decimal">$2</li>')
            // Tables (simple support)
            .replace(/^\|(.+)\|$/gm, function(match, content) {
                var cells = content.split('|').map(function(c) { return c.trim(); });
                return '<tr class="border-b border-border">' +
                    cells.map(function(c) {
                        if (c.match(/^[-:]+$/)) return ''; // Skip separator row
                        return '<td class="px-3 py-2 text-secondary">' + c + '</td>';
                    }).join('') +
                    '</tr>';
            })
            // Paragraphs
            .replace(/\n\n/g, '</p><p class="my-3 text-secondary">')
            .replace(/\n/g, '<br>');

        // Wrap lists
        html = html.replace(/(<li[^>]*>.*<\/li>)+/g, function(match) {
            if (match.includes('list-decimal')) {
                return '<ol class="my-3 list-decimal list-inside">' + match + '</ol>';
            }
            return '<ul class="my-3 list-disc list-inside">' + match + '</ul>';
        });

        // Wrap tables
        html = html.replace(/(<tr[^>]*>.*<\/tr>)+/g, function(match) {
            return '<table class="w-full my-4 border border-border">' + match + '</table>';
        });

        return '<div class="prose prose-invert max-w-none"><p class="my-3 text-secondary">' + html + '</p></div>';
    }
})();
