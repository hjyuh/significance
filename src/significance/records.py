"""Loading and schema validation for Significance claim records.

This module performs structural (JSON Schema) validation only. It does not
enforce cross-record or repository-wide semantic rules (record_id
uniqueness, append-only history, foreign-key resolution of asserted_by
against `parties`, freshness recomputation) — those belong to
`significance validate` (Phase 2) and are out of scope here.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from ruamel.yaml import YAML

_yaml = YAML(typ="safe")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schema" / "record.schema.json"


def load_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def load_record(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return _yaml.load(f)


def validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema(), format_checker=FormatChecker())


def iter_schema_errors(record: dict):
    return validator().iter_errors(record)


def is_valid(record: dict) -> bool:
    return validator().is_valid(record)
