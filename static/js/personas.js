/**
 * Personas page client for Claude Headspace.
 *
 * Handles persona CRUD operations: list, create, edit, archive, delete.
 * Uses existing ConfirmDialog and Toast utilities.
 */

(function(global) {
    'use strict';

    var API_PERSONAS = '/api/personas';
    var API_ROLES = '/api/roles';
    var API_REGISTER = '/api/personas/register';

    var currentStatus = 'active';

    var PersonasPage = {

        /**
         * Initialize the personas page.
         */
        init: function() {
            this.tbody = document.getElementById('personas-tbody');
            this.tableContainer = document.getElementById('personas-table-container');
            this.emptyState = document.getElementById('personas-empty');
            this.loadingState = document.getElementById('personas-loading');

            this.loadPersonas();
        },

        // --- List ---

        /**
         * Fetch and render persona list.
         */
        loadPersonas: async function() {
            try {
                var response = await fetch(API_PERSONAS);
                var personas = await response.json();

                if (this.loadingState) this.loadingState.classList.add('hidden');

                if (!response.ok) {
                    console.error('PersonasPage: Failed to load personas', personas.error);
                    return;
                }

                if (personas.length === 0) {
                    if (this.tableContainer) this.tableContainer.classList.add('hidden');
                    if (this.emptyState) this.emptyState.classList.remove('hidden');
                    return;
                }

                if (this.tableContainer) this.tableContainer.classList.remove('hidden');
                if (this.emptyState) this.emptyState.classList.add('hidden');

                this._renderTable(personas);
            } catch (error) {
                console.error('PersonasPage: Failed to load personas', error);
                if (this.loadingState) this.loadingState.textContent = 'Failed to load personas.';
            }
        },

        /**
         * Render persona table rows.
         */
        _renderTable: function(personas) {
            if (!this.tbody) return;

            this.tbody.innerHTML = personas.map(function(p) {
                var statusClass = p.status === 'active' ? 'text-green' : 'text-muted';
                var statusLabel = p.status === 'active' ? 'Active' : 'Archived';
                var slug = CHUtils.escapeHtml(p.slug || '');
                var created = p.created_at ? new Date(p.created_at).toLocaleDateString() : '';

                return '<tr class="border-b border-border">' +
                    '<td class="py-3 pr-4 font-medium text-primary">' + CHUtils.escapeHtml(p.name) + '</td>' +
                    '<td class="py-3 pr-4 text-secondary text-sm">' + CHUtils.escapeHtml(p.role || '') + '</td>' +
                    '<td class="py-3 pr-4"><span class="' + statusClass + ' text-sm font-medium">' + statusLabel + '</span></td>' +
                    '<td class="py-3 pr-4 text-center text-secondary">' + p.agent_count + '</td>' +
                    '<td class="py-3 pr-4 text-secondary text-sm">' + CHUtils.escapeHtml(created) + '</td>' +
                    '<td class="py-3 pr-4 text-right">' +
                        '<button onclick="PersonasPage.openEditModal(\'' + slug + '\')" ' +
                            'class="text-cyan text-sm hover:underline mr-3" title="Edit persona">Edit</button>' +
                        (p.status === 'active'
                            ? '<button onclick="PersonasPage.archivePersona(\'' + slug + '\', \'' + CHUtils.escapeHtml(p.name) + '\')" ' +
                                'class="text-amber text-sm hover:underline mr-3" title="Archive persona">Archive</button>'
                            : '<button onclick="PersonasPage.restorePersona(\'' + slug + '\', \'' + CHUtils.escapeHtml(p.name) + '\')" ' +
                                'class="text-green text-sm hover:underline mr-3" title="Restore persona">Restore</button>'
                        ) +
                        '<button onclick="PersonasPage.deletePersona(\'' + slug + '\', \'' + CHUtils.escapeHtml(p.name) + '\', ' + p.agent_count + ')" ' +
                            'class="text-red text-sm hover:underline" title="Delete persona">Delete</button>' +
                    '</td>' +
                '</tr>';
            }).join('');
        },

        // --- Create Modal ---

        /**
         * Open modal in create mode.
         */
        openCreateModal: async function() {
            document.getElementById('persona-form-title').textContent = 'New Persona';
            document.getElementById('persona-form-submit').textContent = 'Create Persona';
            document.getElementById('persona-form-slug').value = '';
            document.getElementById('persona-form-mode').value = 'create';
            document.getElementById('persona-form').reset();
            document.getElementById('persona-form-status-group').classList.add('hidden');
            document.getElementById('persona-form-new-role-group').classList.add('hidden');

            // Enable role dropdown for create mode
            var roleSelect = document.getElementById('persona-form-role');
            roleSelect.disabled = false;
            roleSelect.classList.remove('opacity-50', 'cursor-not-allowed');

            this._hideFormError();
            await this._loadRoleOptions();
            document.getElementById('persona-form-modal').classList.remove('hidden');
            document.addEventListener('keydown', PersonasPage._formModalEscHandler);
            document.getElementById('persona-form-name').focus();
        },

        /**
         * Open modal in edit mode (pre-populated).
         */
        openEditModal: async function(slug) {
            try {
                var response = await fetch(API_PERSONAS + '/' + slug);
                var persona = await response.json();

                if (!response.ok) {
                    console.error('PersonasPage: Failed to fetch persona', persona.error);
                    return;
                }

                document.getElementById('persona-form-title').textContent = 'Edit Persona';
                document.getElementById('persona-form-submit').textContent = 'Update Persona';
                document.getElementById('persona-form-slug').value = persona.slug;
                document.getElementById('persona-form-mode').value = 'edit';
                document.getElementById('persona-form-name').value = persona.name || '';
                document.getElementById('persona-form-description').value = persona.description || '';
                document.getElementById('persona-form-new-role-group').classList.add('hidden');

                // Load roles and set current role (read-only in edit mode)
                await this._loadRoleOptions();
                var roleSelect = document.getElementById('persona-form-role');
                roleSelect.value = persona.role || '';
                roleSelect.disabled = true;
                roleSelect.classList.add('opacity-50', 'cursor-not-allowed');

                // Show status toggle in edit mode
                document.getElementById('persona-form-status-group').classList.remove('hidden');
                currentStatus = persona.status || 'active';
                document.getElementById('persona-form-status').value = currentStatus;
                this._updateStatusButtons(currentStatus);

                this._hideFormError();
                document.getElementById('persona-form-modal').classList.remove('hidden');
                document.addEventListener('keydown', PersonasPage._formModalEscHandler);
                document.getElementById('persona-form-name').focus();
            } catch (error) {
                console.error('PersonasPage: Failed to open edit modal', error);
            }
        },

        /**
         * Close the form modal.
         */
        closeFormModal: function() {
            document.getElementById('persona-form-modal').classList.add('hidden');
            document.removeEventListener('keydown', PersonasPage._formModalEscHandler);
        },

        /**
         * Esc key handler for form modal.
         */
        _formModalEscHandler: function(e) {
            if (e.key === 'Escape') {
                PersonasPage.closeFormModal();
            }
        },

        /**
         * Load role options into the dropdown.
         */
        _loadRoleOptions: async function() {
            var roleSelect = document.getElementById('persona-form-role');
            // Preserve "Create new role..." option
            var currentValue = roleSelect.value;

            try {
                var response = await fetch(API_ROLES);
                if (!response.ok) return;

                var roles = await response.json();

                // Clear all options except first (placeholder) and last ("Create new role...")
                roleSelect.innerHTML = '<option value="">Select a role...</option>';
                roles.forEach(function(r) {
                    var opt = document.createElement('option');
                    opt.value = r.name;
                    opt.textContent = r.name;
                    roleSelect.appendChild(opt);
                });
                var newOpt = document.createElement('option');
                newOpt.value = '__new__';
                newOpt.textContent = 'Create new role...';
                roleSelect.appendChild(newOpt);

                // Restore selection if possible
                if (currentValue && currentValue !== '__new__') {
                    roleSelect.value = currentValue;
                }
            } catch (error) {
                console.error('PersonasPage: Failed to load roles', error);
            }
        },

        /**
         * Handle role dropdown change.
         */
        onRoleChange: function(selectEl) {
            var newRoleGroup = document.getElementById('persona-form-new-role-group');
            if (selectEl.value === '__new__') {
                newRoleGroup.classList.remove('hidden');
                document.getElementById('persona-form-new-role').focus();
            } else {
                newRoleGroup.classList.add('hidden');
                document.getElementById('persona-form-new-role').value = '';
            }
        },

        /**
         * Set status value (for status toggle buttons).
         */
        setStatus: function(status) {
            currentStatus = status;
            document.getElementById('persona-form-status').value = status;
            this._updateStatusButtons(status);
        },

        /**
         * Update status button visual state.
         */
        _updateStatusButtons: function(status) {
            var activeBtn = document.getElementById('persona-form-status-active');
            var archivedBtn = document.getElementById('persona-form-status-archived');

            if (status === 'active') {
                activeBtn.className = 'px-3 py-1 rounded text-sm font-medium border transition-colors bg-green/20 border-green/30 text-green';
                archivedBtn.className = 'px-3 py-1 rounded text-sm font-medium border transition-colors bg-surface border-border text-muted';
            } else {
                activeBtn.className = 'px-3 py-1 rounded text-sm font-medium border transition-colors bg-surface border-border text-muted';
                archivedBtn.className = 'px-3 py-1 rounded text-sm font-medium border transition-colors bg-amber/20 border-amber/30 text-amber';
            }
        },

        /**
         * Submit the form (create or edit).
         */
        submitForm: async function() {
            var mode = document.getElementById('persona-form-mode').value;
            var slug = document.getElementById('persona-form-slug').value;
            var name = document.getElementById('persona-form-name').value.trim();

            if (!name) {
                this._showFormError('Name is required.');
                return;
            }

            if (mode === 'create') {
                await this._submitCreate(name);
            } else {
                await this._submitEdit(slug, name);
            }
        },

        /**
         * Submit create form.
         */
        _submitCreate: async function(name) {
            var roleSelect = document.getElementById('persona-form-role');
            var roleName = roleSelect.value;

            // Handle "Create new role..." option
            if (roleName === '__new__') {
                roleName = document.getElementById('persona-form-new-role').value.trim();
            }

            if (!roleName) {
                this._showFormError('Role is required.');
                return;
            }

            var description = document.getElementById('persona-form-description').value.trim() || null;

            var payload = {
                name: name,
                role: roleName,
                description: description
            };

            try {
                var response = await CHUtils.apiFetch(API_REGISTER, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                var data = await response.json();

                if (!response.ok) {
                    this._showFormError(data.error || 'Failed to create persona.');
                    return;
                }

                this.closeFormModal();
                this.loadPersonas();

                if (window.Toast) {
                    window.Toast.success('Persona created', 'Created persona "' + name + '"');
                }
            } catch (error) {
                console.error('PersonasPage: Create failed', error);
                this._showFormError('Network error. Please try again.');
            }
        },

        /**
         * Submit edit form.
         */
        _submitEdit: async function(slug, name) {
            var description = document.getElementById('persona-form-description').value.trim() || null;
            var status = document.getElementById('persona-form-status').value;

            var payload = {
                name: name,
                description: description,
                status: status
            };

            try {
                var response = await CHUtils.apiFetch(API_PERSONAS + '/' + slug, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });

                var data = await response.json();

                if (!response.ok) {
                    this._showFormError(data.error || 'Failed to update persona.');
                    return;
                }

                this.closeFormModal();
                this.loadPersonas();

                if (window.Toast) {
                    window.Toast.success('Persona updated', 'Updated persona "' + name + '"');
                }
            } catch (error) {
                console.error('PersonasPage: Update failed', error);
                this._showFormError('Network error. Please try again.');
            }
        },

        // --- Actions ---

        /**
         * Archive a persona with confirmation.
         */
        archivePersona: async function(slug, name) {
            var ok = await ConfirmDialog.show(
                'Archive Persona',
                'Are you sure you want to archive "' + name + '"? The persona will no longer be available for new agent assignments.',
                {
                    confirmText: 'Archive',
                    confirmClass: 'bg-amber hover:bg-amber/90'
                }
            );

            if (!ok) return;

            try {
                var response = await CHUtils.apiFetch(API_PERSONAS + '/' + slug, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'archived' })
                });

                if (response.ok) {
                    this.loadPersonas();
                    if (window.Toast) {
                        window.Toast.success('Persona archived', '"' + name + '" has been archived.');
                    }
                } else {
                    var data = await response.json();
                    if (window.Toast) {
                        window.Toast.error('Archive failed', data.error || 'Could not archive persona.');
                    }
                }
            } catch (error) {
                console.error('PersonasPage: Archive failed', error);
                if (window.Toast) {
                    window.Toast.error('Archive failed', 'Network error.');
                }
            }
        },

        /**
         * Restore an archived persona.
         */
        restorePersona: async function(slug, name) {
            try {
                var response = await CHUtils.apiFetch(API_PERSONAS + '/' + slug, {
                    method: 'PUT',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: 'active' })
                });

                if (response.ok) {
                    this.loadPersonas();
                    if (window.Toast) {
                        window.Toast.success('Persona restored', '"' + name + '" is now active.');
                    }
                } else {
                    var data = await response.json();
                    if (window.Toast) {
                        window.Toast.error('Restore failed', data.error || 'Could not restore persona.');
                    }
                }
            } catch (error) {
                console.error('PersonasPage: Restore failed', error);
                if (window.Toast) {
                    window.Toast.error('Restore failed', 'Network error.');
                }
            }
        },

        /**
         * Delete a persona with confirmation.
         */
        deletePersona: async function(slug, name, agentCount) {
            if (agentCount > 0) {
                if (window.Toast) {
                    window.Toast.error(
                        'Cannot delete',
                        '"' + name + '" has ' + agentCount + ' linked agent(s). Remove agent links first.'
                    );
                }
                return;
            }

            var ok = await ConfirmDialog.show(
                'Delete Persona',
                'Are you sure you want to permanently delete "' + name + '"? This action cannot be undone.',
                {
                    confirmText: 'Delete',
                    confirmClass: 'bg-red hover:bg-red/90'
                }
            );

            if (!ok) return;

            try {
                var response = await CHUtils.apiFetch(API_PERSONAS + '/' + slug, {
                    method: 'DELETE'
                });

                if (response.ok) {
                    this.loadPersonas();
                    if (window.Toast) {
                        window.Toast.success('Persona deleted', '"' + name + '" has been permanently deleted.');
                    }
                } else {
                    var data = await response.json();
                    if (window.Toast) {
                        window.Toast.error('Delete failed', data.error || 'Could not delete persona.');
                    }
                }
            } catch (error) {
                console.error('PersonasPage: Delete failed', error);
                if (window.Toast) {
                    window.Toast.error('Delete failed', 'Network error.');
                }
            }
        },

        // --- Error display ---

        _showFormError: function(message) {
            var el = document.getElementById('persona-form-error');
            if (el) {
                el.textContent = message;
                el.classList.remove('hidden');
            }
        },

        _hideFormError: function() {
            var el = document.getElementById('persona-form-error');
            if (el) {
                el.textContent = '';
                el.classList.add('hidden');
            }
        }
    };

    // Initialize on DOM ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { PersonasPage.init(); });
    } else {
        PersonasPage.init();
    }

    global.PersonasPage = PersonasPage;

})(typeof window !== 'undefined' ? window : this);
