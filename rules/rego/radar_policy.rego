package upstreamradar.policy

default decision := "quiet"

impact := object.get(input, "semantic_impact", 0)
security := object.get(input, "security_signal", 0)
error_streak := object.get(input, "error_streak", 0)

decision := "critical" if {
  security >= 0.9
}

decision := "critical" if {
  error_streak >= 5
}

decision := "investigate" if {
  impact >= 0.7
  security < 0.9
  error_streak < 5
}

decision := "observe" if {
  impact >= 0.3
  impact < 0.7
  security < 0.9
  error_streak < 5
}
