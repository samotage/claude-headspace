/**
 * Progress Summary UI handlers.
 * Provides toggle, generate, and display functionality for per-project progress summaries.
 */

function toggleProgressSummary(projectId) {
    const panel = document.getElementById('progress-summary-' + projectId);
    if (!panel) return;

    const isHidden = panel.classList.contains('hidden');
    panel.classList.toggle('hidden');

    // Load existing summary when opening
    if (isHidden) {
        loadProgressSummary(projectId);
    }
}

function loadProgressSummary(projectId) {
    const contentEl = document.querySelector(
        '.progress-summary-content[data-project-id="' + projectId + '"]'
    );
    if (!contentEl) return;

    contentEl.innerHTML = '<p class="text-muted italic">Loading...</p>';

    fetch('/api/projects/' + projectId + '/progress-summary')
        .then(function(response) {
            if (response.status === 404) {
                contentEl.innerHTML = '<p class="text-muted italic">No progress summary yet. Click Generate to create one from git history.</p>';
                return null;
            }
            if (!response.ok) {
                throw new Error('Failed to load summary');
            }
            return response.json();
        })
        .then(function(data) {
            if (!data) return;
            renderSummary(contentEl, data);
        })
        .catch(function(err) {
            contentEl.innerHTML = '<p class="text-red text-sm">Error loading summary: ' + err.message + '</p>';
        });
}

function generateProgressSummary(projectId) {
    var btn = document.querySelector(
        '.generate-summary-btn[data-project-id="' + projectId + '"]'
    );
    var contentEl = document.querySelector(
        '.progress-summary-content[data-project-id="' + projectId + '"]'
    );
    if (!contentEl) return;

    // Show panel if hidden
    var panel = document.getElementById('progress-summary-' + projectId);
    if (panel && panel.classList.contains('hidden')) {
        panel.classList.remove('hidden');
    }

    // Disable button and show in-progress
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Generating...';
    }
    contentEl.innerHTML = '<p class="text-muted italic">Generating progress summary from git history...</p>';

    fetch('/api/projects/' + projectId + '/progress-summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
    })
        .then(function(response) {
            if (response.status === 409) {
                contentEl.innerHTML = '<p class="text-amber text-sm">Generation already in progress. Please wait.</p>';
                return null;
            }
            if (response.status === 422) {
                contentEl.innerHTML = '<p class="text-red text-sm">This project is not a git repository.</p>';
                return null;
            }
            if (!response.ok) {
                return response.json().then(function(data) {
                    throw new Error(data.error || 'Generation failed');
                });
            }
            return response.json();
        })
        .then(function(data) {
            if (!data) return;

            if (data.status === 'empty') {
                contentEl.innerHTML = '<p class="text-muted italic">' + (data.message || 'No commits found in scope.') + '</p>';
                return;
            }

            renderSummary(contentEl, data);
        })
        .catch(function(err) {
            contentEl.innerHTML = '<p class="text-red text-sm">Error: ' + err.message + '</p>';
        })
        .finally(function() {
            if (btn) {
                btn.disabled = false;
                btn.textContent = 'Generate';
            }
        });
}

function renderSummary(contentEl, data) {
    var html = '';

    if (data.metadata) {
        var meta = data.metadata;
        html += '<div class="text-muted text-xs mb-2">';
        if (meta.generated_at) {
            html += 'Generated: ' + new Date(meta.generated_at).toLocaleString();
        }
        if (meta.commit_count) {
            html += ' | ' + meta.commit_count + ' commits';
        }
        if (meta.scope) {
            html += ' | scope: ' + meta.scope;
        }
        html += '</div>';
    }

    if (data.summary) {
        // Convert newlines to paragraphs
        var paragraphs = data.summary.split(/\n\n+/);
        html += '<div class="space-y-2">';
        paragraphs.forEach(function(p) {
            p = p.trim();
            if (p) {
                html += '<p class="text-secondary text-sm leading-relaxed">' + escapeHtml(p) + '</p>';
            }
        });
        html += '</div>';
    }

    contentEl.innerHTML = html;
}

function escapeHtml(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
