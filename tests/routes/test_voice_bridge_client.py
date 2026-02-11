"""Tests for the voice bridge PWA client (e6-s2 tasks 3.1-3.7).

Since the PWA is client-side JS, these tests validate:
- Flask route serves the PWA HTML
- Static file structure is correct
- PWA manifest is valid
- Service worker exists with correct cache strategy
- JS modules export expected interfaces
- HTML contains required PWA meta tags
- Auth is skipped for /voice route
"""

import json
import os
from unittest.mock import MagicMock

import pytest
from flask import Flask

from src.claude_headspace.routes.voice_bridge import voice_bridge_bp


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

STATIC_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "static", "voice"
)
STATIC_DIR = os.path.normpath(STATIC_DIR)


@pytest.fixture
def app():
    """Create a test Flask app with voice bridge blueprint."""
    app = Flask(__name__)
    app.register_blueprint(voice_bridge_bp)
    app.config["TESTING"] = True
    app.config["APP_CONFIG"] = {
        "dashboard": {"active_timeout_minutes": 5},
        "tmux_bridge": {"subprocess_timeout": 5, "text_enter_delay_ms": 100},
    }
    app.extensions = {
        "voice_auth": None,
        "voice_formatter": None,
    }
    return app


@pytest.fixture
def app_with_auth():
    """App with auth enabled to test /voice bypasses auth."""
    app = Flask(__name__)
    app.register_blueprint(voice_bridge_bp)
    app.config["TESTING"] = True
    app.config["APP_CONFIG"] = {
        "dashboard": {"active_timeout_minutes": 5},
        "tmux_bridge": {"subprocess_timeout": 5, "text_enter_delay_ms": 100},
    }
    mock_auth = MagicMock()
    mock_auth.authenticate.return_value = None
    app.extensions = {
        "voice_auth": mock_auth,
        "voice_formatter": None,
    }
    return app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def client_with_auth(app_with_auth):
    return app_with_auth.test_client()


# ──────────────────────────────────────────────────────────────
# Task 3.7: PWA manifest tests
# ──────────────────────────────────────────────────────────────

