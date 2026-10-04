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

python3 - <<'PY' || status=1
import json
from pathlib import Path

for path in (
    Path("schemas/harmony-v3-score.schema.json"),
    Path("config/release-hardening.json"),
):
    data = json.loads(path.read_text(encoding="utf-8"))
    print(f"validated_json={path} keys={len(data)}")

hardening = json.loads(Path("config/release-hardening.json").read_text())
assert hardening["mode"] == "release-only"
assert hardening["source_obfuscation"] is False
print("hardening_policy=auditable")
PY

exit "$status"
