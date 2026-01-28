#!/usr/bin/env ruby
# frozen_string_literal: true

# Load .env file internally - no shell prefix required
begin
  env_file = File.expand_path('../.env', __dir__)
  if File.exist?(env_file) && File.readable?(env_file)
    require 'dotenv'
    Dotenv.load(env_file)
  end
rescue LoadError
  # dotenv gem not available, ENV vars must be set externally
rescue StandardError => e
  warn "Warning: Could not load .env: #{e.message}"
end

require 'json'
require 'net/http'
require 'uri'
require 'optparse'
require_relative 'logger'

# PRD Notifier - Simplified Slack notifications for orchestration
#
# Only 3 notification types (interrupt-based, "boy who cried wolf" principle):
# 1. decision_needed - Human decision required (proposal review, test intervention)
# 2. error - Something went wrong that needs attention
# 3. complete - PRD processing finished successfully
#
# Usage:
#   ruby orch/notifier.rb decision_needed --change-name "inquiry-02-email" --message "Proposal ready for review"
#   ruby orch/notifier.rb error --change-name "inquiry-02-email" --message "Tests failed after retries"
#   ruby orch/notifier.rb complete --change-name "inquiry-02-email" --message "PR created and ready for merge"
#
class PrdNotifier
  NOTIFICATION_TYPES = %w[decision_needed error complete].freeze

  def initialize
    @webhook_url = ENV['SLACK_WEBHOOK_URL']
    @logger = OrchLogger.new('PrdNotifier')
  end

  def notify(type, context)
    @logger.info("Sending notification", { type: type, change_name: context[:change_name] })

    unless NOTIFICATION_TYPES.include?(type)
      @logger.warn("Invalid notification type", { type: type, valid_types: NOTIFICATION_TYPES })
      raise ArgumentError, "Invalid type: #{type}. Valid: #{NOTIFICATION_TYPES.join(', ')}"
    end

    unless @webhook_url && !@webhook_url.empty?
      @logger.warn("SLACK_WEBHOOK_URL not configured - notification skipped")
      puts "⚠️  SLACK_WEBHOOK_URL not set - notification skipped (non-blocking)"
      return { success: false, reason: 'webhook_not_configured' }
    end

    blocks = build_blocks(type, context)
    send_to_slack(blocks)
  end

  private

  def build_blocks(type, context)
    case type
    when 'decision_needed'
      decision_needed_blocks(context)
    when 'error'
      error_blocks(context)
    when 'complete'
      complete_blocks(context)
    end
  end

  def decision_needed_blocks(context)
    emoji = context[:checkpoint] == 'awaiting_merge' ? '🔀' : '🔔'
    header = case context[:checkpoint]
    when 'awaiting_proposal_approval'
               'Proposal Ready for Review'
    when 'awaiting_test_review'
               'Test Results Need Review'
    when 'awaiting_merge'
               'PR Ready for Merge'
    else
               'Decision Needed'
    end

    [
      {
        type: 'header',
        text: { type: 'plain_text', text: "#{emoji} #{header}" }
      },
      {
        type: 'section',
        fields: [
          { type: 'mrkdwn', text: "*Change:*\n#{context[:change_name]}" },
          { type: 'mrkdwn', text: "*Branch:*\n#{context[:branch] || 'N/A'}" }
        ]
      },
      {
        type: 'section',
        text: { type: 'mrkdwn', text: "*Message:*\n#{context[:message]}" }
      },
      context[:action] ? {
        type: 'section',
        text: { type: 'mrkdwn', text: "*Action Required:*\n#{context[:action]}" }
      } : nil
    ].compact
  end

  def error_blocks(context)
    [
      {
        type: 'header',
        text: { type: 'plain_text', text: '❌ PRD Orchestration Error' }
      },
      {
        type: 'section',
        fields: [
          { type: 'mrkdwn', text: "*Change:*\n#{context[:change_name] || 'N/A'}" },
          { type: 'mrkdwn', text: "*Phase:*\n#{context[:phase] || 'N/A'}" }
        ]
      },
      {
        type: 'section',
        text: { type: 'mrkdwn', text: "*Error:*\n#{context[:message]}" }
      },
      context[:resolution] ? {
        type: 'section',
        text: { type: 'mrkdwn', text: "*Resolution:*\n#{context[:resolution]}" }
      } : nil
    ].compact
  end

  def complete_blocks(context)
    [
      {
        type: 'header',
        text: { type: 'plain_text', text: '✅ PRD Complete' }
      },
      {
        type: 'section',
        fields: [
          { type: 'mrkdwn', text: "*Change:*\n#{context[:change_name]}" },
          { type: 'mrkdwn', text: "*Branch:*\n#{context[:branch] || 'N/A'}" }
        ]
      },
      {
        type: 'section',
        text: { type: 'mrkdwn', text: "*Status:*\n#{context[:message]}" }
      },
      context[:next_prd] ? {
        type: 'section',
        text: { type: 'mrkdwn', text: "*Next in queue:*\n#{context[:next_prd]}" }
      } : nil
    ].compact
  end

  def send_to_slack(blocks)
    @logger.debug("Sending Slack notification via curl")

    # Use curl for reliable SSL handling
    payload = { blocks: blocks }.to_json

    require 'tempfile'
    require 'shellwords'
    temp = Tempfile.new('prd_notify_payload')
    begin
      temp.write(payload)
      temp.close

      # Build curl command as single line for Claude permission system
      curl_cmd = "curl -s -X POST -H 'Content-type: application/json' --data @#{Shellwords.escape(temp.path)} --fail-with-body --max-time 10 #{Shellwords.escape(@webhook_url)}"

      output = `#{curl_cmd} 2>&1`
      success = $?.success?

      if success
        @logger.info("Slack notification sent successfully")
        puts "✅ Slack notification sent"
        { success: true }
      else
        @logger.warn("Slack notification failed", { error: output })
        warn "⚠️  Slack notification failed: #{output}"
        { success: false, error: output }
      end
    ensure
      temp.unlink
    end
  end
