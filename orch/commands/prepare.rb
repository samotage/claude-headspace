#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative '../state_manager'
require_relative '../queue_manager'
require_relative '../logger'

# Prepare Command - Git preflight and branch setup
#
# Replaces PRD-41 logic with deterministic Ruby execution.
# Returns structured YAML output for AI agent consumption.
#
# Checks:
# 1. PRD file exists
# 2. OpenSpec list is empty (no active changes)
# 3. Current git branch
# 4. Working tree status
# 5. Creates or checks out feature branch
#
# Output: YAML with status, warnings, and next steps
#
class PrepareCommand
  def initialize(prd_path:, force: false)
    @prd_path = prd_path
    @force = force
    @state = StateManager.new
    @queue = QueueManager.new
    @logger = OrchLogger.new('PrepareCommand')
    @warnings = []
    @errors = []
  end

  def execute
    @logger.info("Starting prepare command", { prd_path: @prd_path, force: @force })

    result = {
      'command' => 'prepare',
      'prd_path' => @prd_path,
      'timestamp' => Time.now.iso8601,
      'status' => 'success',
      'warnings' => [],
      'errors' => [],
      'data' => {},
      'checkpoints' => [],
      'next_steps' => []
    }

    begin
      # Step 1: Validate PRD exists
      @logger.debug("Validating PRD file exists")
      validate_prd_exists(result)
      if result['status'] == 'error'
        result['errors'] = @errors if @errors.any?
        return result
      end

      # Step 2: Derive change name
      @logger.debug("Deriving change name from PRD filename")
      derive_change_name(result)

      # Step 3: Check git state
      @logger.debug("Checking git state")
      check_git_state(result)

      # Step 3.25: Check for validation-only changes and handle auto-commit
      @logger.debug("Checking for validation-only changes")
      validation_change = detect_validation_only_change(result)
      if validation_change && validation_change[:detected]
        handle_validation_commit(result, validation_change)
        if result['status'] == 'error'
          result['errors'] = @errors if @errors.any?
          return result
        end
      end

      # Step 3.5: Check OpenSpec is empty
      @logger.debug("Checking OpenSpec empty state")
      check_openspec_empty(result)
      if result['status'] == 'error'
        result['errors'] = @errors if @errors.any?
        return result
      end

      # Step 4: Determine branch actions needed
      @logger.debug("Determining required branch actions")
      determine_branch_actions(result)

      # Step 5: Update state
      if result['status'] == 'success'
        @logger.info("Updating orchestration state", {
          change_name: result['data']['change_name'],
          branch: result['data']['branch']
        })
        update_state(result)
      end

    rescue StandardError => e
      @logger.warn("Exception during prepare execution", { error: e.message })
      result['status'] = 'error'
      result['errors'] << { 'type' => 'exception', 'message' => e.message, 'backtrace' => e.backtrace.first(5) }
    end

    result['warnings'] = @warnings
    result['errors'] = @errors if @errors.any?

    @logger.info("Prepare command completed", { status: result['status'], warnings: @warnings.length, errors: @errors.length })
    result
  end

  private

  def validate_prd_exists(result)
    unless File.exist?(@prd_path)
      @logger.warn("PRD file not found", { prd_path: @prd_path })
      result['status'] = 'error'
      @errors << {
        'type' => 'prd_not_found',
        'message' => "PRD file not found: #{@prd_path}",
        'resolution' => 'Verify the PRD path is correct'
      }
    else
      @logger.info("PRD file validated successfully", { prd_path: @prd_path })
    end
  end

  def derive_change_name(result)
    filename = File.basename(@prd_path, '.md')
    change_name = filename.sub(/-prd$/, '')

    @logger.debug("Derived change name", { filename: filename, change_name: change_name })

    result['data']['change_name'] = change_name
    result['data']['branch'] = "feature/#{change_name}"
  end

  def check_git_state(result)
    # Get current branch
    current_branch = `git branch --show-current 2>/dev/null`.strip
    result['data']['current_branch'] = current_branch
    @logger.debug("Current git branch", { branch: current_branch })

    # Check working tree status
    status_output = `git status --porcelain 2>/dev/null`
    dirty = !status_output.strip.empty?

    result['data']['working_tree_dirty'] = dirty
    result['data']['dirty_files'] = status_output.lines.map(&:strip).first(10) if dirty

    # Check if on development branch
    on_development = current_branch == 'development'
    result['data']['on_development'] = on_development

    # Add warnings for non-ideal states
    if dirty
      @logger.warn("Working tree has uncommitted changes", { file_count: status_output.lines.count })
      @warnings << {
        'type' => 'dirty_working_tree',
        'message' => 'Working tree has uncommitted changes',
        'recommendation' => 'Commit or stash changes before PRD build',
        'files' => result['data']['dirty_files']
      }
      unless @force
        result['checkpoints'] << {
          'type' => 'dirty_tree_confirmation',
          'question' => 'Working tree has uncommitted changes. Proceed anyway?',
          'options' => [ 'yes_proceed', 'no_abort' ]
        }

        # Send notification
        send_notification(
          message: "Working tree has uncommitted changes (#{status_output.lines.count} files)",
          action: "Review uncommitted changes and decide: proceed anyway or abort to commit first",
          result: result
        )
      end
    end

    unless on_development
      @logger.warn("Not on development branch", { current_branch: current_branch })
      @warnings << {
        'type' => 'not_on_development',
        'message' => "Not on development branch (currently on: #{current_branch})",
        'recommendation' => 'Start PRD builds from development branch'
      }
      unless @force
        result['checkpoints'] << {
          'type' => 'branch_confirmation',
          'question' => "Not on development branch (on #{current_branch}). Proceed anyway?",
          'options' => [ 'yes_proceed', 'no_abort' ]
        }

        # Send notification
        send_notification(
          message: "Not on development branch (currently on: #{current_branch})",
          action: "Review current branch and decide: proceed anyway or abort to switch to development",
          result: result
        )
      end
    end
  end

  def check_openspec_empty(result)
    @logger.debug("Checking if OpenSpec is empty")

    # Run openspec list command
    openspec_output = `openspec list 2>&1`
    exit_code = $?.exitstatus

    # Handle command execution errors
    if exit_code != 0
      @logger.warn("OpenSpec command failed", { exit_code: exit_code, output: openspec_output })
      @warnings << {
        'type' => 'openspec_check_failed',
        'message' => 'Could not verify OpenSpec state (command failed)',
        'recommendation' => 'Ensure openspec CLI is installed and working'
      }
      return
    end

    # Parse output to detect active changes
    # OpenSpec list shows either:
    # - "No active changes found." when empty
    # - "Changes:\n  change-name  ..." when there are changes
    # We check for the "No active changes found" message to determine empty state.
    is_empty = openspec_output.include?('No active changes found')

    if is_empty
      @logger.info("OpenSpec is empty - proceeding")
      result['data']['openspec_empty'] = true
    else
      # Extract change names from the output (lines that start with spaces and contain change IDs)
      active_changes = openspec_output.lines
        .map(&:strip)
        .reject(&:empty?)
        .reject { |line| line == 'Changes:' }
        .map { |line| line.split(/\s+/).first }
        .compact

      @logger.warn("OpenSpec has active changes", { count: active_changes.count, changes: active_changes })
      result['status'] = 'error'
      result['data']['openspec_empty'] = false
      result['data']['active_openspec_changes'] = active_changes

      @errors << {
        'type' => 'openspec_not_empty',
        'message' => 'Cannot start new PRD build - active OpenSpec changes exist',
        'details' => active_changes,
        'resolution' => 'Complete current work: merge and archive changes, or use "openspec archive <change-id> --yes"'
      }
    end
  end

  def determine_branch_actions(result)
    branch_name = result['data']['branch']
    current_branch = result['data']['current_branch']

    # Check if branch already exists
    branch_exists = system("git rev-parse --verify #{branch_name} >/dev/null 2>&1")
    result['data']['branch_exists'] = branch_exists

    @logger.debug("Branch existence check", { branch: branch_name, exists: branch_exists })

    if branch_exists
      @logger.warn("Branch already exists", { branch: branch_name })
      @warnings << {
        'type' => 'branch_exists',
        'message' => "Branch #{branch_name} already exists"
      }
      unless @force
        result['checkpoints'] << {
          'type' => 'branch_exists_confirmation',
          'question' => "Branch #{branch_name} already exists. How to proceed?",
          'options' => [ 'use_existing', 'delete_and_recreate', 'abort' ]
        }

        # Send notification
        send_notification(
          message: "Branch #{branch_name} already exists",
          action: "Decide how to proceed: use existing branch, delete and recreate, or abort",
          result: result
        )
      end
    end

    # Determine actions needed
    result['next_steps'] = []

    if result['data']['on_development'] && !result['data']['working_tree_dirty']
      result['next_steps'] << {
        'action' => 'git_pull',
        'command' => 'git pull --rebase origin development',
        'description' => 'Pull latest changes from development'
      }
    end

    if branch_exists
      result['next_steps'] << {
        'action' => 'checkout_existing',
        'command' => "git checkout #{branch_name}",
        'description' => 'Checkout existing feature branch',
        'conditional' => 'if user chooses use_existing'
      }
    else
      result['next_steps'] << {
        'action' => 'create_branch',
        'command' => "git checkout -b #{branch_name}",
        'description' => 'Create and checkout feature branch'
      }
    end

    # Add DOD extraction step
    result['next_steps'] << {
      'action' => 'extract_dod',
      'description' => 'Extract Definition of Done from PRD'
    }

    @logger.info("Determined branch actions", { next_steps_count: result['next_steps'].length })
  end

  def detect_validation_only_change(result)
    # Only check if the PRD file is in the dirty files list
    return false unless result['data']['working_tree_dirty']

    dirty_files = result['data']['dirty_files'] || []
    prd_file_modified = dirty_files.any? { |f| f.include?(@prd_path) }

    return false unless prd_file_modified

    @logger.debug("PRD file is modified, checking if validation-only change", { prd_path: @prd_path })

    # Get current validation metadata
    require_relative '../prd_validator'
    current_validation = PrdValidator.read_metadata(@prd_path)
    current_status = current_validation['status']

    # Get committed version validation metadata
    committed_content = `git show HEAD:#{@prd_path} 2>/dev/null`
    if $?.exitstatus != 0
      # File doesn't exist in HEAD (new file), not a validation-only change
      @logger.debug("PRD file doesn't exist in HEAD", { prd_path: @prd_path })
      return false
    end

    # Parse committed version's frontmatter
    require 'tempfile'
    committed_validation = nil
    Tempfile.create([ 'prd_committed', '.md' ]) do |temp|
      temp.write(committed_content)
      temp.close
      committed_validation = PrdValidator.read_metadata(temp.path)
    end

    # Get committed version without frontmatter
    committed_body = extract_body_without_frontmatter(committed_content)

    # Get current version without frontmatter
    current_content = File.read(@prd_path)
    current_body = extract_body_without_frontmatter(current_content)

    # Check if only validation changed and body is identical
    validation_changed = current_validation != committed_validation
    body_identical = current_body == committed_body

    if validation_changed && body_identical
      @logger.info("Detected validation-only change", {
        prd_path: @prd_path,
        old_status: committed_validation['status'],
        new_status: current_status
      })

      {
        detected: true,
        old_status: committed_validation['status'],
        new_status: current_status,
        old_validation: committed_validation,
        new_validation: current_validation
      }
    elsif validation_changed && !body_identical
      @logger.warn("Detected mixed validation and content changes", {
        prd_path: @prd_path,
        old_status: committed_validation['status'],
        new_status: current_status
      })

      {
        detected: true,
        mixed_changes: true,
        old_status: committed_validation['status'],
        new_status: current_status,
        old_validation: committed_validation,
        new_validation: current_validation
      }
    else
      @logger.debug("Not a validation-only change", {
        validation_changed: validation_changed,
        body_identical: body_identical
      })
      false
    end
  end

  def extract_body_without_frontmatter(content)
    # Strip frontmatter if present
    if content.start_with?("---\n")
      rest = content[4..]
      end_index = rest.index("---\n")
      if end_index
        body_start = 4 + end_index + 4
        return content[body_start..].strip
      end
    end
    content.strip
  end

  def handle_validation_commit(result, validation_change)
    new_status = validation_change[:new_status]
    old_status = validation_change[:old_status]

    @logger.info("Handling validation commit", {
      old_status: old_status,
      new_status: new_status,
      bulk_mode: @state.get('bulk_mode'),
      mixed_changes: validation_change[:mixed_changes]
    })

    # Error Path 2: Mixed changes (validation + content)
    if validation_change[:mixed_changes]
      @logger.warn("PRD has mixed validation and content changes", {
        prd_path: @prd_path,
        old_status: old_status,
        new_status: new_status
      })

      result['status'] = 'error'

      error_details = {
        'type' => 'mixed_validation_content_changes',
        'message' => 'PRD has both validation and content changes - these must be separated',
        'prd_path' => @prd_path,
        'old_status' => old_status,
        'new_status' => new_status,
        'resolution' => 'Commit content changes separately from validation changes. Run validation after content is committed.'
      }

      @errors << error_details

      # Send error notification
      require_relative '../notifier'
      notifier = PrdNotifier.new
      notifier.notify('error', {
        change_name: result['data']['change_name'],
        phase: 'prepare',
        message: error_details['message'],
        resolution: error_details['resolution']
      })

      return
    end

    # Error Path 1: Validation regression (status → invalid/unvalidated)
    if new_status == 'invalid' || new_status == 'unvalidated'
      @logger.warn("PRD validation status changed to #{new_status}", {
        prd_path: @prd_path,
        old_status: old_status,
        new_status: new_status
      })

      result['status'] = 'error'

      error_details = {
        'type' => 'validation_regression',
        'message' => "PRD validation status changed from '#{old_status}' to '#{new_status}'",
        'prd_path' => @prd_path,
        'resolution' => 'Fix validation errors before proceeding with PRD build'
      }

      if new_status == 'invalid'
        errors = validation_change[:new_validation]['validation_errors'] || []
        error_details['validation_errors'] = errors
        error_details['message'] += ". Errors: #{errors.join(', ')}" if errors.any?
      end

      @errors << error_details

      # Send error notification
      require_relative '../notifier'
      notifier = PrdNotifier.new
      notifier.notify('error', {
        change_name: result['data']['change_name'],
        phase: 'prepare',
        message: error_details['message'],
        resolution: error_details['resolution']
      })

      return
    end

    # Only proceed if status changed to 'valid'
    unless new_status == 'valid'
      @logger.debug("Validation status is not 'valid', skipping auto-commit", { status: new_status })
      return
    end

    # Success Path: status → valid
    # Check bulk mode
    if @state.get('bulk_mode')
      # Auto-proceed in bulk mode
      @logger.info("Bulk mode enabled - auto-committing validation change")
      execute_validation_commit(result, validation_change)
    else
      # Manual mode - create checkpoint
      @logger.info("Manual mode - creating validation commit checkpoint")
      result['checkpoints'] << {
        'type' => 'validation_commit_approval',
        'question' => "PRD validation status changed to 'valid'. Auto-commit and push this change?",
        'options' => [ 'yes_commit', 'no_abort' ],
        'details' => {
          'prd_path' => @prd_path,
          'old_status' => old_status,
          'new_status' => new_status,
          'validated_at' => validation_change[:new_validation]['validated_at']
        }
      }

      # Set checkpoint in state
      @state.set('checkpoint', 'awaiting_validation_commit')

      # Send notification
      require_relative '../notifier'
      notifier = PrdNotifier.new
      notifier.notify('decision_needed', {
        change_name: result['data']['change_name'],
        branch: result['data']['branch'],
        checkpoint: 'awaiting_validation_commit',
        message: "PRD validation status changed to 'valid' - approval needed to auto-commit",
        action: "Review the checkpoint and respond with: ruby orch/orchestrator.rb respond yes_commit"
      })
    end
  end

  def execute_validation_commit(result, validation_change)
    @logger.info("Executing validation commit", { prd_path: @prd_path })

    # Stage the PRD file
    require 'shellwords'
    stage_cmd = "git add #{Shellwords.escape(@prd_path)}"
    stage_output = `#{stage_cmd} 2>&1`
    unless $?.success?
      @logger.warn("Failed to stage PRD file", { error: stage_output })
      result['status'] = 'error'
      @errors << {
        'type' => 'git_stage_failed',
        'message' => "Failed to stage PRD file: #{stage_output}",
        'resolution' => 'Manually stage and commit the validation change'
      }
      return
    end

    # Commit with message
    commit_message = <<~MSG.strip
      docs(prd): mark #{result['data']['change_name']} as validated

      Validation status: #{validation_change[:old_status]} → #{validation_change[:new_status]}
      Validated at: #{validation_change[:new_validation]['validated_at']}

      Auto-committed by PRD orchestration system.

      Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
    MSG

    require 'tempfile'
    commit_result = nil
    Tempfile.create('commit_msg') do |temp|
      temp.write(commit_message)
      temp.close

      commit_cmd = "git commit -F #{Shellwords.escape(temp.path)}"
      commit_output = `#{commit_cmd} 2>&1`
      commit_result = $?.success?

      unless commit_result
        @logger.warn("Failed to commit validation change", { error: commit_output })
        result['status'] = 'error'
        @errors << {
          'type' => 'git_commit_failed',
          'message' => "Failed to commit validation change: #{commit_output}",
          'resolution' => 'Manually commit the validation change'
        }
        return
      end

      @logger.info("Validation change committed successfully")
    end

    # Push to remote (assuming branch already exists and has upstream)
    current_branch = result['data']['current_branch']
    push_cmd = "git push origin #{Shellwords.escape(current_branch)} 2>&1"
    push_output = `#{push_cmd}`

    if $?.success?
      @logger.info("Validation change pushed successfully", { branch: current_branch })
      result['data']['validation_committed'] = true
      result['data']['validation_pushed'] = true

      # Update state
      @state.set('validation_auto_committed', true)

      # Clear checkpoint if it was set
      @state.set('checkpoint', 'none') if @state.get('checkpoint') == 'awaiting_validation_commit'

      # Add to warnings (informational)
      @warnings << {
        'type' => 'validation_auto_committed',
        'message' => 'PRD validation status auto-committed and pushed',
        'details' => {
          'old_status' => validation_change[:old_status],
          'new_status' => validation_change[:new_status],
          'committed' => true,
          'pushed' => true
        }
      }
    else
      @logger.warn("Failed to push validation change", {
        error: push_output,
        branch: current_branch
      })

      # This is a warning, not an error - commit succeeded but push failed
      @warnings << {
        'type' => 'validation_push_failed',
        'message' => "Validation change committed locally but push failed: #{push_output}",
        'recommendation' => 'Manually push the validation commit or resolve push conflicts'
      }

      result['data']['validation_committed'] = true
      result['data']['validation_pushed'] = false
    end

    # Update git state in result (working tree should now be clean or different)
    check_git_state(result)
  end

  def send_notification(message:, action: nil, result:)
    require_relative '../notifier'
    notifier = PrdNotifier.new
    context = {
      change_name: result['data']['change_name'],
      branch: result['data']['branch'],
      message: message,
      checkpoint: 'awaiting_prepare_decision',
      action: action
    }

    # Send notification (non-blocking if webhook not configured)
    notify_result = notifier.notify('decision_needed', context)
    @logger.info("Slack notification sent", { success: notify_result[:success] }) if notify_result[:success]
  rescue StandardError => e
    @logger.warn("Failed to send Slack notification", { error: e.message })
    # Don't fail the command if notification fails
  end

  def update_state(result)
    @logger.info("Initializing state for PRD processing")
    @state.start_prd(
      prd_path: @prd_path,
      change_name: result['data']['change_name'],
      branch: result['data']['branch']
    )
  end
end

# CLI interface
if __FILE__ == $PROGRAM_NAME
  require 'optparse'
  require 'yaml'

  options = { force: false, format: 'yaml' }

  OptionParser.new do |opts|
    opts.banner = "Usage: prepare.rb --prd-path PATH [options]"
    opts.on('--prd-path PATH', 'Path to PRD file (required)') { |v| options[:prd_path] = v }
    opts.on('--force', 'Skip confirmation checkpoints') { options[:force] = true }
    opts.on('--format FORMAT', 'Output format: yaml, json') { |v| options[:format] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      exit 0
    end
  end.parse!

  unless options[:prd_path]
    puts "Error: --prd-path is required"
    puts "Run with --help for usage"
    exit 1
  end

  cmd = PrepareCommand.new(prd_path: options[:prd_path], force: options[:force])
  result = cmd.execute

  output = options[:format] == 'json' ? result.to_json : result.to_yaml
  puts output

  exit(result['status'] == 'success' ? 0 : 1)
end
