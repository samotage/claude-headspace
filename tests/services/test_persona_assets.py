"""Unit tests for persona filesystem asset utilities.

Uses pytest tmp_path fixture — no database or Flask app context needed.
"""

import pytest
from pathlib import Path

from claude_headspace.services.persona_assets import (
    AssetStatus,
    EXPERIENCE_FILENAME,
    GUARDRAILS_DIR,
    GUARDRAILS_FILENAME,
    GuardrailValidationError,
    SKILL_FILENAME,
    check_assets,
    compute_guardrails_hash,
    create_persona_assets,
    create_persona_dir,
    get_current_guardrails_hash,
    get_experience_mtime,
    get_persona_dir,
    read_experience_file,
    read_skill_file,
    seed_experience_file,
    seed_skill_file,
    validate_guardrails_content,
    write_skill_file,
)


class TestGetPersonaDir:
    """Test path resolution from slug to directory."""

    def test_returns_correct_path(self, tmp_path):
        result = get_persona_dir("developer-con-1", project_root=tmp_path)
        assert result == tmp_path / "data" / "personas" / "developer-con-1"

    def test_custom_project_root(self, tmp_path):
        custom_root = tmp_path / "my-project"
        custom_root.mkdir()
        result = get_persona_dir("tester-bob-2", project_root=custom_root)
        assert result == custom_root / "data" / "personas" / "tester-bob-2"

    def test_empty_slug(self, tmp_path):
        result = get_persona_dir("", project_root=tmp_path)
        assert result == tmp_path / "data" / "personas" / ""


class TestCreatePersonaDir:
    """Test directory creation with parent directories."""

    def test_creates_directory_with_parents(self, tmp_path):
        result = create_persona_dir("developer-con-1", project_root=tmp_path)
        assert result.is_dir()
        assert result == tmp_path / "data" / "personas" / "developer-con-1"

    def test_idempotent(self, tmp_path):
        create_persona_dir("developer-con-1", project_root=tmp_path)
        # Call again — should not raise
        result = create_persona_dir("developer-con-1", project_root=tmp_path)
        assert result.is_dir()


class TestSeedSkillFile:
    """Test skill.md template seeding."""

    def test_creates_file_with_template(self, tmp_path):
        path = seed_skill_file("developer-con-1", "Con", "developer", project_root=tmp_path)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "# Con — developer" in content
        assert "## Core Identity" in content
        assert "## Skills & Preferences" in content
        assert "## Communication Style" in content

    def test_does_not_overwrite_existing(self, tmp_path):
        seed_skill_file("developer-con-1", "Con", "developer", project_root=tmp_path)
        skill_path = get_persona_dir("developer-con-1", tmp_path) / SKILL_FILENAME
        skill_path.write_text("custom content", encoding="utf-8")

        # Call again — should NOT overwrite
        seed_skill_file("developer-con-1", "Con", "developer", project_root=tmp_path)
        assert skill_path.read_text(encoding="utf-8") == "custom content"


class TestSeedExperienceFile:
    """Test experience.md template seeding."""

    def test_creates_file_with_template(self, tmp_path):
        path = seed_experience_file("developer-con-1", "Con", project_root=tmp_path)
        assert path.exists()
        content = path.read_text(encoding="utf-8")
        assert "# Experience Log — Con" in content
        assert "Append-only" in content

    def test_does_not_overwrite_existing(self, tmp_path):
        seed_experience_file("developer-con-1", "Con", project_root=tmp_path)
        exp_path = get_persona_dir("developer-con-1", tmp_path) / EXPERIENCE_FILENAME
        exp_path.write_text("my experience", encoding="utf-8")

        # Call again — should NOT overwrite
        seed_experience_file("developer-con-1", "Con", project_root=tmp_path)
        assert exp_path.read_text(encoding="utf-8") == "my experience"


class TestCreatePersonaAssets:
    """Test combined directory and template creation."""

    def test_creates_directory_and_both_files(self, tmp_path):
        result = create_persona_assets("developer-con-1", "Con", "developer", project_root=tmp_path)
        assert result.is_dir()
        assert (result / SKILL_FILENAME).exists()
        assert (result / EXPERIENCE_FILENAME).exists()

    def test_idempotent(self, tmp_path):
        create_persona_assets("developer-con-1", "Con", "developer", project_root=tmp_path)
        persona_dir = get_persona_dir("developer-con-1", tmp_path)
        skill_path = persona_dir / SKILL_FILENAME
        original_content = skill_path.read_text(encoding="utf-8")

        # Overwrite with custom content
        skill_path.write_text("custom skill", encoding="utf-8")

        # Call again — should NOT overwrite
        create_persona_assets("developer-con-1", "Con", "developer", project_root=tmp_path)
        assert skill_path.read_text(encoding="utf-8") == "custom skill"


