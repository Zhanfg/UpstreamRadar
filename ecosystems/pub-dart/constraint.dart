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
