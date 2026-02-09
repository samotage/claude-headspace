/**
 * ESLint configuration for Claude Headspace
 *
 * Purpose: Catch undefined variable/function references that silently crash IIFEs.
 * All JS files use the IIFE + window.* globals pattern (no modules, no bundler).
 */

export default [
    {
        files: ["static/js/*.js"],
        languageOptions: {
            ecmaVersion: 2020,
            sourceType: "script",
            globals: {
                // --- Browser environment ---
                window: "readonly",
                document: "readonly",
                console: "readonly",
                fetch: "readonly",
                setTimeout: "readonly",
                clearTimeout: "readonly",
                setInterval: "readonly",
                clearInterval: "readonly",
                requestAnimationFrame: "readonly",
                cancelAnimationFrame: "readonly",
                performance: "readonly",
                navigator: "readonly",
                location: "readonly",
                history: "readonly",
                URL: "readonly",
                URLSearchParams: "readonly",
                Headers: "readonly",
                Request: "readonly",
                Response: "readonly",
                AbortController: "readonly",
                AbortSignal: "readonly",
                FormData: "readonly",
                Blob: "readonly",
                File: "readonly",
                FileReader: "readonly",
                EventSource: "readonly",
                CustomEvent: "readonly",
                Event: "readonly",
                MutationObserver: "readonly",
                IntersectionObserver: "readonly",
                ResizeObserver: "readonly",
                HTMLElement: "readonly",
                Element: "readonly",
                Node: "readonly",
                NodeList: "readonly",
                DOMParser: "readonly",
                XMLSerializer: "readonly",
                alert: "readonly",
                confirm: "readonly",
                prompt: "readonly",
                getComputedStyle: "readonly",
                atob: "readonly",
                btoa: "readonly",
                structuredClone: "readonly",
                queueMicrotask: "readonly",
                reportError: "readonly",
                crypto: "readonly",
                localStorage: "readonly",
                sessionStorage: "readonly",
                indexedDB: "readonly",
                self: "readonly",

                // --- Cross-file globals (codebase exports via window.* / var) ---
                // utils.js
                CHUtils: "readonly",
                // sse-client.js
                SSEClient: "readonly",
                SSEConnectionState: "readonly",
                // dashboard-sse.js
                DashboardSSE: "readonly",
                // card-tooltip.js
                CardTooltip: "readonly",
                // confirm-dialog.js
                ConfirmDialog: "readonly",
                // respond-api.js
                RespondAPI: "readonly",
                // respond-init.js
                RespondInit: "readonly",
                // focus-api.js
                FocusAPI: "readonly",
                // headspace.js
                HeadspaceBanner: "readonly",
                // full-text-modal.js
                FullTextModal: "readonly",
                // help.js
                searchHelp: "readonly",
                loadHelpTopic: "readonly",
                openDocViewer: "readonly",
                closeDocViewer: "readonly",
                // activity.js
                ActivityPage: "readonly",
                // brain-reboot.js
                openBrainReboot: "readonly",
                closeBrainReboot: "readonly",
                copyBrainReboot: "readonly",
                exportBrainReboot: "readonly",
                // logging-inference.js
                InferenceLogPage: "readonly",
                // logging.js
                LoggingPage: "readonly",
                // objective.js
                ObjectivePage: "readonly",
                // projects.js
                ProjectsPage: "readonly",
                // project_show.js
                ProjectShow: "readonly",
                // header-sse.js
                headerSSEClient: "readonly",

                // --- External / CDN ---
                Chart: "readonly",           // Chart.js (CDN)

                // --- Template-injected globals (Jinja2) ---
                Toast: "readonly",           // defined in templates/partials/_toast.html
                FRUSTRATION_THRESHOLDS: "readonly",
                HEADSPACE_ENABLED: "readonly",
            }
        },
        rules: {
            "no-undef": "error",
            "no-unused-vars": ["warn", { args: "none", caughtErrors: "none", varsIgnorePattern: "^_" }],
        }
    }
];
