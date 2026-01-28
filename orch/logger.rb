#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yaml'
require 'fileutils'

# OrchLogger - Centralized logging for orchestration components
#
# Provides structured logging with configurable levels and consistent formatting
# across all orchestration Ruby components.
#
# Features:
# - Unified log file per orchestration run
# - Configurable log levels: debug, info, warn
# - Rich context on each line: timestamp, level, component, phase, change_name
# - Thread-safe file appending
#
# Usage:
#   logger = OrchLogger.new('ComponentName')
#   logger.info('Processing started')
#   logger.debug('Detailed information', { data: value })
#   logger.warn('Something unexpected happened')
#
class OrchLogger
  LEVELS = {
    debug: 0,
    info: 1,
    warn: 2
  }.freeze

  CONFIG_FILE = File.expand_path('../config.yaml', __FILE__)
  STATE_FILE = File.expand_path('../working/state.yaml', __FILE__)

  attr_reader :component_name

  def initialize(component_name)
    @component_name = component_name
    @config = load_config
    @log_level = parse_level(@config.dig('logging', 'level') || 'info')
    @mutex = Mutex.new
  end

  # Log at debug level - detailed execution information
  def debug(message, data = nil)
    log(:debug, message, data)
  end

  # Log at info level - major steps and phase transitions
  def info(message, data = nil)
    log(:info, message, data)
  end

  # Log at warn level - warnings and errors
  def warn(message, data = nil)
    log(:warn, message, data)
  end

  # Alias error to warn (same severity level)
  def error(message, data = nil)
    log(:warn, message, data)
  end

  private

  def log(level, message, data = nil)
    return if LEVELS[level] < @log_level

    log_file = get_log_file
    return unless log_file # Can't log if no log file configured

    context = get_context
    formatted_line = format_log_line(level, message, context, data)

    @mutex.synchronize do
      File.open(log_file, 'a') do |f|
        f.puts formatted_line
        f.flush # Ensure immediate write for tail -f
      end
    end
  rescue StandardError => e
    # Fallback to stderr if logging fails
    warn "Logging failed: #{e.message}"
  end

  def format_log_line(level, message, context, data)
    timestamp = Time.now.strftime('%Y-%m-%dT%H:%M:%S.%3N')
    level_str = level.to_s.upcase.ljust(5)
    component_str = @component_name.ljust(20)
    phase_str = (context['phase'] || 'unknown').ljust(15)
    change_str = (context['change_name'] || '').ljust(25)

    line = "[#{timestamp}] [#{level_str}] [#{component_str}] [phase=#{phase_str}] [change=#{change_str}] #{message}"

    if data
      line += " | #{data.inspect}"
    end

    line
  end

  def get_context
    return {} unless File.exist?(STATE_FILE)

    state = YAML.safe_load(File.read(STATE_FILE)) || {}
    {
      'phase' => state['phase'],
      'change_name' => state['change_name']
    }
  rescue StandardError
    {}
  end

  def get_log_file
    return @log_file if @log_file

    config = load_config
    log_dir = config.dig('logging', 'log_directory') || 'log'
    log_dir_path = File.expand_path("../#{log_dir}", __FILE__)
    FileUtils.mkdir_p(log_dir_path)

    @log_file = File.join(log_dir_path, 'orchestrator.log')
  end

  def load_config
    return {} unless File.exist?(CONFIG_FILE)

    YAML.safe_load(File.read(CONFIG_FILE)) || {}
  rescue StandardError => e
    warn "Warning: Could not load config file: #{e.message}"
    {}
  end

  def parse_level(level_str)
    level_sym = level_str.to_s.downcase.to_sym
    LEVELS[level_sym] || LEVELS[:info]
  end
end
