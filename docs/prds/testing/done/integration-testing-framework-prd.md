---
validation:
  status: valid
  validated_at: '2026-01-31T10:02:32+11:00'
---

## Product Requirements Document (PRD) — Integration Testing Framework

**Project:** Claude Headspace
**Scope:** Replace mock-heavy database tests with real Postgres integration tests
**Author:** PRD Workshop
**Status:** Draft

---

## Executive Summary

Claude Headspace has 780+ tests, but the majority mock SQLAlchemy sessions, engines, and repository methods. These tests verify that mocks behave like mocks — they do not verify that the application correctly persists and retrieves data from a real database.

This PRD defines the requirements for a real integration testing framework that runs against a dedicated Postgres test database. Tests must create, persist, and retrieve actual data through the ORM, with automatic database lifecycle management and clean isolation between tests. The framework will use Factory Boy to generate valid, persistable model instances for all 6 domain models.

The existing mock-based unit tests remain for pure logic (state machine transitions, intent detection, config parsing), but any test verifying database persistence must use real database operations.

---

## 1. Context & Purpose

### 1.1 Context

The current test suite mocks database connections, SQLAlchemy sessions, and service layer dependencies extensively. This creates false confidence: tests pass even when the underlying persistence logic is broken. As new features are added, the risk of undetected database-level bugs increases. The application was built with mock-heavy testing from the start, and the foundation needs to be corrected before more features are built on top of it.

### 1.2 Target User

Developers working on Claude Headspace — primarily AI-assisted development workflows where test reliability directly impacts code quality and iteration speed.

### 1.3 Success Moment

A developer runs `pytest tests/integration/` and gets real confidence that the persistence layer works. A test creates a Project, attaches an Agent, creates a Task with Turns, writes an Event, retrieves them all back, and every assertion passes against actual Postgres data.

---

## 2. Scope

### 2.1 In Scope

- Automatic creation and teardown of a dedicated Postgres test database per test session
- Schema creation in the test database using existing Alembic migrations or model metadata
- Shared pytest fixtures for database session management with per-test cleanup
- Factory Boy factory definitions for all 6 existing domain models (Project, Agent, Task, Turn, Event, Objective) and ObjectiveHistory
- A `tests/integration/` directory for tests that verify real database operations
- Proof-of-concept integration tests covering the core persistence flow (Project → Agent → Task → Turn → Event)
- Addition of required dev dependencies (factory-boy and any test database utilities)
- A brief pattern document so future tests follow the same approach

### 2.2 Out of Scope

- Rewriting or removing existing mock-based unit tests
- CI/CD pipeline configuration or GitHub Actions setup
- Performance testing or load testing
- Test data seeding for manual QA or staging environments
- Changes to production database configuration or connection pooling
- SQLite support — the test database must be Postgres

---

## 3. Success Criteria

### 3.1 Functional Success Criteria

1. Running `pytest tests/integration/` executes tests against a real Postgres test database — not mocks, not SQLite
2. The test database is created automatically at the start of a test session and destroyed automatically at the end — no manual setup required
3. Database schema matches production schema (all tables, indexes, constraints, enums present)
4. Each test starts with a clean database state — no data leaks between tests
5. Factory Boy factories exist for all 6 domain models plus ObjectiveHistory, and each factory produces a valid, persistable model instance
6. At least one end-to-end persistence test creates a full entity chain (Project → Agent → Task → Turn → Event), persists it, retrieves it, and asserts data integrity
7. Integration tests can run alongside existing mock-based tests without interference (`pytest` runs everything, `pytest tests/integration/` runs only integration tests)

### 3.2 Non-Functional Success Criteria

1. Test database creation and teardown completes without requiring manual intervention or pre-existing database state
2. Integration test suite runs reliably on any developer machine with a local Postgres instance available
3. The testing pattern is documented clearly enough that a new developer (or AI agent) can write an integration test by following the example

---

## 4. Functional Requirements (FRs)

**FR1:** The test infrastructure must automatically create a dedicated Postgres test database (e.g., `claude_headspace_test`) at the beginning of a pytest session.

**FR2:** The test infrastructure must automatically drop the test database at the end of a pytest session, ensuring no persistent state remains.

**FR3:** The test database schema must be created using the project's existing model metadata or Alembic migrations, ensuring the test schema matches the production schema.

**FR4:** A shared pytest fixture must provide a database session scoped appropriately for test isolation, ensuring each test operates on a clean database state.

**FR5:** Factory Boy factories must be defined for each of the 6 domain models: Project, Agent, Task, Turn, Event, and Objective — plus ObjectiveHistory. Each factory must be bound to the test database session and must use `SQLAlchemyModelFactory`.

**FR6:** Each factory must produce a fully valid model instance that can be persisted to the database without constraint violations (correct foreign keys, valid enum values, non-null required fields, valid UUIDs).

**FR7:** Factory definitions must respect model relationships — e.g., an Agent factory must create or reference a valid Project, a Task factory must create or reference a valid Agent, a Turn factory must create or reference a valid Task.

**FR8:** Integration tests must be located in `tests/integration/` and must be independently runnable via `pytest tests/integration/`.

**FR9:** A proof-of-concept integration test must verify the complete persistence flow: create a Project, attach an Agent, create a Task for that Agent, add Turns to the Task, write an Event referencing the chain, then retrieve all entities and assert data equality.

**FR10:** Integration tests must not mock SQLAlchemy sessions, queries, engines, or repository methods. All database operations must execute against the real test database.

**FR11:** The testing pattern must be documented with examples showing how to write a new integration test using the fixtures and factories.

---

## 5. Non-Functional Requirements (NFRs)

**NFR1:** The test database must be Postgres — the same database engine used in production. SQLite is explicitly not acceptable.

**NFR2:** The test infrastructure must handle the case where the test database already exists (e.g., from a previous interrupted run) by dropping and recreating it.

**NFR3:** Test database connection configuration must be separate from production configuration, using either a dedicated config key or environment variable override.

---

## 6. UI Overview

Not applicable — this is developer infrastructure with no user-facing interface.
