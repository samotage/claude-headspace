#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative '../state_manager'
require_relative '../logger'

# Proposal Command - OpenSpec generation and validation
#
# This command orchestrates the creation of OpenSpec proposal files by:
# 1. Parsing PRD content and extracting sections
# 2. Analyzing git history for contextual information (NEW)
# 3. Detecting gaps (missing sections, TODOs, placeholders)
# 4. Providing templates for proposal.md, tasks.md, and spec.md
# 5. Checking for existing OpenSpec proposals
#
# Git History Integration:
# The command now includes git history analysis to provide context about:
# - Related files already in the codebase
# - Recent commits (last 12 months)
# - OpenSpec changes previously applied to this subsystem
# - Implementation patterns detected
#
# This context is exposed in the output as data.git_context and used by
# the AI agent to create more accurate and consistent OpenSpec proposals.
#
# Output: YAML with PRD content parsed, git context, and structured data
# for proposal creation
#
class ProposalCommand
  def initialize(prd_path: nil, change_name: nil)
    @state = StateManager.new
    @prd_path = prd_path || @state.get('prd_path')
    @change_name = change_name || @state.get('change_name')
    @logger = OrchLogger.new('ProposalCommand')
  end

  def execute
    @logger.info("Starting proposal command", { prd_path: @prd_path, change_name: @change_name })

    result = {
      'command' => 'proposal',
      'timestamp' => Time.now.iso8601,
      'status' => 'success',
      'data' => {},
      'warnings' => [],
      'errors' => [],
      'next_steps' => []
    }

    begin
      @logger.debug("Validating inputs")
      validate_inputs(result)
      return result if result['status'] == 'error'

      @logger.debug("Parsing PRD content")
      parse_prd(result)

      @logger.debug("Analyzing git history for context")
      analyze_git_history(result)

      @logger.debug("Detecting gaps in PRD")
      detect_gaps(result)

      @logger.debug("Defining OpenSpec structure")
      define_openspec_structure(result)

      @logger.debug("Checking for existing proposal")
      check_existing_proposal(result)

      @logger.debug("Adding next steps")
      add_next_steps(result)

      @logger.info("Transitioning to proposal phase")
      @state.transition_to('proposal')

    rescue StandardError => e
      @logger.warn("Exception during proposal execution", { error: e.message })
      result['status'] = 'error'
      result['errors'] << { 'type' => 'exception', 'message' => e.message }
    end

    @logger.info("Proposal command completed", {
      status: result['status'],
      gaps_found: result['data']['gaps']&.length || 0
    })
    result
  end

  private

  def validate_inputs(result)
    unless @prd_path && File.exist?(@prd_path)
      @logger.warn("PRD file not found or not specified", { prd_path: @prd_path })
      result['status'] = 'error'
      result['errors'] << {
        'type' => 'prd_not_found',
        'message' => "PRD file not found: #{@prd_path}"
      }
      return
    end

    unless @change_name
      @logger.warn("Change name not provided")
      result['status'] = 'error'
      result['errors'] << {
        'type' => 'missing_change_name',
        'message' => 'Change name not provided and not found in state'
      }
    end

    @logger.info("Inputs validated successfully")
  end

  def parse_prd(result)
    content = File.read(@prd_path)
    @logger.debug("PRD content loaded", { size_bytes: content.length })

    result['data']['prd_path'] = @prd_path
    result['data']['change_name'] = @change_name
    result['data']['prd_content'] = {
      'raw' => content,
      'sections' => extract_sections(content)
    }

    @logger.info("PRD parsed successfully", {
      sections_found: result['data']['prd_content']['sections'].keys.length
    })
  end

  def extract_sections(content)
    sections = {}

    # Extract PRD sections matching the workshop template format
    # Workshop generates numbered sections like "## 1. Context & Purpose"
    # These patterns handle both numbered and unnumbered variants
    # NOTE: Lookahead uses (?=^##[^#]|\z) to avoid matching ### subsections
    section_patterns = {
      'executive_summary' => /^##\s*Executive Summary\s*\n(.*?)(?=^##[^#]|\z)/mi,
      'context_purpose' => /^##\s*\d*\.?\s*(?:Context\s*(?:&|and)?\s*Purpose|Purpose)\s*\n(.*?)(?=^##[^#]|\z)/mi,
      'scope' => /^##\s*\d*\.?\s*Scope\s*\n(.*?)(?=^##[^#]|\z)/mi,
      'success_criteria' => /^##\s*\d*\.?\s*Success Criteria\s*\n(.*?)(?=^##[^#]|\z)/mi,
      'functional_requirements' => /^##\s*\d*\.?\s*(?:Functional Requirements|Requirements?)\s*(?:\(FRs?\))?\s*\n(.*?)(?=^##[^#]|\z)/mi,
      'non_functional_requirements' => /^##\s*\d*\.?\s*Non-?Functional Requirements\s*(?:\(NFRs?\))?\s*\n(.*?)(?=^##[^#]|\z)/mi,
      'out_of_scope' => /^###?\s*\d*\.?\d*\s*Out of Scope\s*\n(.*?)(?=^##[^#]|^###|\z)/mi,
      'ui_overview' => /^##\s*\d*\.?\s*(?:UI Overview|UI)\s*.*\n(.*?)(?=^##[^#]|\z)/mi
    }

    section_patterns.each do |name, pattern|
      match = content.match(pattern)
      sections[name] = match[1].strip if match
    end

    sections
  end

  # Analyzes git commit history to provide context about:
  # - Related files in the codebase
  # - Recent commits
  # - OpenSpec change history
  # - Implementation patterns
  #
  # This context is stored in result['data']['git_context'] and used
  # throughout the proposal generation process.
  def analyze_git_history(result)
    require_relative '../git_history_analyzer'

    # Derive subsystem from PRD path
    subsystem = derive_subsystem(@prd_path)

    analyzer = GitHistoryAnalyzer.new(
      subsystem: subsystem,
      prd_path: @prd_path,
      months_back: 12
    )

    git_context = analyzer.analyze
    result['data']['git_context'] = git_context

    @logger.info("Git history analysis included", {
      files: git_context['related_files'].values.flatten.length,
      commits: git_context['recent_commits'].length
    })
  rescue StandardError => e
    @logger.warn("Git history analysis failed", { error: e.message })
    result['warnings'] << {
      'type' => 'git_history_failed',
      'message' => "Could not analyze git history: #{e.message}"
    }
  end

  # Derives subsystem name from PRD file path
  # Example: docs/prds/inquiry/my-feature-prd.md -> "inquiry"
  def derive_subsystem(prd_path)
    # Extract subsystem from path: docs/prds/{subsystem}/{name}.md
    parts = prd_path.split('/')
    return nil unless parts.length >= 3

    parts[-2] # Return the directory name (subsystem)
  end

  def detect_gaps(result)
    sections = result['data']['prd_content']['sections']
    content = result['data']['prd_content']['raw']
    gaps = []

    # Critical PRD sections that should exist (aligned with workshop template)
    # Note: technical_implementation and testing_requirements are OpenSpec/build
    # concerns, NOT PRD requirements - PRDs focus on WHAT, not HOW
    critical_sections = {
      'executive_summary' => 'Executive Summary',
      'context_purpose' => 'Context & Purpose section',
      'scope' => 'Scope section',
      'functional_requirements' => 'Functional Requirements section'
    }

    critical_sections.each do |key, name|
      if sections[key].nil? || sections[key].strip.empty?
        gaps << {
          'type' => 'missing_section',
          'section' => key,
          'severity' => 'high',
          'message' => "PRD is missing '#{name}'"
        }
      end
    end

    # Check for TODO/TBD/FIXME markers indicating incomplete content
    todo_matches = content.scan(/\b(TODO|TBD|FIXME)\b:?\s*(.{0,50})/i)
    if todo_matches.any?
      gaps << {
        'type' => 'incomplete_content',
        'severity' => 'high',
        'message' => "PRD contains #{todo_matches.length} TODO/TBD/FIXME marker(s)",
        'markers' => todo_matches.map { |m| "#{m[0]}: #{m[1].strip}".strip }.first(5)
      }
    end

    # Check for placeholder text patterns like [something?] or [TBD] or [???]
    placeholder_matches = content.scan(/\[([^\]]*\?[^\]]*|\?\?\?|TBD|TODO)\]/i)
    if placeholder_matches.any?
      gaps << {
        'type' => 'placeholder_text',
        'severity' => 'medium',
        'message' => "PRD contains #{placeholder_matches.length} placeholder(s)",
        'placeholders' => placeholder_matches.flatten.first(5)
      }
    end

    # Check for empty bullet points or numbered items
    empty_items = content.scan(/^[-*]\s*$|^\d+\.\s*$/)
    if empty_items.any?
      gaps << {
        'type' => 'empty_items',
        'severity' => 'medium',
        'message' => "PRD contains #{empty_items.length} empty list item(s)"
      }
    end

    # Store gaps in result
    result['data']['gaps'] = gaps

    # Add high-severity gaps to warnings
    high_severity_gaps = gaps.select { |g| g['severity'] == 'high' }
    high_severity_gaps.each do |gap|
      result['warnings'] << gap
    end

    # If there are high-severity gaps, add a clarification checkpoint
    # NOTE: We do NOT send a Slack notification here. The AI agent should first
    # evaluate whether the gaps are real issues or false positives (e.g., section
    # naming format differences). The AI agent should only send a notification
    # via `ruby orch/notifier.rb decision_needed ...` if it cannot resolve the
    # gaps autonomously and needs human intervention.
    if high_severity_gaps.any?
      result['status'] = 'checkpoint'
      @state.set_checkpoint('awaiting_clarification')

      result['checkpoints'] ||= []
      result['checkpoints'] << {
        'type' => 'clarification_needed',
        'reason' => 'gaps_detected',
        'question' => "PRD has #{high_severity_gaps.length} gap(s) that may need clarification before proceeding",
        'gaps' => high_severity_gaps,
        'options' => [ 'proceed_anyway', 'stop_for_clarification' ],
        'ai_guidance' => 'Evaluate the gaps first. If they are false positives (e.g., section naming differences), proceed without notification. Only send a Slack notification if you cannot resolve the gaps autonomously.'
      }
    end
  end

  def define_openspec_structure(result)
    openspec_dir = "openspec/changes/#{@change_name}"

    result['data']['openspec'] = {
      'directory' => openspec_dir,
      'files' => {
        'proposal' => {
          'path' => "#{openspec_dir}/proposal.md",
          'template' => proposal_template
        },
        'tasks' => {
          'path' => "#{openspec_dir}/tasks.md",
          'template' => tasks_template
        },
        'spec' => {
          'path' => "#{openspec_dir}/specs/spec.md",
          'template' => spec_template
        }
      }
    }
  end

  def proposal_template
    <<~TEMPLATE
      ## Why

      [Extract from PRD Purpose - 1-2 sentences on problem/opportunity]

      ## What Changes

      [Extract from PRD Requirements - bullet list]
      [Mark breaking changes with **BREAKING**]

      ## Impact

      - Affected specs: [list capabilities]
      - Affected code: [key files from Technical Implementation]
    TEMPLATE
  end

  def tasks_template
    <<~TEMPLATE
      ## 1. Planning (Phase 1)

      - [x] 1.1 Create OpenSpec proposal files
      - [x] 1.2 Validate proposal with openspec validate
      - [x] 1.3 Review and get approval

      ## 2. Implementation (Phase 2)

      [Convert PRD Implementation Checklist to numbered tasks]

      - [ ] 2.1 [First implementation task]
      - [ ] 2.2 [Second implementation task]

      ## 3. Testing (Phase 3)

      [Convert PRD Testing Requirements to numbered tasks]

      - [ ] 3.1 [First test task]
      - [ ] 3.2 [Second test task]

      ## 4. Final Verification

      - [ ] 4.1 All tests passing
      - [ ] 4.2 No linter errors
      - [ ] 4.3 Manual verification complete
    TEMPLATE
  end

  def spec_template
    <<~TEMPLATE
      ## ADDED Requirements

      ### Requirement: [Name from PRD]

      [Requirement description using SHALL/MUST language]

      #### Scenario: [Success case]

      - **WHEN** [condition]
      - **THEN** [expected result]

      #### Scenario: [Error case]

      - **WHEN** [error condition]
      - **THEN** [expected error handling]
    TEMPLATE
  end

  def check_existing_proposal(result)
    openspec_dir = result['data']['openspec']['directory']

    if Dir.exist?(openspec_dir)
      files = Dir.glob("#{openspec_dir}/**/*").select { |f| File.file?(f) }
      result['warnings'] << {
        'type' => 'proposal_exists',
        'message' => "OpenSpec directory already exists: #{openspec_dir}",
        'existing_files' => files
      }
    end
  end

  def send_notification(message:, action: nil, checkpoint: nil, result:)
    require_relative '../notifier'
    notifier = PrdNotifier.new
    context = {
      change_name: @change_name,
      branch: @state.get('branch'),
      message: message,
      checkpoint: checkpoint || 'awaiting_proposal_decision',
      action: action
    }

    # Send notification (non-blocking if webhook not configured)
    notify_result = notifier.notify('decision_needed', context)
    @logger.info("Slack notification sent", { success: notify_result[:success] }) if notify_result[:success]
  rescue StandardError => e
    @logger.warn("Failed to send Slack notification", { error: e.message })
    # Don't fail the command if notification fails
  end

  def add_next_steps(result)
    result['next_steps'] = [
      {
        'action' => 'create_proposal_files',
        'description' => 'Create OpenSpec proposal, tasks, and spec files',
        'details' => 'Use PRD content to populate the templates'
      },
      {
        'action' => 'validate',
        'command' => "openspec validate #{@change_name} --strict",
        'description' => 'Validate the OpenSpec proposal'
      },
      {
        'action' => 'checkpoint',
        'type' => 'proposal_review',
        'description' => 'Wait for user to review and approve proposal'
      }
    ]
  end
end

# CLI interface
if __FILE__ == $PROGRAM_NAME
  require 'optparse'
  require 'yaml'

  options = { format: 'yaml' }

  OptionParser.new do |opts|
    opts.banner = "Usage: proposal.rb [options]"
    opts.on('--prd-path PATH', 'Path to PRD file') { |v| options[:prd_path] = v }
    opts.on('--change-name NAME', 'Change name') { |v| options[:change_name] = v }
    opts.on('--format FORMAT', 'Output format: yaml, json') { |v| options[:format] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      exit 0
    end
  end.parse!

  cmd = ProposalCommand.new(
    prd_path: options[:prd_path],
    change_name: options[:change_name]
  )
  result = cmd.execute

  output = options[:format] == 'json' ? result.to_json : result.to_yaml
  puts output

  exit(result['status'] == 'success' ? 0 : 1)
end
