/**
 * Logging page client for Claude Headspace.
 *
 * Handles filtering, pagination, SSE updates, and event row expansion.
 */

(function (global) {
  "use strict";

  const EVENTS_API = "/api/events";
  const FILTERS_API = "/api/events/filters";
  const PER_PAGE = 50;

  /**
   * Logging page controller
   */
  const LoggingPage = {
    currentPage: 1,
    totalPages: 0,
    expandedEventIds: new Set(),
    sseClient: null,
    filters: {
      project_id: null,
      agent_id: null,
      event_type: null,
    },

    /**
     * Initialize the logging page
     */
    init: function () {
      // DOM elements
      this.projectFilter = document.getElementById("filter-project");
      this.agentFilter = document.getElementById("filter-agent");
      this.eventTypeFilter = document.getElementById("filter-event-type");
      this.clearFiltersBtn = document.getElementById("clear-filters-btn");
      this.eventsTableBody = document.getElementById("events-table-body");
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

      // Event listeners
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
      if (this.eventTypeFilter) {
        this.eventTypeFilter.addEventListener("change", () =>
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

      // Initialize SSE
      this._initSSE();

      // Load filter options and events
      this._loadFilters();
      this._loadEvents();
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

      // Handle new events (client-side filtering via _eventMatchesFilters)
      client.on("*", (data, eventType) => {
        this._handleSSEEvent(data, eventType);
      });
    },

    /**
     * Handle SSE event
     */
    _handleSSEEvent: function (data, eventType) {
      // Check if event matches current filters
      if (!this._eventMatchesFilters(data)) {
        return;
      }

      // Only add to page 1
      if (this.currentPage !== 1) {
        return;
      }

      // Prepend new event to table
      this._prependEvent(data);
    },

    /**
     * Check if event matches current filters
     */
    _eventMatchesFilters: function (event) {
      if (
        this.filters.project_id &&
        event.project_id !== parseInt(this.filters.project_id)
      ) {
        return false;
      }
      if (
        this.filters.agent_id &&
        event.agent_id !== parseInt(this.filters.agent_id)
      ) {
        return false;
      }
      if (this.filters.event_type && event.event_type !== this.filters.event_type) {
        return false;
      }
      return true;
    },

    /**
     * Prepend a new event to the table with animation
     */
    _prependEvent: function (event) {
      if (!this.eventsTableBody) return;

      // Hide empty/no results states
      this._hideStates();
      this.paginationControls.classList.remove("hidden");

      // Create new row
      const row = this._createEventRow(event);
      row.classList.add("event-new");

      // Prepend to table
      if (this.eventsTableBody.firstChild) {
        this.eventsTableBody.insertBefore(row, this.eventsTableBody.firstChild);
      } else {
        this.eventsTableBody.appendChild(row);
      }

      // Remove highlight after animation
      setTimeout(() => {
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
      // Populate project filter
      if (this.projectFilter && data.projects) {
        const currentValue = this.projectFilter.value;
        this.projectFilter.innerHTML = '<option value="">All Projects</option>';
        data.projects.forEach((project) => {
          const option = document.createElement("option");
          option.value = project.id;
          option.textContent = project.name;
          this.projectFilter.appendChild(option);
        });
        this.projectFilter.value = currentValue;
      }

      // Populate agent filter
      if (this.agentFilter && data.agents) {
        const currentValue = this.agentFilter.value;
        this.agentFilter.innerHTML = '<option value="">All Agents</option>';
        data.agents.forEach((agent) => {
          const option = document.createElement("option");
          option.value = agent.id;
          const prefix = agent.is_active ? "\u25CF " : "";
          const uuid8 = agent.session_uuid.substring(0, 8);
          option.textContent = prefix + uuid8.substring(0, 2) + " - " + uuid8;
          this.agentFilter.appendChild(option);
        });
        this.agentFilter.value = currentValue;
      }

      // Populate event type filter
      if (this.eventTypeFilter && data.event_types) {
        const currentValue = this.eventTypeFilter.value;
        this.eventTypeFilter.innerHTML = '<option value="">All Types</option>';
        data.event_types.forEach((eventType) => {
          const option = document.createElement("option");
          option.value = eventType;
          option.textContent = eventType;
          this.eventTypeFilter.appendChild(option);
        });
        this.eventTypeFilter.value = currentValue;
      }
    },

    /**
     * Handle filter change
     */
    _handleFilterChange: function () {
      // Update filters
      this.filters.project_id = this.projectFilter ? this.projectFilter.value : null;
      this.filters.agent_id = this.agentFilter ? this.agentFilter.value : null;
      this.filters.event_type = this.eventTypeFilter ? this.eventTypeFilter.value : null;

      // Reset to page 1
      this.currentPage = 1;

      // Reload events
      this._loadEvents();
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
     * Clear all logs
     */
    _clearAllLogs: async function () {
      this._hideClearConfirm();

      try {
        const response = await CHUtils.apiFetch(EVENTS_API, { method: "DELETE", headers: { "X-Confirm-Destructive": "true" } });
        if (response.ok) {
          this.currentPage = 1;
          this._loadFilters();
          this._loadEvents();
        } else {
          this._showError();
        }
      } catch (error) {
        console.error("Failed to clear logs:", error);
        this._showError();
      }
    },

    /**
     * Clear all filters
     */
    _clearFilters: function () {
      if (this.projectFilter) this.projectFilter.value = "";
      if (this.agentFilter) this.agentFilter.value = "";
      if (this.eventTypeFilter) this.eventTypeFilter.value = "";

      this.filters = {
        project_id: null,
        agent_id: null,
        event_type: null,
      };

      this.currentPage = 1;
      this._loadEvents();
    },

    /**
     * Load events from API
     */
    _loadEvents: async function () {
      this._showLoading();

      try {
        // Build URL with query parameters
        const url = new URL(EVENTS_API, window.location.origin);
        url.searchParams.set("page", this.currentPage);
        url.searchParams.set("per_page", PER_PAGE);

        if (this.filters.project_id) {
          url.searchParams.set("project_id", this.filters.project_id);
        }
        if (this.filters.agent_id) {
          url.searchParams.set("agent_id", this.filters.agent_id);
        }
        if (this.filters.event_type) {
          url.searchParams.set("event_type", this.filters.event_type);
        }

        const response = await fetch(url);
        const data = await response.json();

        if (response.ok) {
          this._renderEvents(data);
        } else {
          this._showError();
        }
      } catch (error) {
        console.error("Failed to load events:", error);
        this._showError();
      }
    },

    /**
     * Render events in the table
     */
    _renderEvents: function (data) {
      this._hideStates();

      if (!data.events || data.events.length === 0) {
        if (
          this.filters.project_id ||
          this.filters.agent_id ||
          this.filters.event_type
        ) {
          this._showNoResults();
        } else {
          this._showEmpty();
        }
        return;
      }

      // Render events
      if (this.eventsTableBody) {
        this.eventsTableBody.innerHTML = "";
        data.events.forEach((event) => {
          const row = this._createEventRow(event);
          this.eventsTableBody.appendChild(row);
        });
      }

      // Update pagination
      this.totalPages = data.pages;
      this._updatePagination(data);
    },

    /**
     * Create a table row for an event
     */
    _createEventRow: function (event) {
      const row = document.createElement("tr");
      row.className =
        "hover:bg-hover cursor-pointer transition-colors";
      row.dataset.eventId = event.id;

      // Timestamp
      const timestampCell = document.createElement("td");
      timestampCell.className = "px-4 py-3 text-sm text-primary whitespace-nowrap";
      timestampCell.textContent = this._formatTimestamp(event.timestamp);
      row.appendChild(timestampCell);

      // Project
      const projectCell = document.createElement("td");
      projectCell.className = "px-4 py-3 text-sm text-secondary";
      projectCell.textContent = event.project_name || "-";
      row.appendChild(projectCell);

      // Agent
      const agentCell = document.createElement("td");
      agentCell.className = "px-4 py-3 text-sm text-secondary font-mono";
      if (event.agent_session) {
        const uuid8 = event.agent_session.substring(0, 8);
        const heroSpan = document.createElement("span");
        heroSpan.className = "agent-hero";
        heroSpan.textContent = uuid8.substring(0, 2);
        const trailSpan = document.createElement("span");
        trailSpan.className = "agent-hero-trail";
        trailSpan.textContent = uuid8.substring(2);
        agentCell.appendChild(heroSpan);
        agentCell.appendChild(trailSpan);
      } else {
        agentCell.textContent = "-";
      }
      row.appendChild(agentCell);

      // Event Type
      const typeCell = document.createElement("td");
      typeCell.className = "px-4 py-3 text-sm";
      const typeBadge = document.createElement("span");
      if (event.event_type) {
        typeBadge.className = this._getEventTypeBadgeClass(event.event_type);
        typeBadge.textContent = event.event_type;
      } else {
        typeBadge.className = "px-2 py-1 rounded text-xs font-medium bg-surface text-muted";
        typeBadge.textContent = "unknown";
      }
      typeCell.appendChild(typeBadge);
      row.appendChild(typeCell);

      // Message (from turn data)
      const messageCell = document.createElement("td");
      messageCell.className = "px-4 py-3 text-sm text-secondary truncate max-w-xs";
      if (event.message) {
        const actorLabel = event.message_actor === "user" ? "USER" : event.message_actor === "agent" ? "AGENT" : "";
        const truncated = event.message.length > 80 ? event.message.substring(0, 80) + "..." : event.message;
        messageCell.textContent = actorLabel ? actorLabel + ": " + truncated : truncated;
      } else {
        // Fall back to a description based on event_type
        var fallback = this._getEventFallbackMessage(event.event_type);
        if (fallback) {
          messageCell.textContent = fallback;
          messageCell.classList.add("text-muted", "italic");
          messageCell.classList.remove("text-secondary");
        } else {
          messageCell.textContent = "-";
        }
      }
      row.appendChild(messageCell);

      // Details (preview)
      const detailsCell = document.createElement("td");
      detailsCell.className = "px-4 py-3 text-sm text-muted truncate max-w-xs";
      detailsCell.textContent = event.payload
        ? this._getPayloadPreview(event.payload)
        : "-";
      row.appendChild(detailsCell);

      // Click handler for expand/collapse
      row.addEventListener("click", () => this._toggleEventDetails(event, row));

      return row;
    },

    /**
     * Get CSS class for event type badge
     */
    _getEventTypeBadgeClass: function (eventType) {
      const baseClass = "px-2 py-1 rounded text-xs font-medium";
      switch (eventType) {
        case "state_transition":
        case "post_tool_use":
          return baseClass + " bg-blue/20 text-blue";
        case "stop":
        case "objective_changed":
          return baseClass + " bg-green/20 text-green";
        case "pre_tool_use":
        case "notification":
        case "permission_request":
        case "hook_received":
          return baseClass + " bg-amber/20 text-amber";
        case "user_prompt_submit":
        case "session_end":
        case "session_discovered":
        case "session_ended":
          return baseClass + " bg-cyan/20 text-cyan";
        case "turn_detected":
          return baseClass + " bg-purple/20 text-purple";
        default:
          return baseClass + " bg-surface text-secondary";
      }
    },

    /**
     * Get fallback message for events without turn data
     */
    _getEventFallbackMessage: function (eventType) {
      var messages = {
        "session_discovered": "Session started",
        "session_ended": "Session ended",
        "session_end": "Session ended",
        "hook_received": "Hook event received",
        "notification": "Notification sent",
        "state_transition": "State changed",
        "objective_changed": "Objective updated",
        "permission_request": "Permission requested",
        "pre_tool_use": "Tool use started",
        "post_tool_use": "Tool use completed",
        "stop": "Agent stopped",
        "user_prompt_submit": "User prompt submitted"
      };
      return messages[eventType] || null;
    },

    /**
     * Get a preview of the payload
     */
    _getPayloadPreview: function (payload) {
      if (!payload) return "-";
      const str = JSON.stringify(payload);
      if (str.length > 50) {
        return str.substring(0, 50) + "...";
      }
      return str;
    },

    /**
     * Toggle event details expansion
     */
    _toggleEventDetails: function (event, row) {
      const eventId = event.id;

      // If already expanded, collapse it
      if (this.expandedEventIds.has(eventId)) {
        this.expandedEventIds.delete(eventId);
        row.classList.remove("bg-surface");
        const existingDetailRow = row.nextElementSibling;
        if (existingDetailRow && existingDetailRow.classList.contains("event-detail-row")) {
          existingDetailRow.remove();
        }
        return;
      }

      // Expand this row
      this.expandedEventIds.add(eventId);
      row.classList.add("bg-surface");

      // Create detail row
      const detailRow = document.createElement("tr");
      detailRow.className = "event-detail-row";
      const detailCell = document.createElement("td");
      detailCell.colSpan = 6;
      detailCell.className = "px-4 py-4 bg-deep border-t border-b border-border";

      // Format JSON payload
      const pre = document.createElement("pre");
      pre.className = "text-sm text-primary font-mono overflow-x-auto";
      pre.textContent = event.payload
        ? JSON.stringify(event.payload, null, 2)
        : "No payload data";

      detailCell.appendChild(pre);
      detailRow.appendChild(detailCell);

      // Insert after clicked row
      row.after(detailRow);
    },

    /**
     * Format timestamp for display
     */
    _formatTimestamp: function (isoString) {
      if (!isoString) return "-";
      const date = new Date(isoString);
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
     * Update pagination controls
     */
    _updatePagination: function (data) {
      if (!this.paginationControls) return;

      this.paginationControls.classList.remove("hidden");

      // Update page indicator
      if (this.pageIndicator) {
        this.pageIndicator.textContent = `Page ${data.page} of ${data.pages || 1}`;
      }

      // Update button states
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
        this._loadEvents();
      }
    },

    /**
     * Go to next page
     */
    _nextPage: function () {
      if (this.currentPage < this.totalPages) {
        this.currentPage++;
        this._loadEvents();
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
      if (this.eventsTableBody) this.eventsTableBody.classList.remove("hidden");
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
      if (this.eventsTableBody) this.eventsTableBody.innerHTML = "";
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
    document.addEventListener("DOMContentLoaded", () => LoggingPage.init());
  } else {
    LoggingPage.init();
  }

  // Export for potential external use
  global.LoggingPage = LoggingPage;
})(typeof window !== "undefined" ? window : this);
