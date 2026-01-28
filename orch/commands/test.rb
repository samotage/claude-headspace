#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative '../state_manager'
require_relative '../logger'
require_relative '../notifier'

# Test Command - Test execution with Ralph loop support
#
# Runs tests and implements retry logic (Ralph loop):
# - First failure: Attempt to fix and retry
# - Second failure: Attempt to fix and retry again
# - Third failure: Stop and request human intervention
#
# Output: YAML with test results and retry status
#
class TestCommand
  MAX_RALPH_ATTEMPTS = 2

  def initialize(change_name: nil, specs: nil)
    @state = StateManager.new
    @change_name = change_name || @state.get('change_name')
    @specs = specs
    @logger = OrchLogger.new('TestCommand')
  end

  def execute
    @logger.info("Starting test command", { change_name: @change_name, specs: @specs })

    result = {
      'command' => 'test',
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

      @logger.debug("Determining test scope")
      determine_test_scope(result)

      @logger.debug("Getting Ralph status")
      get_ralph_status(result)

      @logger.debug("Adding test guidance")
      add_test_guidance(result)

      @logger.info("Transitioning to test phase")
      @state.transition_to('test')

    rescue StandardError => e
      @logger.warn("Exception during test execution", { error: e.message })
      result['status'] = 'error'
      result['errors'] << { 'type' => 'exception', 'message' => e.message }
    end

    @logger.info("Test command completed", { status: result['status'] })
    result
  end

  # Record test results and determine next action
  def record_results(passed:, total:, failures: [])
    @logger.info("Recording test results", { passed: passed, total: total, failed: total - passed })

    result = {
      'command' => 'test_results',
      'timestamp' => Time.now.iso8601,
      'status' => 'success',
      'data' => {
        'passed' => passed,
        'total' => total,
        'failed' => total - passed,
        'failures' => failures
      },
      'next_steps' => []
    }

    if passed == total
      # All tests passed - checkpoint for human review before finalize
      @logger.info("All tests passed - requesting human review")
      result['data']['outcome'] = 'all_passed'
      @state.reset_ralph_attempts
      result['status'] = 'checkpoint'
      result['checkpoints'] = [ {
        'type' => 'human_review',
        'question' => 'Tests passed. Review the built work before finalizing.',
        'options' => [ 'approved', 'needs_inline_fixes', 'stop_for_manual_fix', 'skip_issues' ]
      } ]
      result['next_steps'] << {
        'action' => 'await_human_review',
        'description' => 'Present review checkpoint to user for manual verification of functionality and task completion'
      }

      # Send Slack notification
      send_notification(
        message: "All tests passed (#{passed}/#{total}). Ready for review before finalizing.",
        checkpoint: 'awaiting_test_review',
        action: 'Review the built work and decide next steps: approved, needs fixes, or manual intervention'
      )
    else
      # Tests failed - check Ralph loop
      attempts = @state.increment_ralph_attempts
      @logger.warn("Tests failed", { attempts: attempts, max: MAX_RALPH_ATTEMPTS })

      if attempts <= MAX_RALPH_ATTEMPTS
        result['data']['outcome'] = 'retry'
        result['data']['ralph_attempt'] = attempts
        result['data']['ralph_remaining'] = MAX_RALPH_ATTEMPTS - attempts + 1
        result['next_steps'] << {
          'action' => 'fix_and_retry',
          'description' => "Attempt #{attempts} of #{MAX_RALPH_ATTEMPTS}: Fix failures and re-run tests",
          'failures_to_fix' => failures.first(5)
        }
      else
        result['data']['outcome'] = 'human_intervention'
        result['data']['ralph_attempts_exhausted'] = true
        result['status'] = 'checkpoint'
        result['checkpoints'] = [ {
          'type' => 'test_intervention',
          'question' => "Tests failed after #{MAX_RALPH_ATTEMPTS} retry attempts. How to proceed?",
          'options' => [ 'fix_manually', 'skip_tests', 'abort' ]
        } ]
        result['next_steps'] << {
          'action' => 'notify_human',
          'description' => 'Notify user that tests failed after retries'
        }

        # Send Slack notification for human intervention
        failure_summary = failures.first(3).map { |f| "#{f['file']}:#{f['line']}" }.join(', ')
        send_notification(
          message: "Tests failed after #{MAX_RALPH_ATTEMPTS} retry attempts. #{total - passed} failing tests. Top failures: #{failure_summary}",
          checkpoint: 'awaiting_test_review',
          action: 'Decide how to proceed: fix manually, skip tests, or abort the build'
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

  def determine_test_scope(result)
    result['data']['change_name'] = @change_name
    result['data']['branch'] = @state.get('branch') || "feature/#{@change_name}"

    # If specific specs provided, use those
    if @specs && !@specs.empty?
      result['data']['test_scope'] = {
        'type' => 'specific',
        'specs' => @specs.split(',').map(&:strip)
      }
      return
    end

    # Try to determine scope from tasks.md testing section
    tasks_path = "openspec/changes/#{@change_name}/tasks.md"
    if File.exist?(tasks_path)
      content = File.read(tasks_path)
      test_tasks = extract_test_tasks(content)
      result['data']['test_scope'] = {
        'type' => 'from_tasks',
        'tasks' => test_tasks
      }
    else
      # Fallback to full test suite
      result['data']['test_scope'] = {
        'type' => 'full_suite',
        'command' => 'pytest'
      }
      result['warnings'] << {
        'type' => 'full_suite_fallback',
        'message' => 'Could not determine specific test scope, will run full suite'
      }
    end

    # Suggest targeted test commands based on change name
    result['data']['suggested_commands'] = suggest_test_commands(@change_name)
  end

  def extract_test_tasks(content)
    tasks = []
    in_testing = false

    content.each_line do |line|
      if line =~ /^##\s+\d+\.\s+Testing/i
        in_testing = true
      elsif line =~ /^##\s+\d+\./ && in_testing
        in_testing = false
      elsif in_testing && line =~ /^-\s+\[([ xX])\]\s+(\d+\.\d+)\s+(.*)/
        tasks << {
          'number' => $2,
          'completed' => $1.downcase == 'x',
          'description' => $3.strip
        }
      end
    end

    tasks
  end

  def suggest_test_commands(change_name)
    commands = []

    # Derive likely test file patterns from change name
    # e.g., inquiry-02-email -> inquiry, email
    parts = change_name.split('-').reject { |p| p =~ /^\d+$/ }

    parts.each do |part|
      commands << "pytest tests/*#{part}* -v"
      commands << "pytest -k '#{part}' -v"
    end

    # Add common patterns
    commands << "pytest -v"
    commands << "pytest --cov=. -v"
    commands << "pytest --lf" if File.exist?('.pytest_cache')

    commands.uniq
  end

  def get_ralph_status(result)
    attempts = @state.get('ralph_attempts') || 0
    result['data']['ralph'] = {
      'attempts' => attempts,
      'max_attempts' => MAX_RALPH_ATTEMPTS,
      'remaining' => [ MAX_RALPH_ATTEMPTS - attempts, 0 ].max
    }

    if attempts >= MAX_RALPH_ATTEMPTS
      result['warnings'] << {
        'type' => 'ralph_exhausted',
        'message' => "Ralph loop exhausted (#{attempts} attempts). Human intervention may be required."
      }
    end
  end

  def add_test_guidance(result)
    result['next_steps'] = [
      {
        'action' => 'run_tests',
        'description' => 'Run the test suite',
        'suggested_commands' => result['data']['suggested_commands']
      },
      {
        'action' => 'record_results',
        'description' => 'Record test results using test.rb record_results',
        'note' => 'This will determine if retry or human intervention is needed'
      }
    ]

    result['data']['guidance'] = {
      'ralph_loop' => "Automatic retry up to #{MAX_RALPH_ATTEMPTS} times on failure",
      'on_failure' => 'Analyze failures, attempt fixes, re-run tests',
      'on_exhausted' => 'Human intervention required - user will be notified'
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
    opts.banner = "Usage: test.rb [action] [options]"
    opts.on('--change-name NAME', 'Change name') { |v| options[:change_name] = v }
    opts.on('--specs SPECS', 'Comma-separated list of spec files') { |v| options[:specs] = v }
    opts.on('--passed N', Integer, 'Number of passed tests') { |v| options[:passed] = v }
    opts.on('--total N', Integer, 'Total number of tests') { |v| options[:total] = v }
    opts.on('--failures JSON', 'JSON array of failure details') { |v| options[:failures] = v }
    opts.on('--format FORMAT', 'Output format: yaml, json') { |v| options[:format] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      puts <<~HELP

        Actions:
          check (default) - Get test scope and Ralph status
          record          - Record test results (requires --passed, --total)
      HELP
      exit 0
    end
  end.parse!

  cmd = TestCommand.new(
    change_name: options[:change_name],
    specs: options[:specs]
  )

  result = case action
  when 'check'
             cmd.execute
  when 'record'
             failures = options[:failures] ? JSON.parse(options[:failures]) : []
             cmd.record_results(
               passed: options[:passed] || 0,
               total: options[:total] || 0,
               failures: failures
             )
  else
             puts "Unknown action: #{action}"
             exit 1
  end

  output = options[:format] == 'json' ? result.to_json : result.to_yaml
  puts output

  exit(result['status'] == 'success' ? 0 : 1)
end
