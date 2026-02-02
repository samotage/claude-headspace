/**
 * Brain Reboot modal handlers.
 * Provides generate, display, clipboard, and export functionality.
 */

var brainRebootState = {
    projectId: null,
    projectName: null,
    content: null,
    isOpen: false
};

function openBrainReboot(projectId, projectName) {
    brainRebootState.projectId = projectId;
    brainRebootState.projectName = projectName || 'Project';
    brainRebootState.content = null;
    brainRebootState.isOpen = true;

    var backdrop = document.getElementById('brain-reboot-backdrop');
    var slider = document.getElementById('brain-reboot-slider');
    if (!slider) return;

    // Update header
    var subtitle = document.getElementById('brain-reboot-subtitle');
    if (subtitle) {
        subtitle.textContent = projectName || '';
    }

    // Show slider
    if (backdrop) backdrop.classList.add('active');
    slider.classList.add('active');
    document.body.style.overflow = 'hidden';

    // Show loading state
    var contentEl = document.getElementById('brain-reboot-content');
    if (contentEl) {
        contentEl.innerHTML = '<p class="text-muted italic">Generating brain reboot...</p>';
    }

    // Reset status
    var statusEl = document.getElementById('brain-reboot-status');
    if (statusEl) statusEl.textContent = '';
    var artifactsEl = document.getElementById('brain-reboot-artifacts');
    if (artifactsEl) artifactsEl.textContent = '';

    // Add escape key listener
    document.addEventListener('keydown', brainRebootKeyHandler);

    // Generate brain reboot
    fetch('/api/projects/' + projectId + '/brain-reboot', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(function(response) {
            if (!response.ok) {
                return response.json().then(function(data) {
                    throw new Error(data.error || 'Generation failed');
                });
            }
            return response.json();
        })
        .then(function(data) {
            brainRebootState.content = data.content;
            renderBrainRebootContent(contentEl, data);

            // Update status
            if (statusEl && data.metadata && data.metadata.generated_at) {
                statusEl.textContent = 'Generated: ' + new Date(data.metadata.generated_at).toLocaleString();
            }

            // Update artifacts info
            if (artifactsEl) {
                var parts = [];
                if (data.has_waypoint) parts.push('Waypoint');
                if (data.has_summary) parts.push('Progress Summary');
                if (parts.length > 0) {
                    artifactsEl.textContent = 'Includes: ' + parts.join(', ');
                } else {
                    artifactsEl.textContent = 'No artifacts available';
                }
            }
        })
        .catch(function(err) {
            if (contentEl) {
                contentEl.innerHTML = '<p class="text-red text-sm">Error: ' + escapeHtmlBR(err.message) + '</p>';
            }
        });
}

function closeBrainReboot() {
    var backdrop = document.getElementById('brain-reboot-backdrop');
    var slider = document.getElementById('brain-reboot-slider');
    if (backdrop) backdrop.classList.remove('active');
    if (slider) slider.classList.remove('active');
    document.body.style.overflow = '';
    brainRebootState.isOpen = false;
    document.removeEventListener('keydown', brainRebootKeyHandler);
}

function brainRebootKeyHandler(e) {
    if (e.key === 'Escape' && brainRebootState.isOpen) {
        closeBrainReboot();
    }
}

function copyBrainReboot() {
    if (!brainRebootState.content) return;

    var btn = document.getElementById('brain-reboot-copy-btn');
    navigator.clipboard.writeText(brainRebootState.content).then(function() {
        if (btn) {
            var original = btn.textContent;
            btn.textContent = 'Copied!';
            btn.style.color = '#22d3ee';
            btn.style.borderColor = '#22d3ee';
            setTimeout(function() {
                btn.textContent = original;
                btn.style.color = '';
                btn.style.borderColor = '';
            }, 1500);
        }
    }).catch(function() {
        if (btn) {
            var original = btn.textContent;
            btn.textContent = 'Copy failed';
            btn.style.color = '#ef4444';
            setTimeout(function() {
                btn.textContent = original;
                btn.style.color = '';
            }, 1500);
        }
    });
}

function exportBrainReboot() {
    if (!brainRebootState.projectId) return;

    var btn = document.getElementById('brain-reboot-export-btn');
    if (btn) {
        btn.disabled = true;
        btn.textContent = 'Exporting...';
    }

    fetch('/api/projects/' + brainRebootState.projectId + '/brain-reboot/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(function(response) {
            if (!response.ok) {
                return response.json().then(function(data) {
                    throw new Error(data.error || 'Export failed');
                });
            }
            return response.json();
        })
        .then(function(data) {
            if (btn) {
                btn.textContent = 'Exported!';
                btn.style.color = '#22c55e';
                btn.style.borderColor = '#22c55e';
                setTimeout(function() {
                    btn.textContent = 'Export';
                    btn.style.color = '';
                    btn.style.borderColor = '';
                    btn.disabled = false;
                }, 1500);
            }

            var statusEl = document.getElementById('brain-reboot-status');
            if (statusEl) {
                statusEl.textContent = 'Exported to: ' + (data.path || 'project directory');
            }
        })
        .catch(function(err) {
            if (btn) {
                btn.textContent = 'Export failed';
                btn.style.color = '#ef4444';
                btn.style.borderColor = '#ef4444';
                setTimeout(function() {
                    btn.textContent = 'Export';
                    btn.style.color = '';
                    btn.style.borderColor = '';
                    btn.disabled = false;
                }, 2000);
            }
        });
}

