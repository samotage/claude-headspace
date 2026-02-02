/**
 * Headspace monitoring UI — SSE listeners and banner controls.
 *
 * Listens for headspace_update, headspace_alert, and headspace_flow
 * events from the shared SSE connection (window.headerSSEClient).
 */

var HeadspaceBanner = (function () {
  "use strict";

  var FLOW_TOAST_DURATION_MS = 8000;
  var _flowTimer = null;

  /* ---------- traffic-light indicator ---------- */

  function updateIndicator(state) {
    var el = document.getElementById("headspace-indicator");
    if (!el) return;

    // Remove old state class, add new one
    el.className = el.className
      .replace(/headspace-(green|yellow|red)/g, "")
      .trim();
    el.classList.add("headspace-" + (state || "green"));

    var label = el.querySelector(".headspace-label");
    if (label) {
      var labels = { green: "HEADSPACE", yellow: "HEADSPACE", red: "HEADSPACE" };
      label.textContent = labels[state] || "HEADSPACE";
    }

    el.title = "Headspace: " + (state || "green");
  }

  /* ---------- alert banner ---------- */

  function showAlert(message) {
    var banner = document.getElementById("headspace-alert-banner");
    var text = document.getElementById("headspace-alert-message");
    if (!banner || !text) return;

    text.textContent = message;
    banner.classList.remove("hidden");
  }

  function dismiss() {
    var banner = document.getElementById("headspace-alert-banner");
    if (banner) banner.classList.add("hidden");
  }

  function suppress() {
    dismiss();
    // POST to suppress endpoint (1 hour)
    fetch("/api/headspace/suppress", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ hours: 1 }),
    }).catch(function (err) {
      console.warn("Headspace suppress failed:", err);
    });
  }

  /* ---------- flow toast ---------- */

  function showFlowToast(message) {
    var toast = document.getElementById("headspace-flow-toast");
    var text = document.getElementById("headspace-flow-message");
    if (!toast || !text) return;

    text.textContent = message;
    toast.classList.remove("hidden");

    if (_flowTimer) clearTimeout(_flowTimer);
    _flowTimer = setTimeout(function () {
      toast.classList.add("hidden");
    }, FLOW_TOAST_DURATION_MS);
  }

  /* ---------- SSE wiring ---------- */

  function init() {
    var client = window.headerSSEClient;
    if (!client) return;

    client.on("headspace_update", function (data) {
      if (data && data.state) {
        updateIndicator(data.state);
      }
    });

    client.on("headspace_alert", function (data) {
      if (data && data.message) {
        showAlert(data.message);
      }
    });

    client.on("headspace_flow", function (data) {
      if (data && data.message) {
        showFlowToast(data.message);
      }
    });
  }

  /* ---------- bootstrap ---------- */

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }

  return {
    dismiss: dismiss,
    suppress: suppress,
  };
})();
