enum ConstraintStability { exact, compatible, range, floating, source }

ConstraintStability classifyConstraint(String raw) {
  final value = raw.trim().toLowerCase();
  if (value.startsWith('git:') || value.startsWith('path:') || value.startsWith('sdk:')) {
    return ConstraintStability.source;
  }
  if (value == 'any' || value.contains('*')) return ConstraintStability.floating;
  if (value.startsWith('^')) return ConstraintStability.compatible;
  if (value.contains('>') || value.contains('<') || value.contains('||')) {
    return ConstraintStability.range;
  }
  return ConstraintStability.exact;
}

void main(List<String> args) {
  for (final value in args) {
    print(value + '\t' + classifyConstraint(value).name);
  }
}


double constraintRisk(String raw) {
  final kind = classifyConstraint(raw);
  final value = raw.trim().toLowerCase();
  var risk = switch (kind) {
    ConstraintStability.exact => 0.05,
    ConstraintStability.compatible => 0.18,
    ConstraintStability.range => 0.32,
    ConstraintStability.source => 0.48,
    ConstraintStability.floating => 0.72,
  };
  if (value.contains('dev') || value.contains('git:')) risk += 0.15;
  if (value == 'any') risk += 0.10;
  return risk.clamp(0.0, 1.0);
}

double compatibilityConfidence(String raw) =>
    (1.0 - 0.78 * constraintRisk(raw)).clamp(0.0, 1.0);
