#!/usr/bin/env sh
set -eu

need() {
  command -v "$1" >/dev/null 2>&1 || {
    printf 'missing tool: %s\n' "$1" >&2
    return 1
  }
}

status=0
for tool in git python3; do
  need "$tool" || status=1
done

printf 'repository=%s\n' "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
printf 'python=%s\n' "$(python3 --version 2>&1 || true)"
printf 'git=%s\n' "$(git --version 2>&1 || true)"
exit "$status"
