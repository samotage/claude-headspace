## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

- [x] 2.1 Create registration service (`services/persona_registration.py`) with `register_persona()` function — role lookup/create, persona insert, filesystem asset creation, result dataclass
- [x] 2.2 Create Flask CLI command group (`cli/persona_cli.py`) with `flask persona register` command using Click
- [x] 2.3 Register CLI group in app factory (`app.py`)
- [x] 2.4 Create REST API endpoint (`routes/personas.py`) with `POST /api/personas/register` returning JSON
- [x] 2.5 Register personas blueprint in app factory (`app.py`)

## 3. Testing (Phase 3)

- [x] 3.1 Unit tests for registration service (`tests/services/test_persona_registration.py`) — role create/reuse, persona creation, slug generation, validation errors, partial failure handling, duplicate handling
- [x] 3.2 Route tests for API endpoint (`tests/routes/test_personas.py`) — success 201, validation 400, JSON response format
- [x] 3.3 Integration tests (`tests/integration/test_persona_registration.py`) — end-to-end registration with real DB + filesystem via tmp_path

## 4. Final Verification

- [x] 4.1 All tests passing
- [x] 4.2 No linter errors
- [x] 4.3 Manual verification complete
