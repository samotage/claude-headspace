#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yaml'
require 'fileutils'
require 'time'

# UsageTracker - Tracks Claude Code API usage across orchestration phases
#
# Tracks message counts per phase to help understand API consumption
# during PRD workflow execution.
#
# Phases tracked:
# - openspec_generation: Proposal phase (Command 30)
# - branch_setup: Prepare phase (part of Command 30)
# - implementation: Build phase (Command 35)
# - testing: Test phase (Command 40)
# - pr_creation: Finalize phase (Command 50)
# - cleanup_merge: Post-merge phase (Command 60)
#
class UsageTracker
  USAGE_FILE = File.expand_path('../working/usage.yaml', __FILE__)
  USAGE_LOG_FILE = File.expand_path('../log/orchestration_usage.log', __FILE__)

  PHASES = %w[
    openspec_generation
    branch_setup
    implementation
    testing
    pr_creation
    cleanup_merge
  ].freeze

  # Human-readable phase names for the report
  PHASE_LABELS = {
    'openspec_generation' => 'OpenSpec Generation',
    'branch_setup' => 'Branch Setup',
    'implementation' => 'Implementation',
    'testing' => 'Testing',
    'pr_creation' => 'PR Creation',
    'cleanup_merge' => 'Cleanup/Merge'
  }.freeze

  # Assumed session message limit for 5x plan (for impact calculation)
  SESSION_LIMIT = 135

  def initialize
    @usage = load_usage
  end

  # Start tracking a new PRD workflow
  def start_workflow(prd_path:, prd_title: nil)
    @usage = {
      'prd_path' => prd_path,
      'prd_title' => prd_title || File.basename(prd_path, '.md'),
      'started_at' => Time.now.iso8601,
      'completed_at' => nil,
      'phases' => PHASES.to_h { |p| [p, 0] }
    }
    save_usage
    @usage
  end

  # Increment message count for a specific phase
  def increment(phase, count: 1)
    unless PHASES.include?(phase)
      raise ArgumentError, "Invalid phase: #{phase}. Valid phases: #{PHASES.join(', ')}"
    end

    @usage['phases'] ||= PHASES.to_h { |p| [p, 0] }
    @usage['phases'][phase] = (@usage['phases'][phase] || 0) + count
    save_usage
    @usage['phases'][phase]
  end

  # Get current count for a phase
  def count_for(phase)
    @usage.dig('phases', phase) || 0
  end

  # Get total message count across all phases
  def total_messages
    (@usage['phases'] || {}).values.sum
  end

  # Complete the workflow and generate final report
  def complete_workflow
    @usage['completed_at'] = Time.now.iso8601
    save_usage

    report = generate_report
    log_report(report)
    report
  end

  # Generate the formatted usage report
  def generate_report
    phases = @usage['phases'] || {}
    total = phases.values.sum
    total = 1 if total.zero? # Avoid division by zero

    started = @usage['started_at'] ? Time.parse(@usage['started_at']) : nil
    completed = @usage['completed_at'] ? Time.parse(@usage['completed_at']) : Time.now
    duration = started ? format_duration(completed - started) : 'N/A'

    # Build the table rows
    rows = PHASES.map do |phase|
      count = phases[phase] || 0
      percentage = ((count.to_f / total) * 100).round
      {
        label: PHASE_LABELS[phase],
        count: count,
        percentage: percentage
      }
    end

    # Calculate session impact
    session_impact = ((total.to_f / SESSION_LIMIT) * 100).round

    {
      prd_path: @usage['prd_path'],
      prd_title: @usage['prd_title'],
      started_at: @usage['started_at'],
      completed_at: @usage['completed_at'],
      duration: duration,
      phases: rows,
      total_messages: total == 1 && phases.values.sum.zero? ? 0 : total,
      session_impact: session_impact,
      session_limit: SESSION_LIMIT
    }
  end

  # Format the report as a printable table
  def format_report_table(report = nil)
    report ||= generate_report
    total = report[:total_messages]

    lines = []
    lines << ''
    lines << '=== PRD Workflow Usage Report ==='
    lines << "PRD: #{report[:prd_title]}"
    lines << "Started: #{report[:started_at]}"
    lines << "Completed: #{report[:completed_at]}"
    lines << "Duration: #{report[:duration]}"
    lines << ''
    lines << 'Phase Breakdown:'
    lines << '┌─────────────────────────┬──────────┬────────────┐'
    lines << '│ Phase                   │ Messages │ % of Total │'
    lines << '├─────────────────────────┼──────────┼────────────┤'

    report[:phases].each do |phase|
      label = phase[:label].ljust(23)
      count = phase[:count].to_s.rjust(8)
      pct = "#{phase[:percentage]}%".rjust(10)
      lines << "│ #{label} │ #{count} │ #{pct} │"
    end

    lines << '├─────────────────────────┼──────────┼────────────┤'
    total_str = total.to_s.rjust(8)
    lines << "│ TOTAL                   │ #{total_str} │       100% │"
    lines << '└─────────────────────────┴──────────┴────────────┘'
    lines << ''
    lines << "Session Impact: #{total} messages (~#{report[:session_impact]}% of 5x plan session limit)"
    lines << ''

    lines.join("\n")
  end

  # Get current usage state
  def current
    @usage
  end

  # Check if a workflow is in progress
  def in_progress?
    @usage['started_at'] && !@usage['completed_at']
  end

  # Reset usage tracking
  def reset
    @usage = {}
    save_usage
    @usage
  end

  # Delete the usage file
  def delete_file
    return { success: false, message: "Usage file doesn't exist" } unless File.exist?(USAGE_FILE)

    FileUtils.rm(USAGE_FILE)
    @usage = {}
    { success: true, message: 'Usage file deleted' }
  end

  # Output as YAML
  def to_yaml
    @usage.to_yaml
  end

  private

  def load_usage
    return {} unless File.exist?(USAGE_FILE)

    YAML.safe_load(File.read(USAGE_FILE)) || {}
  rescue StandardError => e
    warn "Warning: Could not load usage file: #{e.message}"
    {}
  end

  def save_usage
    FileUtils.mkdir_p(File.dirname(USAGE_FILE))
    File.write(USAGE_FILE, @usage.to_yaml)
  end

  def log_report(report)
    FileUtils.mkdir_p(File.dirname(USAGE_LOG_FILE))

    entry = {
      'logged_at' => Time.now.iso8601,
      'prd_path' => report[:prd_path],
      'prd_title' => report[:prd_title],
      'started_at' => report[:started_at],
      'completed_at' => report[:completed_at],
      'duration' => report[:duration],
      'total_messages' => report[:total_messages],
      'session_impact_percent' => report[:session_impact],
      'phases' => report[:phases].to_h { |p| [p[:label], p[:count]] }
    }

    File.open(USAGE_LOG_FILE, 'a') do |f|
      f.puts '---'
      f.puts entry.to_yaml.sub(/^---\n/, '')
    end
  rescue StandardError => e
    warn "Warning: Could not log usage report: #{e.message}"
  end

  def format_duration(seconds)
    if seconds < 60
      "#{seconds.round}s"
    elsif seconds < 3600
      minutes = (seconds / 60).floor
      secs = (seconds % 60).round
      "#{minutes}m #{secs}s"
    else
      hours = (seconds / 3600).floor
      minutes = ((seconds % 3600) / 60).floor
      "#{hours}h #{minutes}m"
    end
  end
