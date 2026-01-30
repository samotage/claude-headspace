---
validation:
  status: valid
  validated_at: '2026-01-30T13:38:56+11:00'
---

## Product Requirements Document (PRD) — Git Analyzer & Progress Summary

**Project:** Claude Headspace v3.1
**Scope:** Epic 3, Sprint 4 — Git-based progress summary generation for project context restoration
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

Claude Headspace tracks real-time agent activity across projects, but lacks a historical view of what has been accomplished. Developers returning to a project after days or weeks have no concise summary of progress — only raw git logs. This PRD defines a git analyzer service that extracts commit history from target project repositories and a progress summary generator that produces LLM-powered narrative summaries of accomplishments.

The progress summary is a repo artifact: a markdown file written to the target project's `docs/brain_reboot/` directory (not stored in Claude Headspace). Previous versions are archived with date timestamps before overwriting. The commit scope is configurable — since last generation, last N commits, or time-based — and generation is triggered manually via a dashboard button or API endpoint.

This sprint provides the "what's been done" half of the brain reboot system (E3-S5), which combines progress_summary with waypoint for full context restoration. Success is measured by: accurate git extraction across scope modes, readable narrative summaries, correct file placement and archiving in target repos, and graceful handling of non-git projects and error conditions.

---

## 1. Context & Purpose

### 1.1 Context

Claude Headspace monitors Claude Code sessions across multiple projects. Epic 1 established the core architecture with Project models containing filesystem paths to target repositories. Epic 2 added waypoint editing for the "path ahead" view. Epic 3 adds the intelligence layer, with E3-S1 providing inference infrastructure and E3-S2 providing turn/task summarisation.

This sprint adds the complementary historical view: what has been accomplished in each project, derived from git commit history and rendered as a human-readable narrative by the LLM inference service.

The conceptual overview (Section 6) defines repo artifacts as markdown files stored in each target project's repository — not in Claude Headspace itself. Progress summaries follow this pattern:

```
<target_project>/
└── docs/
    └── brain_reboot/
        ├── progress_summary.md              (current)
        └── archive/
            ├── progress_summary_2025-01-10.md
            ├── progress_summary_2025-01-20.md
            └── ...
```

The system already has:
- Flask application with blueprints and service injection (`app.extensions`)
- PostgreSQL database with SQLAlchemy models and Alembic migrations
- Project model with `path` field pointing to target project repositories
- Configuration via `config.yaml` with environment variable overrides
- E3-S1 inference service with model selection by level, caching, and InferenceCall logging
- Dashboard with project panels and SSE real-time updates

**Prerequisite:** E3-S1 (OpenRouter Integration & Inference Service) must be complete before this sprint begins.

### 1.2 Target User

The primary user is the Claude Headspace dashboard operator — a developer managing multiple projects who needs to quickly understand what has been accomplished in each project without manually reading git logs. Progress summaries serve both direct reading and as input to the brain reboot system (E3-S5).

### 1.3 Success Moment

A developer clicks "Generate Progress Summary" on a project they haven't touched in two weeks. Within seconds, the dashboard displays a clear narrative: what features were built, what bugs were fixed, and where the project currently stands — all derived automatically from git history. The summary is also saved to the project's repository for future reference and brain reboot generation.

---

## 2. Scope

### 2.1 In Scope

- Git analyzer service that extracts commit history from target project repositories (commit messages, authors, files changed, date ranges)
- Progress summary generator that produces a 3-5 paragraph narrative from git analysis
- Configurable commit scope: since last generation (default), last N commits, or time-based (last N days)
- Configurable maximum commit cap to prevent excessive prompt sizes from large histories
- Write `progress_summary.md` to each target project's `docs/brain_reboot/` directory
- Generated file includes a metadata header (generation timestamp, scope used, date range, commit count)
- Archive previous `progress_summary.md` with date timestamp before overwriting (`archive/progress_summary_YYYY-MM-DD.md`)
- Create `docs/brain_reboot/` and `archive/` directory structure if missing
- Dashboard UI: "Generate Progress Summary" button per project in the project panel
- Dashboard UI: display generated progress summary content in the project panel
- Dashboard UI: in-progress indicator while generation is running
- Concurrent generation guard: one generation per project at a time
- API endpoint: POST `/api/projects/<id>/progress-summary` — trigger generation
- API endpoint: GET `/api/projects/<id>/progress-summary` — retrieve current summary
- Configuration schema additions for progress summary settings
- Prompt template for progress summary generation (as design guidance)
- Graceful error handling for non-git projects, permission failures, empty histories, and git command failures

### 2.2 Out of Scope

