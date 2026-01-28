#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yaml'
require 'time'
require 'fileutils'
require_relative 'logger'

# PrdValidator - Manages PRD validation state in YAML frontmatter
#
# Handles reading and writing validation metadata in PRD markdown files.
# Validation metadata is stored in YAML frontmatter at the top of the file.
#
# Status values:
# - 'valid' - PRD passed validation checks
# - 'invalid' - PRD failed validation with documented errors
# - 'unvalidated' - PRD has not been validated yet
#
class PrdValidator
  FRONTMATTER_DELIMITER = "---\n"
  STATUSES = %w[valid invalid unvalidated].freeze

  class << self
    def logger
      @logger ||= OrchLogger.new('PrdValidator')
    end

    # Read validation metadata from PRD file
    #
    # @param prd_path [String] Path to PRD file
    # @return [Hash] Validation metadata or empty hash if none exists
    def read_metadata(prd_path)
      logger.debug("Reading validation metadata", { prd_path: prd_path })
      return {} unless File.exist?(prd_path)

      content = File.read(prd_path)
      frontmatter = extract_frontmatter(content)

      return {} unless frontmatter

      begin
        parsed = YAML.safe_load(frontmatter)
        metadata = parsed.is_a?(Hash) ? (parsed['validation'] || {}) : {}
        logger.debug("Metadata read successfully", { prd_path: prd_path, status: metadata['status'] })
        metadata
      rescue Psych::SyntaxError => e
        logger.warn("Failed to parse YAML frontmatter", { prd_path: prd_path, error: e.message })
        warn "Warning: Failed to parse YAML frontmatter in #{prd_path}: #{e.message}"
        {}
      end
    end

    # Get validation status from PRD file
    #
    # @param prd_path [String] Path to PRD file
    # @return [String] 'valid', 'invalid', or 'unvalidated'
    def get_status(prd_path)
      metadata = read_metadata(prd_path)
      status = metadata['status']

      STATUSES.include?(status) ? status : 'unvalidated'
    end

    # Write validation status to PRD file frontmatter
    #
    # @param prd_path [String] Path to PRD file
    # @param status [String] 'valid', 'invalid', or 'unvalidated'
    # @param errors [Array<String>] List of validation errors (for invalid status)
    # @return [Boolean] True if successful
    def write_validation_status(prd_path, status, errors: [])
      logger.info("Writing validation status", { prd_path: prd_path, status: status, error_count: errors.length })

      unless STATUSES.include?(status)
        logger.warn("Invalid validation status", { status: status, valid_statuses: STATUSES })
        raise ArgumentError, "Invalid status: #{status}. Must be one of: #{STATUSES.join(', ')}"
      end

      unless File.exist?(prd_path)
        logger.warn("PRD file not found", { prd_path: prd_path })
        raise ArgumentError, "PRD file not found: #{prd_path}"
      end

      content = File.read(prd_path)
      frontmatter, body = split_frontmatter(content)

      # Parse existing frontmatter or create new
      metadata = if frontmatter
                   begin
                     YAML.safe_load(frontmatter) || {}
                   rescue Psych::SyntaxError
                     logger.warn("Corrupted frontmatter, replacing", { prd_path: prd_path })
                     warn "Warning: Corrupted frontmatter, replacing with new"
                     {}
                   end
      else
                   {}
      end

      # Update validation metadata
      validation_data = {
        'status' => status,
        'validated_at' => Time.now.iso8601
      }

      if status == 'invalid' && !errors.empty?
        validation_data['validation_errors'] = errors
      end

      metadata['validation'] = validation_data

      # Write updated file
      new_content = build_file_content(metadata, body)
      File.write(prd_path, new_content)

      logger.info("Validation status written successfully", { prd_path: prd_path })
      true
    end

    # List all PRDs with their validation status
    #
    # @param prds_root [String] Root directory for PRDs (default: docs/prds)
    # @return [Array<Hash>] Array of {path:, status:, subsystem:, name:}
    def list_all(prds_root = 'docs/prds')
      logger.info("Listing all PRDs", { prds_root: prds_root })
      return [] unless Dir.exist?(prds_root)

      prds = []

      Dir.glob(File.join(prds_root, '*', '*.md')).each do |path|
        # Skip done/ directories
        next if path.include?('/done/')

        subsystem = File.basename(File.dirname(path))
        name = File.basename(path, '.md')
        status = get_status(path)

        prds << {
          path: path,
          status: status,
          subsystem: subsystem,
          name: name,
          metadata: read_metadata(path)
        }
      end

      logger.info("PRD list generated", { total: prds.length })
      prds.sort_by { |p| [ p[:subsystem], p[:name] ] }
    end

    private

    # Extract frontmatter from file content
    #
    # @param content [String] File content
    # @return [String, nil] Frontmatter YAML or nil if none exists
    def extract_frontmatter(content)
      return nil unless content.start_with?(FRONTMATTER_DELIMITER)

      # Find the closing delimiter
      rest = content[FRONTMATTER_DELIMITER.length..]
      end_index = rest.index(FRONTMATTER_DELIMITER)

      return nil unless end_index

      rest[0...end_index]
    end

    # Split content into frontmatter and body
    #
    # @param content [String] File content
    # @return [Array<String, String>] [frontmatter_yaml, body_content]
    def split_frontmatter(content)
      if content.start_with?(FRONTMATTER_DELIMITER)
        rest = content[FRONTMATTER_DELIMITER.length..]
        end_index = rest.index(FRONTMATTER_DELIMITER)

        if end_index
          frontmatter = rest[0...end_index]
          body_start = FRONTMATTER_DELIMITER.length + end_index + FRONTMATTER_DELIMITER.length
          body = content[body_start..]
          return [ frontmatter, body ]
        end
      end

      # No frontmatter found
      [ nil, content ]
    end

    # Build file content from frontmatter and body
    #
    # @param metadata [Hash] Frontmatter metadata
    # @param body [String] Body content
    # @return [String] Complete file content
    def build_file_content(metadata, body)
      # Ensure body starts with a newline if it doesn't already
      body = "\n#{body}" unless body.start_with?("\n")

      FRONTMATTER_DELIMITER + metadata.to_yaml.sub(/^---\n/, '') + FRONTMATTER_DELIMITER + body
    end
  end
