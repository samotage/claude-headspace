# Delta Spec: Persona Filesystem Assets

**Change ID:** e8-s5-persona-filesystem-assets
**Affects:** New service module `persona_assets.py`

## ADDED Requirements

### Requirement: Persona asset path convention

The system SHALL use `data/personas/{slug}/` as the standard filesystem location for persona assets. Path resolution accepts a slug string only — no database lookup required.

#### Scenario: Path resolution for valid slug
- **WHEN** `get_persona_dir("developer-con-1")` is called
- **THEN** the returned path ends with `data/personas/developer-con-1`

### Requirement: Persona directory creation

The system SHALL create a persona's asset directory including any missing parent directories. Creation is idempotent.

#### Scenario: Directory created with parents
- **WHEN** `create_persona_dir("developer-con-1")` is called and `data/personas/` does not exist
- **THEN** both `data/personas/` and `data/personas/developer-con-1/` are created

#### Scenario: Idempotent directory creation
- **WHEN** `create_persona_dir("developer-con-1")` is called and the directory already exists
- **THEN** no error occurs and the existing directory is not modified

### Requirement: Skill file template seeding

The system SHALL create a `skill.md` file seeded with persona name, role, and section scaffolding (Core Identity, Skills & Preferences, Communication Style). Existing files are not overwritten.

#### Scenario: Skill file created with template
- **WHEN** `seed_skill_file("developer-con-1", "Con", "developer")` is called
- **THEN** `data/personas/developer-con-1/skill.md` is created with heading "# Con — developer" and three sections

#### Scenario: Existing skill file preserved
- **WHEN** `seed_skill_file` is called and `skill.md` already exists
- **THEN** the existing file content is not modified

### Requirement: Experience file template seeding

The system SHALL create an `experience.md` file seeded with persona header and append-only convention markers. Existing files are not overwritten.

#### Scenario: Experience file created with template
- **WHEN** `seed_experience_file("developer-con-1", "Con")` is called
- **THEN** `data/personas/developer-con-1/experience.md` is created with heading "# Experience Log — Con" and convention comments

#### Scenario: Existing experience file preserved
- **WHEN** `seed_experience_file` is called and `experience.md` already exists
- **THEN** the existing file content is not modified

### Requirement: Combined directory and template creation

The system SHALL provide a single function that creates the directory and seeds both template files in one operation.

#### Scenario: Full persona asset creation
- **WHEN** `create_persona_assets("developer-con-1", "Con", "developer")` is called
- **THEN** the directory is created and both `skill.md` and `experience.md` are seeded

### Requirement: Read skill file content

The system SHALL read and return skill.md content as a string. Missing files return None.

#### Scenario: Skill file read successfully
- **WHEN** `read_skill_file("developer-con-1")` is called and the file exists
- **THEN** the file content is returned as a string

#### Scenario: Missing skill file
- **WHEN** `read_skill_file("developer-con-1")` is called and the file does not exist
- **THEN** None is returned

### Requirement: Read experience file content

The system SHALL read and return experience.md content as a string. Missing files return None.

#### Scenario: Experience file read successfully
- **WHEN** `read_experience_file("developer-con-1")` is called and the file exists
- **THEN** the file content is returned as a string

#### Scenario: Missing experience file
- **WHEN** `read_experience_file("developer-con-1")` is called and the file does not exist
- **THEN** None is returned

### Requirement: Asset existence check

The system SHALL check and report the presence of skill.md and experience.md independently.

#### Scenario: Both files present
- **WHEN** `check_assets("developer-con-1")` is called and both files exist
- **THEN** result reports `skill_exists=True` and `experience_exists=True`

#### Scenario: No files present
- **WHEN** `check_assets("developer-con-1")` is called and neither file exists
- **THEN** result reports `skill_exists=False` and `experience_exists=False`
