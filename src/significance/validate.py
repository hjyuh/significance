"""`significance validate`: schema validity, single-record semantic rules,
record_id uniqueness across the validated set, and (with a base revision)
append-only history enforcement.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from ruamel.yaml import YAML

from significance.boards import board_validator, board_violations, is_board
from significance.records import load_record, validator
from significance.schema_checks import schema_violations
from significance.semantics import check_append_only, check_dependencies, check_uniqueness, semantic_violations
from significance.violations import Violation

_yaml = YAML(typ="safe")


def collect_yaml_files(paths: list[str]) -> list[Path]:
    files: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.glob("*.yaml")))
        else:
            files.append(p)
    return files


@lru_cache(maxsize=None)
def _repo_root(start: str) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=start,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def resolve_base(ref_or_file: str, record_path: Path) -> dict | None:
    """Load the base version of `record_path`. `ref_or_file` is either an
    existing file path (compared directly) or a git ref (record_path is
    resolved relative to the repo root and read via `git show`).
    Returns None if the record doesn't exist at the base (e.g. it's new)."""
    candidate = Path(ref_or_file)
    if candidate.is_file():
        return load_record(candidate)

    root = _repo_root(str(record_path.resolve().parent))
    if root is None:
        return None
    rel = record_path.resolve().relative_to(Path(root)).as_posix()
    result = subprocess.run(
        ["git", "show", f"{ref_or_file}:{rel}"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode != 0:
        return None
    return _yaml.load(result.stdout)


def validate_paths(paths: list[str], base: str | None = None) -> list[Violation]:
    files = collect_yaml_files(paths)
    schema_validator = validator()
    board_schema_validator = board_validator()
    loaded: list[tuple[str, dict]] = []
    violations: list[Violation] = []

    for f in files:
        file_str = str(f)
        try:
            record = load_record(f)
        except Exception as exc:  # malformed YAML, not a record shape issue
            violations.append(Violation("parse-error", str(exc), "$", file=file_str))
            continue

        # A board answers to a different schema and different rules. The
        # discriminator is explicit (`kind: board`) rather than sniffed, so a
        # record with an unusual shape is never quietly checked against the
        # wrong schema -- it fails as the record it is.
        if is_board(record):
            file_violations = board_violations(record, board_schema_validator)
            for v in file_violations:
                v.file = file_str
            violations.extend(file_violations)
            continue

        loaded.append((file_str, record))

        file_violations = schema_violations(record, schema_validator)
        file_violations += semantic_violations(record)

        if base is not None:
            base_record = resolve_base(base, f)
            if base_record is not None:
                file_violations += check_append_only(record, base_record)

        for v in file_violations:
            v.file = file_str
        violations.extend(file_violations)

    known_ids = {r.get('record_id') for _, r in loaded}
    for file_str, record in loaded:
        extra = check_dependencies(record, known_ids)
        # dependencies may refer forward to a sibling, so run after loading all files
        for v in extra:
            if v.rule == "depends-on-unknown-record":
                v.file = file_str
                violations.append(v)
    violations.extend(check_uniqueness(loaded))
    return violations
