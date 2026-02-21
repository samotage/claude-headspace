"""Unit tests for persona filesystem asset utilities.

Uses pytest tmp_path fixture — no database or Flask app context needed.
"""

from pathlib import Path

from claude_headspace.services.persona_assets import (
    AssetStatus,
    EXPERIENCE_FILENAME,
    SKILL_FILENAME,
    check_assets,
    create_persona_assets,
    create_persona_dir,
    get_persona_dir,
    read_experience_file,
    read_skill_file,
    seed_experience_file,
    seed_skill_file,
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
