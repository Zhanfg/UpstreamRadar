# frozen_string_literal: true

module UpstreamRadar
  module RubyGems
    module_function

    def classify(requirement)
      value = requirement.to_s.strip.downcase
      return :unbounded if value.empty? || value == ">= 0" || value == ">= 0.0.0"
      return :prerelease if value.match?(/[a-z]/)
      return :pessimistic if value.start_with?("~>")
      return :bounded_range if value.include?("<") && value.include?(">")
      return :minimum_only if value.start_with?(">=")
      return :exact if value.start_with?("=") || value.match?(/^\d+(\.\d+){1,3}$/)
      :custom
    end
  end
end

if $PROGRAM_NAME == __FILE__
  ARGV.each { |value| puts "#{value}\t#{UpstreamRadar::RubyGems.classify(value)}" }
end