- OpenRouter API client and inference service infrastructure (E3-S1, prerequisite)
- Turn/task summarisation (E3-S2)
- Priority scoring (E3-S3)
- Brain reboot generation combining waypoint + progress_summary (E3-S5)
- Waypoint management (E2-S2, already complete)
- Auto-trigger on significant commit activity (deferred — manual generation only for initial release)
- Full diff inclusion in git analysis (commit messages + file list only)
- Archive retention limits (all versions are kept)
- Git write operations (no commits or pushes to target repos — read-only git access)
- User editing of generated summaries via dashboard
- Scheduled or cron-based generation

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Git analyzer extracts commits from a target project's repository using the configured commit scope
2. All three commit scopes work correctly: since_last (commits since previous generation), last_n (most recent N commits), time_based (commits within last N days)
3. Progress summary is generated as a 3-5 paragraph narrative from the extracted commit data
4. `progress_summary.md` is written to `docs/brain_reboot/` in the target project's repository with a metadata header
5. Previous version is archived as `archive/progress_summary_YYYY-MM-DD.md` before the new version is written
6. Directory structure (`docs/brain_reboot/`, `archive/`) is created automatically if missing
7. Dashboard shows "Generate Progress Summary" button per project
8. Generated summary is viewable in the project panel on the dashboard
9. POST `/api/projects/<id>/progress-summary` triggers generation and returns the result
10. GET `/api/projects/<id>/progress-summary` returns the current summary content

### 3.2 Non-Functional Success Criteria

1. Non-git projects are detected and handled gracefully — clear feedback without errors or crashes
2. File permission failures are handled gracefully — error logged, user informed, no crash
3. Projects with no commits in the configured scope receive a clear message rather than an empty or failed summary
4. Only one generation runs per project at a time — concurrent requests receive an "in progress" status
5. Progress summary generation uses a capable model appropriate for narrative generation quality

---

## 4. Functional Requirements (FRs)

### Git Analysis

**FR1:** The system shall extract commit history from a target project's git repository, including: commit hash, commit message, author, timestamp, and list of files changed per commit.

**FR2:** The system shall support three configurable commit scopes for determining which commits to analyse:
- **since_last:** All commits since the last progress summary was generated (determined by the metadata in the existing `progress_summary.md`)
- **last_n:** The most recent N commits (N configurable)
- **time_based:** All commits within the last N days (N configurable)

**FR3:** The default commit scope shall be "since_last". If no previous summary exists, the system shall fall back to the "last_n" scope.

**FR4:** The system shall enforce a configurable maximum number of commits to include in a single analysis, selecting the most recent commits when the scope exceeds the cap.

**FR5:** The git analyzer shall produce a structured analysis result containing: the list of commits, unique files changed across all commits, unique authors, date range (earliest to latest commit), and total commit count.

### Progress Summary Generation

**FR6:** The progress summary generator shall produce a 3-5 paragraph narrative summarising: what major work was completed, what features or fixes were implemented, the current state of the project, and any patterns or themes in the work.

**FR7:** The progress summary generator shall include as context for the LLM prompt: the project name, date range, commit count, individual commit details (hash prefix, message, author, timestamp), and the list of files changed.

**FR8:** The generated narrative shall be written in past tense, focusing on accomplishments.

**FR9:** All progress summary inference calls shall be made through the E3-S1 inference service at the "project" inference level, using a model appropriate for narrative generation quality.

**FR10:** Inference calls shall include the correct entity associations (project ID) so that InferenceCall records are linked to the relevant project.

### File Output & Archiving

**FR11:** The generated progress summary shall be written to `{project.path}/docs/brain_reboot/progress_summary.md` in the target project's repository.

**FR12:** The generated file shall include a metadata header containing: generation timestamp, commit scope used, date range of commits analysed, and total commit count.

**FR13:** Before writing a new `progress_summary.md`, the system shall archive the existing file (if present) to `{project.path}/docs/brain_reboot/archive/progress_summary_YYYY-MM-DD.md` where the date is the archive date.

**FR14:** If the archive directory already contains a file with the same date-stamped name, the system shall append a numeric suffix to avoid overwriting (e.g., `progress_summary_2025-01-28_2.md`).

**FR15:** The system shall create the `docs/brain_reboot/` and `archive/` directory structure in the target project if it does not exist.

**FR16:** The system shall archive the previous file before writing the new one, so that if the new write fails, the archived version is preserved.

### API Endpoints

**FR17:** POST `/api/projects/<id>/progress-summary` shall trigger progress summary generation for the specified project. The request may optionally specify a commit scope override; if not provided, the configured default scope shall be used.

**FR18:** POST `/api/projects/<id>/progress-summary` shall return the generated summary content along with generation metadata (scope used, commit count, date range).

**FR19:** GET `/api/projects/<id>/progress-summary` shall return the current `progress_summary.md` content for the specified project. If no summary exists, it shall return an appropriate empty response (404 or empty content with status indication).

