#!/usr/bin/env python3
"""Fail if a production site build contains any test-fixture record or board ID."""

from __future__ import annotations

import sys
from pathlib import Path

from ruamel.yaml import YAML

ROOT = Path(__file__).resolve().parents[1]
SITE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site"
_YAML = YAML(typ="safe")


def declared_ids(root: Path) -> set[str]:
    found: set[str] = set()
    for path in root.rglob("*.yaml"):
        try:
            value = _YAML.load(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not isinstance(value, dict):
            continue
        for key in ("record_id", "board_id"):
            identifier = value.get(key)
            if isinstance(identifier, str) and identifier:
                found.add(identifier)
    return found


production_ids = declared_ids(ROOT / "records") | declared_ids(ROOT / "boards")
fixture_ids = declared_ids(ROOT / "tests" / "fixtures") - production_ids

hits: list[tuple[Path, str]] = []
for path in SITE.rglob("*"):
    if not path.is_file():
        continue
    relative = path.relative_to(SITE)
    content = path.read_bytes()
    for identifier in fixture_ids:
        encoded = identifier.encode("utf-8")
        if identifier in relative.as_posix() or encoded in content:
            hits.append((relative, identifier))

if hits:
    print("Fixture identifiers escaped into the production site build:", file=sys.stderr)
    for path, identifier in sorted(set(hits)):
        print(f"  {identifier}: {path}", file=sys.stderr)
    raise SystemExit(1)

print(f"OK: production build contains none of {len(fixture_ids)} fixture identifiers.")