class TestReadSkillFile:
    """Test reading skill.md content."""

    def test_returns_content_when_exists(self, tmp_path):
        create_persona_assets("developer-con-1", "Con", "developer", project_root=tmp_path)
        content = read_skill_file("developer-con-1", project_root=tmp_path)
        assert content is not None
        assert "# Con — developer" in content

    def test_returns_none_when_missing(self, tmp_path):
        result = read_skill_file("nonexistent-slug", project_root=tmp_path)
        assert result is None


class TestReadExperienceFile:
    """Test reading experience.md content."""

    def test_returns_content_when_exists(self, tmp_path):
        create_persona_assets("developer-con-1", "Con", "developer", project_root=tmp_path)
        content = read_experience_file("developer-con-1", project_root=tmp_path)
        assert content is not None
        assert "# Experience Log — Con" in content

    def test_returns_none_when_missing(self, tmp_path):
        result = read_experience_file("nonexistent-slug", project_root=tmp_path)
        assert result is None


class TestCheckAssets:
    """Test asset existence checking."""

    def test_both_files_present(self, tmp_path):
        create_persona_assets("developer-con-1", "Con", "developer", project_root=tmp_path)
        status = check_assets("developer-con-1", project_root=tmp_path)
        assert status.skill_exists is True
        assert status.experience_exists is True
        assert status.directory_exists is True

    def test_skill_only(self, tmp_path):
        seed_skill_file("developer-con-1", "Con", "developer", project_root=tmp_path)
        status = check_assets("developer-con-1", project_root=tmp_path)
        assert status.skill_exists is True
        assert status.experience_exists is False
        assert status.directory_exists is True

    def test_experience_only(self, tmp_path):
        seed_experience_file("developer-con-1", "Con", project_root=tmp_path)
        status = check_assets("developer-con-1", project_root=tmp_path)
        assert status.skill_exists is False
        assert status.experience_exists is True
        assert status.directory_exists is True

    def test_no_files_present(self, tmp_path):
        status = check_assets("nonexistent-slug", project_root=tmp_path)
        assert status.skill_exists is False
        assert status.experience_exists is False
        assert status.directory_exists is False

    def test_empty_directory(self, tmp_path):
        create_persona_dir("developer-con-1", project_root=tmp_path)
        status = check_assets("developer-con-1", project_root=tmp_path)
        assert status.skill_exists is False
        assert status.experience_exists is False
        assert status.directory_exists is True


class TestWriteSkillFile:
    """Test writing skill.md content."""

    def test_writes_new_file(self, tmp_path):
        """Creates a new skill file with the given content."""
        path = write_skill_file("developer-con-1", "# Custom Skill", project_root=tmp_path)
        assert path.exists()
        assert path.read_text(encoding="utf-8") == "# Custom Skill"

    def test_overwrites_existing(self, tmp_path):
        """Overwrites an existing skill file."""
        seed_skill_file("developer-con-1", "Con", "developer", project_root=tmp_path)
        write_skill_file("developer-con-1", "Updated content", project_root=tmp_path)
        content = read_skill_file("developer-con-1", project_root=tmp_path)
        assert content == "Updated content"

    def test_creates_directory_if_missing(self, tmp_path):
        """Creates the persona directory if it does not exist."""
        path = write_skill_file("new-persona-99", "# New", project_root=tmp_path)
        assert path.exists()
        assert path.parent.is_dir()
        assert path.read_text(encoding="utf-8") == "# New"