**FR20:** Both endpoints shall return appropriate error responses when the specified project does not exist (404), when the project is not a git repository (422), or when generation is already in progress (409).

### Concurrent Generation Guard

**FR21:** Only one progress summary generation shall run per project at a time. If a generation request arrives while one is already in progress for the same project, the system shall return a "generation in progress" status without starting a duplicate.

**FR22:** The in-progress state shall be cleared when generation completes (successfully or with error), ensuring the project is not permanently locked.

### Dashboard Integration

**FR23:** The project panel on the dashboard shall include a "Generate Progress Summary" button for each project.

**FR24:** While generation is in progress, the button shall display an in-progress indicator and be disabled to prevent duplicate requests.

**FR25:** After generation completes, the progress summary content shall be displayed in the project panel.

**FR26:** If generation fails, the dashboard shall display an informative error message in the project panel.

### Error Handling

**FR27:** When the target project path is not a git repository, the system shall return a clear error indicating the project does not have git history available. The "Generate" button shall still be visible but the error shall be shown on click.

**FR28:** When a file write or archive operation fails due to permission errors, the system shall log the error, report the failure to the user via the API response, and not corrupt any existing files.

**FR29:** When the configured commit scope returns zero commits, the system shall return a clear message ("No commits found in configured scope") without calling the inference service.

**FR30:** Failed inference calls during generation shall be logged via the E3-S1 InferenceCall system with the error recorded. The user shall be informed that generation failed.

### Configuration

**FR31:** The `config.yaml` file shall include a `progress_summary` section with: default commit scope (`since_last`, `last_n`, or `time_based`), the N value for `last_n` scope, the N value for `time_based` scope (days), and the maximum commit cap.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Git operations shall be read-only — the system shall never modify, commit to, or push to target project repositories.

**NFR2:** Progress summary generation shall not block the Flask request thread. The POST endpoint shall initiate generation asynchronously and return immediately with an accepted status, or perform generation synchronously if it completes within a reasonable request timeout.

**NFR3:** File I/O operations on target project directories shall handle permission errors, missing directories, and disk space issues without crashing the application.

**NFR4:** The git analyzer shall handle edge cases gracefully: detached HEAD, shallow clones, empty repositories, and repositories with no commits in the configured scope.

**NFR5:** The system shall start and remain operational when target project paths are inaccessible, with progress summary features degraded for those projects but all other dashboard functionality unaffected.

**NFR6:** The commit cap shall prevent excessively large prompts — the system shall truncate to the most recent commits within scope when the cap is reached.

---

## 6. UI Overview

### Project Panel — Generate Button

Each project panel on the dashboard shall include a "Generate Progress Summary" button:

- **Idle state:** Button enabled, labelled "Generate Progress Summary"
- **In-progress state:** Button disabled, showing a generation indicator (e.g., spinner or "Generating...")
- **Error state:** Button re-enabled, error message displayed below

### Project Panel — Summary Display

Below the generate button, the project panel shall display the progress summary content:

- **Summary available:** Render the narrative text with generation metadata (date, scope, commit count)
- **No summary:** Display a message indicating no summary has been generated yet
- **Generation failed:** Display the error message from the most recent failed attempt

### Interaction Flow

1. User clicks "Generate Progress Summary" on a project panel
2. Button transitions to in-progress state
3. Generation runs (git analysis → LLM inference → file write)
4. On success: summary content appears in the project panel, button returns to idle
5. On failure: error message appears, button returns to idle

---

## 7. Prompt Design Guidance

The following prompt template represents the recommended approach for progress summary generation. It expresses the **intent** of what the summary should cover and the context to include. Exact wording may be refined during implementation.

### Progress Summary Prompt

```
Generate a narrative progress summary for this project based on recent git activity.

Project: {project.name}
Date Range: {start_date} to {end_date}
Commit Count: {commit_count}

Recent Commits:
{for commit in commits}
- {commit.hash[:8]}: {commit.message} ({commit.author}, {commit.timestamp})
{endfor}

Files Changed: {files_changed}

Write a 3-5 paragraph narrative summarising:
1. What major work was completed
2. What features or fixes were implemented
3. Current state of the project
4. Any patterns or themes in the work

Write in past tense, focus on accomplishments.
```

### Prompt Design Principles

- The narrative should be readable by someone unfamiliar with the project's daily activity
- Focus on accomplishments and outcomes, not individual commits
- Group related work into themes (e.g., "authentication improvements", "test coverage expansion")
- Use past tense throughout — this is a record of what was done
- The model should be capable of producing coherent multi-paragraph narratives from structured commit data
- Keep the narrative concise (3-5 paragraphs) — this is a summary, not a changelog