end

# CLI interface
if __FILE__ == $PROGRAM_NAME
  options = {}
  notification_type = ARGV.shift

  unless notification_type
    puts "Usage: notifier.rb [decision_needed|error|complete] [options]"
    puts ""
    puts "Options:"
    puts "  --change-name NAME     Change name (required)"
    puts "  --message MSG          Message to display (required)"
    puts "  --branch BRANCH        Branch name"
    puts "  --phase PHASE          Current phase (for errors)"
    puts "  --checkpoint TYPE      Checkpoint type (for decisions)"
    puts "  --action ACTION        Required action description"
    puts "  --resolution RES       Resolution guidance (for errors)"
    puts "  --next-prd PATH        Next PRD in queue (for complete)"
    puts ""
    puts "Notification Types:"
    puts "  decision_needed  - Human intervention required"
    puts "  error            - Something went wrong"
    puts "  complete         - PRD finished processing"
    exit 1
  end

  OptionParser.new do |opts|
    opts.on('--change-name NAME') { |v| options[:change_name] = v }
    opts.on('--message MSG') { |v| options[:message] = v }
    opts.on('--branch BRANCH') { |v| options[:branch] = v }
    opts.on('--phase PHASE') { |v| options[:phase] = v }
    opts.on('--checkpoint TYPE') { |v| options[:checkpoint] = v }
    opts.on('--action ACTION') { |v| options[:action] = v }
    opts.on('--resolution RES') { |v| options[:resolution] = v }
    opts.on('--next-prd PATH') { |v| options[:next_prd] = v }
  end.parse!

  notifier = PrdNotifier.new
  result = notifier.notify(notification_type, options)

  exit(result[:success] ? 0 : 1)
end