end

# CLI interface when run directly
if __FILE__ == $PROGRAM_NAME
  require 'optparse'

  action = ARGV.shift
  options = {}

  OptionParser.new do |opts|
    opts.banner = 'Usage: usage_tracker.rb [action] [options]'
    opts.on('--prd-path PATH', 'PRD file path') { |v| options[:prd_path] = v }
    opts.on('--prd-title TITLE', 'PRD title') { |v| options[:prd_title] = v }
    opts.on('--phase PHASE', 'Phase to increment') { |v| options[:phase] = v }
    opts.on('--count N', Integer, 'Count to add (default: 1)') { |v| options[:count] = v }
    opts.on('--format FORMAT', 'Output format: yaml, table') { |v| options[:format] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      puts <<~HELP

        Actions:
          start         - Start tracking a new PRD workflow (requires --prd-path)
          increment     - Increment phase counter (requires --phase)
          count         - Get count for a phase (requires --phase)
          total         - Get total message count
          report        - Generate usage report
          show          - Show current usage state
          complete      - Complete workflow and generate final report
          reset         - Reset usage tracking
          delete        - Delete usage file

        Phases:
          openspec_generation, branch_setup, implementation,
          testing, pr_creation, cleanup_merge
      HELP
      exit 0
    end
  end.parse!

  tracker = UsageTracker.new
  format = options[:format] || 'yaml'

  result = case action
           when 'start'
             tracker.start_workflow(
               prd_path: options[:prd_path],
               prd_title: options[:prd_title]
             )
           when 'increment'
             count = options[:count] || 1
             new_count = tracker.increment(options[:phase], count: count)
             { phase: options[:phase], count: new_count, total: tracker.total_messages }
           when 'count'
             { phase: options[:phase], count: tracker.count_for(options[:phase]) }
           when 'total'
             { total_messages: tracker.total_messages }
           when 'report'
             if format == 'table'
               puts tracker.format_report_table
               exit 0
             else
               tracker.generate_report
             end
           when 'show'
             tracker.current
           when 'complete'
             report = tracker.complete_workflow
             if format == 'table'
               puts tracker.format_report_table(report)
               exit 0
             else
               report
             end
           when 'reset'
             tracker.reset
             { message: 'Usage tracking reset' }
           when 'delete'
             tracker.delete_file
           else
             puts "Unknown action: #{action}"
             puts 'Run with --help for usage'
             exit 1
           end

  puts result.to_yaml
end
