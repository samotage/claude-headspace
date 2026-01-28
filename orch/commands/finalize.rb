#!/usr/bin/env ruby
# frozen_string_literal: true

require 'fileutils'
require_relative '../state_manager'
require_relative '../queue_manager'
require_relative '../logger'

# Finalize Command - Complete PRD workflow with PR creation
#
# Handles:
# 1. Commit all changes (with warnings for out-of-scope files)
# 2. Create PR targeting development branch
# 3. Open PR in browser for review
# 4. Await merge confirmation
# 5. Post-merge cleanup and queue continuation
#
# Output: YAML with commit/PR details and next steps
#
class FinalizeCommand
  # CRITICAL: PR merge checkpoint is MANDATORY in all modes
  # This checkpoint requires human verification of the PR merge
  # and MUST NOT be auto-approved even in bulk_mode
  MERGE_CHECKPOINT_MANDATORY = true

  def initialize(change_name: nil, skip_pr: false, post_merge: false, skip_archive: false)
    @state = StateManager.new
    @queue = QueueManager.new
    @change_name = change_name || @state.get('change_name')
    @skip_pr = skip_pr
    @post_merge = post_merge
    @skip_archive = skip_archive
    @logger = OrchLogger.new('FinalizeCommand')
  end

  def execute
    @logger.info("Starting finalize command", {
      change_name: @change_name,
      skip_pr: @skip_pr,
      post_merge: @post_merge
    })

    result = {
      'command' => 'finalize',
      'timestamp' => Time.now.iso8601,
      'status' => 'success',
      'data' => {},
      'warnings' => [],
      'errors' => [],
      'checkpoints' => [],
      'next_steps' => []
    }

    begin
      @logger.debug("Validating inputs")
      validate_inputs(result)
      return result if result['status'] == 'error'

      if @post_merge
        @logger.info("Running post-merge cleanup")
        handle_post_merge(result)
      else
        if @skip_archive
          @logger.info("Skipping archive - already done by skill")
          result['data']['openspec_archived'] = true
          result['data']['executed_steps'] ||= []
          result['data']['executed_steps'] << 'openspec archive (skipped - done by skill)'
        else
          @logger.debug("Executing openspec archive")
          return result unless execute_openspec_archive(result)
        end

        @logger.debug("Moving PRD to done directory")
        move_prd_to_done(result)

        @logger.debug("Analyzing changes")
        analyze_changes(result)

        @logger.debug("Executing commit with polling")
        return result unless execute_commit_with_polling(result)

        @logger.debug("Preparing commit metadata")
        prepare_commit(result)

        unless @skip_pr
          @logger.debug("Preparing PR")
          prepare_pr(result)
        end

        @logger.debug("Adding checkpoint")
        add_checkpoint(result)
      end

      @logger.info("Transitioning to finalize phase")
      @state.transition_to('finalize')

    rescue StandardError => e
      @logger.warn("Exception during finalize execution", { error: e.message })
      result['status'] = 'error'
      result['errors'] << { 'type' => 'exception', 'message' => e.message }
    end

    @logger.info("Finalize command completed", { status: result['status'] })
    result
  end

  private

  def validate_inputs(result)
    unless @change_name
      result['status'] = 'error'
      result['errors'] << {
        'type' => 'missing_change_name',
        'message' => 'Change name not provided and not found in state'
      }
    end
  end

  def analyze_changes(result)
    status = `git status --porcelain 2>/dev/null`
    branch = `git branch --show-current 2>/dev/null`.strip

    result['data']['branch'] = branch
    result['data']['change_name'] = @change_name

    # Categorize files
    in_scope = []
    out_of_scope = []
    openspec_dir = "openspec/changes/#{@change_name}"

    status.each_line do |line|
      filepath = line[3..].strip.split(' -> ').last # Handle renames

      # Determine if file is in scope for this PRD
      if in_scope_file?(filepath, openspec_dir)
        in_scope << { 'path' => filepath, 'status' => line[0..1].strip }
      else
        out_of_scope << { 'path' => filepath, 'status' => line[0..1].strip }
      end
    end

    result['data']['changes'] = {
      'in_scope' => in_scope,
      'out_of_scope' => out_of_scope,
      'total' => in_scope.length + out_of_scope.length
    }

    # Warning for out-of-scope files
    if out_of_scope.any?
      result['warnings'] << {
        'type' => 'out_of_scope_files',
        'message' => "#{out_of_scope.length} file(s) outside direct PRD scope will be included",
        'files' => out_of_scope.map { |f| f['path'] },
        'note' => 'These may be adjacent work or fixes made during the build'
      }
    end
  end

  def in_scope_file?(filepath, openspec_dir)
    # Files directly related to the PRD change
    return true if filepath.start_with?(openspec_dir)
    return true if filepath.start_with?('openspec/')

    # Derive likely patterns from change name
    # e.g., inquiry-02-email -> anything with inquiry or email
    parts = @change_name.split('-').reject { |p| p =~ /^\d+$/ }
    parts.any? { |part| filepath.downcase.include?(part.downcase) }
  end

  def execute_openspec_archive(result)
    @logger.info("Archiving OpenSpec change", { change_name: @change_name })
    archive_cmd = "openspec archive #{@change_name} --yes"
    archive_output = `#{archive_cmd} 2>&1`

    if $?.success?
      result['data']['executed_steps'] ||= []
      result['data']['executed_steps'] << archive_cmd
      result['data']['openspec_archived'] = true
      @logger.info("OpenSpec change archived successfully", { output: archive_output })
    else
      @logger.error("Failed to archive OpenSpec change", { output: archive_output, command: archive_cmd })
      result['status'] = 'error'
      result['errors'] << {
        'step' => 'openspec_archive',
        'message' => "Failed to archive OpenSpec change: #{archive_output}",
        'command' => archive_cmd,
        'severity' => 'error'
      }
      return false
    end

    true
  end

  def move_prd_to_done(result)
    prd_path = @state.get('prd_path')

    # Skip if no prd_path in state
    unless prd_path
      result['warnings'] << {
        'type' => 'no_prd_path',
        'message' => 'No prd_path in state - skipping move to done directory'
      }
      return
    end

    # Skip if already in done/ directory
    if prd_path.include?('/done/')
      result['warnings'] << {
        'type' => 'already_in_done',
        'message' => "PRD already in done directory: #{prd_path}"
      }
      return
    end

    # Derive the done path: insert /done/ before filename
    # e.g., docs/prds/inquiry-system/inquiry-02-email-prd.md
    #    -> docs/prds/inquiry-system/done/inquiry-02-email-prd.md
    dir = File.dirname(prd_path)
    filename = File.basename(prd_path)
    done_dir = File.join(dir, 'done')
    done_path = File.join(done_dir, filename)

    # Execute the move
    begin
      # Create done directory if it doesn't exist
      FileUtils.mkdir_p(done_dir)

      # Execute git mv
      unless system("git mv #{prd_path} #{done_path}")
        raise "git mv command failed"
      end

      # Update state with new path
      @state.set('prd_path_done', done_path)
      @state.set('prd_path', done_path)  # Update current path too

      result['data']['prd_move'] = {
        'original_path' => prd_path,
        'done_path' => done_path,
        'status' => 'completed'
      }
    rescue StandardError => e
      result['warnings'] << {
        'type' => 'prd_move_failed',
        'message' => "Failed to move PRD: #{e.message}",
        'original_path' => prd_path,
        'intended_path' => done_path
      }
    end
  end

  def execute_commit_with_polling(result)
    @logger.info("Starting commit process with filesystem sync and polling", { change_name: @change_name })

    # STEP 1: Wait for filesystem synchronization
    wait_seconds = 15
    @logger.info("Waiting #{wait_seconds} seconds for filesystem synchronization")
    sleep(wait_seconds)

    # STEP 2: Polling loop to stage ALL changes
    max_attempts = 5
    attempt = 0

    loop do
      attempt += 1
      @logger.info("Staging attempt #{attempt}/#{max_attempts}")

      # Check what needs staging
      unstaged = `git diff --name-only 2>&1`.lines.map(&:strip)
      untracked = `git ls-files --others --exclude-standard 2>&1`.lines.map(&:strip)
      all_pending = unstaged + untracked

      # If nothing pending, we're done staging
      if all_pending.empty?
        @logger.info("All files staged, ready to commit")
        break
      end

      # Log what we're about to stage
      @logger.info("Found #{all_pending.length} files to stage")
      @logger.debug("Files to stage", { files: all_pending.first(20) })

      # Stage everything
      add_output = `git add -A 2>&1`
      unless $?.success?
        @logger.error("git add -A failed", { output: add_output, attempt: attempt })
        result['status'] = 'error'
        result['errors'] << {
          'step' => 'git_add_failed',
          'message' => "git add -A failed: #{add_output}",
          'attempt' => attempt,
          'severity' => 'error'
        }
        return false
      end

      @logger.info("Staged files, waiting 2 seconds before re-checking")
      sleep(2)

      # Safety: prevent infinite loop
      if attempt >= max_attempts
        # One final verification
        redevelopmenting = `git status --porcelain 2>&1`.lines.map(&:strip)
        if redevelopmenting.any?
          @logger.error("Could not stage all files", {
            attempts: max_attempts,
            redevelopmenting: redevelopmenting
          })
          result['status'] = 'error'
          result['errors'] << {
            'step' => 'git_staging_timeout',
            'message' => "Could not stage all files after #{max_attempts} attempts",
            'redevelopmenting_files' => redevelopmenting,
            'severity' => 'error'
          }
          return false
        end
        @logger.info("All files staged after #{attempt} attempts")
        break
      end
    end

    # STEP 3: Pre-commit verification (safety check)
    final_check = `git status --porcelain 2>&1`.lines.map(&:strip)
    if final_check.any?
      @logger.error("Pre-commit verification failed", { uncommitted: final_check })
      result['status'] = 'error'
      result['errors'] << {
        'step' => 'pre_commit_verification_failed',
        'message' => 'Files redevelopment unstaged despite polling loop completing',
        'files' => final_check,
        'severity' => 'error'
      }
      return false
    end

    # STEP 4: Execute commit
    commit_msg = "feat(#{@change_name}): implementation complete"
    @logger.info("Executing commit", { message: commit_msg })
    commit_output = `git commit -m "#{commit_msg}" 2>&1`

    unless $?.success?
      @logger.error("git commit failed", { output: commit_output })
      result['status'] = 'error'
      result['errors'] << {
        'step' => 'git_commit_failed',
        'message' => "git commit failed: #{commit_output}",
        'severity' => 'error'
      }
      return false
    end

    # STEP 5: Post-commit verification
    post_commit_status = `git status --porcelain 2>&1`.lines.map(&:strip)
    if post_commit_status.any?
      @logger.error("Post-commit verification failed", { uncommitted: post_commit_status })
      result['status'] = 'error'
      result['errors'] << {
        'step' => 'post_commit_verification_failed',
        'message' => 'Working tree not clean after commit - files redevelopment uncommitted',
        'uncommitted_files' => post_commit_status,
        'severity' => 'error'
      }
      return false
    end

    @logger.info("Commit completed successfully", {
      attempts: attempt,
      message: commit_msg
    })

    result['data']['executed_steps'] ||= []
    result['data']['executed_steps'] << "wait #{wait_seconds}s for filesystem sync"
    result['data']['executed_steps'] << "polling loop (#{attempt} attempts)"
    result['data']['executed_steps'] << 'git add -A'
    result['data']['executed_steps'] << "git commit -m \"#{commit_msg}\""
    result['data']['commit_completed'] = true
    result['data']['staging_attempts'] = attempt
    result['data']['staging_wait_seconds'] = wait_seconds

    true
  end

  def prepare_commit(result)
    result['data']['commit'] = {
      'message' => "feat(#{@change_name}): implementation complete",
      'commands' => [
        'git add -A',
        "git commit -m \"feat(#{@change_name}): implementation complete\""
      ],
      'note' => 'Using git add -A to include all changes'
    }
  end

  def prepare_pr(result)
    branch = result['data']['branch']
    prd_path = @state.get('prd_path')

    # Build PR title and body
    pr_title = "feat(#{@change_name}): implementation"
    pr_body = build_pr_body(prd_path)

    result['data']['pr'] = {
      'title' => pr_title,
      'body' => pr_body,
      'base' => 'development',
      'head' => branch,
      'commands' => [
        "git push -u origin #{branch}",
        "gh pr create --title \"#{pr_title}\" --body \"#{escape_for_shell(pr_body)}\" --base development --head #{branch}",
        "gh pr view --web"
      ]
    }

    # Check if gh CLI is available
    unless system('which gh > /dev/null 2>&1')
      result['warnings'] << {
        'type' => 'gh_cli_not_found',
        'message' => 'GitHub CLI (gh) not found - PR commands may fail',
        'resolution' => 'Install gh CLI or create PR manually'
      }
    end
  end

  def build_pr_body(prd_path)
    body = <<~BODY
      ## Summary

      Implementation for #{@change_name}

      ## PRD Reference

      #{prd_path || 'N/A'}

      ## Changes

      See OpenSpec: `openspec/changes/#{@change_name}/`

      ## Testing

      - [ ] All tests passing
      - [ ] Manual verification complete
    BODY

    body.strip
  end

  def escape_for_shell(str)
    str.gsub('"', '\\"').gsub('`', '\\`').gsub('$', '\\$')
  end

  def add_checkpoint(result)
    # ========================================================================
    # CRITICAL SAFEGUARD: This checkpoint is MANDATORY regardless of bulk_mode
    # ========================================================================
    #
    # The PR merge must be manually confirmed by a human in ALL modes.
    # This is a safety gate to prevent:
    # - Merging broken/incomplete PRs
    # - Bypassing code review
    # - Auto-proceeding past critical human verification point
    #
    # Unlike other checkpoints in the pipeline (proposal review, human testing
    # review) which can be auto-approved in bulk_mode, the merge checkpoint
    # MUST ALWAYS require explicit human confirmation.
    #
    # This follows the ERROR checkpoint pattern from Command 30 - it ALWAYS stops.
    #
    # ⚠️  WARNING TO FUTURE DEVELOPERS: DO NOT add bulk_mode bypass logic here
    # ========================================================================

    unless MERGE_CHECKPOINT_MANDATORY
      raise "MERGE_CHECKPOINT_MANDATORY constant violated - this should never happen"
    end

    result['checkpoints'] = [ {
      'type' => 'awaiting_merge',
      'question' => 'PR created and opened in browser. After merging, select "merged" to continue.',
      'options' => [ 'merged', 'abort' ]
    } ]

    completed_steps = []

    # Document what was already completed
    if result['data']['openspec_archived']
      completed_steps << {
        'action' => 'openspec_archived',
        'description' => "OpenSpec change '#{@change_name}' archived successfully"
      }
    end

    if result['data']['prd_move'] && result['data']['prd_move']['status'] == 'completed'
      completed_steps << {
        'action' => 'prd_moved',
        'description' => "PRD moved to: #{result['data']['prd_move']['done_path']}"
      }
    end

    if result['data']['commit_completed']
      completed_steps << {
        'action' => 'committed',
        'description' => "Changes committed with message: feat(#{@change_name}): implementation complete"
      }
    end

    result['next_steps'] = completed_steps + [
      {
        'action' => 'create_pr',
        'commands' => result['data']['pr']['commands'],
        'description' => 'Push, create PR, and open in browser'
      },
      {
        'action' => 'await_merge',
        'description' => 'Wait for user to review and merge PR'
      },
      {
        'action' => 'post_merge',
        'command' => 'ruby orch/commands/finalize.rb --post-merge',
        'description' => 'Run post-merge cleanup'
      }
    ]

    @state.set_checkpoint('awaiting_merge')

    # Send notification
    send_notification(
      message: "PR created for #{@change_name}. Waiting for merge confirmation.",
      action: "Review and merge the PR, then confirm merge to continue orchestration",
      checkpoint: 'awaiting_merge',
      result: result
    )
  end

  def handle_post_merge(result)
    result['data']['post_merge'] = true
    result['data']['change_name'] = @change_name
    result['data']['executed_steps'] = []
    result['data']['failed_steps'] = []

    prd_path = @state.get('prd_path')

    # Execute git checkout development
    @logger.info("Checking out development branch")
    checkout_output = `git checkout development 2>&1`
    if $?.success?
      result['data']['executed_steps'] << 'git checkout development'
      @logger.info("Checked out development branch successfully")
    else
      @logger.warn("Failed to checkout development branch", { output: checkout_output })
      result['errors'] << {
        'step' => 'checkout_development',
        'message' => "Failed to checkout development: #{checkout_output}",
        'severity' => 'error'
      }
      result['status'] = 'error'
      return
    end

    # Execute git pull
    @logger.info("Pulling latest changes from development")
    pull_output = `git pull --rebase origin development 2>&1`
    if $?.success?
      result['data']['executed_steps'] << 'git pull --rebase origin development'
      @logger.info("Pulled latest changes successfully")
    else
      @logger.warn("Git pull failed", { output: pull_output })
      result['warnings'] << {
        'step' => 'pull_latest',
        'message' => "Git pull failed - may need manual resolution: #{pull_output}"
      }
    end

    # Verify archive was completed in pre-commit phase
    @logger.debug("Verifying OpenSpec archive was completed")
    list_output = `openspec list 2>&1`
    if list_output.include?(@change_name)
      @logger.warn("Change still appears in openspec list", { change_name: @change_name })
      result['warnings'] << {
        'type' => 'archive_verification_failed',
        'message' => "Change '#{@change_name}' still appears in openspec list - archive may not have been completed in pre-commit phase"
      }
    else
      @logger.info("Archive verified - change no longer in active list")
      result['data']['archive_verified'] = true
    end

    result['next_steps'] = [
      {
        'action' => 'mark_complete',
        'description' => 'Mark PRD as complete in queue'
      }
    ]

    # Mark complete in queue
    if prd_path
      @queue.complete(prd_path)
      @logger.info("Marked PRD as complete in queue", { prd_path: prd_path })
    end

    # Check for next in queue
    next_item = @queue.next_pending
    if next_item
      result['data']['next_prd'] = next_item['prd_path']
      result['next_steps'] << {
        'action' => 'process_next',
        'description' => "Continue to next PRD: #{next_item['prd_path']}",
        'prd_path' => next_item['prd_path']
      }
    else
      result['data']['queue_empty'] = true
      result['next_steps'] << {
        'action' => 'queue_complete',
        'description' => 'No more PRDs in queue - orchestration complete'
      }
    end

    # Complete state
    @state.complete
    @state.clear_checkpoint
  end

  def send_notification(message:, action: nil, checkpoint: nil, result:)
    require_relative '../notifier'
    notifier = PrdNotifier.new
    context = {
      change_name: @change_name,
      branch: @state.get('branch'),
      message: message,
      checkpoint: checkpoint || 'awaiting_finalize_decision',
      action: action
    }

    # Send notification (non-blocking if webhook not configured)
    notify_result = notifier.notify('decision_needed', context)
    @logger.info("Slack notification sent", { success: notify_result[:success] }) if notify_result[:success]
  rescue StandardError => e
    @logger.warn("Failed to send Slack notification", { error: e.message })
    # Don't fail the command if notification fails
  end
end

# CLI interface
if __FILE__ == $PROGRAM_NAME
  require 'optparse'
  require 'yaml'

  options = { format: 'yaml', skip_pr: false, post_merge: false, skip_archive: false }

  OptionParser.new do |opts|
    opts.banner = "Usage: finalize.rb [options]"
    opts.on('--change-name NAME', 'Change name') { |v| options[:change_name] = v }
    opts.on('--skip-pr', 'Skip PR creation (commit only)') { options[:skip_pr] = true }
    opts.on('--post-merge', 'Run post-merge cleanup') { options[:post_merge] = true }
    opts.on('--skip-archive', 'Skip archive (already done by skill)') { options[:skip_archive] = true }
    opts.on('--format FORMAT', 'Output format: yaml, json') { |v| options[:format] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      exit 0
    end
  end.parse!

  cmd = FinalizeCommand.new(
    change_name: options[:change_name],
    skip_pr: options[:skip_pr],
    post_merge: options[:post_merge],
    skip_archive: options[:skip_archive]
  )
  result = cmd.execute

  output = options[:format] == 'json' ? result.to_json : result.to_yaml
  puts output

  exit(result['status'] == 'success' ? 0 : 1)
end
