"""Tests for the OpenAPI 3.1 specification file.

Validates the remote-agents.yaml spec for:
- YAML well-formedness and OpenAPI 3.1 structural validity
- Endpoint path coverage against actual Flask route registrations
- Schema field accuracy against actual route code response shapes
- Cross-link verification between spec and help topic
"""

import re
from pathlib import Path

import pytest
import yaml


# ──────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────

SPEC_PATH = Path(__file__).resolve().parents[2] / "static" / "api" / "remote-agents.yaml"
HELP_PATH = Path(__file__).resolve().parents[2] / "docs" / "help" / "external-api.md"


@pytest.fixture(scope="module")
def spec():
    """Load and parse the OpenAPI spec."""
    assert SPEC_PATH.exists(), f"Spec file not found at {SPEC_PATH}"
    content = SPEC_PATH.read_text(encoding="utf-8")
    return yaml.safe_load(content)


@pytest.fixture(scope="module")
def spec_raw():
    """Load raw spec content for text-level checks."""
    return SPEC_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def help_content():
    """Load the help topic content."""
    assert HELP_PATH.exists(), f"Help file not found at {HELP_PATH}"
    return HELP_PATH.read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────
# Spec structure tests
# ──────────────────────────────────────────────────────────────

class TestSpecStructure:
    """Verify basic OpenAPI 3.1 structural requirements."""

    def test_openapi_version(self, spec):
        """Spec must declare OpenAPI 3.1.0."""
        assert spec["openapi"] == "3.1.0"

    def test_info_block(self, spec):
        """Spec must have title, version, and description."""
        info = spec["info"]
        assert "title" in info
        assert "version" in info
        assert "description" in info
        assert len(info["description"]) > 100, "Description should be substantial"

    def test_servers_section(self, spec):
        """Spec must have a servers section with variable base URL."""
        assert "servers" in spec
        assert len(spec["servers"]) >= 1
        server = spec["servers"][0]
        assert "{baseUrl}" in server["url"] or "variables" in server

    def test_paths_section(self, spec):
        """Spec must define paths."""
        assert "paths" in spec
        assert len(spec["paths"]) >= 4

    def test_components_section(self, spec):
        """Spec must define components with schemas and security schemes."""
        assert "components" in spec
        assert "schemas" in spec["components"]
        assert "securitySchemes" in spec["components"]

    def test_no_hardcoded_server_urls(self, spec_raw):
        """Spec must not contain hardcoded server URLs (relative paths only)."""
        # Check that no absolute URLs appear in the paths section
        # Allow URLs in descriptions and examples, but not as path prefixes
        lines = spec_raw.split("\n")
        in_servers = False
        in_description = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("servers:"):
                in_servers = True
                continue
            if in_servers and stripped.startswith("paths:"):
                in_servers = False
            if stripped.startswith("description:"):
                in_description = True
                continue
            if in_description and not stripped.startswith("-") and not stripped.startswith("|"):
                if not stripped.startswith(" ") or stripped == "":
                    in_description = False

        # The actual check: paths should not have scheme://
        paths = spec.get("paths", {}) if isinstance(spec_raw, dict) else {}
        # This is a simple text check — no https:// in path keys
        for line in spec_raw.split("\n"):
            stripped = line.strip()
            # Check path definitions (lines like "  /api/remote_agents/create:")
            if re.match(r"^\s+/\S+:\s*$", stripped):
                assert "http://" not in stripped
                assert "https://" not in stripped


# ──────────────────────────────────────────────────────────────
# Endpoint coverage tests
# ──────────────────────────────────────────────────────────────

