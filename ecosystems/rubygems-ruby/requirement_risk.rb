# frozen_string_literal: true

module UpstreamRadar
  module RubyGems
    module_function

    def clamp01(value)
      [[value.to_f, 0.0].max, 1.0].min
    end

    def bernoulli_kl(q, p)
      eps = 1e-12
      q = [[q.to_f, eps].max, 1.0 - eps].min
      p = [[p.to_f, eps].max, 1.0 - eps].min
      q * Math.log(q / p) + (1.0 - q) * Math.log((1.0 - q) / (1.0 - p))
    end

    def bayesian_surprise(empirical, predicted)
      clamp01(1.0 - Math.exp(-3.4 * bernoulli_kl(empirical, predicted)))
    end

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

    def risk_score(requirement)
      value = requirement.to_s.strip.downcase
      base = case classify(value)
             when :unbounded then 0.80
             when :prerelease then 0.62
             when :minimum_only then 0.46
             when :bounded_range then 0.30
             when :pessimistic then 0.18
             when :exact then 0.06
             else 0.40
             end
      base += 0.12 if value.include?("git")
      clamp01(base)
    end
  end
end

if $PROGRAM_NAME == __FILE__
  ARGV.each { |value| puts "#{value}\t#{UpstreamRadar::RubyGems.classify(value)}" }
end
