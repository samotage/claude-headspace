---
validation:
  status: valid
  validated_at: '2026-02-02T13:01:24+11:00'
---

## Product Requirements Document (PRD) — Archive System

**Project:** Claude Headspace
**Scope:** Centralized artifact archiving with retention policies and retrieval API
**Author:** PRD Workshop (AI-assisted)
**Status:** Draft

---

## Executive Summary

Claude Headspace manages three key brain_reboot artifacts per monitored project: `waypoint.md`, `progress_summary.md`, and `brain_reboot.md`. These artifacts are overwritten in-place when new versions are created, losing previous context. Two of the three artifacts (waypoint and progress_summary) already have ad-hoc inline archiving with date-only filenames and integer collision counters — an inconsistent and fragile pattern. Brain reboot has no archiving at all.

This PRD defines a centralized archive system that replaces the scattered inline archive logic with a unified service. All artifacts are archived with second-precision timestamps (`YYYY-MM-DD_HH-MM-SS`), eliminating the need for collision counters. The service adds configurable retention policies (keep all, keep last N, or time-based), and exposes archive listing and retrieval via API endpoints. Exporting a brain_reboot cascades to also archive its source artifacts (waypoint and progress_summary), capturing a complete point-in-time snapshot.

The result is a clean, consistent archive system that preserves developer context history, enables future dashboard browsing of artifact versions, and prevents unbounded disk growth in monitored project repositories.

---

## 1. Context & Purpose

### 1.1 Context

Brain_reboot artifacts (`waypoint.md`, `progress_summary.md`, `brain_reboot.md`) are the developer's working memory for each monitored project. They are overwritten when new versions are saved or generated. Without archiving, previous versions — and the context they contain — are permanently lost.

Archive logic currently exists inline in two services (`waypoint_editor.py` and `progress_summary.py`) with inconsistent patterns: different atomicity guarantees, date-only filenames with integer counters for same-day collisions, and no retention management. The third artifact (`brain_reboot.md`) has no archiving at all.

Adding brain_reboot archiving is the trigger to consolidate all archive logic into a proper centralized service.

### 1.2 Target User

Developers using Claude Headspace to monitor Claude Code sessions across multiple projects. The archive system operates transparently — users benefit from preserved history without managing it manually.

### 1.3 Success Moment

A developer returns to a project after a week, opens the archive listing, and can see how their waypoint priorities evolved over time — confirming that no context was lost during their absence.

---

## 2. Scope

### 2.1 In Scope

- Centralized archiving capability for all three brain_reboot artifact types (waypoint, progress_summary, brain_reboot)
- Proper `YYYY-MM-DD_HH-MM-SS` timestamp format for all archive filenames, replacing the existing date-only format with integer counters
- Cascading archive: exporting brain_reboot also archives current waypoint and progress_summary
- Automatic archive directory creation (`docs/brain_reboot/archive/`)
- Configurable retention policy (`keep_all`, `keep_last_n`, `time_based`) via `config.yaml`
- Retention enforcement after each archive operation
- Archive listing API endpoint
- Archive retrieval API endpoint
- Removal of inline archive code from `waypoint_editor.py` and `progress_summary.py`, replaced with delegation to the centralized service
- Addition of archive triggering to `brain_reboot.py` export

### 2.2 Out of Scope

- Archive browsing UI in the dashboard (future work)
- Diffing or comparison between archived versions
- Archive compression or binary artifact support
- Migration of existing archive files (none exist)
- Changes to brain_reboot generation logic (only export triggers archiving)
- Archiving of config.yaml or non-brain_reboot files
- Cross-project archive operations

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Saving a waypoint via the UI archives the previous version as `waypoint_YYYY-MM-DD_HH-MM-SS.md`
2. Generating a progress_summary archives the previous version as `progress_summary_YYYY-MM-DD_HH-MM-SS.md`
3. Exporting a brain_reboot archives the previous brain_reboot (if it exists) AND archives the current waypoint and progress_summary
4. Archive directory (`docs/brain_reboot/archive/`) is created automatically if missing
5. `GET /api/projects/<id>/archives` returns a list of all archived versions grouped by artifact type
6. `GET /api/projects/<id>/archives/<artifact>/<timestamp>` returns the content of a specific archived version
7. Retention policy is configurable in `config.yaml` and enforced after each archive operation
8. No counter-based collision filenames exist — all archives use second-precision timestamps
9. The previous date-only archive format with integer counters is fully removed from the codebase

### 3.2 Non-Functional Success Criteria

1. Archive operations do not corrupt existing files on failure (archive completes before overwrite)
2. Cascading archive is best-effort — failure to archive one artifact does not block archiving of others or the primary operation
3. Archive and retention operations add negligible latency to save/generate/export operations
4. Concurrent archive operations for the same project do not cause data loss (second-precision timestamps provide natural uniqueness)

---

## 4. Functional Requirements (FRs)

### Archive Operations

**FR1:** When a waypoint is saved, the previous version of `waypoint.md` is archived before the new content is written.

