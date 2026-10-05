from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from upstreamradar.museum.registry import EXHIBITS


DEFAULT_OUTPUT = Path("museum/catalog.json")


def render() -> str:
    payload = {
        "version": 1,
        "count": len(EXHIBITS),
        "families": sorted({item.family for item in EXHIBITS}),
        "exhibits": [
            asdict(item)
            for item in sorted(EXHIBITS, key=lambda item: (item.introduced, item.slug))
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    expected = render()
    if args.check:
        actual = args.output.read_text(encoding="utf-8") if args.output.exists() else ""
        if actual != expected:
            raise SystemExit(f"{args.output} is stale; run the exporter")
        print(f"catalog_ok={args.output} exhibits={len(EXHIBITS)}")
        return 0

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(expected, encoding="utf-8")
    print(f"catalog_written={args.output} exhibits={len(EXHIBITS)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