class TestPWAManifest:
    """Validate PWA manifest.json structure for installability."""

    def test_manifest_exists(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        assert os.path.isfile(path), "manifest.json must exist"

    def test_manifest_valid_json(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path) as f:
            data = json.load(f)
        assert isinstance(data, dict)

    def test_manifest_has_name(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path) as f:
            data = json.load(f)
        assert "name" in data
        assert len(data["name"]) > 0

    def test_manifest_standalone_display(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path) as f:
            data = json.load(f)
        assert data.get("display") == "standalone"

    def test_manifest_has_icons(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path) as f:
            data = json.load(f)
        icons = data.get("icons", [])
        assert len(icons) >= 2
        sizes = [i["sizes"] for i in icons]
        assert "192x192" in sizes
        assert "512x512" in sizes

    def test_manifest_icons_exist(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path) as f:
            data = json.load(f)
        for icon in data.get("icons", []):
            # Icon src is an absolute URL path like /static/voice/icons/icon-192.png
            # Resolve to filesystem
            src = icon["src"]
            if src.startswith("/static/voice/"):
                rel = src.replace("/static/voice/", "")
                icon_path = os.path.join(STATIC_DIR, rel)
                assert os.path.isfile(icon_path), f"Icon file missing: {src}"

    def test_manifest_has_start_url(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path) as f:
            data = json.load(f)
        assert "start_url" in data

    def test_manifest_has_theme_color(self):
        path = os.path.join(STATIC_DIR, "manifest.json")
        with open(path) as f:
            data = json.load(f)
        assert "theme_color" in data


# ──────────────────────────────────────────────────────────────
# Task 3.6: Service worker tests
# ──────────────────────────────────────────────────────────────

class TestServiceWorker:
    """Validate service worker file and cache strategy."""

    def test_sw_exists(self):
        path = os.path.join(STATIC_DIR, "sw.js")
        assert os.path.isfile(path), "sw.js must exist"

    def test_sw_has_cache_name(self):
        path = os.path.join(STATIC_DIR, "sw.js")
        with open(path) as f:
            content = f.read()
        assert "CACHE_NAME" in content

    def test_sw_caches_app_shell(self):
        path = os.path.join(STATIC_DIR, "sw.js")
        with open(path) as f:
            content = f.read()
        # Should cache key static files
        assert "voice.css" in content
        assert "voice-app.js" in content

    def test_sw_has_install_handler(self):
        path = os.path.join(STATIC_DIR, "sw.js")
        with open(path) as f:
            content = f.read()
        assert "install" in content

    def test_sw_has_fetch_handler(self):
        path = os.path.join(STATIC_DIR, "sw.js")
        with open(path) as f:
            content = f.read()
        assert "fetch" in content

    def test_sw_network_first_for_api(self):
        """API calls should use network-first strategy."""
        path = os.path.join(STATIC_DIR, "sw.js")
        with open(path) as f:
            content = f.read()
        assert "/api/" in content


# ──────────────────────────────────────────────────────────────
# Static file structure tests
# ──────────────────────────────────────────────────────────────

class TestStaticFileStructure:
    """Validate all required static files exist."""

    REQUIRED_FILES = [
        "voice.html",
        "voice.css",
        "voice-input.js",
        "voice-output.js",
        "voice-api.js",
        "voice-app.js",
        "manifest.json",
        "sw.js",
        "icons/icon-192.png",
        "icons/icon-512.png",
    ]

    @pytest.mark.parametrize("filename", REQUIRED_FILES)
    def test_file_exists(self, filename):
        path = os.path.join(STATIC_DIR, filename)
        assert os.path.isfile(path), f"Missing required file: {filename}"

    def test_total_bundle_under_100kb(self):
        """All HTML/CSS/JS/JSON files combined must be under 100KB uncompressed."""
        total = 0
        for ext in ("*.html", "*.css", "*.js", "*.json"):
            import glob
            for fpath in glob.glob(os.path.join(STATIC_DIR, ext)):
                total += os.path.getsize(fpath)
        assert total < 100 * 1024, f"Bundle size {total} bytes exceeds 100KB"


# ──────────────────────────────────────────────────────────────
# Task 3.1: Voice API client tests (file-level validation)
# ──────────────────────────────────────────────────────────────

class TestVoiceAPIModule:
    """Validate voice-api.js module structure."""

    def test_exports_voiceapi(self):
        path = os.path.join(STATIC_DIR, "voice-api.js")
        with open(path) as f:
            content = f.read()
        assert "window.VoiceAPI" in content

    def test_has_bearer_auth(self):
        path = os.path.join(STATIC_DIR, "voice-api.js")
        with open(path) as f:
            content = f.read()
        assert "Bearer" in content

    def test_has_sse_connection(self):
        path = os.path.join(STATIC_DIR, "voice-api.js")
        with open(path) as f:
            content = f.read()
        assert "EventSource" in content

    def test_has_reconnect_logic(self):
        path = os.path.join(STATIC_DIR, "voice-api.js")
        with open(path) as f:
            content = f.read()
        assert "reconnect" in content.lower() or "backoff" in content.lower() or "SSE_MAX_DELAY" in content

    def test_has_connection_state(self):
        path = os.path.join(STATIC_DIR, "voice-api.js")
        with open(path) as f:
            content = f.read()
        assert "connected" in content
        assert "reconnecting" in content
        assert "disconnected" in content

    def test_has_all_endpoints(self):
        """API client should reference all voice bridge endpoints."""
        path = os.path.join(STATIC_DIR, "voice-api.js")
        with open(path) as f:
            content = f.read()
        assert "/api/voice/sessions" in content
        assert "/api/voice/command" in content
        assert "/output" in content
        assert "/question" in content

    def test_has_polling_fallback(self):
        path = os.path.join(STATIC_DIR, "voice-api.js")
        with open(path) as f:
            content = f.read()
        assert "poll" in content.lower() or "setInterval" in content


# ──────────────────────────────────────────────────────────────
# Task 3.2: Voice input tests (file-level validation)
# ──────────────────────────────────────────────────────────────

class TestVoiceInputModule:
    """Validate voice-input.js module structure."""

    def test_exports_voiceinput(self):
        path = os.path.join(STATIC_DIR, "voice-input.js")
        with open(path) as f:
            content = f.read()
        assert "window.VoiceInput" in content

    def test_uses_speech_recognition(self):
        path = os.path.join(STATIC_DIR, "voice-input.js")
        with open(path) as f:
            content = f.read()
        assert "SpeechRecognition" in content
        assert "webkitSpeechRecognition" in content  # Vendor prefix for Safari

    def test_has_silence_timeout(self):
        path = os.path.join(STATIC_DIR, "voice-input.js")
        with open(path) as f:
            content = f.read()
        assert "silenceTimeout" in content or "_silenceTimeout" in content
        assert "800" in content  # Default timeout

    def test_has_done_word_detection(self):
        path = os.path.join(STATIC_DIR, "voice-input.js")
        with open(path) as f:
            content = f.read()
        assert "send" in content
        assert "over" in content
        assert "done" in content
        assert "doneWord" in content.lower() or "_doneWords" in content

    def test_has_debounce(self):
        path = os.path.join(STATIC_DIR, "voice-input.js")
        with open(path) as f:
            content = f.read()
        # Debounce resets the silence timer
        assert "reset" in content.lower() or "clearTimeout" in content

    def test_has_start_stop_abort(self):
        path = os.path.join(STATIC_DIR, "voice-input.js")
        with open(path) as f:
            content = f.read()
        assert "start:" in content or "start =" in content or "function start" in content
        assert "stop:" in content or "stop =" in content or "function stop" in content
        assert "abort:" in content or "abort =" in content or "function abort" in content

    def test_timeout_range_validation(self):
        """Timeout range should be 600-1200ms."""
        path = os.path.join(STATIC_DIR, "voice-input.js")
        with open(path) as f:
            content = f.read()
        assert "600" in content
        assert "1200" in content


# ──────────────────────────────────────────────────────────────
# Task 3.3: Voice output tests (file-level validation)
# ──────────────────────────────────────────────────────────────

class TestVoiceOutputModule:
    """Validate voice-output.js module structure."""

    def test_exports_voiceoutput(self):
        path = os.path.join(STATIC_DIR, "voice-output.js")
        with open(path) as f:
            content = f.read()
        assert "window.VoiceOutput" in content

    def test_uses_speech_synthesis(self):
        path = os.path.join(STATIC_DIR, "voice-output.js")
        with open(path) as f:
            content = f.read()
        assert "SpeechSynthesis" in content or "speechSynthesis" in content

    def test_has_audio_cues(self):
        path = os.path.join(STATIC_DIR, "voice-output.js")
        with open(path) as f:
            content = f.read()
        assert "ready" in content
        assert "sent" in content
        assert "needs-input" in content
        assert "error" in content

    def test_uses_web_audio_api(self):
        path = os.path.join(STATIC_DIR, "voice-output.js")
        with open(path) as f:
            content = f.read()
        assert "AudioContext" in content or "webkitAudioContext" in content
        assert "createOscillator" in content

    def test_has_tts_toggle(self):
        path = os.path.join(STATIC_DIR, "voice-output.js")
        with open(path) as f:
            content = f.read()
        assert "ttsEnabled" in content or "_ttsEnabled" in content
        assert "localStorage" in content

    def test_has_structured_response_reading(self):
        """Should read status_line, results, next_action in order."""
        path = os.path.join(STATIC_DIR, "voice-output.js")
        with open(path) as f:
            content = f.read()
        assert "status_line" in content
        assert "results" in content
        assert "next_action" in content
        assert "speakResponse" in content

    def test_has_queue_management(self):
        path = os.path.join(STATIC_DIR, "voice-output.js")
        with open(path) as f:
            content = f.read()
        assert "_queue" in content or "queue" in content


# ──────────────────────────────────────────────────────────────
# Task 3.4: Voice app tests (file-level validation)
# ──────────────────────────────────────────────────────────────

class TestVoiceAppModule:
    """Validate voice-app.js module structure."""

    def test_exports_voiceapp(self):
        path = os.path.join(STATIC_DIR, "voice-app.js")
        with open(path) as f:
            content = f.read()
        assert "window.VoiceApp" in content

    def test_has_screen_navigation(self):
        path = os.path.join(STATIC_DIR, "voice-app.js")
        with open(path) as f:
            content = f.read()
        assert "showScreen" in content
        assert "setup" in content
        assert "agents" in content
        assert "listening" in content
        assert "question" in content
        assert "settings" in content

    def test_has_agent_list_rendering(self):
        path = os.path.join(STATIC_DIR, "voice-app.js")
        with open(path) as f:
            content = f.read()
        assert "renderAgentList" in content or "_renderAgentList" in content
        assert "agent-card" in content

    def test_has_auto_target(self):
        path = os.path.join(STATIC_DIR, "voice-app.js")
        with open(path) as f:
            content = f.read()
        assert "autoTarget" in content or "_autoTarget" in content
        assert "awaiting_input" in content

    def test_has_settings_persistence(self):
        path = os.path.join(STATIC_DIR, "voice-app.js")
        with open(path) as f:
            content = f.read()
        assert "localStorage" in content
        assert "loadSettings" in content
        assert "saveSettings" in content

    def test_has_question_rendering(self):
        path = os.path.join(STATIC_DIR, "voice-app.js")
        with open(path) as f:
            content = f.read()
        assert "option-btn" in content
        assert "question_options" in content


# ──────────────────────────────────────────────────────────────
# Task 3.5: Settings persistence tests
# ──────────────────────────────────────────────────────────────

class TestSettingsPersistence:
    """Validate settings handling in voice-app.js."""

    def test_default_silence_timeout(self):
        path = os.path.join(STATIC_DIR, "voice-app.js")
        with open(path) as f:
            content = f.read()
        assert "silenceTimeout: 800" in content or "silenceTimeout: 800" in content

    def test_default_done_word(self):
        path = os.path.join(STATIC_DIR, "voice-app.js")
        with open(path) as f:
            content = f.read()
        assert "doneWord:" in content
        assert "'send'" in content

    def test_settings_use_localstorage(self):
        path = os.path.join(STATIC_DIR, "voice-app.js")
        with open(path) as f:
            content = f.read()
        assert "voice_settings" in content
        assert "localStorage.setItem" in content
        assert "localStorage.getItem" in content


# ──────────────────────────────────────────────────────────────
# Flask route tests — /voice serves PWA HTML
# ──────────────────────────────────────────────────────────────

class TestVoiceRoute:
    """Test the /voice route that serves the PWA."""

    def test_voice_route_returns_html(self, client):
        response = client.get("/voice")
        assert response.status_code == 200
        assert b"<!DOCTYPE html>" in response.data
        assert b"Voice Bridge" in response.data

    def test_voice_route_has_pwa_meta(self, client):
        response = client.get("/voice")
        html = response.data.decode()
        assert "apple-mobile-web-app-capable" in html
        assert 'rel="manifest"' in html
        assert "theme-color" in html

    def test_voice_route_includes_js_modules(self, client):
        response = client.get("/voice")
        html = response.data.decode()
        assert "voice-api.js" in html
        assert "voice-input.js" in html
        assert "voice-output.js" in html
        assert "voice-app.js" in html

    def test_voice_route_has_service_worker_registration(self, client):
        response = client.get("/voice")
        html = response.data.decode()
        assert "serviceWorker" in html
        assert "register('/voice-sw.js'" in html
        assert "scope: '/voice'" in html

    def test_voice_route_has_all_screens(self, client):
        response = client.get("/voice")
        html = response.data.decode()
        assert 'id="screen-setup"' in html
        assert 'id="screen-agents"' in html
        assert 'id="screen-listening"' in html
        assert 'id="screen-question"' in html
        assert 'id="screen-settings"' in html

    def test_voice_route_has_mic_button(self, client):
        response = client.get("/voice")
        html = response.data.decode()
        assert 'id="mic-btn"' in html

    def test_voice_route_has_text_fallback(self, client):
        response = client.get("/voice")
        html = response.data.decode()
        assert 'id="text-form"' in html
        assert 'id="text-input"' in html

    def test_voice_route_has_settings_form(self, client):
        response = client.get("/voice")
        html = response.data.decode()
        assert 'id="settings-form"' in html
        assert 'id="setting-silence"' in html
        assert 'id="setting-doneword"' in html
        assert 'id="setting-tts"' in html
        assert 'id="setting-cues"' in html

    def test_voice_route_has_connection_indicator(self, client):
        response = client.get("/voice")
        html = response.data.decode()
        assert 'id="connection-status"' in html

    def test_voice_route_bypasses_auth(self, client_with_auth, app_with_auth):
        """The /voice route should NOT trigger auth check."""
        response = client_with_auth.get("/voice")
        assert response.status_code == 200
        # Auth's authenticate() should NOT have been called for /voice
        app_with_auth.extensions["voice_auth"].authenticate.assert_not_called()

    def test_api_route_still_requires_auth_from_remote(self, client_with_auth, app_with_auth):
        """API routes from public (non-LAN) IPs should still trigger auth."""
        from unittest.mock import patch
        with patch("src.claude_headspace.routes.voice_bridge.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.all.return_value = []
            client_with_auth.get("/api/voice/sessions", environ_base={"REMOTE_ADDR": "8.8.8.8"})
            app_with_auth.extensions["voice_auth"].authenticate.assert_called()

    def test_api_route_bypasses_auth_from_lan(self, client_with_auth, app_with_auth):
        """API routes from LAN IPs (192.168.x.x) should bypass auth."""
        from unittest.mock import patch
        with patch("src.claude_headspace.routes.voice_bridge.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.all.return_value = []
            client_with_auth.get("/api/voice/sessions", environ_base={"REMOTE_ADDR": "192.168.1.100"})
            app_with_auth.extensions["voice_auth"].authenticate.assert_not_called()

    def test_api_route_bypasses_auth_from_localhost(self, client_with_auth, app_with_auth):
        """API routes from localhost should bypass auth."""
        from unittest.mock import patch
        with patch("src.claude_headspace.routes.voice_bridge.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.all.return_value = []
            client_with_auth.get("/api/voice/sessions")  # test client defaults to 127.0.0.1
            app_with_auth.extensions["voice_auth"].authenticate.assert_not_called()

    def test_api_route_bypasses_auth_from_tailscale(self, client_with_auth, app_with_auth):
        """API routes from Tailscale CGNAT IPs (100.x) should bypass auth."""
        from unittest.mock import patch
        with patch("src.claude_headspace.routes.voice_bridge.db") as mock_db:
            mock_db.session.query.return_value.filter.return_value.all.return_value = []
            client_with_auth.get("/api/voice/sessions", environ_base={"REMOTE_ADDR": "100.100.1.1"})
            app_with_auth.extensions["voice_auth"].authenticate.assert_not_called()

    def test_voice_sw_route_returns_js(self, client):
        """The /voice-sw.js route should serve the service worker file."""
        response = client.get("/voice-sw.js")
        assert response.status_code == 200
        assert b"CACHE_NAME" in response.data

    def test_voice_sw_route_has_scope_header(self, client):
        """The /voice-sw.js route should include Service-Worker-Allowed header."""
        response = client.get("/voice-sw.js")
        assert response.headers.get("Service-Worker-Allowed") == "/"

    def test_voice_sw_route_bypasses_auth(self, client_with_auth, app_with_auth):
        """The /voice-sw.js route should NOT trigger auth check."""
        response = client_with_auth.get("/voice-sw.js")
        assert response.status_code == 200
        app_with_auth.extensions["voice_auth"].authenticate.assert_not_called()


# ──────────────────────────────────────────────────────────────
# HTML structure tests
# ──────────────────────────────────────────────────────────────

class TestHTMLStructure:
    """Validate voice.html has required elements."""

    def test_has_viewport_meta(self):
        path = os.path.join(STATIC_DIR, "voice.html")
        with open(path) as f:
            content = f.read()
        assert "viewport" in content
        assert "user-scalable=no" in content

    def test_has_apple_meta_tags(self):
        path = os.path.join(STATIC_DIR, "voice.html")
        with open(path) as f:
            content = f.read()
        assert "apple-mobile-web-app-capable" in content
        assert "apple-touch-icon" in content

    def test_has_setup_form(self):
        path = os.path.join(STATIC_DIR, "voice.html")
        with open(path) as f:
            content = f.read()
        assert 'id="setup-form"' in content
        assert 'id="setup-url"' in content
        assert 'id="setup-token"' in content