end

# CLI interface when run directly
if __FILE__ == $PROGRAM_NAME
  require 'optparse'

  action = ARGV.shift
  options = {}

  OptionParser.new do |opts|
    opts.banner = "Usage: prd_validator.rb [action] [options]"

    opts.on('--prd-path PATH', 'PRD file path') { |v| options[:prd_path] = v }
    opts.on('--status STATUS', 'Validation status (valid, invalid, unvalidated)') { |v| options[:status] = v }
    opts.on('--errors ERROR1,ERROR2', Array, 'Validation errors (comma-separated)') { |v| options[:errors] = v }
    opts.on('--prds-root PATH', 'PRDs root directory (default: docs/prds)') { |v| options[:prds_root] = v }

    opts.on('-h', '--help', 'Show help') do
      puts opts
      puts <<~HELP

        Actions:
          status        - Get validation status of a PRD (requires --prd-path)
          update        - Update validation status (requires --prd-path, --status)
          list-all      - List all PRDs with validation status (optional --prds-root)
          metadata      - Show full validation metadata (requires --prd-path)

        Examples:
          # Get status
          ruby orch/prd_validator.rb status --prd-path docs/prds/campaigns/my-prd.md

          # Mark as valid
          ruby orch/prd_validator.rb update --prd-path docs/prds/campaigns/my-prd.md --status valid

          # Mark as invalid with errors
          ruby orch/prd_validator.rb update --prd-path docs/prds/campaigns/my-prd.md --status invalid --errors "Missing section,TODO markers found"

          # List all PRDs
          ruby orch/prd_validator.rb list-all

          # Show full metadata
          ruby orch/prd_validator.rb metadata --prd-path docs/prds/campaigns/my-prd.md
      HELP
      exit 0
    end
  end.parse!

  case action
  when 'status'
    unless options[:prd_path]
      puts "Error: --prd-path required"
      exit 1
    end

    status = PrdValidator.get_status(options[:prd_path])
    puts status

  when 'metadata'
    unless options[:prd_path]
      puts "Error: --prd-path required"
      exit 1
    end

    metadata = PrdValidator.read_metadata(options[:prd_path])
    puts metadata.to_yaml

  when 'update'
    unless options[:prd_path] && options[:status]
      puts "Error: --prd-path and --status required"
      exit 1
    end

    begin
      PrdValidator.write_validation_status(
        options[:prd_path],
        options[:status],
        errors: options[:errors] || []
      )
      puts "✓ Updated validation status to: #{options[:status]}"
    rescue ArgumentError => e
      puts "Error: #{e.message}"
      exit 1
    end

  when 'list-all'
    prds_root = options[:prds_root] || 'docs/prds'
    prds = PrdValidator.list_all(prds_root)

    if prds.empty?
      puts "No PRDs found in #{prds_root}"
      exit 0
    end

    current_subsystem = nil
    prds.each do |prd|
      if prd[:subsystem] != current_subsystem
        puts "\n#{prd[:subsystem]}/" if current_subsystem
        puts "#{prd[:subsystem]}/" unless current_subsystem
        current_subsystem = prd[:subsystem]
      end

      status_badge = case prd[:status]
      when 'valid'
                       validated_at = prd.dig(:metadata, 'validated_at')
                       date = validated_at ? Time.parse(validated_at).strftime('%b %-d') : 'unknown'
                       "[✓ Valid - #{date}]"
      when 'invalid'
                       error_count = prd.dig(:metadata, 'validation_errors')&.length || 0
                       "[✗ Invalid - #{error_count} error#{'s' if error_count != 1}]"
      else
                       "[⊗ Unvalidated]"
      end

      puts "  - #{prd[:name]}.md #{status_badge}"
      puts "    #{prd[:path]}"
    end

    puts "\nTotal: #{prds.length} PRDs"

  else
    puts "Unknown action: #{action}"
    puts "Run with --help for usage"
    exit 1
  end
end