**FR2:** When a progress summary is generated, the previous version of `progress_summary.md` is archived before the new content is written.

**FR3:** When a brain reboot is exported, the previous version of `brain_reboot.md` is archived (if it exists) before the new content is written.

**FR4:** When a brain reboot is exported, the current `waypoint.md` and `progress_summary.md` are also archived (cascading archive), capturing a point-in-time snapshot of all source artifacts.

**FR5:** All archive filenames follow the format `{artifact}_{YYYY-MM-DD_HH-MM-SS}.md` using UTC timestamps.

**FR6:** The archive directory (`{project_path}/docs/brain_reboot/archive/`) is created automatically if it does not exist when an archive operation is triggered.

### Retention Policy

**FR7:** The retention policy is configurable in `config.yaml` with three modes:
- `keep_all` — retain all archived versions (default)
- `keep_last_n` — retain only the most recent N versions per artifact type
- `time_based` — retain versions created within the last N days

**FR8:** Retention is enforced after each archive operation, cleaning up versions that exceed the configured policy for the artifact type that was just archived.

**FR9:** The default retention policy is `keep_all`.

### Retrieval API

**FR10:** `GET /api/projects/<id>/archives` returns a list of all archived versions for the project, grouped by artifact type, with filename and timestamp for each entry.

**FR11:** `GET /api/projects/<id>/archives/<artifact>/<timestamp>` returns the full content of a specific archived version, where `<artifact>` is one of `waypoint`, `progress_summary`, or `brain_reboot`, and `<timestamp>` matches the `YYYY-MM-DD_HH-MM-SS` format.

**FR12:** The archive listing endpoint returns an empty list (not an error) when no archives exist for a project or artifact type.

**FR13:** The archive retrieval endpoint returns a 404 when the requested artifact/timestamp combination does not exist.

### Refactoring

**FR14:** The inline archive logic in `waypoint_editor.py` (`get_archive_filename()` function and archive block in `save_waypoint()`) is removed and replaced with delegation to the centralized archive capability.

**FR15:** The inline archive logic in `progress_summary.py` (`_archive_existing()` method) is removed and replaced with delegation to the centralized archive capability.

**FR16:** The `brain_reboot.py` `export()` method is updated to trigger archiving of the previous brain_reboot file and cascade to archive waypoint and progress_summary.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** Archive operations must complete before the primary write operation (archive-then-overwrite ordering) to prevent data loss.

**NFR2:** If an individual archive operation fails (e.g., permission error), it is logged and does not block the primary save/generate/export operation or other archive operations in a cascade.

**NFR3:** Retention cleanup failure is logged and does not block the archive or primary operation.

**NFR4:** Archive and retention operations targeting the same project are safe under concurrent access (second-precision timestamps provide natural filename uniqueness).

---

## 6. Config.yaml Addition

```yaml
archive:
  enabled: true
  retention:
    policy: keep_all    # keep_all, keep_last_n, time_based
    keep_last_n: 10     # Used when policy = keep_last_n
    days: 90            # Used when policy = time_based
```

---

## 7. API Endpoints

### List Archives

```
GET /api/projects/<id>/archives
```

Response:
```json
{
  "project_id": 1,
  "archives": {
    "waypoint": [
      {"filename": "waypoint_2026-01-28_14-30-00.md", "timestamp": "2026-01-28T14:30:00Z"},
      {"filename": "waypoint_2026-01-25_09-15-00.md", "timestamp": "2026-01-25T09:15:00Z"}
    ],
    "progress_summary": [
      {"filename": "progress_summary_2026-01-29_16-00-00.md", "timestamp": "2026-01-29T16:00:00Z"}
    ],
    "brain_reboot": [
      {"filename": "brain_reboot_2026-01-29_16-05-00.md", "timestamp": "2026-01-29T16:05:00Z"}
    ]
  }
}
```

### Retrieve Specific Archive

```
GET /api/projects/<id>/archives/<artifact>/<timestamp>
```

Response:
```json
{
  "artifact": "waypoint",
  "timestamp": "2026-01-28T14:30:00Z",
  "filename": "waypoint_2026-01-28_14-30-00.md",
  "content": "# Waypoint\n\n## Next Up\n..."
}
```

---

## 8. Integration Points

- Waypoint save operation (currently `waypoint_editor.py` `save_waypoint()`)
- Progress summary generation (currently `progress_summary.py` `_write_summary()`)
- Brain reboot export (currently `brain_reboot.py` `export()`)
- Project model for project filesystem paths
- Application configuration for retention policy settings

---

## 9. Archive Directory Structure

```
{project_path}/docs/brain_reboot/
├── waypoint.md                                  # Current version
├── progress_summary.md                          # Current version
├── brain_reboot.md                              # Current version (if exported)
└── archive/
    ├── waypoint_2026-01-28_14-30-00.md          # Previous versions
    ├── waypoint_2026-01-25_09-15-00.md
    ├── progress_summary_2026-01-29_16-00-00.md
    └── brain_reboot_2026-01-29_16-05-00.md
```
