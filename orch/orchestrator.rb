#!/usr/bin/env ruby
# frozen_string_literal: true

# PRD Orchestrator - Main entry point for PRD workflow orchestration
#
# This is the central dispatcher for all PRD orchestration commands.
# It provides a unified interface for the AI agent to interact with
# the Ruby-backed orchestration system.
#
# Usage:
#   ruby orch/orchestrator.rb [command] [options]
#
# Commands:
#   prepare      - Git preflight and branch setup
#   proposal     - OpenSpec generation
#   prebuild     - Safety snapshot commit
#   build        - Implementation phase
#   test         - Test execution with Ralph loop
#   validate     - Spec compliance validation
#   finalize     - Commit, PR, and completion
#
#   queue add    - Add PRD(s) to queue
#   queue list   - List queue items
#   queue next   - Get next pending item
#   queue status - Show queue statistics
#
#   state show   - Show current state
#   state reset  - Reset state
#
#   notify       - Send Slack notification
#

require_relative 'state_manager'
require_relative 'queue_manager'
require_relative 'notifier'
require_relative 'logger'
require_relative 'usage_tracker'

class Orchestrator
  COMMANDS = {
    'prepare' => 'commands/prepare.rb',
    'proposal' => 'commands/proposal.rb',
    'prebuild' => 'commands/prebuild.rb',
    'build' => 'commands/build.rb',
    'test' => 'commands/test.rb',
    'validate' => 'commands/validate_spec.rb',
    'finalize' => 'commands/finalize.rb'
  }.freeze

  def initialize
    @state = StateManager.new
    @queue = QueueManager.new
    @usage = UsageTracker.new
    @logger = OrchLogger.new('Orchestrator')
  end

  def run(args)
    command = args.shift
    @logger.debug("Orchestrator invoked with command: #{command}", { args: args })

    case command
    when 'prepare', 'proposal', 'prebuild', 'build', 'test', 'validate', 'finalize'
      @logger.info("Executing workflow command: #{command}")
      run_command(command, args)
    when 'queue'
      @logger.info("Executing queue operation")
      handle_queue(args)
    when 'state'
      @logger.info("Executing state operation")
      handle_state(args)
    when 'notify'
      @logger.info("Executing notify operation")
      handle_notify(args)
    when 'usage'
      @logger.info("Executing usage operation")
      handle_usage(args)
    when 'status'
      @logger.info("Showing orchestration status")
      show_status
    when 'help', '-h', '--help', nil
      show_help
    else
      @logger.warn("Unknown command received: #{command}")
      puts "Unknown command: #{command}"
      puts "Run 'orchestrator.rb help' for usage"
      exit 1
    end
  end

  private

  def run_command(command, args)
    script_path = File.join(File.dirname(__FILE__), COMMANDS[command])
    @logger.debug("Dispatching to command script: #{script_path}", { args: args })
    exec('ruby', script_path, *args)
  end

  def handle_queue(args)
    action = args.shift
    require 'yaml'

    case action
    when 'add'
      prd_path = extract_option(args, '--prd-path')
      paths = extract_option(args, '--paths')

      if paths
        @logger.info("Adding batch of PRDs to queue", { count: paths.split(',').length })
        result = @queue.add_batch(paths.split(','))
      elsif prd_path
        @logger.info("Adding PRD to queue", { prd_path: prd_path })
        result = @queue.add(prd_path)
      else
        @logger.warn("Queue add called without prd_path or paths")
        puts "Error: --prd-path or --paths required"
        exit 1
      end
      puts result.to_yaml

    when 'list'
      @logger.debug("Listing all queue items")
      puts({ queue: @queue.all, stats: @queue.stats }.to_yaml)

    when 'next'
      @logger.debug("Getting next pending queue item")
      item = @queue.next_pending
      if item
        prd_path = item['prd_path']
        @logger.info("Next pending item retrieved", { prd_path: prd_path })
        puts item.to_yaml
      else
        @logger.info("Queue is empty")
        puts "---\nqueue_empty: true"
      end

    when 'status'
      @logger.debug("Getting queue status")
      puts @queue.stats.to_yaml

    when 'start'
      prd_path = extract_option(args, '--prd-path')
      @logger.info("Starting PRD processing", { prd_path: prd_path })

      # Derive change name and initialize state
      filename = File.basename(prd_path, '.md').sub(/-prd$/, '')
      change_name = filename
      branch = "feature/#{change_name}"

      @state.start_prd(
        prd_path: prd_path,
        change_name: change_name,
        branch: branch
      )

      result = @queue.start(prd_path)
      puts result.to_yaml

    when 'complete'
      prd_path = extract_option(args, '--prd-path')
      @logger.info("Marking PRD as complete", { prd_path: prd_path })
      result = @queue.complete(prd_path)
      puts result.to_yaml

    when 'fail'
      prd_path = extract_option(args, '--prd-path')
      reason = extract_option(args, '--reason')
      @logger.warn("Marking PRD as failed", { prd_path: prd_path, reason: reason })
      result = @queue.fail(prd_path, reason: reason)
      puts result.to_yaml

    when 'clear'
      @logger.info("Clearing completed queue items")
      result = @queue.clear_completed
      puts result.to_yaml

    when 'archive'
      @logger.info("Archiving queue file")
      result = @queue.archive
      puts result.to_yaml

    when 'update-field'
      prd_path = extract_option(args, '--prd-path')
      field = extract_option(args, '--field')
      value = extract_option(args, '--value')
      @logger.info("Updating queue item field", { prd_path: prd_path, field: field, value: value })
      result = @queue.update_field(prd_path, field: field, value: value)
      puts result.to_yaml

    else
      puts "Unknown queue action: #{action}"
      puts "Actions: add, list, next, status, start, complete, fail, clear, archive, update-field"
      exit 1
    end
  end

  def handle_state(args)
    action = args.shift
    require 'yaml'

    case action
    when 'show'
      @logger.debug("Showing current state")
      puts @state.current.to_yaml

    when 'reset'
      @logger.info("Resetting orchestration state")
      @state.reset
      puts "State reset"

    when 'get'
      key = extract_option(args, '--key')
      @logger.debug("Getting state key", { key: key })
      puts({ key => @state.get(key) }.to_yaml)

    when 'set'
      key = extract_option(args, '--key')
      value = extract_option(args, '--value')
      @logger.debug("Setting state key", { key: key, value: value })
      @state.set(key, value)
      puts "Set #{key} = #{value}"

    when 'transition'
      phase = extract_option(args, '--phase')
      @logger.info("Transitioning to phase", { phase: phase })
      @state.transition_to(phase)
      puts @state.current.to_yaml

    when 'checkpoint'
      checkpoint = extract_option(args, '--checkpoint')
      @logger.info("Setting checkpoint", { checkpoint: checkpoint })
      @state.set_checkpoint(checkpoint)
      puts @state.current.to_yaml

    when 'clear-checkpoint'
      @logger.info("Clearing checkpoint")
      @state.clear_checkpoint
      puts "Checkpoint cleared"

    when 'delete'
      @logger.info("Deleting state file")
      result = @state.delete_file
      puts result.to_yaml

    else
      puts "Unknown state action: #{action}"
      puts "Actions: show, reset, get, set, transition, checkpoint, clear-checkpoint, delete"
      exit 1
    end
  end

  def handle_notify(args)
    type = args.shift
    options = {}

    # Parse remaining args
    while args.any?
      arg = args.shift
      if arg.start_with?('--')
        key = arg[2..].tr('-', '_').to_sym
        options[key] = args.shift
      end
    end

    # Add state context if not provided
    options[:change_name] ||= @state.get('change_name')
    options[:branch] ||= @state.get('branch')
    options[:phase] ||= @state.get('phase')

    notifier = PrdNotifier.new
    result = notifier.notify(type, options)

    require 'yaml'
    puts result.to_yaml
  end

  def handle_usage(args)
    action = args.shift
    require 'yaml'

    case action
    when 'start'
      prd_path = extract_option(args, '--prd-path')
      prd_title = extract_option(args, '--prd-title')
      @logger.info("Starting usage tracking", { prd_path: prd_path })
      result = @usage.start_workflow(prd_path: prd_path, prd_title: prd_title)
      puts result.to_yaml

    when 'increment'
      phase = extract_option(args, '--phase')
      count = extract_option(args, '--count')&.to_i || 1
      @logger.debug("Incrementing usage", { phase: phase, count: count })
      new_count = @usage.increment(phase, count: count)
      puts({ phase: phase, count: new_count, total: @usage.total_messages }.to_yaml)

    when 'count'
      phase = extract_option(args, '--phase')
      puts({ phase: phase, count: @usage.count_for(phase) }.to_yaml)

    when 'total'
      puts({ total_messages: @usage.total_messages }.to_yaml)

    when 'report'
      format = extract_option(args, '--format') || 'yaml'
      if format == 'table'
        puts @usage.format_report_table
      else
        puts @usage.generate_report.to_yaml
      end

    when 'show'
      puts @usage.current.to_yaml

    when 'complete'
      format = extract_option(args, '--format') || 'table'
      @logger.info("Completing usage tracking")
      report = @usage.complete_workflow
      if format == 'table'
        puts @usage.format_report_table(report)
      else
        puts report.to_yaml
      end

    when 'reset'
      @logger.info("Resetting usage tracking")
      @usage.reset
      puts "Usage tracking reset"

    when 'delete'
      @logger.info("Deleting usage file")
      result = @usage.delete_file
      puts result.to_yaml

    else
      puts "Unknown usage action: #{action}"
      puts "Actions: start, increment, count, total, report, show, complete, reset, delete"
      exit 1
    end
  end

  def show_status
    require 'yaml'

    status = {
      'state' => @state.current,
      'queue' => @queue.stats,
      'current_prd' => @queue.current,
      'next_prd' => @queue.next_pending
    }

    puts status.to_yaml
  end

  def show_help
    puts <<~HELP
      PRD Orchestrator - Ruby-backed workflow automation for PRD builds

      USAGE:
        ruby orch/orchestrator.rb [command] [options]

      WORKFLOW COMMANDS:
        prepare       Git preflight and branch setup
                      --prd-path PATH    Path to PRD file (required)
                      --force            Skip confirmation checkpoints

        proposal      OpenSpec generation
                      --prd-path PATH    Path to PRD file
                      --change-name NAME Change name

        prebuild      Safety snapshot commit
                      --change-name NAME Change name

        build         Implementation phase
                      --change-name NAME Change name
                      --prd-path PATH    Path to PRD file

        test          Test execution with Ralph loop
                      --change-name NAME Change name
                      --specs SPECS      Comma-separated spec files

        validate      Spec compliance validation
                      --change-name NAME Change name

        finalize      Commit, PR, and completion
                      --change-name NAME Change name
                      --skip-pr          Skip PR creation
                      --post-merge       Run post-merge cleanup

      QUEUE COMMANDS:
        queue add     Add PRD to queue
                      --prd-path PATH    Single PRD path
                      --paths x,y,z      Multiple PRD paths

        queue list    List all queue items
        queue next    Get next pending item
        queue status  Show queue statistics
        queue start   Mark item as in_progress
        queue complete Mark item as completed
        queue fail    Mark item as failed
        queue clear   Clear completed items
        queue update-field  Update a field on queue item
                      --prd-path PATH    PRD path (required)
                      --field FIELD      Field name to update
                      --value VALUE      Value to set

      STATE COMMANDS:
        state show    Show current state
        state reset   Reset all state
        state get     Get a state key (--key KEY)
        state set     Set a state key (--key KEY --value VAL)
        state transition  Transition to phase (--phase PHASE)
        state checkpoint  Set checkpoint (--checkpoint TYPE)

      NOTIFICATION COMMANDS:
        notify TYPE   Send Slack notification
                      Types: decision_needed, error, complete
                      --change-name NAME
                      --message MSG
                      --branch BRANCH
                      --checkpoint TYPE

      USAGE TRACKING COMMANDS:
        usage start   Start tracking a new PRD workflow
                      --prd-path PATH    Path to PRD file
                      --prd-title TITLE  Human-readable title

        usage increment  Increment phase message counter
                      --phase PHASE      Phase name (see below)
                      --count N          Count to add (default: 1)

        usage count   Get count for a phase (--phase PHASE)
        usage total   Get total message count
        usage report  Generate usage report
                      --format yaml|table  Output format (default: yaml)
        usage show    Show current usage state
        usage complete  Complete workflow and generate final report
                      --format yaml|table  Output format (default: table)
        usage reset   Reset usage tracking
        usage delete  Delete usage file

        Phases: openspec_generation, branch_setup, implementation,
                testing, pr_creation, cleanup_merge

      STATUS:
        status        Show combined state and queue status

      EXAMPLES:
        # Add PRDs to queue
        ruby orch/orchestrator.rb queue add --prd-path docs/prds/inquiry-02-email-prd.md

        # Start processing
        ruby orch/orchestrator.rb prepare --prd-path docs/prds/inquiry-02-email-prd.md

        # Check status
        ruby orch/orchestrator.rb status

        # Notify on decision needed
        ruby orch/orchestrator.rb notify decision_needed --message "Proposal ready for review"

      The orchestrator outputs YAML for AI agent consumption. The agent reads
      the structured output and makes decisions based on status, warnings,
      checkpoints, and next_steps fields.
    HELP
  end

  def extract_option(args, flag)
    idx = args.index(flag)
    return nil unless idx

    args.delete_at(idx)
    args.delete_at(idx)
  end
end

# Run orchestrator
Orchestrator.new.run(ARGV) if __FILE__ == $PROGRAM_NAME
