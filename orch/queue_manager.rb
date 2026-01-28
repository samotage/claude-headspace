#!/usr/bin/env ruby
# frozen_string_literal: true

require 'yaml'
require 'fileutils'
require_relative 'logger'

# QueueManager - Manages the PRD queue for continuous processing
#
# Queue is stored in orch/working/queue.yaml and contains:
# - Ordered list of PRD paths to process
# - Status of each item (pending, in_progress, completed, failed)
#
class QueueManager
  QUEUE_FILE = File.expand_path('../working/queue.yaml', __FILE__)

  STATUSES = %w[pending in_progress completed failed skipped].freeze

  def initialize
    @queue = load_queue
    @logger = OrchLogger.new('QueueManager')
  end

  # Get the full queue
  def all
    @queue
  end

  # Get only pending items
  def pending
    @queue.select { |item| item['status'] == 'pending' }
  end

  # Get the next pending item
  def next_pending
    item = @queue.find { |i| i['status'] == 'pending' }
    @logger.debug("Getting next pending item", { found: !item.nil?, prd_path: item&.[]('prd_path') })
    item
  end

  # Get the current in_progress item
  def current
    @queue.find { |item| item['status'] == 'in_progress' }
  end

  # Add a PRD to the queue
  def add(prd_path, priority: nil)
    @logger.info("Adding PRD to queue", { prd_path: prd_path, priority: priority })

    # Derive change name from path
    filename = File.basename(prd_path, '.md').sub(/-prd$/, '')
    change_name = filename

    # Check if already in queue
    existing = @queue.find { |item| item['prd_path'] == prd_path }
    if existing
      @logger.warn("PRD already in queue", { prd_path: prd_path, status: existing['status'] })
      return { success: false, message: "PRD already in queue: #{prd_path}", item: existing }
    end

    item = {
      'prd_path' => prd_path,
      'change_name' => change_name,
      'status' => 'pending',
      'added_at' => Time.now.iso8601,
      'priority' => priority || @queue.length + 1
    }

    @queue << item
    sort_by_priority
    save_queue

    position = position_of(prd_path)
    @logger.info("PRD added to queue successfully", { prd_path: prd_path, position: position })
    { success: true, message: "Added to queue: #{prd_path}", item: item, position: position }
  end

  # Add multiple PRDs at once
  def add_batch(prd_paths)
    results = prd_paths.map { |path| add(path) }
    {
      added: results.count { |r| r[:success] },
      skipped: results.count { |r| !r[:success] },
      results: results
    }
  end

  # Remove a PRD from the queue
  def remove(prd_path)
    item = @queue.find { |i| i['prd_path'] == prd_path }
    return { success: false, message: "Not found in queue: #{prd_path}" } unless item

    @queue.delete(item)
    save_queue
    { success: true, message: "Removed from queue: #{prd_path}", item: item }
  end

  # Mark an item as in_progress
  def start(prd_path)
    @logger.info("Starting PRD processing", { prd_path: prd_path })

    item = find_item(prd_path)
    return { success: false, message: "Not found: #{prd_path}" } unless item

    # Check if another item is already in progress
    current_item = current
    if current_item && current_item['prd_path'] != prd_path
      @logger.warn("Another PRD already in progress", {
        requested: prd_path,
        current: current_item['prd_path']
      })
      return {
        success: false,
        message: "Another PRD is in progress: #{current_item['prd_path']}",
        current: current_item
      }
    end

    item['status'] = 'in_progress'
    item['started_at'] = Time.now.iso8601
    save_queue

    @logger.info("PRD marked as in_progress", { prd_path: prd_path })
    { success: true, message: "Started: #{prd_path}", item: item }
  end

  # Mark an item as completed
  def complete(prd_path)
    item = find_item(prd_path)
    return { success: false, message: "Not found: #{prd_path}" } unless item

    item['status'] = 'completed'
    item['completed_at'] = Time.now.iso8601
    save_queue

    { success: true, message: "Completed: #{prd_path}", item: item, next: next_pending }
  end

  # Mark an item as failed
  def fail(prd_path, reason: nil)
    @logger.warn("Marking PRD as failed", { prd_path: prd_path, reason: reason })

    item = find_item(prd_path)
    return { success: false, message: "Not found: #{prd_path}" } unless item

    item['status'] = 'failed'
    item['failed_at'] = Time.now.iso8601
    item['failure_reason'] = reason if reason
    save_queue

    { success: true, message: "Failed: #{prd_path}", item: item }
  end

  # Skip an item
  def skip(prd_path, reason: nil)
    item = find_item(prd_path)
    return { success: false, message: "Not found: #{prd_path}" } unless item

    item['status'] = 'skipped'
    item['skipped_at'] = Time.now.iso8601
    item['skip_reason'] = reason if reason
    save_queue

    { success: true, message: "Skipped: #{prd_path}", item: item }
  end

  # Reset a failed/skipped item to pending
  def retry(prd_path)
    item = find_item(prd_path)
    return { success: false, message: "Not found: #{prd_path}" } unless item

    item['status'] = 'pending'
    item['retry_at'] = Time.now.iso8601
    save_queue

    { success: true, message: "Reset to pending: #{prd_path}", item: item }
  end

  # Update a specific field on a queue item
  def update_field(prd_path, field:, value:)
    @logger.info("Updating queue item field", { prd_path: prd_path, field: field, value: value })

    item = find_item(prd_path)
    return { success: false, message: "Not found: #{prd_path}" } unless item

    item[field] = value
    save_queue

    @logger.info("Queue item field updated", { prd_path: prd_path, field: field })
    { success: true, message: "Updated #{field} on #{prd_path}", item: item }
  end

  # Get position of an item
  def position_of(prd_path)
    pending_items = pending
    idx = pending_items.find_index { |i| i['prd_path'] == prd_path }
    idx ? idx + 1 : nil
  end

  # Get queue statistics
  def stats
    {
      total: @queue.length,
      pending: @queue.count { |i| i['status'] == 'pending' },
      in_progress: @queue.count { |i| i['status'] == 'in_progress' },
      completed: @queue.count { |i| i['status'] == 'completed' },
      failed: @queue.count { |i| i['status'] == 'failed' },
      skipped: @queue.count { |i| i['status'] == 'skipped' }
    }
  end

  # Check if queue is empty (no pending items)
  def empty?
    pending.empty?
  end

  # Check if queue has items in progress
  def processing?
    !current.nil?
  end

  # Clear completed items from queue
  def clear_completed
    count = @queue.count { |i| i['status'] == 'completed' }
    @queue.reject! { |i| i['status'] == 'completed' }
    save_queue
    { cleared: count }
  end

  # Clear all items from queue
  def clear_all
    count = @queue.length
    @queue = []
    save_queue
    { cleared: count }
  end

  # Reorder queue (move item to position)
  def move(prd_path, position)
    item = find_item(prd_path)
    return { success: false, message: "Not found: #{prd_path}" } unless item

    @queue.delete(item)
    @queue.insert(position - 1, item)
    reindex_priorities
    save_queue

    { success: true, message: "Moved to position #{position}", item: item }
  end

  # Archive the queue file with timestamp
  def archive
    @logger.info("Archiving queue file")
    return { success: false, message: "Queue file doesn't exist" } unless File.exist?(QUEUE_FILE)

    timestamp = Time.now.strftime('%Y-%m-%d-%H%M')
    archive_dir = File.dirname(QUEUE_FILE)
    archive_path = File.join(archive_dir, "z_queue_processed_#{timestamp}.yaml")

    FileUtils.cp(QUEUE_FILE, archive_path)
    FileUtils.rm(QUEUE_FILE)

    @logger.info("Queue file archived", { archived_to: archive_path })
    { success: true, archived_to: archive_path }
  end

  # Output queue as YAML
  def to_yaml
    { 'queue' => @queue, 'stats' => stats }.to_yaml
  end

  # Output queue as JSON
  def to_json(*_args)
    require 'json'
    { 'queue' => @queue, 'stats' => stats }.to_json
  end

  private

  def find_item(prd_path)
    @queue.find { |i| i['prd_path'] == prd_path }
  end

  def sort_by_priority
    @queue.sort_by! { |i| i['priority'] || 999 }
    reindex_priorities
  end

  def reindex_priorities
    @queue.each_with_index { |item, idx| item['priority'] = idx + 1 }
  end

  def load_queue
    return [] unless File.exist?(QUEUE_FILE)

    data = YAML.safe_load(File.read(QUEUE_FILE))
    data.is_a?(Array) ? data : (data['queue'] || [])
  rescue StandardError => e
    warn "Warning: Could not load queue file: #{e.message}"
    []
  end

  def save_queue
    FileUtils.mkdir_p(File.dirname(QUEUE_FILE))
    File.write(QUEUE_FILE, @queue.to_yaml)
  end
