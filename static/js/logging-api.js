/**
 * API call log page client for Claude Headspace.
 *
 * Handles filtering, pagination, and row expansion for API call log records.
 */

(function (global) {
  "use strict";

  const CALLS_API = "/api/logging/api-calls";
  const FILTERS_API = "/api/logging/api-calls/filters";
  const PER_PAGE = 50;

  /**
   * API log page controller
   */
  const ApiLogPage = {
    currentPage: 1,
    totalPages: 0,
    expandedCallIds: new Set(),
    sseClient: null,
    _fetchController: null,
    filters: {
      search: null,
      endpoint_path: null,
      http_method: null,
      status_category: null,
      auth_status: null,
    },
    _searchDebounceTimer: null,

    /**
     * Initialize the API log page
     */
    init: function () {
      this.searchFilter = document.getElementById("filter-search");
      this.endpointFilter = document.getElementById("filter-endpoint");
      this.methodFilter = document.getElementById("filter-method");
      this.statusFilter = document.getElementById("filter-status");
      this.authFilter = document.getElementById("filter-auth");
      this.clearFiltersBtn = document.getElementById("clear-filters-btn");
      this.tableBody = document.getElementById("api-calls-table-body");
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
      if (this.endpointFilter) {
        this.endpointFilter.addEventListener("change", () =>
          this._handleFilterChange()
        );
      }
      if (this.methodFilter) {
        this.methodFilter.addEventListener("change", () =>
          this._handleFilterChange()
        );
      }
      if (this.statusFilter) {
        this.statusFilter.addEventListener("change", () =>
          this._handleFilterChange()
        );
      }
      if (this.authFilter) {
        this.authFilter.addEventListener("change", () =>
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

      client.on("api_call_logged", function (data) {
        this._handleSSEEvent(data);
      }.bind(this));
    },

    /**
     * Handle SSE api_call_logged event
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
     * Check if an API call event matches current filters
     */
    _eventMatchesFilters: function (call) {
      if (this.filters.endpoint_path && call.endpoint_path !== this.filters.endpoint_path) {
        return false;
      }
      if (this.filters.http_method && call.http_method !== this.filters.http_method) {
        return false;
      }
      if (this.filters.status_category) {
        var statusCode = call.response_status_code;
        var cat = this.filters.status_category;
        if (cat === "2xx" && (statusCode < 200 || statusCode >= 300)) return false;
        if (cat === "4xx" && (statusCode < 400 || statusCode >= 500)) return false;
        if (cat === "5xx" && (statusCode < 500 || statusCode >= 600)) return false;
      }
      if (this.filters.auth_status && call.auth_status !== this.filters.auth_status) {
        return false;
      }
      return true;
    },

    /**
     * Prepend a new API call to the table with animation
     */
    _prependCall: function (call) {
      if (!this.tableBody) return;

      this._hideStates();
      if (this.paginationControls) this.paginationControls.classList.remove("hidden");

      var row = this._createCallRow(call);
      row.classList.add("event-new");

      if (this.tableBody.firstChild) {
        this.tableBody.insertBefore(row, this.tableBody.firstChild);
      } else {
        this.tableBody.appendChild(row);
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
      if (this.endpointFilter && data.endpoints) {
        const currentValue = this.endpointFilter.value;
        this.endpointFilter.innerHTML = '<option value="">All Endpoints</option>';
        data.endpoints.forEach(function (endpoint) {
          var option = document.createElement("option");
          option.value = endpoint;
          option.textContent = endpoint;
          this.endpointFilter.appendChild(option);
        }.bind(this));
        this.endpointFilter.value = currentValue;
      }

      if (this.methodFilter && data.methods) {
        const currentValue = this.methodFilter.value;
        this.methodFilter.innerHTML = '<option value="">All Methods</option>';
        data.methods.forEach(function (method) {
          var option = document.createElement("option");
          option.value = method;
          option.textContent = method;
          this.methodFilter.appendChild(option);
        }.bind(this));
        this.methodFilter.value = currentValue;
      }

      if (this.statusFilter && data.status_categories) {
        const currentValue = this.statusFilter.value;
        this.statusFilter.innerHTML = '<option value="">All Statuses</option>';
        data.status_categories.forEach(function (cat) {
          var option = document.createElement("option");
          option.value = cat;
          option.textContent = cat;
          this.statusFilter.appendChild(option);
        }.bind(this));
        this.statusFilter.value = currentValue;
      }

      if (this.authFilter && data.auth_statuses) {
        const currentValue = this.authFilter.value;
        this.authFilter.innerHTML = '<option value="">All Auth</option>';
        data.auth_statuses.forEach(function (status) {
          var option = document.createElement("option");
          option.value = status;
          option.textContent = status;
          this.authFilter.appendChild(option);
        }.bind(this));
        this.authFilter.value = currentValue;
      }
    },

    /**
     * Handle filter change
     */
    _handleFilterChange: function () {
      this.filters.search = this.searchFilter ? this.searchFilter.value : null;
      this.filters.endpoint_path = this.endpointFilter ? this.endpointFilter.value : null;
      this.filters.http_method = this.methodFilter ? this.methodFilter.value : null;
      this.filters.status_category = this.statusFilter ? this.statusFilter.value : null;
      this.filters.auth_status = this.authFilter ? this.authFilter.value : null;

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
     * Clear all API call logs
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
        console.error("Failed to clear API logs:", error);
        this._showError();
      }
    },

    /**
     * Clear all filters
     */
    _clearFilters: function () {
      if (this.searchFilter) this.searchFilter.value = "";
      if (this.endpointFilter) this.endpointFilter.value = "";
      if (this.methodFilter) this.methodFilter.value = "";
      if (this.statusFilter) this.statusFilter.value = "";
      if (this.authFilter) this.authFilter.value = "";

      this.filters = {
        search: null,
        endpoint_path: null,
        http_method: null,
        status_category: null,
        auth_status: null,
      };

      this.currentPage = 1;
      this._loadCalls();
    },

    /**
     * Load API calls from server
     */
    _loadCalls: async function () {
      this._showLoading();

      // Abort any in-flight filter fetch to prevent race conditions
      if (this._fetchController) this._fetchController.abort();
      this._fetchController = new AbortController();

      try {
        const url = new URL(CALLS_API, window.location.origin);
        url.searchParams.set("page", this.currentPage);
        url.searchParams.set("per_page", PER_PAGE);

        if (this.filters.search) {
          url.searchParams.set("search", this.filters.search);
        }
        if (this.filters.endpoint_path) {
          url.searchParams.set("endpoint_path", this.filters.endpoint_path);
        }
        if (this.filters.http_method) {
          url.searchParams.set("http_method", this.filters.http_method);
        }
        if (this.filters.status_category) {
          url.searchParams.set("status_category", this.filters.status_category);
        }
        if (this.filters.auth_status) {
          url.searchParams.set("auth_status", this.filters.auth_status);
        }

        const response = await fetch(url, { signal: this._fetchController.signal });
        const data = await response.json();

        if (response.ok) {
          this._renderCalls(data);
        } else {
          this._showError();
        }
      } catch (error) {
        if (error.name === 'AbortError') return;
        console.error("Failed to load API calls:", error);
        this._showError();
      }
    },

    /**
     * Render API calls in the table
     */
    _renderCalls: function (data) {
      this._hideStates();

      if (!data.calls || data.calls.length === 0) {
        if (
          this.filters.search ||
          this.filters.endpoint_path ||
          this.filters.http_method ||
          this.filters.status_category ||
          this.filters.auth_status
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
        }.bind(this));
      }

      this.totalPages = data.pages;
      this._updatePagination(data);
    },

    /**
     * Create a table row for an API call
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

      // Method (badge)
      var methodCell = document.createElement("td");
      methodCell.className = "px-4 py-3 text-sm";
      var methodBadge = document.createElement("span");
      methodBadge.className = this._getMethodBadgeClass(call.http_method);
      methodBadge.textContent = call.http_method;
      methodCell.appendChild(methodBadge);
      row.appendChild(methodCell);

      // Endpoint
      var endpointCell = document.createElement("td");
      endpointCell.className = "px-4 py-3 text-sm text-secondary font-mono truncate max-w-xs";
      endpointCell.textContent = call.endpoint_path || "-";
      endpointCell.title = call.endpoint_path || "";
      row.appendChild(endpointCell);

      // Status (colour-coded badge)
      var statusCell = document.createElement("td");
      statusCell.className = "px-4 py-3 text-sm";
      var statusBadge = document.createElement("span");
      statusBadge.className = this._getStatusBadgeClass(call.response_status_code);
      statusBadge.textContent = call.response_status_code;
      statusCell.appendChild(statusBadge);
      row.appendChild(statusCell);

      // Latency
      var latencyCell = document.createElement("td");
      latencyCell.className = "px-4 py-3 text-sm text-secondary whitespace-nowrap";
      latencyCell.textContent = call.latency_ms != null ? call.latency_ms + "ms" : "-";
      row.appendChild(latencyCell);

      // Source IP
      var ipCell = document.createElement("td");
      ipCell.className = "px-4 py-3 text-sm text-secondary font-mono";
      ipCell.textContent = call.source_ip || "-";
      row.appendChild(ipCell);

      // Auth Status
      var authCell = document.createElement("td");
      authCell.className = "px-4 py-3 text-sm";
      var authBadge = document.createElement("span");
      authBadge.className = this._getAuthBadgeClass(call.auth_status);
      authBadge.textContent = call.auth_status || "-";
      authCell.appendChild(authBadge);
      row.appendChild(authCell);

      row.addEventListener("click", function () {
        this._toggleCallDetails(call, row);
      }.bind(this));

      return row;
    },

    /**
     * Get CSS class for HTTP method badge
     */
    _getMethodBadgeClass: function (method) {
      var baseClass = "px-2 py-1 rounded text-xs font-medium font-mono";
      switch (method) {
        case "GET":
          return baseClass + " bg-blue/20 text-blue";
        case "POST":
          return baseClass + " bg-green/20 text-green";
        case "PUT":
          return baseClass + " bg-amber/20 text-amber";
        case "DELETE":
          return baseClass + " bg-red/20 text-red";
        case "OPTIONS":
          return baseClass + " bg-surface text-secondary";
        default:
          return baseClass + " bg-surface text-secondary";
      }
    },

    /**
     * Get CSS class for status code badge
     */
    _getStatusBadgeClass: function (statusCode) {
      var baseClass = "px-2 py-1 rounded text-xs font-medium";
      if (statusCode >= 200 && statusCode < 300) {
        return baseClass + " bg-green/20 text-green";
      }
      if (statusCode >= 400 && statusCode < 500) {
        return baseClass + " bg-amber/20 text-amber";
      }
      if (statusCode >= 500) {
        return baseClass + " bg-red/20 text-red";
      }
      return baseClass + " bg-surface text-secondary";
    },

    /**
     * Get CSS class for auth status badge
     */
    _getAuthBadgeClass: function (authStatus) {
      var baseClass = "px-2 py-1 rounded text-xs font-medium";
      switch (authStatus) {
        case "authenticated":
          return baseClass + " bg-green/20 text-green";
        case "failed":
          return baseClass + " bg-red/20 text-red";
        case "unauthenticated":
          return baseClass + " bg-surface text-secondary";
        case "bypassed":
          return baseClass + " bg-cyan/20 text-cyan";
        default:
          return baseClass + " bg-surface text-secondary";
      }
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
     * Toggle API call details expansion
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
      detailCell.colSpan = 7;
      detailCell.className = "px-4 py-4 bg-deep border-t border-b border-border";

      var content = document.createElement("div");
      content.className = "grid grid-cols-1 lg:grid-cols-2 gap-4";

      // Request section
      var requestSection = document.createElement("div");
      var requestLabel = document.createElement("div");
      requestLabel.className = "text-sm text-secondary font-medium mb-2";
      requestLabel.textContent = "Request";
      requestSection.appendChild(requestLabel);

      // Request headers
      if (call.request_headers && Object.keys(call.request_headers).length > 0) {
        var headersDiv = document.createElement("div");
        headersDiv.className = "mb-2";
        var headersLabel = document.createElement("div");
        headersLabel.className = "text-xs text-muted mb-1";
        headersLabel.textContent = "Headers:";
        headersDiv.appendChild(headersLabel);
        var headersPre = document.createElement("pre");
        headersPre.className = "text-xs text-primary font-mono overflow-x-auto bg-surface rounded p-2 max-h-32 overflow-y-auto whitespace-pre-wrap";
        headersPre.textContent = JSON.stringify(call.request_headers, null, 2);
        headersDiv.appendChild(headersPre);
        requestSection.appendChild(headersDiv);
      }

      // Request body
      if (call.request_body) {
        var reqBodyDiv = document.createElement("div");
        var reqBodyLabel = document.createElement("div");
        reqBodyLabel.className = "text-xs text-muted mb-1";
        reqBodyLabel.textContent = "Body:";
        reqBodyDiv.appendChild(reqBodyLabel);
        var reqBodyPre = document.createElement("pre");
        reqBodyPre.className = "text-xs text-primary font-mono overflow-x-auto bg-surface rounded p-2 max-h-64 overflow-y-auto whitespace-pre-wrap";
        reqBodyPre.textContent = this._prettyPrint(call.request_body);
        reqBodyDiv.appendChild(reqBodyPre);
        requestSection.appendChild(reqBodyDiv);
      }

      if (!call.request_headers && !call.request_body) {
        var noReqData = document.createElement("p");
        noReqData.className = "text-xs text-muted";
        noReqData.textContent = "No request body or headers captured.";
        requestSection.appendChild(noReqData);
      }

      content.appendChild(requestSection);

      // Response section
      var responseSection = document.createElement("div");
      var responseLabel = document.createElement("div");
      responseLabel.className = "text-sm text-secondary font-medium mb-2";
      responseLabel.textContent = "Response (" + call.response_status_code + ")";
      responseSection.appendChild(responseLabel);

      // Response body
      if (call.response_body) {
        var resBodyDiv = document.createElement("div");
        var resBodyLabel = document.createElement("div");
        resBodyLabel.className = "text-xs text-muted mb-1";
        resBodyLabel.textContent = "Body:";
        resBodyDiv.appendChild(resBodyLabel);
        var resBodyPre = document.createElement("pre");
        resBodyPre.className = "text-xs text-primary font-mono overflow-x-auto bg-surface rounded p-2 max-h-64 overflow-y-auto whitespace-pre-wrap";
        resBodyPre.textContent = this._prettyPrint(call.response_body);
        resBodyDiv.appendChild(resBodyPre);
        responseSection.appendChild(resBodyDiv);
      } else {
        var noResData = document.createElement("p");
        noResData.className = "text-xs text-muted";
        noResData.textContent = "No response body captured.";
        responseSection.appendChild(noResData);
      }

      content.appendChild(responseSection);

      // Metadata row beneath
      var metaDiv = document.createElement("div");
      metaDiv.className = "col-span-full text-xs text-muted pt-2 border-t border-border";
      var metaParts = [];
      if (call.query_string) metaParts.push("Query: " + call.query_string);
      if (call.request_content_type) metaParts.push("Content-Type: " + call.request_content_type);
      if (call.project_name) metaParts.push("Project: " + call.project_name);
      if (call.agent_session) {
        var uuid8 = call.agent_session.substring(0, 8);
        metaParts.push("Agent: " + uuid8.substring(0, 2) + " - " + uuid8);
      }
      if (metaParts.length > 0) {
        metaDiv.textContent = metaParts.join(" | ");
        content.appendChild(metaDiv);
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
      ApiLogPage.init();
    });
  } else {
    ApiLogPage.init();
  }

  global.ApiLogPage = ApiLogPage;
})(typeof window !== "undefined" ? window : this);
