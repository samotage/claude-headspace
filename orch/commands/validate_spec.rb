#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative '../state_manager'
require_relative '../logger'
require_relative '../notifier'

# ValidateSpecCommand - Spec compliance validation with retry loop
#
# Validates that the implementation matches the spec artifacts:
# - PRD functional requirements
# - proposal.md - planned changes + Definition of Done
# - design.md - technical patterns
# - specs/*.md - delta specifications
# - tasks.md - all tasks completed
#
# Implements retry logic similar to Ralph loop:
# - First failure: Attempt to fix (code/tests/specs) and retry
# - Second failure: Attempt to fix and retry again
# - Third failure: Stop and request human intervention
#
# Output: YAML with validation results and retry status
#
class ValidateSpecCommand
  MAX_COMPLIANCE_ATTEMPTS = 2

  def initialize(change_name: nil)
    @state = StateManager.new
    @change_name = change_name || @state.get('change_name')
    @logger = OrchLogger.new('ValidateSpecCommand')
  end

  def execute
    @logger.info("Starting spec validation command", { change_name: @change_name })

    result = {
      'command' => 'validate_spec',
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

      @logger.debug("Gathering spec artifacts")
      gather_spec_artifacts(result)

      @logger.debug("Getting compliance status")
      get_compliance_status(result)

      @logger.debug("Adding validation guidance")
      add_validation_guidance(result)

      @logger.info("Transitioning to validate phase")
      @state.transition_to('validate')

    rescue StandardError => e
      @logger.warn("Exception during validation execution", { error: e.message })
      result['status'] = 'error'
      result['errors'] << { 'type' => 'exception', 'message' => e.message }
    end

    @logger.info("Validate spec command completed", { status: result['status'] })
    result
  end

  # Record validation results and determine next action
  def record_results(compliant:, issues: [], report_path: nil)
    @logger.info("Recording validation results", { compliant: compliant, issue_count: issues.length })

    result = {
      'command' => 'validate_spec_results',
      'timestamp' => Time.now.iso8601,
      'status' => 'success',
      'data' => {
        'compliant' => compliant,
        'issues' => issues,
        'report_path' => report_path
      },
      'next_steps' => []
    }

    if compliant
      # All specs validated - proceed to finalize
      @logger.info("Spec compliance validated - ready for finalize")
      result['data']['outcome'] = 'compliant'
      @state.reset_spec_compliance_attempts
      result['next_steps'] << {
        'action' => 'proceed_to_finalize',
        'description' => 'Implementation matches spec. Proceed to finalize phase.'
      }

      # Send Slack notification
      send_notification(
        message: "Spec compliance validated. Implementation matches all requirements.",
        checkpoint: nil,
        action: 'Proceeding to finalize phase'
      )
    else
      # Validation failed - check retry loop
      attempts = @state.increment_spec_compliance_attempts
      @logger.warn("Spec compliance failed", { attempts: attempts, max: MAX_COMPLIANCE_ATTEMPTS })

      if attempts <= MAX_COMPLIANCE_ATTEMPTS
        result['data']['outcome'] = 'retry'
        result['data']['compliance_attempt'] = attempts
        result['data']['compliance_remaining'] = MAX_COMPLIANCE_ATTEMPTS - attempts + 1
        result['next_steps'] << {
          'action' => 'fix_and_retry',
          'description' => "Attempt #{attempts} of #{MAX_COMPLIANCE_ATTEMPTS}: Fix issues and re-validate",
          'issues_to_fix' => issues.first(10),
          'fix_scope' => 'May modify code, tests, or specs to resolve issues'
        }
      else
        result['data']['outcome'] = 'human_intervention'
        result['data']['compliance_attempts_exhausted'] = true
        result['status'] = 'checkpoint'
        result['checkpoints'] = [{
          'type' => 'spec_compliance_failed_review',
          'question' => "Spec compliance failed after #{MAX_COMPLIANCE_ATTEMPTS} retry attempts. How to proceed?",
          'options' => ['fix_manually', 'skip_validation', 'abort']
        }]
        result['next_steps'] << {
          'action' => 'notify_human',
          'description' => 'Notify user that spec compliance failed after retries'
        }

        # Send Slack notification for human intervention
        issue_summary = issues.first(3).map { |i| i['description'] || i.to_s }.join('; ')
        send_notification(
          message: "Spec compliance failed after #{MAX_COMPLIANCE_ATTEMPTS} retry attempts. #{issues.length} issues found. Top issues: #{issue_summary}",
          checkpoint: 'spec_compliance_failed_review',
          action: 'Decide how to proceed: fix manually, skip validation, or abort the build'
        )
      end
    end

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

  def gather_spec_artifacts(result)
    result['data']['change_name'] = @change_name
    result['data']['branch'] = @state.get('branch') || "feature/#{@change_name}"

    openspec_dir = "openspec/changes/#{@change_name}"
    prd_path = @state.get('prd_path')

    artifacts = {
      'prd_path' => prd_path,
      'proposal_path' => "#{openspec_dir}/proposal.md",
      'tasks_path' => "#{openspec_dir}/tasks.md",
      'design_path' => "#{openspec_dir}/design.md",
      'proposal_summary_path' => "#{openspec_dir}/proposal-summary.md",
      'specs_dir' => "#{openspec_dir}/specs",
      'compliance_report_path' => "#{openspec_dir}/compliance-report.md"
    }

    # Check which artifacts exist
    artifacts_status = {}
    artifacts.each do |key, path|
      if key.end_with?('_dir')
        artifacts_status[key] = Dir.exist?(path)
      else
        artifacts_status[key] = File.exist?(path)
      end
    end

    result['data']['artifacts'] = artifacts
    result['data']['artifacts_status'] = artifacts_status

    # Warn about missing critical artifacts
    critical = %w[proposal_path tasks_path]
    missing = critical.select { |k| !artifacts_status[k] }
    if missing.any?
      result['warnings'] << {
        'type' => 'missing_artifacts',
        'message' => "Missing critical spec artifacts: #{missing.join(', ')}",
        'paths' => missing.map { |k| artifacts[k] }
      }
    end

    # List spec files if specs directory exists
    if artifacts_status['specs_dir']
      spec_files = Dir.glob("#{artifacts['specs_dir']}/**/*.md")
      result['data']['spec_files'] = spec_files
    else
      result['data']['spec_files'] = []
    end
  end

  def get_compliance_status(result)
    attempts = @state.get('spec_compliance_attempts') || 0
    result['data']['compliance'] = {
      'attempts' => attempts,
      'max_attempts' => MAX_COMPLIANCE_ATTEMPTS,
      'remaining' => [MAX_COMPLIANCE_ATTEMPTS - attempts, 0].max
    }

    if attempts >= MAX_COMPLIANCE_ATTEMPTS
      result['warnings'] << {
        'type' => 'compliance_exhausted',
        'message' => "Compliance loop exhausted (#{attempts} attempts). Human intervention may be required."
      }
    end
  end

  def add_validation_guidance(result)
    artifacts = result['data']['artifacts']

    result['next_steps'] = [
      {
        'action' => 'read_spec_artifacts',
        'description' => 'Read all spec artifacts to understand requirements',
        'files' => [
          artifacts['prd_path'],
          artifacts['proposal_path'],
          artifacts['tasks_path'],
          artifacts['design_path'],
          artifacts['proposal_summary_path']
        ].compact + (result['data']['spec_files'] || [])
      },
      {
        'action' => 'review_implementation',
        'description' => 'Review the implementation code against spec requirements',
        'check_areas' => [
          'All acceptance criteria from proposal.md Definition of Done',
          'All functional requirements from PRD',
          'All tasks in tasks.md are completed',
          'Code patterns match design.md',
          'Implementation satisfies delta specs (ADDED/MODIFIED/REMOVED)'
        ]
      },
      {
        'action' => 'generate_compliance_report',
        'description' => 'Generate compliance-report.md with validation results',
        'output_path' => artifacts['compliance_report_path']
      },
      {
        'action' => 'record_results',
        'description' => 'Record validation results using validate_spec.rb record',
        'note' => 'This will determine if retry or human intervention is needed'
      }
    ]

    result['data']['guidance'] = {
      'compliance_loop' => "Automatic retry up to #{MAX_COMPLIANCE_ATTEMPTS} times on failure",
      'on_failure' => 'Analyze issues, attempt fixes (code/tests/specs), re-run tests, re-validate',
      'on_exhausted' => 'Human intervention required - user will be notified',
      'fix_scope' => 'May modify implementation code, tests, or spec amendments if spec was ambiguous'
    }
  end

  def send_notification(message:, checkpoint: nil, action: nil)
    notifier = PrdNotifier.new
    context = {
      change_name: @change_name,
      branch: @state.get('branch'),
      message: message,
      checkpoint: checkpoint,
      action: action
    }

    # Send notification (non-blocking if webhook not configured)
    result = notifier.notify('decision_needed', context)
    @logger.info("Slack notification sent", { success: result[:success] }) if result[:success]
  rescue StandardError => e
    @logger.warn("Failed to send Slack notification", { error: e.message })
    # Don't fail the command if notification fails
  end
end

# CLI interface
if __FILE__ == $PROGRAM_NAME
  require 'optparse'
  require 'yaml'
  require 'json'

  action = ARGV.shift unless ARGV.first&.start_with?('--')
  action ||= 'check'
  options = { format: 'yaml' }

  OptionParser.new do |opts|
    opts.banner = "Usage: validate_spec.rb [action] [options]"
    opts.on('--change-name NAME', 'Change name') { |v| options[:change_name] = v }
    opts.on('--compliant', 'Mark as compliant (for record action)') { options[:compliant] = true }
    opts.on('--not-compliant', 'Mark as not compliant (for record action)') { options[:compliant] = false }
    opts.on('--issues JSON', 'JSON array of compliance issues') { |v| options[:issues] = v }
    opts.on('--report-path PATH', 'Path to compliance report') { |v| options[:report_path] = v }
    opts.on('--format FORMAT', 'Output format: yaml, json') { |v| options[:format] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      puts <<~HELP

        Actions:
          check (default) - Get spec artifacts and compliance status
          record          - Record validation results (requires --compliant or --not-compliant)

        Examples:
          # Check spec artifacts and get validation guidance
          ruby orch/commands/validate_spec.rb check --change-name my-feature

          # Record compliant result
          ruby orch/commands/validate_spec.rb record --compliant --report-path openspec/changes/my-feature/compliance-report.md

          # Record non-compliant result with issues
          ruby orch/commands/validate_spec.rb record --not-compliant --issues '[{"type":"missing_requirement","description":"Missing logout button"}]'
      HELP
      exit 0
    end
  end.parse!

  cmd = ValidateSpecCommand.new(
    change_name: options[:change_name]
  )

  result = case action
  when 'check'
             cmd.execute
  when 'record'
             issues = options[:issues] ? JSON.parse(options[:issues]) : []
             cmd.record_results(
               compliant: options[:compliant] == true,
               issues: issues,
               report_path: options[:report_path]
             )
  else
             puts "Unknown action: #{action}"
             exit 1
  end

  output = options[:format] == 'json' ? result.to_json : result.to_yaml
  puts output

  exit(result['status'] == 'success' ? 0 : 1)
end
