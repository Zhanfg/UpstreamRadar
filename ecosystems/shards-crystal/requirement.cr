module UpstreamRadar
  enum RequirementKind
    Exact
    Compatible
    Range
    Branch
    Floating
  end

  def self.classify_requirement(raw : String) : RequirementKind
    value = raw.strip.downcase
    return RequirementKind::Floating if value.empty? || value == "*" || value == "latest"
    return RequirementKind::Branch if value.starts_with?("git:") || value.starts_with?("branch:")
    return RequirementKind::Compatible if value.starts_with?("~>") || value.starts_with?("^")
    return RequirementKind::Range if value.includes?(">") || value.includes?("<") || value.includes?("||")
    RequirementKind::Exact
  end
end
