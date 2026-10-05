package upstreamradar.policy

default decision := "quiet"

impact := object.get(input, "semantic_impact", 0)
security := object.get(input, "security_signal", 0)
error_streak := object.get(input, "error_streak", 0)
surprise := object.get(input, "bayesian_surprise", 0)
novelty := object.get(input, "structural_novelty", 0)
tail_risk := object.get(input, "tail_risk", 0)

evidence := 0.46 * impact + 0.24 * security + 0.18 * surprise + 0.12 * novelty
risk_adjusted := evidence * (1 - 0.08 * tail_risk)

decision := "critical" if {
  security >= 0.9
}

decision := "critical" if {
  error_streak >= 5
}

decision := "investigate" if {
  risk_adjusted >= 0.65
  security < 0.9
  error_streak < 5
}

decision := "observe" if {
  risk_adjusted >= 0.3
  risk_adjusted < 0.65
  security < 0.9
  error_streak < 5
}
