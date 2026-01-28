#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yaml'
require 'fileutils'

# StateManager - Manages persistent state for PRD orchestration across sessions
#
# State is stored in orch/working/state.yaml and includes:
# - Current PRD being processed
# - Current phase (prepare, proposal, prebuild, build, test, finalize)
# - Variables that need to persist across sub-agent spawns
# - Checkpoint status (awaiting_approval, awaiting_merge, etc.)
#
class StateManager
  STATE_FILE = File.expand_path('../working/state.yaml', __FILE__)

  PHASES = %w[
    idle
    prepare
    proposal
    proposal_review
    prebuild
    build
    test
    validate
    finalize
    complete
  ].freeze

  CHECKPOINTS = %w[
    none
    awaiting_clarification
    awaiting_proposal_approval
    awaiting_validation_commit
    awaiting_test_review
    spec_compliance_failed_review
    awaiting_merge
  ].freeze

  def initialize
    @state = load_state
  end

  # Get the current state as a hash
  def current
    @state
  end

  # Get a specific key from state
  def get(key)
    @state[key.to_s]
  end

  # Set a specific key in state and persist
  def set(key, value)
    @state[key.to_s] = value
    save_state
    value
  end

  # Set multiple keys at once
  def update(hash)
    hash.each { |k, v| @state[k.to_s] = v }
    save_state
    @state
  end

  # Start processing a new PRD (preserves session settings like bulk_mode)
  def start_prd(prd_path:, change_name:, branch: nil)
    preserved_bulk_mode = @state['bulk_mode']
    @state = {
      'prd_path' => prd_path,
      'change_name' => change_name,
      'branch' => branch || "feature/#{change_name}",
      'phase' => 'prepare',
      'checkpoint' => 'none',
      'started_at' => Time.now.iso8601,
      'ralph_attempts' => 0,
      'spec_compliance_attempts' => 0,
      'errors' => [],
      'warnings' => []
    }
    @state['bulk_mode'] = preserved_bulk_mode if preserved_bulk_mode
    save_state
    @state
  end

  # Transition to a new phase
  def transition_to(phase)
    unless PHASES.include?(phase)
      raise ArgumentError, "Invalid phase: #{phase}. Valid phases: #{PHASES.join(', ')}"
    end

    @state['previous_phase'] = @state['phase']
    @state['phase'] = phase
    @state['phase_started_at'] = Time.now.iso8601
    save_state
    @state
  end

  # Set a checkpoint (awaiting human intervention)
  def set_checkpoint(checkpoint)
    unless CHECKPOINTS.include?(checkpoint)
      raise ArgumentError, "Invalid checkpoint: #{checkpoint}. Valid: #{CHECKPOINTS.join(', ')}"
    end

    @state['checkpoint'] = checkpoint
    @state['checkpoint_set_at'] = Time.now.iso8601
    save_state
    @state
  end

  # Clear the checkpoint
  def clear_checkpoint
    @state['checkpoint'] = 'none'
    @state.delete('checkpoint_set_at')
    save_state
    @state
  end

  # Record an error
  def add_error(message, details: nil)
    @state['errors'] ||= []
    @state['errors'] << {
      'message' => message,
      'details' => details,
      'timestamp' => Time.now.iso8601,
      'phase' => @state['phase']
    }
    save_state
    @state
  end

  # Record a warning
  def add_warning(message, details: nil)
    @state['warnings'] ||= []
    @state['warnings'] << {
      'message' => message,
      'details' => details,
      'timestamp' => Time.now.iso8601,
      'phase' => @state['phase']
    }
    save_state
    @state
  end

  # Increment Ralph loop attempt counter
  def increment_ralph_attempts
    @state['ralph_attempts'] = (@state['ralph_attempts'] || 0) + 1
    save_state
    @state['ralph_attempts']
  end

  # Reset Ralph attempts
  def reset_ralph_attempts
    @state['ralph_attempts'] = 0
    save_state
  end

  # Increment spec compliance attempt counter
  def increment_spec_compliance_attempts
    @state['spec_compliance_attempts'] = (@state['spec_compliance_attempts'] || 0) + 1
    save_state
    @state['spec_compliance_attempts']
  end

  # Reset spec compliance attempts
  def reset_spec_compliance_attempts
    @state['spec_compliance_attempts'] = 0
    save_state
  end

  # Check if processing is in progress
  def in_progress?
    @state['phase'] && @state['phase'] != 'idle' && @state['phase'] != 'complete'
  end

  # Check if at a checkpoint
  def at_checkpoint?
    @state['checkpoint'] && @state['checkpoint'] != 'none'
  end

  # Check if a specific phase is complete
  def phase_complete?(expected_phase)
    @state['phase'] == expected_phase
  end

  # Check if currently at a checkpoint that needs human intervention
  def checkpoint_active?
    checkpoint = @state['checkpoint']
    checkpoint && checkpoint != 'none'
  end

  # Get time since phase started (in seconds)
  def phase_duration
    return 0 unless @state['phase_started_at']
    Time.now - Time.parse(@state['phase_started_at'])
  end

  # Check if phase has any errors
  def has_errors?
    errors = @state['errors']
    errors && errors.is_a?(Array) && !errors.empty?
  end

  # Complete the current PRD
  def complete
    @state['phase'] = 'complete'
    @state['checkpoint'] = 'none'
    @state['completed_at'] = Time.now.iso8601
    save_state
    @state
  end

  # Reset state (clear PRD-specific data, preserve session settings like bulk_mode)
  def reset
    preserved_bulk_mode = @state['bulk_mode']
    @state = { 'phase' => 'idle', 'checkpoint' => 'none' }
    @state['bulk_mode'] = preserved_bulk_mode if preserved_bulk_mode
    save_state
    @state
  end

  # Delete the state file completely
  def delete_file
    return { success: false, message: "State file doesn't exist" } unless File.exist?(STATE_FILE)

    FileUtils.rm(STATE_FILE)
    @state = default_state
    { success: true, message: "State file deleted" }
  end

  # Set bulk mode for the session
  def set_bulk_mode(value)
    @state['bulk_mode'] = value
    save_state
    value
  end

  # Get bulk mode setting
  def bulk_mode?
    @state['bulk_mode'] == true || @state['bulk_mode'] == 'true'
  end

  # Output state as YAML for agent consumption
  def to_yaml
    @state.to_yaml
  end

  # Output state as JSON
  def to_json(*_args)
    require 'json'
    @state.to_json
  end

  private

  def load_state
    return default_state unless File.exist?(STATE_FILE)

    YAML.safe_load(File.read(STATE_FILE)) || default_state
  rescue StandardError => e
    warn "Warning: Could not load state file: #{e.message}"
    default_state
  end

  def save_state
    FileUtils.mkdir_p(File.dirname(STATE_FILE))
    File.write(STATE_FILE, @state.to_yaml)
  end

  def default_state
    { 'phase' => 'idle', 'checkpoint' => 'none' }
  end
