/**
 * Brain Reboot modal handlers.
 * Provides generate, display, clipboard, and export functionality.
 */

(function() {
    'use strict';

var brainRebootState = {
    projectId: null,
    projectName: null,
    content: null,
    isOpen: false
};

function openBrainReboot(projectId, projectName, projectSlug) {
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
        if (projectSlug) {
            subtitle.href = '/projects/' + projectSlug;
        } else {
            subtitle.removeAttribute('href');
        }
    }

    // Update project show page link
    var projectLink = document.getElementById('brain-reboot-project-link');
    if (projectLink) {
        if (projectSlug) {
            projectLink.href = '/projects/' + projectSlug;
            projectLink.textContent = 'View ' + (projectName || 'Project');
            projectLink.classList.remove('hidden');
        } else {
            projectLink.classList.add('hidden');
        }
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
    CHUtils.apiFetch('/api/projects/' + projectId + '/brain-reboot', {
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
                contentEl.innerHTML = '<p class="text-red text-sm">Error: ' + CHUtils.escapeHtml(err.message) + '</p>';
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

    CHUtils.apiFetch('/api/projects/' + brainRebootState.projectId + '/brain-reboot/export', {
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

    contentEl.innerHTML = '<div class="prose prose-invert max-w-none">' + CHUtils.renderMarkdown(data.content) + '</div>';

    // Add "Generate/Regenerate Progress Summary" button
    var btnWrap = document.createElement('div');
    btnWrap.className = 'mt-4 flex items-center justify-end gap-3';
    var btn = document.createElement('button');
    btn.id = 'brain-reboot-generate-summary-btn';
    btn.className = 'px-3 py-1.5 text-xs font-medium rounded border border-cyan/30 text-cyan hover:bg-cyan/10 transition-colors disabled:opacity-50 disabled:cursor-not-allowed';
    btn.textContent = data.has_summary ? 'Regenerate Progress Summary' : 'Generate Progress Summary';
    btn.onclick = function() { generateProgressSummary(btn); };
    btnWrap.appendChild(btn);
    contentEl.appendChild(btnWrap);
}

function generateProgressSummary(btn) {
    if (!brainRebootState.projectId) return;

    btn.disabled = true;
    btn.textContent = 'Generating...';

    // Show in-progress message next to the button
    var btnWrap = btn.parentElement;
    var statusMsg = document.createElement('span');
    statusMsg.className = 'text-muted text-xs italic';
    statusMsg.textContent = 'Generating progress summary from git history — this may take a moment...';
    statusMsg.id = 'brain-reboot-summary-status';
    if (btnWrap) btnWrap.insertBefore(statusMsg, btn);

    // Use time_based scope to force full regeneration (since_last returns empty if no new commits)
    CHUtils.apiFetch('/api/projects/' + brainRebootState.projectId + '/progress-summary', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scope: 'time_based' })
    })
        .then(function(response) {
            if (!response.ok) {
                return response.json().catch(function() {
                    throw new Error('Generation failed (HTTP ' + response.status + ')');
                }).then(function(data) {
                    throw new Error(data.error || 'Generation failed');
                });
            }
            return response.json();
        })
        .then(function(summaryData) {
            // Handle empty result (no commits in scope)
            if (summaryData.status === 'empty') {
                throw new Error('No commits found in the configured time window');
            }

            // Update status message while refreshing
            if (statusMsg) statusMsg.textContent = 'Refreshing brain reboot...';

            return CHUtils.apiFetch('/api/projects/' + brainRebootState.projectId + '/brain-reboot', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' }
            });
        })
        .then(function(response) {
            if (!response.ok) {
                return response.json().then(function(data) {
                    throw new Error(data.error || 'Refresh failed');
                });
            }
            return response.json();
        })
        .then(function(data) {
            brainRebootState.content = data.content;
            var contentEl = document.getElementById('brain-reboot-content');
            if (contentEl) {
                renderBrainRebootContent(contentEl, data);
            }

            // Update status
            var statusEl = document.getElementById('brain-reboot-status');
            if (statusEl && data.metadata && data.metadata.generated_at) {
                statusEl.textContent = 'Generated: ' + new Date(data.metadata.generated_at).toLocaleString();
            }

            // Update artifacts info
            var artifactsEl = document.getElementById('brain-reboot-artifacts');
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
            btn.disabled = false;
            btn.textContent = 'Regenerate Progress Summary';
            btn.style.color = '#ef4444';
            btn.style.borderColor = '#ef4444';
            // Remove status message and show error
            if (statusMsg && statusMsg.parentElement) statusMsg.remove();
            var contentEl = document.getElementById('brain-reboot-content');
            var errorP = document.createElement('p');
            errorP.className = 'text-red text-sm mt-2';
            errorP.textContent = 'Error: ' + err.message;
            if (contentEl) contentEl.appendChild(errorP);
            setTimeout(function() {
                btn.style.color = '';
                btn.style.borderColor = '';
            }, 2000);
        });
}

    // Export globals for template onclick handlers
    window.openBrainReboot = openBrainReboot;
    window.closeBrainReboot = closeBrainReboot;
    window.copyBrainReboot = copyBrainReboot;
    window.exportBrainReboot = exportBrainReboot;

})();
