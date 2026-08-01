"""Scans Lean source for kernel-bypass options that axiom closure
structurally cannot see: `set_option debug.skipKernelTC` and any
`debug.skip*` option. A hit fails the audit under its own named rule
(RULE below), independent of whether isolation was otherwise clean --
even a genuinely reproduced build cannot be trusted if the kernel
typechecker itself was told to skip.

Deliberately conservative: matches inside comments too. A scanner that
misses an obfuscated bypass is worse than one that occasionally flags an
inert comment.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path

RULE = "kernel-bypass-option-detected"

_PATTERN = re.compile(r"set_option\s+(debug\.skip\w*)")
_EXCLUDED_PARTS = frozenset({".git", ".lake", "build", "dist"})


@dataclass
class BypassHit:
    file: str
    line: int
    option: str


def scan_file(path: Path) -> list[BypassHit]:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    hits = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for m in _PATTERN.finditer(line):
            hits.append(BypassHit(file=str(path), line=lineno, option=m.group(1)))
    return hits


def scan_tree(root: Path) -> list[BypassHit]:
    hits: list[BypassHit] = []
    for directory, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in _EXCLUDED_PARTS)
        for filename in sorted(filenames):
            if filename.endswith(".lean"):
                hits.extend(scan_file(Path(directory) / filename))
    return hits


def main(argv: list[str] | None = None) -> int:
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    hits = scan_tree(Path(args.source_root))
    Path(args.out).write_text(
        json.dumps({"clean": not hits, "hits": [h.__dict__ for h in hits]}, indent=2),
        encoding="utf-8",
    )
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
