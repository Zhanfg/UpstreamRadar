module UpstreamRadar
  enum RequirementKind
    Exact
    Compatible
    Range
    Branch
    Floating
  end

  def self.clamp01(value : Float64) : Float64
    value.clamp(0.0, 1.0)
  end

  def self.bernoulli_kl(q0 : Float64, p0 : Float64) : Float64
    eps = 1e-12
    q = q0.clamp(eps, 1.0 - eps)
    p = p0.clamp(eps, 1.0 - eps)
    q * Math.log(q / p) + (1.0 - q) * Math.log((1.0 - q) / (1.0 - p))
  end

  def self.bayesian_surprise(empirical : Float64, predicted : Float64) : Float64
    clamp01(1.0 - Math.exp(-3.4 * bernoulli_kl(empirical, predicted)))
  end

  def self.classify_requirement(raw : String) : RequirementKind
    value = raw.strip.downcase
    return RequirementKind::Floating if value.empty? || value == "*" || value == "latest"
    return RequirementKind::Branch if value.starts_with?("git:") || value.starts_with?("branch:")
    return RequirementKind::Compatible if value.starts_with?("~>") || value.starts_with?("^")
    return RequirementKind::Range if value.includes?(">") || value.includes?("<") || value.includes?("||")
    RequirementKind::Exact
  end

  def self.risk_score(raw : String) : Float64
    value = raw.strip.downcase
    base = case classify_requirement(value)
           when RequirementKind::Floating then 0.80
           when RequirementKind::Branch then 0.64
           when RequirementKind::Range then 0.34
           when RequirementKind::Compatible then 0.18
           else 0.06
           end
    base += 0.10 if value.includes?("git")
    clamp01(base)
  end
end
