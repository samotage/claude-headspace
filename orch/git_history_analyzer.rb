#!/usr/bin/env ruby
# frozen_string_literal: true

require_relative 'logger'
require 'yaml'
require 'date'

# Git History Analyzer - Extracts contextual information from git history
# to inform PRD development and OpenSpec proposal generation
#
# This module provides context about:
# - Related files already in the codebase for a given subsystem
# - Recent commits (last 12 months by default)
# - OpenSpec changes previously applied
# - Implementation patterns detected (models, services, controllers, etc.)
#
# Usage:
#   analyzer = GitHistoryAnalyzer.new(subsystem: 'inquiry-system')
#   result = analyzer.analyze
#   puts result.to_yaml
#
class GitHistoryAnalyzer
  def initialize(subsystem: nil, prd_path: nil, months_back: 12)
    @subsystem = subsystem
    @prd_path = prd_path
    @months_back = months_back
    @logger = OrchLogger.new('GitHistoryAnalyzer')
  end

  def analyze
    @logger.info("Starting git history analysis", {
      subsystem: @subsystem,
      prd_path: @prd_path,
      months_back: @months_back
    })

    result = {
      'subsystem' => @subsystem,
      'analysis_date' => Time.now.iso8601,
      'timeframe_months' => @months_back,
      'related_files' => find_related_files,
      'recent_commits' => fetch_recent_commits,
      'openspec_history' => analyze_openspec_history,
      'patterns_detected' => detect_implementation_patterns
    }

    @logger.info("Git history analysis complete", {
      files_found: result['related_files'].values.flatten.length,
      commits_found: result['recent_commits'].length,
      changes_found: result['openspec_history'].length
    })

    result
  end

  private

  def find_related_files
    # Find files related to the subsystem
    search_pattern = derive_search_pattern

    files = `git ls-files | grep -iE "#{search_pattern}"`.split("\n")

    # Categorize by type
    categorize_files(files)
  end

  def fetch_recent_commits(limit: 20)
    # Get recent commits related to subsystem
    search_pattern = derive_search_pattern
    since_date = (Date.today << @months_back).strftime('%Y-%m-%d')

    # Format: sha|date|author|message
    commits_raw = `git log --since="#{since_date}" --grep="#{@subsystem}" --format="%H|%ai|%an|%s" --no-merges`.split("\n")

    commits = commits_raw.first(limit).map do |line|
      sha, date, author, message = line.split('|', 4)
      {
        'sha' => sha[0..7],
        'date' => date,
        'author' => author,
        'message' => message,
        'files_changed' => get_commit_files(sha)
      }
    end

    commits
  end

  def analyze_openspec_history
    # Find archived OpenSpec changes related to this subsystem
    archives = Dir.glob("openspec/changes/archive/**/*#{@subsystem}*/")

    archives.map do |archive_path|
      change_name = File.basename(archive_path).gsub(/^\d{4}-\d{2}-\d{2}-/, '')
      proposal_file = File.join(archive_path, 'proposal.md')

      next unless File.exist?(proposal_file)

      {
        'change_name' => change_name,
        'archive_path' => archive_path,
        'archived_date' => extract_archive_date(archive_path),
        'affected_specs' => find_affected_specs(archive_path)
      }
    end.compact
  end

  def detect_implementation_patterns
    # Analyze file structure to detect patterns
    files = find_related_files

    {
      'has_main_modules' => files['main']&.any? || false,
      'has_modules' => files['modules']&.any? || false,
      'has_tests' => files['tests']&.any? || false,
      'has_templates' => files['templates']&.any? || false,
      'has_static' => files['static']&.any? || false,
      'has_bin' => files['bin']&.any? || false,
      'has_config' => files['config']&.any? || false,
      'typical_structure' => derive_typical_structure(files)
    }
  end

  def derive_search_pattern
    if @subsystem
      # Convert subsystem name to various patterns
      # e.g., "inquiry-system" -> "inquiry"
      base = @subsystem.gsub(/-system$/, '').gsub(/-/, '_')
      base
    elsif @prd_path
      # Extract from PRD path
      File.basename(@prd_path, '.md').gsub(/-prd$/, '').gsub(/-/, '_')
    else
      ''
    end
  end

  def categorize_files(files)
    {
      'main' => files.grep(/^[^\/]+\.py$/),
      'modules' => files.grep(/\.py$/).reject { |f| f.start_with?('tests/') || f =~ /test_|_test\.py$/ },
      'tests' => files.grep(/tests\/|test_|_test\.py/),
      'templates' => files.grep(/templates\//),
      'static' => files.grep(/static\//),
      'bin' => files.grep(/^bin\//),
      'config' => files.grep(/config|\.yaml|\.yml|\.json/)
    }
  end

  def get_commit_files(sha)
    `git show --name-only --format="" #{sha}`.split("\n").first(5)
  end

  def extract_archive_date(path)
    match = File.basename(path).match(/^(\d{4}-\d{2}-\d{2})/)
    match ? match[1] : nil
  end

  def find_affected_specs(archive_path)
    specs_dir = File.join(archive_path, 'specs')
    return [] unless Dir.exist?(specs_dir)

    Dir.glob("#{specs_dir}/*").map { |d| File.basename(d) }
  end

  def derive_typical_structure(files)
    structure = []
    structure << 'main_module' if files['main']&.any?
    structure << 'modules' if files['modules']&.any?
    structure << 'tests' if files['tests']&.any?
    structure << 'templates' if files['templates']&.any?
    structure << 'static' if files['static']&.any?
    structure << 'bin' if files['bin']&.any?
    structure << 'config' if files['config']&.any?
    structure
  end
end

# CLI interface
if __FILE__ == $PROGRAM_NAME
  require 'optparse'

  options = { months_back: 12 }

  OptionParser.new do |opts|
    opts.banner = "Usage: git_history_analyzer.rb [options]"
    opts.on('--subsystem NAME', 'Subsystem name') { |v| options[:subsystem] = v }
    opts.on('--prd-path PATH', 'PRD file path') { |v| options[:prd_path] = v }
    opts.on('--months-back N', Integer, 'Months to look back (default: 12)') { |v| options[:months_back] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      exit 0
    end
  end.parse!

  analyzer = GitHistoryAnalyzer.new(
    subsystem: options[:subsystem],
    prd_path: options[:prd_path],
    months_back: options[:months_back]
  )

  result = analyzer.analyze
  puts result.to_yaml
end