end

# CLI interface when run directly
if __FILE__ == $PROGRAM_NAME
  require 'optparse'

  action = ARGV.shift
  options = {}

  OptionParser.new do |opts|
    opts.banner = "Usage: queue_manager.rb [action] [options]"
    opts.on('--prd-path PATH', 'PRD file path') { |v| options[:prd_path] = v }
    opts.on('--paths x,y,z', Array, 'Multiple PRD paths') { |v| options[:paths] = v }
    opts.on('--priority N', Integer, 'Queue priority') { |v| options[:priority] = v }
    opts.on('--position N', Integer, 'Position to move to') { |v| options[:position] = v }
    opts.on('--reason REASON', 'Reason for failure/skip') { |v| options[:reason] = v }
    opts.on('--field FIELD', 'Field name to update') { |v| options[:field] = v }
    opts.on('--value VALUE', 'Value to set for field') { |v| options[:value] = v }
    opts.on('--format FORMAT', 'Output format: yaml, json') { |v| options[:format] = v }
    opts.on('-h', '--help', 'Show help') do
      puts opts
      puts <<~HELP

        Actions:
          list          - List all queue items
          status        - Show queue statistics
          add           - Add PRD to queue (requires --prd-path)
          add-batch     - Add multiple PRDs (requires --paths)
          remove        - Remove PRD from queue (requires --prd-path)
          next          - Get next pending item
          current       - Get currently processing item
          start         - Mark item as in_progress (requires --prd-path)
          complete      - Mark item as completed (requires --prd-path)
          fail          - Mark item as failed (requires --prd-path, optional --reason)
          skip          - Skip an item (requires --prd-path, optional --reason)
          retry         - Reset failed/skipped to pending (requires --prd-path)
          move          - Move item to position (requires --prd-path, --position)
          update-field  - Update a field on queue item (requires --prd-path, --field, --value)
          clear         - Clear completed items
          clear-all     - Clear entire queue
          archive       - Archive queue file with timestamp
      HELP
      exit 0
    end
  end.parse!

  manager = QueueManager.new
  format = options[:format] || 'yaml'

  result = case action
  when 'list'
             { queue: manager.all, stats: manager.stats }
  when 'status'
             manager.stats
  when 'add'
             manager.add(options[:prd_path], priority: options[:priority])
  when 'add-batch'
             manager.add_batch(options[:paths])
  when 'remove'
             manager.remove(options[:prd_path])
  when 'next'
             { next: manager.next_pending }
  when 'current'
             { current: manager.current }
  when 'start'
             manager.start(options[:prd_path])
  when 'complete'
             manager.complete(options[:prd_path])
  when 'fail'
             manager.fail(options[:prd_path], reason: options[:reason])
  when 'skip'
             manager.skip(options[:prd_path], reason: options[:reason])
  when 'retry'
             manager.retry(options[:prd_path])
  when 'move'
             manager.move(options[:prd_path], options[:position])
  when 'update-field'
             manager.update_field(options[:prd_path], field: options[:field], value: options[:value])
  when 'clear'
             manager.clear_completed
  when 'clear-all'
             manager.clear_all
  when 'archive'
             manager.archive
  else
             puts "Unknown action: #{action}"
             puts "Run with --help for usage"
             exit 1
  end

  output = format == 'json' ? result.to_json : result.to_yaml
  puts output
end
