/**
 * Reusable custom confirm dialog component.
 *
 * Replaces native window.confirm() with a styled modal that:
 * - Doesn't get dismissed by SSE-triggered page reloads
 * - Returns a Promise<boolean> (true = confirm, false = cancel)
 * - Exposes isOpen() for SSE reload gating
 * - Defers SSE reloads via window._sseReloadDeferred and executes on close
 *
 * Usage:
 *   const ok = await ConfirmDialog.show('Title', 'Message');
 *   const ok = await ConfirmDialog.show('Title', 'Message', {
 *     confirmText: 'Delete',
 *     cancelText: 'Keep',
 *     confirmClass: 'bg-red hover:bg-red/90'
 *   });
 */
(function(global) {
    'use strict';

    var dialogEl = null;
    var open = false;
    var resolver = null;

    function ensureDOM() {
        if (dialogEl) return;

        dialogEl = document.createElement('div');
        dialogEl.id = 'confirm-dialog';
        dialogEl.className = 'fixed inset-0 z-[220] hidden';
        dialogEl.style.cssText = 'position:fixed;top:0;right:0;bottom:0;left:0;z-index:220;display:none';
        dialogEl.setAttribute('role', 'alertdialog');
        dialogEl.setAttribute('aria-modal', 'true');
        dialogEl.setAttribute('aria-labelledby', 'confirm-dialog-title');
        dialogEl.setAttribute('aria-describedby', 'confirm-dialog-message');

        dialogEl.innerHTML =
            '<div class="absolute inset-0 bg-black/60 backdrop-blur-sm" data-confirm-backdrop ' +
                'style="position:absolute;top:0;right:0;bottom:0;left:0;background:rgba(0,0,0,0.6);backdrop-filter:blur(4px)"></div>' +
            '<div class="absolute inset-0 flex items-start justify-center pt-16 px-4" ' +
                'style="position:absolute;top:0;right:0;bottom:0;left:0;display:flex;align-items:flex-start;justify-content:center;padding-top:64px;padding-left:16px;padding-right:16px">' +
                '<div class="bg-surface border border-border rounded-lg p-6 max-w-md w-full shadow-lg" ' +
                    'style="max-width:28rem;width:100%">' +
                    '<h3 id="confirm-dialog-title" class="text-lg font-semibold text-primary mb-2"></h3>' +
                    '<p id="confirm-dialog-message" class="text-secondary text-sm mb-6"></p>' +
                    '<div class="flex items-center justify-end gap-3">' +
                        '<button type="button" data-confirm-cancel ' +
                            'class="px-4 py-2 bg-surface border border-border text-secondary font-medium rounded hover:bg-hover hover:text-primary transition-colors">' +
                            'Cancel' +
                        '</button>' +
                        '<button type="button" data-confirm-ok ' +
                            'class="px-4 py-2 font-medium rounded transition-colors text-void">' +
                            'Confirm' +
                        '</button>' +
                    '</div>' +
                '</div>' +
            '</div>';

        document.body.appendChild(dialogEl);

        // Backdrop click -> cancel
        dialogEl.querySelector('[data-confirm-backdrop]').addEventListener('click', function() {
            resolve(false);
        });

        // Button clicks
        dialogEl.querySelector('[data-confirm-cancel]').addEventListener('click', function() {
            resolve(false);
        });
        dialogEl.querySelector('[data-confirm-ok]').addEventListener('click', function() {
            resolve(true);
        });

        // Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape' && open) {
                e.stopPropagation();
                resolve(false);
            }
        });
    }

    function resolve(value) {
        if (!open) return;
        open = false;
        dialogEl.classList.add('hidden');
        dialogEl.style.display = 'none';

        if (resolver) {
            var fn = resolver;
            resolver = null;
            fn(value);
        }

        // Execute any deferred SSE reload — but only on cancel.
        // When the user confirms, the .then() callback hasn't run yet
        // (Promise microtask). Firing the deferred reload now would
        // reload the page before the action (shutdown/dismiss) starts.
        if (global._sseReloadDeferred) {
            if (value) {
                // Confirmed — discard the deferred reload. The confirmed
                // action will produce its own SSE events to update state.
                global._sseReloadDeferred = null;
            } else {
                // Cancelled — execute the deferred reload now.
                var deferred = global._sseReloadDeferred;
                global._sseReloadDeferred = null;
                deferred();
            }
        }
    }

    global.ConfirmDialog = {
        /**
         * Show a confirm dialog.
         * @param {string} title - Dialog title
         * @param {string} message - Dialog message
         * @param {object} [opts] - Options
         * @param {string} [opts.confirmText='Confirm'] - Confirm button text
         * @param {string} [opts.cancelText='Cancel'] - Cancel button text
         * @param {string} [opts.confirmClass='bg-cyan hover:bg-cyan/90'] - Confirm button class
         * @returns {Promise<boolean>} true if confirmed, false if cancelled
         */
        show: function(title, message, opts) {
            ensureDOM();

            opts = opts || {};
            var confirmText = opts.confirmText || 'Confirm';
            var cancelText = opts.cancelText || 'Cancel';
            var confirmClass = opts.confirmClass || 'bg-cyan hover:bg-cyan/90';

            // Set content (titleHTML overrides plain-text title for styled content)
            var titleEl = dialogEl.querySelector('#confirm-dialog-title');
            if (opts.titleHTML) {
                titleEl.innerHTML = opts.titleHTML;
            } else {
                titleEl.textContent = title;
            }
            dialogEl.querySelector('#confirm-dialog-message').textContent = message;

            var cancelBtn = dialogEl.querySelector('[data-confirm-cancel]');
            cancelBtn.textContent = cancelText;

            var okBtn = dialogEl.querySelector('[data-confirm-ok]');
            okBtn.textContent = confirmText;
            // Reset and apply confirm button class
            okBtn.className = 'px-4 py-2 font-medium rounded transition-colors text-void ' + confirmClass;

            // Show
            dialogEl.classList.remove('hidden');
            dialogEl.style.display = '';
            open = true;

            // Focus the confirm button so Enter fires the action
            okBtn.focus();

            return new Promise(function(res) {
                resolver = res;
            });
        },

        /**
         * Check if a confirm dialog is currently open.
         * Used by SSE reload gating.
         * @returns {boolean}
         */
        isOpen: function() {
            return open;
        }
    };

})(typeof window !== 'undefined' ? window : this);