class TestGetExperienceMtime:
    """Test experience.md last-modified timestamp."""

    def test_returns_iso_timestamp_when_exists(self, tmp_path):
        """Returns an ISO 8601 timestamp when the file exists."""
        seed_experience_file("developer-con-1", "Con", project_root=tmp_path)
        mtime = get_experience_mtime("developer-con-1", project_root=tmp_path)
        assert mtime is not None
        # Should be a valid ISO 8601 string with timezone
        assert "T" in mtime
        assert "+" in mtime or "Z" in mtime or mtime.endswith("+00:00")

    def test_returns_none_when_missing(self, tmp_path):
        """Returns None when the experience file does not exist."""
        result = get_experience_mtime("nonexistent-slug", project_root=tmp_path)
        assert result is None


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_slug_get_dir(self, tmp_path):
        # Should not raise — returns a path even for empty slug
        result = get_persona_dir("", project_root=tmp_path)
        assert result == tmp_path / "data" / "personas" / ""

    def test_slug_with_special_characters(self, tmp_path):
        result = create_persona_assets("dev-con-1", "Con", "dev", project_root=tmp_path)
        assert result.is_dir()
        assert read_skill_file("dev-con-1", project_root=tmp_path) is not None


# ──────────────────────────────────────────────────────────────
# Guardrail Versioning Tests
# ──────────────────────────────────────────────────────────────


def _create_guardrails(tmp_path, content="# Platform Guardrails\n\nThese are the rules."):
    """Helper to create a guardrails file in the expected location."""
    guardrails_dir = tmp_path / GUARDRAILS_DIR
    guardrails_dir.mkdir(parents=True, exist_ok=True)
    guardrails_path = guardrails_dir / GUARDRAILS_FILENAME
    guardrails_path.write_text(content, encoding="utf-8")
    return guardrails_path


class TestComputeGuardrailsHash:
    """Test SHA-256 content hashing of guardrails."""

    def test_deterministic_hash(self):
        """Same content always produces the same hash."""
        content = "# Platform Guardrails\n\nRule 1."
        hash1 = compute_guardrails_hash(content)
        hash2 = compute_guardrails_hash(content)
        assert hash1 == hash2

    def test_hash_is_64_char_hex(self):
        """Hash is a 64-character hex digest (SHA-256)."""
        h = compute_guardrails_hash("some content")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_changes_with_content(self):
        """Different content produces a different hash."""
        h1 = compute_guardrails_hash("Version 1")
        h2 = compute_guardrails_hash("Version 2")
        assert h1 != h2

    def test_empty_string_has_valid_hash(self):
        """Empty string still produces a valid SHA-256 hash."""
        h = compute_guardrails_hash("")
        assert len(h) == 64


class TestValidateGuardrailsContent:
    """Test guardrails file validation."""

    def test_valid_file_returns_content_and_hash(self, tmp_path):
        """Valid guardrails file returns (content, hash) tuple."""
        content_text = "# Guardrails\n\nThese are the rules."
        _create_guardrails(tmp_path, content_text)
        content, hash_val = validate_guardrails_content(project_root=tmp_path)
        assert content == content_text
        assert hash_val == compute_guardrails_hash(content_text)

    def test_missing_file_raises(self, tmp_path):
        """Missing guardrails file raises GuardrailValidationError."""
        with pytest.raises(GuardrailValidationError, match="not found"):
            validate_guardrails_content(project_root=tmp_path)

    def test_empty_file_raises(self, tmp_path):
        """Empty guardrails file (whitespace only) raises GuardrailValidationError."""
        _create_guardrails(tmp_path, "   \n\n  ")
        with pytest.raises(GuardrailValidationError, match="empty"):
            validate_guardrails_content(project_root=tmp_path)

    def test_whitespace_only_raises(self, tmp_path):
        """File with only whitespace is treated as empty."""
        _create_guardrails(tmp_path, "\t  \n  \t")
        with pytest.raises(GuardrailValidationError, match="empty"):
            validate_guardrails_content(project_root=tmp_path)


class TestGetCurrentGuardrailsHash:
    """Test convenience function for staleness comparison."""

    def test_returns_hash_for_valid_file(self, tmp_path):
        content = "# Valid guardrails"
        _create_guardrails(tmp_path, content)
        h = get_current_guardrails_hash(project_root=tmp_path)
        assert h == compute_guardrails_hash(content)

    def test_returns_none_for_missing_file(self, tmp_path):
        h = get_current_guardrails_hash(project_root=tmp_path)
        assert h is None

    def test_returns_none_for_empty_file(self, tmp_path):
        _create_guardrails(tmp_path, "  ")
        h = get_current_guardrails_hash(project_root=tmp_path)
        assert h is None
