## 1. Planning (Phase 1)

- [x] 1.1 Create OpenSpec proposal files
- [x] 1.2 Validate proposal with openspec validate
- [x] 1.3 Review and get approval

## 2. Implementation (Phase 2)

### 2.1 Database Migration

- [x] 2.1.1 Add `description` (Text, nullable), `inference_paused` (Boolean, not null, default false), `inference_paused_at` (DateTime(timezone=True), nullable), `inference_paused_reason` (Text, nullable) columns to `projects` table
- [x] 2.1.2 Update Project model in `models/project.py` with new fields
- [x] 2.1.3 Run migration and verify schema

### 2.2 Project CRUD Routes

- [x] 2.2.1 Create `src/claude_headspace/routes/projects.py` blueprint with:
  - `GET /api/projects` — list all projects with agent_count
  - `POST /api/projects` — create project (name, path required; github_repo, description optional); 201 on success, 409 on duplicate path
  - `GET /api/projects/<id>` — get project detail with agents list
  - `PUT /api/projects/<id>` — update project metadata; 200 on success, 404 not found, 409 path conflict
  - `DELETE /api/projects/<id>` — cascade delete project and agents; 200 on success, 404 not found
- [x] 2.2.2 Register `projects_bp` in `app.py` `register_blueprints()`

### 2.3 Project Settings Routes

- [x] 2.3.1 Add to `routes/projects.py`:
  - `GET /api/projects/<id>/settings` — get inference_paused, inference_paused_at, inference_paused_reason
  - `PUT /api/projects/<id>/settings` — set inference_paused (bool) and inference_paused_reason (optional); auto-set/clear inference_paused_at

### 2.4 SSE Broadcasting

- [x] 2.4.1 Broadcast `project_changed` SSE event (action: created/updated/deleted, project_id) on CRUD operations
- [x] 2.4.2 Broadcast `project_settings_changed` SSE event (project_id, inference_paused, inference_paused_at) on settings changes

### 2.5 Disable Auto-Discovery

- [x] 2.5.1 In `session_correlator.py` `_create_agent_for_session()`: remove Project auto-creation; raise `ValueError` with message directing user to register project when working directory doesn't match registered project
- [x] 2.5.2 In `routes/sessions.py` `create_session()`: remove Project auto-creation; return 404 with message directing user to register project when project_path doesn't match registered project
- [x] 2.5.3 Verify error messages include rejected path and reference to `/projects` management page

### 2.6 Inference Gating

- [x] 2.6.1 In `summarisation_service.py`: add inference pause check before `summarise_turn()`, `summarise_task()`, `summarise_instruction()` — return None if project.inference_paused, with debug log
- [x] 2.6.2 In `priority_scoring.py` `score_all_agents()`: filter out agents from paused projects in query; skip scoring entirely if all agents belong to paused projects

## 3. Testing (Phase 3)

### 3.1 Project CRUD Route Tests

- [x] 3.1.1 Create `tests/routes/test_projects.py`
  - Test GET /api/projects returns 200 with list including agent_count
  - Test POST /api/projects creates project and returns 201
  - Test POST /api/projects with duplicate path returns 409
  - Test POST /api/projects with missing required fields returns 400
  - Test GET /api/projects/<id> returns 200 with detail including agents
  - Test GET /api/projects/<id> returns 404 for missing
  - Test PUT /api/projects/<id> updates and returns 200
  - Test PUT /api/projects/<id> returns 404 for missing
  - Test PUT /api/projects/<id> with conflicting path returns 409
  - Test DELETE /api/projects/<id> returns 200
  - Test DELETE /api/projects/<id> returns 404 for missing

### 3.2 Project Settings Route Tests

- [x] 3.2.1 Add to `tests/routes/test_projects.py`
  - Test GET /api/projects/<id>/settings returns 200
  - Test PUT /api/projects/<id>/settings with inference_paused=true sets timestamp
  - Test PUT /api/projects/<id>/settings with inference_paused=false clears timestamp and reason
  - Test PUT /api/projects/<id>/settings returns 404 for missing project

### 3.3 Auto-Discovery Removal Tests

- [x] 3.3.1 Update `tests/services/test_session_correlator.py` — test ValueError raised for unregistered project
- [x] 3.3.2 Update `tests/routes/test_sessions.py` — test 404 returned for unregistered project

### 3.4 Inference Gating Tests

- [x] 3.4.1 Create `tests/services/test_inference_gating.py`
  - Test summarise_turn returns None when project inference_paused
  - Test summarise_task returns None when project inference_paused
  - Test summarise_instruction returns None when project inference_paused
  - Test score_all_agents excludes paused project agents
  - Test score_all_agents skips entirely when all agents paused

### 3.5 SSE Broadcasting Tests

- [x] 3.5.1 Test project CRUD operations broadcast project_changed events
- [x] 3.5.2 Test settings changes broadcast project_settings_changed events

## 4. Final Verification

- [x] 4.1 All tests passing
- [ ] 4.2 No linter errors
- [ ] 4.3 Manual verification complete
- [x] 4.4 Auto-discovery fully disabled (no Project auto-creation in codebase)
- [x] 4.5 Inference gating verified for all call paths
