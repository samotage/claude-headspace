/**
 * Inference log page client for Claude Headspace.
 *
 * Handles filtering, pagination, and row expansion for inference call records.
 */

(function (global) {
  "use strict";

  const CALLS_API = "/api/inference/calls";
  const FILTERS_API = "/api/inference/calls/filters";
  const PER_PAGE = 50;

  /**
   * Inference log page controller
   */
  const InferenceLogPage = {
    currentPage: 1,
    totalPages: 0,
    expandedCallIds: new Set(),
    sseClient: null,
    _fetchController: null,
    filters: {
      search: null,
      level: null,
      model: null,
      project_id: null,
      agent_id: null,
      cached: null,
    },
    _searchDebounceTimer: null,

    /**
     * Initialize the inference log page
     */
    init: function () {
      this.searchFilter = document.getElementById("filter-search");
      this.levelFilter = document.getElementById("filter-level");
      this.modelFilter = document.getElementById("filter-model");
      this.projectFilter = document.getElementById("filter-project");
      this.agentFilter = document.getElementById("filter-agent");
      this.cachedFilter = document.getElementById("filter-cached");
      this.clearFiltersBtn = document.getElementById("clear-filters-btn");
      this.tableBody = document.getElementById("inference-table-body");
      this.emptyState = document.getElementById("empty-state");
      this.noResultsState = document.getElementById("no-results-state");
      this.errorState = document.getElementById("error-state");
      this.loadingState = document.getElementById("loading-state");
      this.paginationControls = document.getElementById("pagination-controls");
      this.prevPageBtn = document.getElementById("prev-page-btn");
      this.nextPageBtn = document.getElementById("next-page-btn");
      this.pageIndicator = document.getElementById("page-indicator");
      this.clearLogsBtn = document.getElementById("clear-logs-btn");
      this.clearLogsConfirm = document.getElementById("clear-logs-confirm");
      this.clearLogsYes = document.getElementById("clear-logs-yes");
      this.clearLogsCancel = document.getElementById("clear-logs-cancel");

      if (this.searchFilter) {
        this.searchFilter.addEventListener("input", () => {
          clearTimeout(this._searchDebounceTimer);
          this._searchDebounceTimer = setTimeout(() => {
            this._handleFilterChange();
          }, 300);
        });
      }
      if (this.levelFilter) {
        this.levelFilter.addEventListener("change", () =>
          this._handleFilterChange()
        );
      }
      if (this.modelFilter) {
        this.modelFilter.addEventListener("change", () =>
          this._handleFilterChange()
        );
      }
      if (this.projectFilter) {
        this.projectFilter.addEventListener("change", () =>
          this._handleFilterChange()
        );
      }
      if (this.agentFilter) {
        this.agentFilter.addEventListener("change", () =>
          this._handleFilterChange()
        );
      }
      if (this.cachedFilter) {
        this.cachedFilter.addEventListener("change", () =>
          this._handleFilterChange()
        );
      }
      if (this.clearFiltersBtn) {
        this.clearFiltersBtn.addEventListener("click", () =>
          this._clearFilters()
        );
      }
      if (this.clearLogsBtn) {
        this.clearLogsBtn.addEventListener("click", () =>
          this._showClearConfirm()
        );
      }
      if (this.clearLogsYes) {
        this.clearLogsYes.addEventListener("click", () =>
          this._clearAllLogs()
        );
      }
      if (this.clearLogsCancel) {
        this.clearLogsCancel.addEventListener("click", () =>
          this._hideClearConfirm()
        );
      }
      if (this.prevPageBtn) {
        this.prevPageBtn.addEventListener("click", () => this._prevPage());
      }
      if (this.nextPageBtn) {
        this.nextPageBtn.addEventListener("click", () => this._nextPage());
      }

      this._initSSE();
      this._loadFilters();
      this._loadCalls();
    },

    /**
     * Initialize SSE client for real-time updates.
     * Uses the shared SSE connection from header-sse.js (window.headerSSEClient).
     */
    _initSSE: function () {
      var client = window.headerSSEClient;
      if (!client) {
        console.warn("Shared SSE client not available (headerSSEClient)");
        return;
      }

      this.sseClient = client;

      client.on("inference_call", function (data) {
        this._handleSSEEvent(data);
      }.bind(this));
    },

    /**
     * Handle SSE inference_call event
     */
    _handleSSEEvent: function (data) {
      // Search is server-side only; reload from API when active
      if (this.filters.search) {
        if (this.currentPage === 1) {
          this._loadCalls();
        }
        return;
      }

      if (!this._eventMatchesFilters(data)) {
        return;
      }

      if (this.currentPage !== 1) {
        return;
      }

      this._prependCall(data);
    },

    /**
     * Check if an inference call event matches current filters
     */
    _eventMatchesFilters: function (call) {
      if (this.filters.level && call.level !== this.filters.level) {
        return false;
      }
      if (this.filters.model && call.model !== this.filters.model) {
        return false;
      }
      if (this.filters.project_id && call.project_id !== parseInt(this.filters.project_id)) {
        return false;
      }
      if (this.filters.agent_id && call.agent_id !== parseInt(this.filters.agent_id)) {
        return false;
      }
      if (this.filters.cached) {
        var wantCached = this.filters.cached === "true";
        if (call.cached !== wantCached) {
          return false;
        }
      }
      return true;
    },

    /**
     * Prepend a new inference call to the table with animation
     */
    _prependCall: function (call) {
      if (!this.tableBody) return;

      this._hideStates();
      if (this.paginationControls) this.paginationControls.classList.remove("hidden");

      var row = this._createCallRow(call);
      row.classList.add("event-new");

      if (this.tableBody.firstChild) {
        this.tableBody.insertBefore(row, this.tableBody.firstChild);
        if (row._snippetRow) {
          row.after(row._snippetRow);
        }
      } else {
        this.tableBody.appendChild(row);
        if (row._snippetRow) {
          this.tableBody.appendChild(row._snippetRow);
        }
      }

      setTimeout(function () {
        row.classList.remove("event-new");
      }, 2000);
    },

    /**
     * Load filter options from API
     */
    _loadFilters: async function () {
      try {
        const response = await fetch(FILTERS_API);
        const data = await response.json();

        if (response.ok) {
          this._populateFilterDropdowns(data);
        }
      } catch (error) {
        console.error("Failed to load filters:", error);
      }
    },

    /**
     * Populate filter dropdowns with options
     */
    _populateFilterDropdowns: function (data) {
      if (this.levelFilter && data.levels) {
        const currentValue = this.levelFilter.value;
        this.levelFilter.innerHTML = '<option value="">All Levels</option>';
        data.levels.forEach(function (level) {
          var option = document.createElement("option");
          option.value = level;
          option.textContent = level;
          this.levelFilter.appendChild(option);
        }.bind(this));
        this.levelFilter.value = currentValue;
      }

      if (this.modelFilter && data.models) {
        const currentValue = this.modelFilter.value;
        this.modelFilter.innerHTML = '<option value="">All Models</option>';
        data.models.forEach(function (model) {
          var option = document.createElement("option");
          option.value = model;
          option.textContent = model;
          this.modelFilter.appendChild(option);
        }.bind(this));
        this.modelFilter.value = currentValue;
      }

      if (this.projectFilter && data.projects) {
        const currentValue = this.projectFilter.value;
        this.projectFilter.innerHTML = '<option value="">All Projects</option>';
        data.projects.forEach(function (project) {
          var option = document.createElement("option");
          option.value = project.id;
          option.textContent = project.name;
          this.projectFilter.appendChild(option);
        }.bind(this));
        this.projectFilter.value = currentValue;
      }

      if (this.agentFilter && data.agents) {
        const currentValue = this.agentFilter.value;
        this.agentFilter.innerHTML = '<option value="">All Agents</option>';
        data.agents.forEach(function (agent) {
          var option = document.createElement("option");
          option.value = agent.id;
          var prefix = agent.is_active ? "\u25CF " : "";
          var uuid8 = agent.session_uuid.substring(0, 8);
          option.textContent = prefix + uuid8.substring(0, 2) + " - " + uuid8;
          this.agentFilter.appendChild(option);
        }.bind(this));
        this.agentFilter.value = currentValue;
      }
    },

    /**
     * Handle filter change
     */
    _handleFilterChange: function () {
      this.filters.search = this.searchFilter ? this.searchFilter.value : null;
      this.filters.level = this.levelFilter ? this.levelFilter.value : null;
      this.filters.model = this.modelFilter ? this.modelFilter.value : null;
      this.filters.project_id = this.projectFilter ? this.projectFilter.value : null;
      this.filters.agent_id = this.agentFilter ? this.agentFilter.value : null;
      this.filters.cached = this.cachedFilter ? this.cachedFilter.value : null;

      this.currentPage = 1;
      this._loadCalls();
    },

    /**
     * Show inline confirmation for clearing logs
     */
    _showClearConfirm: function () {
      if (this.clearLogsBtn) this.clearLogsBtn.classList.add("hidden");
      if (this.clearLogsConfirm) this.clearLogsConfirm.classList.remove("hidden");
    },

    /**
     * Hide inline confirmation for clearing logs
     */
    _hideClearConfirm: function () {
      if (this.clearLogsBtn) this.clearLogsBtn.classList.remove("hidden");
      if (this.clearLogsConfirm) this.clearLogsConfirm.classList.add("hidden");
    },

    /**
     * Clear all inference logs
     */
    _clearAllLogs: async function () {
      this._hideClearConfirm();

      try {
        const response = await CHUtils.apiFetch(CALLS_API, { method: "DELETE", headers: { "X-Confirm-Destructive": "true" } });
        if (response.ok) {
          this.currentPage = 1;
          this._loadFilters();
          this._loadCalls();
        } else {
          this._showError();
        }
      } catch (error) {
        console.error("Failed to clear inference logs:", error);
        this._showError();
      }
    },

    /**
     * Clear all filters
     */
    _clearFilters: function () {
      if (this.searchFilter) this.searchFilter.value = "";
      if (this.levelFilter) this.levelFilter.value = "";
      if (this.modelFilter) this.modelFilter.value = "";
      if (this.projectFilter) this.projectFilter.value = "";
      if (this.agentFilter) this.agentFilter.value = "";
      if (this.cachedFilter) this.cachedFilter.value = "";

      this.filters = {
        search: null,
        level: null,
        model: null,
        project_id: null,
        agent_id: null,
        cached: null,
      };

      this.currentPage = 1;
      this._loadCalls();
    },

    /**
     * Load inference calls from API
     */
    _loadCalls: async function () {
      this._showLoading();

      // Abort any in-flight filter fetch to prevent race conditions (M14)
      if (this._fetchController) this._fetchController.abort();
      this._fetchController = new AbortController();

      try {
        const url = new URL(CALLS_API, window.location.origin);
        url.searchParams.set("page", this.currentPage);
        url.searchParams.set("per_page", PER_PAGE);

        if (this.filters.search) {
          url.searchParams.set("search", this.filters.search);
        }
        if (this.filters.level) {
          url.searchParams.set("level", this.filters.level);
        }
        if (this.filters.model) {
          url.searchParams.set("model", this.filters.model);
        }
        if (this.filters.project_id) {
          url.searchParams.set("project_id", this.filters.project_id);
        }
        if (this.filters.agent_id) {
          url.searchParams.set("agent_id", this.filters.agent_id);
        }
        if (this.filters.cached) {
          url.searchParams.set("cached", this.filters.cached);
        }

        const response = await fetch(url, { signal: this._fetchController.signal });
        const data = await response.json();

        if (response.ok) {
          this._renderCalls(data);
        } else {
          this._showError();
        }
      } catch (error) {
        if (error.name === 'AbortError') return; // Superseded by newer request
        console.error("Failed to load inference calls:", error);
        this._showError();
      }
    },

    /**
     * Render inference calls in the table
     */
    _renderCalls: function (data) {
      this._hideStates();

      if (!data.calls || data.calls.length === 0) {
        if (
          this.filters.search ||
          this.filters.level ||
          this.filters.model ||
          this.filters.project_id ||
          this.filters.agent_id ||
          this.filters.cached
        ) {
          this._showNoResults();
        } else {
          this._showEmpty();
        }
        return;
      }

      if (this.tableBody) {
        this.tableBody.innerHTML = "";
        data.calls.forEach(function (call) {
          var row = this._createCallRow(call);
          this.tableBody.appendChild(row);
          if (row._snippetRow) {
            this.tableBody.appendChild(row._snippetRow);
          }
        }.bind(this));
      }

      this.totalPages = data.pages;
      this._updatePagination(data);
    },

    /**
     * Create a table row for an inference call
     */
    _createCallRow: function (call) {
      var row = document.createElement("tr");
      row.className = "hover:bg-hover cursor-pointer transition-colors";
      row.dataset.callId = call.id;

      // Timestamp
      var tsCell = document.createElement("td");
      tsCell.className = "px-4 py-3 text-sm text-primary whitespace-nowrap";
      tsCell.textContent = this._formatTimestamp(call.timestamp);
      row.appendChild(tsCell);

      // Agent
      var agentCell = document.createElement("td");
      agentCell.className = "px-4 py-3 text-sm text-secondary font-mono";
      if (call.agent_session) {
        var uuid8 = call.agent_session.substring(0, 8);
        var heroSpan = document.createElement("span");
        heroSpan.className = "agent-hero";
        heroSpan.textContent = uuid8.substring(0, 2);
        var trailSpan = document.createElement("span");
        trailSpan.className = "agent-hero-trail";
        trailSpan.textContent = uuid8.substring(2);
        agentCell.appendChild(heroSpan);
        agentCell.appendChild(trailSpan);
      } else {
        agentCell.textContent = "-";
      }
      row.appendChild(agentCell);

      // Level
      var levelCell = document.createElement("td");
      levelCell.className = "px-4 py-3 text-sm";
      var levelBadge = document.createElement("span");
      levelBadge.className = this._getLevelBadgeClass(call.level);
      levelBadge.textContent = call.level;
      levelCell.appendChild(levelBadge);
      row.appendChild(levelCell);

      // Model
      var modelCell = document.createElement("td");
      modelCell.className = "px-4 py-3 text-sm text-secondary font-mono";
      modelCell.textContent = call.model || "-";
      row.appendChild(modelCell);

      // Purpose
      var purposeCell = document.createElement("td");
      purposeCell.className = "px-4 py-3 text-sm text-secondary truncate max-w-xs";
      purposeCell.textContent = call.purpose || "-";
      row.appendChild(purposeCell);

      // Tokens (in / out)
      var tokensCell = document.createElement("td");
      tokensCell.className = "px-4 py-3 text-sm text-secondary whitespace-nowrap";
      tokensCell.textContent = this._formatTokens(call.input_tokens, call.output_tokens);
      row.appendChild(tokensCell);

      // Latency
      var latencyCell = document.createElement("td");
      latencyCell.className = "px-4 py-3 text-sm text-secondary whitespace-nowrap";
      latencyCell.textContent = call.latency_ms != null ? call.latency_ms + "ms" : "-";
      row.appendChild(latencyCell);

      // Cost
      var costCell = document.createElement("td");
      costCell.className = "px-4 py-3 text-sm text-secondary whitespace-nowrap";
      costCell.textContent = this._formatCost(call.cost);
      row.appendChild(costCell);

      // Status
      var statusCell = document.createElement("td");
      statusCell.className = "px-4 py-3 text-sm";
      var statusBadge = document.createElement("span");
      statusBadge.className = this._getStatusBadgeClass(call);
      statusBadge.textContent = this._getStatusText(call);
      statusCell.appendChild(statusBadge);
      row.appendChild(statusCell);

      row.addEventListener("click", function () {
        this._toggleCallDetails(call, row);
      }.bind(this));

      // Add match snippet row when search is active
      var snippet = this._getMatchSnippet(call);
      if (snippet) {
        var snippetRow = document.createElement("tr");
        snippetRow.className = "snippet-row";
        snippetRow.addEventListener("click", function () {
          this._toggleCallDetails(call, row);
        }.bind(this));
        var snippetCell = document.createElement("td");
        snippetCell.colSpan = 9;
        snippetCell.className = "px-4 pb-2 pt-0 text-xs cursor-pointer";

        var snippetLabel = document.createElement("span");
        snippetLabel.className = "text-muted";
        snippetLabel.textContent = "match in " + snippet.label + ": ";
        snippetCell.appendChild(snippetLabel);

        var snippetText = document.createElement("span");
        snippetText.className = "text-secondary font-mono";
        this._setTextWithHighlight(snippetText, snippet.snippet);
        snippetCell.appendChild(snippetText);

        snippetRow.appendChild(snippetCell);
        row._snippetRow = snippetRow;
      }

      return row;
    },

    /**
     * Get CSS class for level badge
     */
    _getLevelBadgeClass: function (level) {
      var baseClass = "px-2 py-1 rounded text-xs font-medium";
      switch (level) {
        case "turn":
          return baseClass + " bg-blue/20 text-blue";
        case "task":
          return baseClass + " bg-cyan/20 text-cyan";
        case "project":
          return baseClass + " bg-amber/20 text-amber";
        case "objective":
          return baseClass + " bg-green/20 text-green";
        default:
          return baseClass + " bg-surface text-secondary";
      }
    },

    /**
     * Get CSS class for status badge
     */
    _getStatusBadgeClass: function (call) {
      var baseClass = "px-2 py-1 rounded text-xs font-medium";
      if (call.error_message) {
        return baseClass + " bg-red/20 text-red";
      }
      if (call.cached) {
        return baseClass + " bg-green/20 text-green";
      }
      return baseClass + " bg-surface text-secondary";
    },

    /**
     * Get status text for a call
     */
    _getStatusText: function (call) {
      if (call.error_message) return "error";
      if (call.cached) return "cached";
      return "ok";
    },

    /**
     * Format tokens display
     */
    _formatTokens: function (input, output) {
      if (input == null && output == null) return "-";
      var inStr = input != null ? input.toLocaleString() : "?";
      var outStr = output != null ? output.toLocaleString() : "?";
      return inStr + " / " + outStr;
    },

    /**
     * Format cost display
     */
    _formatCost: function (cost) {
      if (cost == null) return "-";
      return "$" + cost.toFixed(4);
    },

    /**
     * Format timestamp for display
     */
    _formatTimestamp: function (isoString) {
      if (!isoString) return "-";
      var date = new Date(isoString);
      if (isNaN(date.getTime())) return isoString;
      return date.toLocaleString("en-US", {
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hour12: false,
      });
    },

    /**
     * Pretty-print text: if it looks like JSON, format it nicely.
     * Otherwise return the text as-is.
     */
    _prettyPrint: function (text) {
      if (!text) return text;
      var trimmed = text.trim();
      if ((trimmed.startsWith("{") && trimmed.endsWith("}")) ||
          (trimmed.startsWith("[") && trimmed.endsWith("]"))) {
        try {
          var parsed = JSON.parse(trimmed);
          return JSON.stringify(parsed, null, 2);
        } catch (e) {
          // Not valid JSON, return as-is
        }
      }
      return text;
    },

    /**
     * Set text content with optional search term highlighting.
     * When search is active, uses innerHTML with <mark> tags.
     * Otherwise uses textContent for safety.
     */
    _setTextWithHighlight: function (element, text) {
      if (!this.filters.search || !text) {
        element.textContent = text || "";
        return;
      }
      var escaped = CHUtils.escapeHtml(text);
      var searchTerm = this.filters.search;
      var escapedTerm = CHUtils.escapeHtml(searchTerm);
      var regex = new RegExp("(" + escapedTerm.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")", "gi");
      element.innerHTML = escaped.replace(regex, '<mark class="bg-amber/40 text-primary rounded px-0.5">$1</mark>');

      // Scroll first highlight into view within the container
      var firstMark = element.querySelector("mark");
      if (firstMark) {
        setTimeout(function () {
          firstMark.scrollIntoView({ block: "center", behavior: "smooth" });
        }, 50);
      }
    },

    /**
     * Extract a short context snippet around the first match of the search term
     */
    _getMatchSnippet: function (call) {
      if (!this.filters.search) return null;
      var term = this.filters.search.toLowerCase();
      var fields = [
        { label: "prompt", text: call.input_text },
        { label: "response", text: call.result_text },
        { label: "purpose", text: call.purpose },
      ];
      for (var i = 0; i < fields.length; i++) {
        var text = fields[i].text;
        if (!text) continue;
        var idx = text.toLowerCase().indexOf(term);
        if (idx !== -1) {
          var start = Math.max(0, idx - 40);
          var end = Math.min(text.length, idx + term.length + 40);
          var snippet = (start > 0 ? "\u2026" : "") + text.substring(start, end) + (end < text.length ? "\u2026" : "");
          return { label: fields[i].label, snippet: snippet };
        }
      }
      return null;
    },

    /**
     * Toggle inference call details expansion
     */
    _toggleCallDetails: function (call, row) {
      var callId = call.id;

      // If already expanded, collapse it
      if (this.expandedCallIds.has(callId)) {
        this.expandedCallIds.delete(callId);
        row.classList.remove("bg-surface");
        var existingDetailRow = row.nextElementSibling;
        if (existingDetailRow && existingDetailRow.classList.contains("call-detail-row")) {
          existingDetailRow.remove();
        }
        return;
      }

      // Expand this row
      this.expandedCallIds.add(callId);
      row.classList.add("bg-surface");

      var detailRow = document.createElement("tr");
      detailRow.className = "call-detail-row";
      var detailCell = document.createElement("td");
      detailCell.colSpan = 9;
      detailCell.className = "px-4 py-4 bg-deep border-t border-b border-border";

      var content = document.createElement("div");
      content.className = "space-y-3";

      // Error message
      if (call.error_message) {
        var errorDiv = document.createElement("div");
        errorDiv.className = "text-sm";
        var errorLabel = document.createElement("span");
        errorLabel.className = "text-red font-medium";
        errorLabel.textContent = "Error: ";
        errorDiv.appendChild(errorLabel);
        var errorText = document.createElement("span");
        errorText.className = "text-red/80";
        errorText.textContent = call.error_message;
        errorDiv.appendChild(errorText);
        content.appendChild(errorDiv);
      }

      // Prompt (input_text)
      if (call.input_text) {
        var promptDiv = document.createElement("div");
        var promptLabel = document.createElement("div");
        promptLabel.className = "text-sm text-secondary font-medium mb-1";
        promptLabel.textContent = "Prompt:";
        promptDiv.appendChild(promptLabel);
        var promptPre = document.createElement("pre");
        promptPre.className = "text-sm text-primary font-mono overflow-x-auto bg-surface rounded p-3 max-h-64 overflow-y-auto whitespace-pre-wrap";
        this._setTextWithHighlight(promptPre, this._prettyPrint(call.input_text));
        promptDiv.appendChild(promptPre);
        content.appendChild(promptDiv);
      }

      // Response (result_text)
      if (call.result_text) {
        var resultDiv = document.createElement("div");
        var resultLabel = document.createElement("div");
        resultLabel.className = "text-sm text-secondary font-medium mb-1";
        resultLabel.textContent = "Response:";
        resultDiv.appendChild(resultLabel);
        var resultPre = document.createElement("pre");
        resultPre.className = "text-sm text-primary font-mono overflow-x-auto bg-surface rounded p-3 max-h-64 overflow-y-auto whitespace-pre-wrap";
        this._setTextWithHighlight(resultPre, this._prettyPrint(call.result_text));
        resultDiv.appendChild(resultPre);
        content.appendChild(resultDiv);
      }

      // Metadata
      var metaDiv = document.createElement("div");
      metaDiv.className = "text-sm text-muted";
      var parts = [];
      if (call.project_name) parts.push("Project: " + call.project_name);
      if (call.agent_session) {
        var uuid8m = call.agent_session.substring(0, 8);
        parts.push("Agent: " + uuid8m.substring(0, 2) + " - " + uuid8m);
      }
      else if (call.agent_id) parts.push("Agent ID: " + call.agent_id);
      if (parts.length > 0) {
        metaDiv.textContent = parts.join(" | ");
        content.appendChild(metaDiv);
      }

      if (!call.error_message && !call.input_text && !call.result_text && parts.length === 0) {
        var noData = document.createElement("p");
        noData.className = "text-sm text-muted";
        noData.textContent = "No additional details available.";
        content.appendChild(noData);
      }

      detailCell.appendChild(content);
      detailRow.appendChild(detailCell);
      row.after(detailRow);
    },

    /**
     * Update pagination controls
     */
    _updatePagination: function (data) {
      if (!this.paginationControls) return;

      this.paginationControls.classList.remove("hidden");

      if (this.pageIndicator) {
        this.pageIndicator.textContent = "Page " + data.page + " of " + (data.pages || 1);
      }

      if (this.prevPageBtn) {
        this.prevPageBtn.disabled = !data.has_previous;
      }
      if (this.nextPageBtn) {
        this.nextPageBtn.disabled = !data.has_next;
      }
    },

    /**
     * Go to previous page
     */
    _prevPage: function () {
      if (this.currentPage > 1) {
        this.currentPage--;
        this._loadCalls();
      }
    },

    /**
     * Go to next page
     */
    _nextPage: function () {
      if (this.currentPage < this.totalPages) {
        this.currentPage++;
        this._loadCalls();
      }
    },

    /**
     * Hide all states
     */
    _hideStates: function () {
      if (this.loadingState) this.loadingState.classList.add("hidden");
      if (this.emptyState) this.emptyState.classList.add("hidden");
      if (this.noResultsState) this.noResultsState.classList.add("hidden");
      if (this.errorState) this.errorState.classList.add("hidden");
      if (this.paginationControls) this.paginationControls.classList.add("hidden");
      if (this.tableBody) this.tableBody.classList.remove("hidden");
    },

    /**
     * Show loading state
     */
    _showLoading: function () {
      if (this.loadingState) this.loadingState.classList.remove("hidden");
      if (this.emptyState) this.emptyState.classList.add("hidden");
      if (this.noResultsState) this.noResultsState.classList.add("hidden");
      if (this.errorState) this.errorState.classList.add("hidden");
      if (this.paginationControls) this.paginationControls.classList.add("hidden");
      if (this.tableBody) this.tableBody.innerHTML = "";
    },

    /**
     * Show empty state
     */
    _showEmpty: function () {
      if (this.loadingState) this.loadingState.classList.add("hidden");
      if (this.emptyState) this.emptyState.classList.remove("hidden");
      if (this.noResultsState) this.noResultsState.classList.add("hidden");
      if (this.errorState) this.errorState.classList.add("hidden");
      if (this.paginationControls) this.paginationControls.classList.add("hidden");
    },

    /**
     * Show no results state
     */
    _showNoResults: function () {
      if (this.loadingState) this.loadingState.classList.add("hidden");
      if (this.emptyState) this.emptyState.classList.add("hidden");
      if (this.noResultsState) this.noResultsState.classList.remove("hidden");
      if (this.errorState) this.errorState.classList.add("hidden");
      if (this.paginationControls) this.paginationControls.classList.add("hidden");
    },

    /**
     * Show error state
     */
    _showError: function () {
      if (this.loadingState) this.loadingState.classList.add("hidden");
      if (this.emptyState) this.emptyState.classList.add("hidden");
      if (this.noResultsState) this.noResultsState.classList.add("hidden");
      if (this.errorState) this.errorState.classList.remove("hidden");
      if (this.paginationControls) this.paginationControls.classList.add("hidden");
    },
  };

  // Initialize on DOM ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      InferenceLogPage.init();
    });
  } else {
    InferenceLogPage.init();
  }

  global.InferenceLogPage = InferenceLogPage;
})(typeof window !== "undefined" ? window : this);
