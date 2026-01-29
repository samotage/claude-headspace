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
    expandedEventId: null,
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
      this.connectionIndicator = document.getElementById("connection-indicator");

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
     * Initialize SSE client for real-time updates
     */
    _initSSE: function () {
      if (typeof SSEClient === "undefined") {
        console.warn("SSEClient not available");
        return;
      }

      this.sseClient = new SSEClient({
        url: "/api/events/stream",
      });

      // Handle connection state changes
      this.sseClient.onStateChange((newState) => {
        this._updateConnectionIndicator(newState);
      });

      // Handle new events
      this.sseClient.on("*", (data, eventType) => {
        this._handleSSEEvent(data, eventType);
      });

      this.sseClient.connect();
    },

    /**
     * Update connection indicator based on SSE state
     */
    _updateConnectionIndicator: function (state) {
      if (!this.connectionIndicator) return;

      const dot = this.connectionIndicator.querySelector(".connection-dot");
      const text = this.connectionIndicator.querySelector(".connection-text");

      switch (state) {
        case "connected":
          if (dot) dot.className = "connection-dot w-2 h-2 rounded-full bg-green";
          if (text) {
            text.textContent = "Live";
            text.className = "connection-text text-green text-sm";
          }
          break;
        case "connecting":
        case "reconnecting":
          if (dot) dot.className = "connection-dot w-2 h-2 rounded-full bg-amber";
          if (text) {
            text.textContent = state === "reconnecting" ? "Reconnecting..." : "Connecting...";
            text.className = "connection-text text-amber text-sm";
          }
          break;
        case "disconnected":
          if (dot) dot.className = "connection-dot w-2 h-2 rounded-full bg-muted";
          if (text) {
            text.textContent = "Disconnected";
            text.className = "connection-text text-muted text-sm";
          }
          break;
      }
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
          option.textContent = "#" + agent.session_uuid.substring(0, 4) + "...";
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
      agentCell.textContent = event.agent_session
        ? "#" + event.agent_session.substring(0, 4) + "..."
        : "-";
      row.appendChild(agentCell);

      // Event Type
      const typeCell = document.createElement("td");
      typeCell.className = "px-4 py-3 text-sm";
      const typeBadge = document.createElement("span");
      typeBadge.className = this._getEventTypeBadgeClass(event.event_type);
      typeBadge.textContent = event.event_type;
      typeCell.appendChild(typeBadge);
      row.appendChild(typeCell);

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
          return baseClass + " bg-blue/20 text-blue";
        case "session_discovered":
        case "session_ended":
          return baseClass + " bg-cyan/20 text-cyan";
        case "turn_detected":
          return baseClass + " bg-purple/20 text-purple";
        case "hook_received":
          return baseClass + " bg-amber/20 text-amber";
        case "objective_changed":
          return baseClass + " bg-green/20 text-green";
        default:
          return baseClass + " bg-surface text-secondary";
      }
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

      // Remove any existing detail rows
      const existingDetailRow = document.querySelector(".event-detail-row");
      if (existingDetailRow) {
        existingDetailRow.remove();
      }

      // If clicking the same event, just collapse
      if (this.expandedEventId === eventId) {
        this.expandedEventId = null;
        row.classList.remove("bg-surface");
        return;
      }

      // Collapse previously expanded row
      const prevExpandedRow = document.querySelector(
        `tr[data-event-id="${this.expandedEventId}"]`
      );
      if (prevExpandedRow) {
        prevExpandedRow.classList.remove("bg-surface");
      }

      // Expand this row
      this.expandedEventId = eventId;
      row.classList.add("bg-surface");

      // Create detail row
      const detailRow = document.createElement("tr");
      detailRow.className = "event-detail-row";
      const detailCell = document.createElement("td");
      detailCell.colSpan = 5;
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
