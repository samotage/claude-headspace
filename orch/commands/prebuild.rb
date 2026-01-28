#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative '../state_manager'
require_relative '../logger'

# Prebuild Command - Create safety snapshot commit before build
#
# Commits the approved OpenSpec proposal as a checkpoint before
# the implementation build begins.
#
# Output: YAML with commit details and verification
#
class PrebuildCommand
  def initialize(change_name: nil)
    @state = StateManager.new
    @change_name = change_name || @state.get('change_name')
    @logger = OrchLogger.new('PrebuildCommand')
  end

  def execute
    @logger.info("Starting prebuild command", { change_name: @change_name })

    result = {
      'command' => 'prebuild',
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

      @logger.debug("Checking git status")
      check_git_status(result)
      return result if result['status'] == 'error'

      @logger.debug("Preparing commit")
      prepare_commit(result)
      add_next_steps(result)

      @logger.info("Transitioning to prebuild phase")
      @state.transition_to('prebuild')

    rescue StandardError => e
      @logger.warn("Exception during prebuild execution", { error: e.message })
      result['status'] = 'error'
      result['errors'] << { 'type' => 'exception', 'message' => e.message }
    end

    @logger.info("Prebuild command completed", { status: result['status'] })
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

    openspec_dir = "openspec/changes/#{@change_name}"
    unless Dir.exist?(openspec_dir)
      result['status'] = 'error'
      result['errors'] << {
        'type' => 'openspec_not_found',
        'message' => "OpenSpec directory not found: #{openspec_dir}",
        'resolution' => 'Run proposal command first to create OpenSpec files'
      }
    end
  end

  def check_git_status(result)
    status = `git status --porcelain 2>/dev/null`
    openspec_dir = "openspec/changes/#{@change_name}"

    staged_files = []
    unstaged_spec_files = []
    app_code_files = []

    status.each_line do |line|
      status_code = line[0..1]
      filepath = line[3..].strip

      if filepath.start_with?(openspec_dir) || filepath.start_with?('openspec/')
        if status_code.include?('?') || status_code.include?('M') || status_code.include?('A')
          unstaged_spec_files << filepath
        end
      elsif filepath.match?(%r{^(app/|spec/|lib/)})
        app_code_files << filepath
      end

      staged_files << filepath if status_code[0] != ' ' && status_code[0] != '?'
    end

    result['data']['git_status'] = {
      'staged_files' => staged_files,
      'unstaged_spec_files' => unstaged_spec_files,
      'app_code_files' => app_code_files
    }

    # Warn about app code files
    if app_code_files.any?
      result['warnings'] << {
        'type' => 'app_code_detected',
        'message' => 'App/spec code files detected in working tree',
        'files' => app_code_files,
        'note' => 'These will NOT be included in prebuild commit'
      }
    end
  end

  def prepare_commit(result)
    openspec_dir = "openspec/changes/#{@change_name}"

    result['data']['commit'] = {
      'files_to_add' => [ openspec_dir ],
      'message' => "chore(spec): #{@change_name} pre-build snapshot",
      'commands' => [
        "git add #{openspec_dir}/",
        "git commit -m \"chore(spec): #{@change_name} pre-build snapshot\""
      ]
    }

    # Check current branch for push command
    current_branch = `git branch --show-current 2>/dev/null`.strip
    result['data']['commit']['push_command'] = "git push -u origin #{current_branch}"
    result['data']['current_branch'] = current_branch
  end

  def add_next_steps(result)
    result['next_steps'] = [
      {
        'action' => 'stage_files',
        'command' => result['data']['commit']['commands'][0],
        'description' => 'Stage OpenSpec files'
      },
      {
        'action' => 'commit',
        'command' => result['data']['commit']['commands'][1],
        'description' => 'Commit prebuild snapshot'
      },
      {
        'action' => 'push',
        'command' => result['data']['commit']['push_command'],
        'description' => 'Push to remote',
        'optional' => true
      },
      {
        'action' => 'compact',
        'command' => '/compact',
        'description' => 'Compact context before build phase',
        'note' => 'AI agent must run /compact command'
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
    opts.banner = "Usage: prebuild.rb [options]"
    opts.on('--change-name NAME', 'Change name') { |v| options[:change_name] = v }
    opts.on('--format FORMAT', 'Output format: yaml, json') { |v| options[:format] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      exit 0
    end
  end.parse!

  cmd = PrebuildCommand.new(change_name: options[:change_name])
  result = cmd.execute

  output = options[:format] == 'json' ? result.to_json : result.to_yaml
  puts output

  exit(result['status'] == 'success' ? 0 : 1)
end
