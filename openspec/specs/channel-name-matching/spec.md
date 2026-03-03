# channel-name-matching Specification

## Purpose
TBD - created by archiving change e9-s8-voice-bridge-channels. Update Purpose after archive.
## Requirements
### Requirement: Fuzzy Channel Name Matching
The channel matcher SHALL fuzzy-match the extracted channel reference against all active channels (status `pending` or `active`) visible to the operator. Matching SHALL be performed against both the channel `name` and `slug` fields using a 4-tier algorithm.

#### Scenario: Exact slug match
- **WHEN** the channel reference exactly matches a channel's slug
- **THEN** the match is returned with confidence 1.0
- **AND** no further matching is attempted

#### Scenario: Exact name match (case-insensitive)
- **WHEN** the channel reference exactly matches a channel's name (case-insensitive)
- **THEN** the match is returned with confidence 1.0

#### Scenario: Substring match
- **WHEN** the channel reference is a substring of a channel's name or slug, or vice versa
- **THEN** the channel is a candidate with confidence 0.8

#### Scenario: Token overlap match
- **WHEN** the channel reference's tokens overlap with a channel's name/slug tokens by at least 50%
- **THEN** the channel is a candidate with a score proportional to the overlap ratio

### Requirement: Ambiguity Resolution
If multiple channels match the fuzzy query with scores within 0.2 of each other, the voice bridge SHALL return a clarification prompt listing the ambiguous matches. No default selection on ambiguity.

#### Scenario: Two close matches
- **WHEN** "workshop" matches both `persona-alignment-workshop` (score 0.8) and `api-design-workshop` (score 0.8)
- **THEN** a clarification response is returned listing both channels
- **AND** `next_action` suggests saying the full channel name

### Requirement: No-Match Handling
If no channels match the fuzzy query, the voice bridge SHALL return an error indicating no matching channel was found, with a suggestion to list available channels.

#### Scenario: No channel found
- **WHEN** the operator references "foobar" and no channel matches
- **THEN** an error response is returned with `status_line: "No channel found matching 'foobar'."`
- **AND** `next_action: "Check channel names or say 'list channels'."`

### Requirement: Speech-to-Text Robustness
Channel name matching SHALL tolerate common speech-to-text artifacts: missing/added articles ("the workshop" vs "workshop"), singular/plural variations, and trailing punctuation.

#### Scenario: Article stripping
- **WHEN** the operator says "the workshop" (with article)
- **THEN** "the" is stripped before matching
- **AND** "workshop" matches against channel names correctly

#### Scenario: Punctuation cleanup
- **WHEN** the channel reference ends with "?", "!", or "."
- **THEN** trailing punctuation is stripped before matching

### Requirement: Persona Name Matching for Member Addition
When the operator says "add [name] to [channel]", the voice bridge SHALL fuzzy-match the persona name against active persona names and slugs using the same algorithm as channel name matching (exact, substring, token overlap). Ambiguous persona matches return a clarification prompt.

#### Scenario: Persona match
- **WHEN** the operator says "add Con to the workshop"
- **THEN** "Con" is fuzzy-matched against active personas
- **AND** the matching persona is added to the channel

#### Scenario: Ambiguous persona
- **WHEN** the persona reference matches multiple active personas
- **THEN** a clarification response is returned listing the matching persona names