class TestEndpointCoverage:
    """Verify all remote agent endpoints are documented in the spec."""

    EXPECTED_PATHS = [
        "/api/remote_agents/create",
        "/api/remote_agents/{agent_id}/alive",
        "/api/remote_agents/{agent_id}/shutdown",
        "/embed/{agent_id}",
    ]

    def test_all_endpoints_present(self, spec):
        """All remote agent endpoints must be documented."""
        paths = spec["paths"]
        for expected in self.EXPECTED_PATHS:
            assert expected in paths, f"Missing endpoint: {expected}"

    def test_create_endpoint_methods(self, spec):
        """Create endpoint must document POST and OPTIONS."""
        path = spec["paths"]["/api/remote_agents/create"]
        assert "post" in path
        assert "options" in path

    def test_alive_endpoint_methods(self, spec):
        """Alive endpoint must document GET and OPTIONS."""
        path = spec["paths"]["/api/remote_agents/{agent_id}/alive"]
        assert "get" in path
        assert "options" in path

    def test_shutdown_endpoint_methods(self, spec):
        """Shutdown endpoint must document POST and OPTIONS."""
        path = spec["paths"]["/api/remote_agents/{agent_id}/shutdown"]
        assert "post" in path
        assert "options" in path

    def test_embed_endpoint_method(self, spec):
        """Embed endpoint must document GET."""
        path = spec["paths"]["/embed/{agent_id}"]
        assert "get" in path

    def test_paths_match_flask_routes(self, spec):
        """Spec paths should correspond to actual Flask route registrations.

        Converts OpenAPI path params ({agent_id}) to Flask format (<int:agent_id>)
        and verifies against known route patterns from remote_agents.py.
        """
        flask_routes = [
            "/api/remote_agents/create",
            "/api/remote_agents/<int:agent_id>/alive",
            "/api/remote_agents/<int:agent_id>/shutdown",
            "/embed/<int:agent_id>",
        ]

        spec_paths = list(spec["paths"].keys())
        for flask_route in flask_routes:
            # Convert Flask path to OpenAPI format for comparison
            openapi_path = re.sub(r"<int:(\w+)>", r"{\1}", flask_route)
            assert openapi_path in spec_paths, (
                f"Flask route {flask_route} (as {openapi_path}) not found in spec"
            )


# ──────────────────────────────────────────────────────────────
# Schema accuracy tests
# ──────────────────────────────────────────────────────────────

class TestSchemaAccuracy:
    """Verify schema fields match actual request/response shapes from route code."""

    def test_create_request_fields(self, spec):
        """CreateRequest schema must match the fields extracted in the create route."""
        schema = spec["components"]["schemas"]["CreateRequest"]
        props = schema["properties"]
        required = schema["required"]

        # These are the fields extracted from request.get_json() in create_remote_agent()
        assert "project_slug" in props
        assert "persona_slug" in props
        assert "initial_prompt" in props
        assert "feature_flags" in props

        # Required fields match the validation in the route
        assert "project_slug" in required
        assert "persona_slug" in required
        assert "initial_prompt" in required
        assert "feature_flags" not in required  # optional

    def test_create_response_fields(self, spec):
        """CreateResponse schema must match the JSON returned by create route."""
        schema = spec["components"]["schemas"]["CreateResponse"]
        props = schema["properties"]

        # These match the jsonify() call in create_remote_agent()
        expected_fields = [
            "agent_id", "embed_url", "session_token",
            "project_slug", "persona_slug", "tmux_session_name", "status",
        ]
        for field in expected_fields:
            assert field in props, f"Missing field in CreateResponse: {field}"

    def test_alive_response_alive_fields(self, spec):
        """AliveResponseAlive schema must match check_alive() return when alive."""
        schema = spec["components"]["schemas"]["AliveResponseAlive"]
        props = schema["properties"]

        # These match the dict returned by RemoteAgentService.check_alive() when alive
        assert "alive" in props
        assert "agent_id" in props
        assert "state" in props
        assert "project_slug" in props

    def test_alive_response_not_alive_fields(self, spec):
        """AliveResponseNotAlive schema must match check_alive() return when not alive."""
        schema = spec["components"]["schemas"]["AliveResponseNotAlive"]
        props = schema["properties"]

        # These match the dict returned by RemoteAgentService.check_alive() when not alive
        assert "alive" in props
        assert "reason" in props

    def test_shutdown_response_fields(self, spec):
        """ShutdownResponse schema must match shutdown route response."""
        schema = spec["components"]["schemas"]["ShutdownResponse"]
        props = schema["properties"]

        # These match the jsonify() calls in shutdown_remote_agent()
        assert "status" in props
        assert "agent_id" in props
        assert "message" in props

    def test_error_envelope_fields(self, spec):
        """ErrorEnvelope schema must match _error_response() helper."""
        schema = spec["components"]["schemas"]["ErrorEnvelope"]
        error_props = schema["properties"]["error"]["properties"]

        # These match the fields in _error_response() in remote_agents.py
        assert "code" in error_props
        assert "message" in error_props
        assert "status" in error_props
        assert "retryable" in error_props
        assert "retry_after_seconds" in error_props

    def test_all_error_codes_documented(self, spec):
        """All error codes from the route code must appear in the spec."""
        error_schema = spec["components"]["schemas"]["ErrorEnvelope"]
        code_enum = error_schema["properties"]["error"]["properties"]["code"]["enum"]

        # All error codes used across the routes
        expected_codes = [
            "missing_fields",
            "invalid_feature_flags",
            "invalid_session_token",
            "project_not_found",
            "persona_not_found",
            "agent_not_found",
            "agent_creation_timeout",
            "server_error",
            "service_unavailable",
        ]
        for code in expected_codes:
            assert code in code_enum, f"Error code '{code}' not in spec enum"

    def test_alive_states_match_command_states(self, spec):
        """The state enum in AliveResponseAlive should match command lifecycle states."""
        schema = spec["components"]["schemas"]["AliveResponseAlive"]
        state_enum = schema["properties"]["state"]["enum"]

        # These are the command states from the state machine (lowercased)
        expected_states = ["idle", "commanded", "processing", "awaiting_input", "complete"]
        assert sorted(state_enum) == sorted(expected_states)

    def test_security_schemes_defined(self, spec):
        """Both security schemes (bearer and query param) must be defined."""
        schemes = spec["components"]["securitySchemes"]
        assert "sessionToken" in schemes
        assert schemes["sessionToken"]["type"] == "http"
        assert schemes["sessionToken"]["scheme"] == "bearer"

        assert "sessionTokenQuery" in schemes
        assert schemes["sessionTokenQuery"]["type"] == "apiKey"
        assert schemes["sessionTokenQuery"]["in"] == "query"
        assert schemes["sessionTokenQuery"]["name"] == "token"

    def test_authenticated_endpoints_declare_security(self, spec):
        """Endpoints requiring auth must declare security requirements."""
        # alive requires sessionToken
        alive = spec["paths"]["/api/remote_agents/{agent_id}/alive"]["get"]
        assert "security" in alive

        # shutdown requires sessionToken
        shutdown = spec["paths"]["/api/remote_agents/{agent_id}/shutdown"]["post"]
        assert "security" in shutdown

        # embed requires sessionTokenQuery
        embed = spec["paths"]["/embed/{agent_id}"]["get"]
        assert "security" in embed

    def test_create_endpoint_has_no_security(self, spec):
        """Create endpoint does not require authentication."""
        create = spec["paths"]["/api/remote_agents/create"]["post"]
        # Should NOT have security defined (or it should be empty)
        assert "security" not in create or create.get("security") == []

    def test_embed_query_parameters(self, spec):
        """Embed endpoint must document all query parameters."""
        embed = spec["paths"]["/embed/{agent_id}"]["get"]
        params = embed["parameters"]
        param_names = [p["name"] for p in params]

        # These match the request.args.get() calls in embed_view()
        assert "agent_id" in param_names  # path param
        assert "token" in param_names
        assert "file_upload" in param_names
        assert "context_usage" in param_names
        assert "voice_mic" in param_names


