/**
 * SSE Client for Claude Headspace real-time updates.
 *
 * Features:
 * - Automatic reconnection with exponential backoff and jitter
 * - Event filtering (types, project_id, agent_id)
 * - Custom event handlers
 * - Connection state management
 */

(function (global) {
  "use strict";

  // Connection states
  const ConnectionState = {
    DISCONNECTED: "disconnected",
    CONNECTING: "connecting",
    CONNECTED: "connected",
    RECONNECTING: "reconnecting",
  };

  // Default configuration
  const DEFAULT_CONFIG = {
    url: "/api/events/stream",
    reconnectBaseDelay: 1000, // 1 second
    reconnectMaxDelay: 30000, // 30 seconds
    reconnectJitter: 0.3, // 30% jitter
    maxReconnectAttempts: Infinity,
    types: null, // Event types to filter
    projectId: null, // Project ID to filter
    agentId: null, // Agent ID to filter
  };

  /**
   * SSE Client class
   */
  class SSEClient {
    constructor(config = {}) {
      this.config = { ...DEFAULT_CONFIG, ...config };
      this.eventSource = null;
      this.state = ConnectionState.DISCONNECTED;
      this.reconnectAttempts = 0;
      this.lastEventId = null;
      this.handlers = new Map();
      this.stateChangeCallbacks = [];

      // Bind methods
      this._onOpen = this._onOpen.bind(this);
      this._onError = this._onError.bind(this);
      this._onMessage = this._onMessage.bind(this);
    }

    /**
     * Build the SSE URL with query parameters
     */
    _buildUrl() {
      const url = new URL(this.config.url, window.location.origin);

      if (this.config.types && this.config.types.length > 0) {
        url.searchParams.set("types", this.config.types.join(","));
      }

      if (this.config.projectId) {
        url.searchParams.set("project_id", this.config.projectId);
      }

      if (this.config.agentId) {
        url.searchParams.set("agent_id", this.config.agentId);
      }

      return url.toString();
    }

    /**
     * Calculate reconnection delay with exponential backoff and jitter
     */
    _calculateReconnectDelay() {
      const baseDelay = Math.min(
        this.config.reconnectBaseDelay *
          Math.pow(2, this.reconnectAttempts - 1),
        this.config.reconnectMaxDelay
      );

      // Add jitter
      const jitterRange = baseDelay * this.config.reconnectJitter;
      const jitter = Math.random() * jitterRange * 2 - jitterRange;

      return Math.max(0, baseDelay + jitter);
    }

    /**
     * Update connection state and notify listeners
     */
    _setState(newState) {
      const oldState = this.state;
      this.state = newState;

      if (oldState !== newState) {
        this.stateChangeCallbacks.forEach((callback) => {
          try {
            callback(newState, oldState);
          } catch (e) {
            console.error("Error in state change callback:", e);
          }
        });
      }
    }

    /**
     * Handle connection open
     */
    _onOpen() {
      console.log("SSE connection established");
      this._setState(ConnectionState.CONNECTED);
      this.reconnectAttempts = 0;
    }

    /**
     * Handle connection error
     */
    _onError(event) {
      console.error("SSE connection error:", event);

      // Close the current connection
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }

      // Attempt reconnection
      this._scheduleReconnect();
    }

    /**
     * Handle incoming message
     */
    _onMessage(event) {
      try {
        // Update last event ID
        if (event.lastEventId) {
          this.lastEventId = event.lastEventId;
        }

        // Parse event data
        const data = JSON.parse(event.data);

        // Dispatch to handlers
        this._dispatchEvent(event.type, data);
      } catch (e) {
        console.error("Error processing SSE message:", e, event);
      }
    }

    /**
     * Dispatch event to registered handlers
     */
    _dispatchEvent(eventType, data) {
      // Call type-specific handlers
      const typeHandlers = this.handlers.get(eventType);
      if (typeHandlers) {
        typeHandlers.forEach((handler) => {
          try {
            handler(data, eventType);
          } catch (e) {
            console.error(`Error in handler for event type '${eventType}':`, e);
          }
        });
      }

      // Call wildcard handlers
      const wildcardHandlers = this.handlers.get("*");
      if (wildcardHandlers) {
        wildcardHandlers.forEach((handler) => {
          try {
            handler(data, eventType);
          } catch (e) {
            console.error("Error in wildcard handler:", e);
          }
        });
      }
    }

    /**
     * Schedule reconnection attempt
     */
    _scheduleReconnect() {
      this.reconnectAttempts++;

      if (this.reconnectAttempts > this.config.maxReconnectAttempts) {
        console.error("Max reconnection attempts reached");
        this._setState(ConnectionState.DISCONNECTED);
        return;
      }

      this._setState(ConnectionState.RECONNECTING);

      const delay = this._calculateReconnectDelay();
      console.log(
        `Reconnecting in ${Math.round(delay)}ms (attempt ${this.reconnectAttempts})`
      );

      setTimeout(() => {
        if (this.state === ConnectionState.RECONNECTING) {
          this.connect();
        }
      }, delay);
    }

    /**
     * Connect to the SSE endpoint
     */
    connect() {
      if (
        this.state === ConnectionState.CONNECTED ||
        this.state === ConnectionState.CONNECTING
      ) {
        console.warn("SSE client already connected or connecting");
        return;
      }

      this._setState(ConnectionState.CONNECTING);

      const url = this._buildUrl();
      console.log("Connecting to SSE endpoint:", url);

      this.eventSource = new EventSource(url);

      // Set up event handlers
      this.eventSource.onopen = this._onOpen;
      this.eventSource.onerror = this._onError;

      // Handle generic messages
      this.eventSource.onmessage = this._onMessage;

      // Set up typed event handlers for common event types
      const commonTypes = [
        "state_transition",
        "turn_detected",
        "session_started",
        "session_ended",
        "agent_created",
        "agent_updated",
        "error",
      ];

      commonTypes.forEach((type) => {
        this.eventSource.addEventListener(type, this._onMessage);
      });
    }

    /**
     * Disconnect from the SSE endpoint
     */
    disconnect() {
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }

      this._setState(ConnectionState.DISCONNECTED);
      this.reconnectAttempts = 0;
      console.log("SSE connection closed");
    }

    /**
     * Register an event handler
     *
     * @param {string} eventType - Event type to handle, or '*' for all events
     * @param {function} handler - Handler function(data, eventType)
     * @returns {function} Unsubscribe function
     */
    on(eventType, handler) {
      if (!this.handlers.has(eventType)) {
        this.handlers.set(eventType, new Set());
      }

      this.handlers.get(eventType).add(handler);

      // Return unsubscribe function
      return () => {
        const handlers = this.handlers.get(eventType);
        if (handlers) {
          handlers.delete(handler);
        }
      };
    }

    /**
     * Register a one-time event handler
     *
     * @param {string} eventType - Event type to handle
     * @param {function} handler - Handler function(data, eventType)
     */
    once(eventType, handler) {
      const unsubscribe = this.on(eventType, (data, type) => {
        unsubscribe();
        handler(data, type);
      });
    }

    /**
     * Register a state change callback
     *
     * @param {function} callback - Callback function(newState, oldState)
     * @returns {function} Unsubscribe function
     */
    onStateChange(callback) {
      this.stateChangeCallbacks.push(callback);

      return () => {
        const index = this.stateChangeCallbacks.indexOf(callback);
        if (index > -1) {
          this.stateChangeCallbacks.splice(index, 1);
        }
      };
    }

    /**
     * Get current connection state
     */
    getState() {
      return this.state;
    }

    /**
     * Check if connected
     */
    isConnected() {
      return this.state === ConnectionState.CONNECTED;
    }

    /**
     * Get last received event ID
     */
    getLastEventId() {
      return this.lastEventId;
    }
  }

  // Export
  global.SSEClient = SSEClient;
  global.SSEConnectionState = ConnectionState;
})(typeof window !== "undefined" ? window : this);