end

# CLI interface when run directly
if __FILE__ == $PROGRAM_NAME
  require 'optparse'

  action = ARGV.shift
  options = {}

  OptionParser.new do |opts|
    opts.banner = "Usage: state_manager.rb [action] [options]"
    opts.on('--prd-path PATH', 'PRD file path') { |v| options[:prd_path] = v }
    opts.on('--change-name NAME', 'Change name') { |v| options[:change_name] = v }
    opts.on('--branch BRANCH', 'Branch name') { |v| options[:branch] = v }
    opts.on('--phase PHASE', 'Phase to transition to') { |v| options[:phase] = v }
    opts.on('--checkpoint CHECKPOINT', 'Checkpoint to set') { |v| options[:checkpoint] = v }
    opts.on('--key KEY', 'Key to get/set') { |v| options[:key] = v }
    opts.on('--value VALUE', 'Value to set') { |v| options[:value] = v }
    opts.on('--message MSG', 'Error/warning message') { |v| options[:message] = v }
    opts.on('--format FORMAT', 'Output format: yaml, json') { |v| options[:format] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      puts <<~HELP

        Actions:
          show          - Show current state
          start         - Start processing a PRD (requires --prd-path, --change-name)
          transition    - Transition to phase (requires --phase)
          checkpoint    - Set checkpoint (requires --checkpoint)
          clear         - Clear checkpoint
          get           - Get a key (requires --key)
          set           - Set a key (requires --key, --value)
          error         - Record an error (requires --message)
          warning       - Record a warning (requires --message)
          ralph         - Increment Ralph attempt counter
          spec-compliance - Increment spec compliance attempt counter
          complete      - Mark PRD as complete
          reset         - Reset all state
          delete        - Delete state file completely
      HELP
      exit 0
    end
  end.parse!

  manager = StateManager.new
  format = options[:format] || 'yaml'

  result = case action
  when 'show'
             manager.current
  when 'start'
             manager.start_prd(
               prd_path: options[:prd_path],
               change_name: options[:change_name],
               branch: options[:branch]
             )
  when 'transition'
             manager.transition_to(options[:phase])
  when 'checkpoint'
             manager.set_checkpoint(options[:checkpoint])
  when 'clear'
             manager.clear_checkpoint
  when 'get'
             { options[:key] => manager.get(options[:key]) }
  when 'set'
             manager.set(options[:key], options[:value])
  when 'error'
             manager.add_error(options[:message])
  when 'warning'
             manager.add_warning(options[:message])
  when 'ralph'
             { 'ralph_attempts' => manager.increment_ralph_attempts }
  when 'spec-compliance'
             { 'spec_compliance_attempts' => manager.increment_spec_compliance_attempts }
  when 'complete'
             manager.complete
  when 'reset'
             manager.reset
  when 'delete'
             manager.delete_file
  else
             puts "Unknown action: #{action}"
             puts "Run with --help for usage"
             exit 1
  end

  output = format == 'json' ? result.to_json : result.to_yaml
  puts output
end