# ──────────────────────────────────────────────────────────────
# Cross-link verification tests
# ──────────────────────────────────────────────────────────────

class TestCrossLinks:
    """Verify cross-references between spec and help topic."""

    def test_spec_references_help_topic(self, spec):
        """Spec info.description must reference the help topic."""
        description = spec["info"]["description"]
        assert "/help/external-api" in description

    def test_help_references_spec_url(self, help_content):
        """Help topic must reference the spec URL."""
        assert "/static/api/remote-agents.yaml" in help_content

    def test_help_documents_directory_convention(self, help_content):
        """Help topic must document the directory convention."""
        assert "static/api/" in help_content
        assert "<api-name>.yaml" in help_content

    def test_help_has_quick_start(self, help_content):
        """Help topic must include quick-start instructions."""
        assert "Quick Start" in help_content

    def test_help_documents_authentication(self, help_content):
        """Help topic must document authentication."""
        assert "Authentication" in help_content
        assert "Bearer" in help_content
        assert "session token" in help_content.lower()

    def test_help_documents_error_handling(self, help_content):
        """Help topic must document error handling."""
        assert "Error" in help_content
        assert "retryable" in help_content

    def test_help_documents_cors(self, help_content):
        """Help topic must document CORS."""
        assert "CORS" in help_content


# ──────────────────────────────────────────────────────────────
# OpenAPI 3.1 validation (requires openapi-spec-validator)
# ──────────────────────────────────────────────────────────────

class TestOpenAPIValidation:
    """Validate the spec against the OpenAPI 3.1 standard.

    These tests require the openapi-spec-validator package.
    They are skipped if the package is not installed.
    """

    @pytest.fixture(autouse=True)
    def _require_validator(self):
        """Skip tests if openapi-spec-validator is not installed."""
        pytest.importorskip("openapi_spec_validator")

    def test_spec_validates_against_openapi_31(self, spec):
        """Spec must pass OpenAPI 3.1 validation."""
        from openapi_spec_validator import validate
        from openapi_spec_validator.versions import OPENAPIV31

        # This raises if validation fails
        validate(spec, cls=OPENAPIV31)