function renderBrainRebootContent(contentEl, data) {
    if (!contentEl || !data || !data.content) return;

    // Convert markdown-like content to HTML paragraphs
    var lines = data.content.split('\n');
    var html = '';
    var inList = false;

    lines.forEach(function(line) {
        var trimmed = line.trim();

        if (trimmed === '') {
            if (inList) {
                html += '</ul>';
                inList = false;
            }
            return;
        }

        if (trimmed.startsWith('# ')) {
            html += '<h1 class="text-primary text-xl font-display mb-3">' + escapeHtmlBR(trimmed.substring(2)) + '</h1>';
        } else if (trimmed.startsWith('## ')) {
            html += '<h2 class="text-primary text-lg font-display mt-6 mb-2">' + escapeHtmlBR(trimmed.substring(3)) + '</h2>';
        } else if (trimmed.startsWith('### ')) {
            html += '<h3 class="text-secondary text-base font-medium mt-4 mb-2">' + escapeHtmlBR(trimmed.substring(4)) + '</h3>';
        } else if (trimmed.startsWith('- ') || trimmed.startsWith('* ')) {
            if (!inList) {
                html += '<ul class="list-disc pl-5 space-y-1 text-secondary text-sm">';
                inList = true;
            }
            html += '<li>' + escapeHtmlBR(trimmed.substring(2)) + '</li>';
        } else if (trimmed.startsWith('---')) {
            html += '<hr class="border-border my-4">';
        } else if (trimmed.startsWith('_') && trimmed.endsWith('_')) {
            html += '<p class="text-muted text-sm italic mt-4">' + escapeHtmlBR(trimmed.slice(1, -1)) + '</p>';
        } else if (trimmed.startsWith('*') && trimmed.endsWith('*')) {
            html += '<p class="text-muted text-sm italic">' + escapeHtmlBR(trimmed.slice(1, -1)) + '</p>';
        } else if (trimmed.startsWith('**') && trimmed.endsWith('**')) {
            html += '<p class="text-primary text-sm font-medium">' + escapeHtmlBR(trimmed.slice(2, -2)) + '</p>';
        } else if (trimmed.startsWith('Generated:')) {
            html += '<p class="text-muted text-xs mb-4">' + escapeHtmlBR(trimmed) + '</p>';
        } else {
            html += '<p class="text-secondary text-sm leading-relaxed mb-2">' + escapeHtmlBR(trimmed) + '</p>';
        }
    });

    if (inList) {
        html += '</ul>';
    }

    contentEl.innerHTML = html;
}

function escapeHtmlBR(text) {
    var div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
