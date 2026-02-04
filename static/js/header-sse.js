/**
 * Shared SSE connection for Claude Headspace.
 *
 * Creates a single SSE connection used by all pages.
 * Updates the header connection indicator and exposes the
 * client as window.headerSSEClient for page-specific scripts.
 */

(function (global) {
  "use strict";

  function updateConnectionIndicator(state) {
    var indicator = document.getElementById("connection-indicator");
    if (!indicator) return;

    var dot = indicator.querySelector(".connection-dot");
    var text = indicator.querySelector(".connection-text");

    if (!dot || !text) return;

    switch (state) {
      case "connected":
        dot.className = "connection-dot connected";
        text.textContent = "Live";
        text.className = "connection-text";
        text.style.color = "var(--green)";
        break;
      case "connecting":
      case "reconnecting":
        dot.className = "connection-dot";
        text.textContent =
          state === "reconnecting" ? "Reconnecting..." : "Connecting...";
        text.className = "connection-text";
        text.style.color = "";
        break;
      case "disconnected":
      default:
        dot.className = "connection-dot";
        text.textContent = "Offline";
        text.className = "connection-text";
        text.style.color = "var(--red)";
        break;
    }
  }

  function init() {
    if (typeof SSEClient === "undefined") {
      updateConnectionIndicator("disconnected");
      return;
    }

    var client = new SSEClient({
      url: "/api/events/stream",
      reconnectBaseDelay: 1000,
      reconnectMaxDelay: 30000,
    });

    client.onStateChange(function (newState) {
      updateConnectionIndicator(newState);
    });

    client.connect();

    global.headerSSEClient = client;

    // Close SSE connection before page unload to free the browser connection slot.
    // Chrome limits HTTP/1.1 to 6 connections per host — without this,
    // navigating between pages accumulates stale SSE connections and
    // eventually blocks all new requests.
    window.addEventListener("beforeunload", function () {
      client.disconnect();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})(typeof window !== "undefined" ? window : this);
