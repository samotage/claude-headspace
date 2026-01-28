#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative '../state_manager'
require_relative '../logger'

# Build Command - Implementation phase support
#
# Provides structured information for the AI agent to execute
# the implementation tasks from the OpenSpec tasks.md file.
#
# Output: YAML with tasks to implement and guidance
#
class BuildCommand
  def initialize(change_name: nil, prd_path: nil)
    @state = StateManager.new
    @change_name = change_name || @state.get('change_name')
    @prd_path = prd_path || @state.get('prd_path')
    @logger = OrchLogger.new('BuildCommand')
  end

  def execute
    @logger.info("Starting build command", { change_name: @change_name, prd_path: @prd_path })

    result = {
      'command' => 'build',
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

      @logger.debug("Loading tasks")
      load_tasks(result)

      @logger.debug("Loading PRD context")
      load_prd_context(result)

      @logger.debug("Adding build guidance")
      add_build_guidance(result)

      @logger.info("Transitioning to build phase")
      @state.transition_to('build')

    rescue StandardError => e
      @logger.warn("Exception during build execution", { error: e.message })
      result['status'] = 'error'
      result['errors'] << { 'type' => 'exception', 'message' => e.message }
    end

    @logger.info("Build command completed", {
      status: result['status'],
      tasks_total: result.dig('data', 'progress', 'implementation_total')
    })
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
      return
    end

    @tasks_path = "openspec/changes/#{@change_name}/tasks.md"
    unless File.exist?(@tasks_path)
      result['status'] = 'error'
      result['errors'] << {
        'type' => 'tasks_not_found',
        'message' => "Tasks file not found: #{@tasks_path}",
        'resolution' => 'Run proposal command first'
      }
    end
  end

  def load_tasks(result)
    content = File.read(@tasks_path)

    result['data']['tasks_file'] = @tasks_path
    result['data']['change_name'] = @change_name
    result['data']['branch'] = @state.get('branch') || "feature/#{@change_name}"

    # Parse tasks
    tasks = parse_tasks(content)
    result['data']['tasks'] = tasks

    # Count completion status
    implementation_tasks = tasks['implementation'] || []
    completed = implementation_tasks.count { |t| t['completed'] }
    total = implementation_tasks.length

    result['data']['progress'] = {
      'implementation_completed' => completed,
      'implementation_total' => total,
      'percentage' => total > 0 ? (completed.to_f / total * 100).round(1) : 0
    }
  end

  def parse_tasks(content)
    tasks = {
      'planning' => [],
      'implementation' => [],
      'testing' => [],
      'verification' => []
    }

    current_section = nil
    content.each_line do |line|
      if line =~ /^##\s+\d+\.\s+(\w+)/i
        section = $1.downcase
        current_section = case section
        when 'planning' then 'planning'
        when 'implementation' then 'implementation'
        when 'testing' then 'testing'
        when 'final', 'verification' then 'verification'
        else nil
        end
      elsif current_section && line =~ /^-\s+\[([ xX])\]\s+(\d+\.\d+)\s+(.*)/
        tasks[current_section] << {
          'number' => $2,
          'completed' => $1.downcase == 'x',
          'description' => $3.strip
        }
      end
    end

    tasks
  end

  def load_prd_context(result)
    return unless @prd_path && File.exist?(@prd_path)

    content = File.read(@prd_path)

    # Extract key sections for context
    result['data']['prd_context'] = {
      'path' => @prd_path,
      'technical_hints' => extract_section(content, 'Technical Implementation'),
      'files_mentioned' => extract_file_paths(content)
    }
  end

  def extract_section(content, section_name)
    pattern = /^##\s*#{Regexp.escape(section_name)}\s*\n(.*?)(?=^##|\z)/mi
    match = content.match(pattern)
    match ? match[1].strip : nil
  end

  def extract_file_paths(content)
    # Find file paths mentioned in backticks
    paths = content.scan(/`([^`]+\.(rb|erb|haml|js|css|yml|yaml|json))`/)
    paths.flatten.uniq.select { |p| p.include?('/') || p.include?('.') }
  end

  def add_build_guidance(result)
    incomplete_tasks = (result['data']['tasks']['implementation'] || []).reject { |t| t['completed'] }
    all_tasks_complete = incomplete_tasks.empty?

    if all_tasks_complete
      # All implementation tasks are complete - direct to TEST phase
      @logger.info("All implementation tasks complete - directing to TEST phase")

      result['data']['implementation_complete'] = true
      result['next_steps'] = [
        {
          'action' => 'proceed_to_test',
          'description' => 'All implementation tasks are complete. Proceed to TEST phase.',
          'command' => 'ruby orch/orchestrator.rb test',
          'auto_proceed' => @state.bulk_mode?
        }
      ]

      result['data']['guidance'] = {
        'status' => 'IMPLEMENTATION COMPLETE',
        'next_phase' => 'TEST',
        'instruction' => 'Run the test command to begin the TEST phase'
      }
    else
      # Still have tasks to implement
      result['data']['implementation_complete'] = false
      result['next_steps'] = [
        {
          'action' => 'implement_tasks',
          'description' => 'Implement each task sequentially',
          'tasks_remaining' => incomplete_tasks.length,
          'first_task' => incomplete_tasks.first
        },
        {
          'action' => 'update_tasks_file',
          'description' => 'Mark tasks complete in tasks.md as you go',
          'file' => @tasks_path
        },
        {
          'action' => 'run_tests',
          'description' => 'Run relevant tests after each major component',
          'note' => 'Fix failures before proceeding'
        }
      ]

      result['data']['guidance'] = {
        'approach' => 'Implement tasks one at a time, testing as you go',
        'on_error' => 'If stuck, document the issue and proceed to next task',
        'completion' => 'When all implementation tasks are marked [x], proceed to test phase'
      }
    end
  end
end

# CLI interface
if __FILE__ == $PROGRAM_NAME
  require 'optparse'
  require 'yaml'

  options = { format: 'yaml' }

  OptionParser.new do |opts|
    opts.banner = "Usage: build.rb [options]"
    opts.on('--change-name NAME', 'Change name') { |v| options[:change_name] = v }
    opts.on('--prd-path PATH', 'Path to PRD file') { |v| options[:prd_path] = v }
    opts.on('--format FORMAT', 'Output format: yaml, json') { |v| options[:format] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      exit 0
    end
  end.parse!

  cmd = BuildCommand.new(
    change_name: options[:change_name],
    prd_path: options[:prd_path]
  )
  result = cmd.execute

  output = options[:format] == 'json' ? result.to_json : result.to_yaml
  puts output

  exit(result['status'] == 'success' ? 0 : 1)
end
