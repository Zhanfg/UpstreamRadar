#!/usr/bin/env sh
set -eu

ROOT="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
cd "$ROOT"

echo "HARDENING=release-only"

if command -v npm >/dev/null 2>&1 && [ -d apps/web/node_modules ]; then
  echo "HARDENING=web-minify"
  npm --prefix apps/web run build:release
else
  echo "HARDENING=web-skip node_modules-unavailable"
fi

if command -v strip >/dev/null 2>&1 && command -v file >/dev/null 2>&1; then
  for dir in build dist out; do
    [ -d "$dir" ] || continue
    find "$dir" -type f | while IFS= read -r candidate; do
      kind="$(file -b "$candidate" 2>/dev/null || true)"
      case "$kind" in
        *ELF*)
          echo "HARDENING=strip $candidate"
          strip --strip-unneeded "$candidate" 2>/dev/null || true
          ;;
      esac
    done
  done
fi

echo "HARDENING=done"
