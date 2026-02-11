/**
 * Full-text modal for displaying complete command input and agent output.
 * Fetches on-demand from /api/tasks/<id>/full-text and displays in a scrollable overlay.
 */
(function() {
    'use strict';

    var modal = null;
    var cache = {};  // taskId -> { full_command, full_output }

    function createModal() {
        if (modal) return modal;

        modal = document.createElement('div');
        modal.id = 'full-text-modal';
        modal.className = 'full-text-modal-overlay';
        modal.style.display = 'none';
        modal.setAttribute('role', 'dialog');
        modal.setAttribute('aria-modal', 'true');
        modal.innerHTML =
            '<div class="full-text-modal-backdrop" onclick="window.FullTextModal.hide()"></div>' +
            '<div class="full-text-modal-content">' +
                '<div class="full-text-modal-header">' +
                    '<span class="full-text-modal-title"></span>' +
                    '<button type="button" class="full-text-modal-close" onclick="window.FullTextModal.hide()" aria-label="Close">&times;</button>' +
                '</div>' +
                '<div class="full-text-modal-body">' +
                    '<pre class="full-text-modal-text"></pre>' +
                '</div>' +
            '</div>';

        document.body.appendChild(modal);

        // Close on Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && modal.style.display !== 'none') {
                window.FullTextModal.hide();
            }
        });

        return modal;
    }

    function show(taskId, type) {
        var m = createModal();
        var titleEl = m.querySelector('.full-text-modal-title');
        var textEl = m.querySelector('.full-text-modal-text');

        var titles = { command: 'Full Command', output: 'Full Output', plan: 'Agent Plan' };
        titleEl.textContent = titles[type] || 'Full Output';
        textEl.textContent = 'Loading...';
        m.style.display = 'flex';

        // Use cache if available
        if (cache[taskId]) {
            var text = type === 'command' ? cache[taskId].full_command
                     : type === 'plan' ? cache[taskId].plan_content
                     : cache[taskId].full_output;
            textEl.textContent = text || 'No content available';
            return;
        }

        fetch('/api/tasks/' + taskId + '/full-text')
            .then(function(response) {
                if (!response.ok) throw new Error('Failed to fetch');
                return response.json();
            })
            .then(function(data) {
                cache[taskId] = data;
                var text = type === 'command' ? data.full_command
                         : type === 'plan' ? data.plan_content
                         : data.full_output;
                textEl.textContent = text || 'No content available';
            })
            .catch(function() {
                textEl.textContent = 'Failed to load content.';
            });
    }

    function hide() {
        if (modal) {
            modal.style.display = 'none';
        }
    }

    window.FullTextModal = {
        show: show,
        hide: hide,
    };
})();
