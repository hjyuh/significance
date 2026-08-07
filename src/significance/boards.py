"""Status boards: loading, schema validation, and the rules a board schema
cannot express.

A board answers one question across several results at once — are these real? —
and holds no evidence of its own. Every row either links a record, which is
where evidence lives, or quotes a source directly. That is the whole design
constraint, and it is why this is a separate schema rather than a record
variant: a board that could carry evidence fields would become a second, weaker
kind of record, with none of the append-only history or receipt rules that make
the first kind worth anything.

The rules here mirror the record rules deliberately. Attribution resolves to a
declared party via the same check the records use. The plain-language status
fields answer to the same word cap and the same verdict lint as the record-page
strip, because they are the same thing at a different scale, and a reader who
learned to trust one should not find the other held to a looser standard.
"""

from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from ruamel.yaml import YAML

from significance.pathfmt import format_path
from significance.schema_checks import classify
from significance.semantics import (
    PLAIN_SUMMARY_MAX_WORDS,
    check_asserted_by_parties,
    check_source_quote_locators,
    verdict_violations,
    word_count,
)
from significance.violations import Violation

_yaml = YAML(typ="safe")

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA_PATH = _REPO_ROOT / "schema" / "board.schema.json"

#: What a placeholder row's fields must carry, so a half-filled row cannot look
#: finished. Matched case-insensitively at the start of the string.
FILL_MARKER = "[fill"

STATUS_FIELDS = ("checked", "not_checked")


def load_board_schema() -> dict:
    return json.loads(_SCHEMA_PATH.read_text(encoding="utf-8"))


def board_validator() -> Draft202012Validator:
    return Draft202012Validator(load_board_schema(), format_checker=FormatChecker())


def load_board(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return _yaml.load(f)


def is_board(document) -> bool:
    """Whether a loaded YAML document is a board rather than a record.

    Reads the explicit `kind` discriminator rather than sniffing for
    board-shaped keys, so a record with an unusual shape is never silently
    validated against the wrong schema — it fails as the record it is.
    """
    return isinstance(document, dict) and document.get("kind") == "board"


def check_rows(board: dict) -> list[Violation]:
    """The row rules: no unsourced assertion, no placeholder wearing a result."""
    violations: list[Violation] = []
    rows = board.get("rows")
    if not isinstance(rows, list):
        return violations

    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            continue
        location = f"rows[{index}]"
        state = row.get("state")

        if state == "placeholder":
            # The name slot must still look like a slot. Without this, an
            # editor who fills in a result's name and stops has produced a row
            # that reads as researched and carries nothing.
            result = row.get("result")
            if isinstance(result, str) and not result.strip().lower().startswith(FILL_MARKER):
                violations.append(
                    Violation(
                        "placeholder-row-looks-filled",
                        f"row is a placeholder but its result name {result!r} carries no [FILL] "
                        "marker; either finish the row (state: recorded) or leave the marker in "
                        "place, because a half-filled row reads as a finished one",
                        f"{location}.result",
                    )
                )
            if row.get("record"):
                violations.append(
                    Violation(
                        "placeholder-row-links-record",
                        "a placeholder row links a record; a row with a record behind it has "
                        "been researched and belongs in state: recorded",
                        f"{location}.record",
                    )
                )
            continue

        # A recorded row has to rest on something. Without either a record or a
        # quoted source, the board would be asserting a result exists on
        # nobody's authority — which is the one thing a record can never do and
        # so is the one thing a board built from records must not do either.
        if not row.get("record") and not row.get("claim"):
            violations.append(
                Violation(
                    "row-without-source",
                    "row links no record and carries no source-quoted claim, so nothing on it "
                    "is attributable to anyone",
                    location,
                )
            )

        status = row.get("status")
        if isinstance(status, dict):
            for field in STATUS_FIELDS:
                value = status.get(field)
                if not isinstance(value, str):
                    continue  # presence is the schema's job
                field_location = f"{location}.status.{field}"
                count = word_count(value)
                if count > PLAIN_SUMMARY_MAX_WORDS:
                    violations.append(
                        Violation(
                            "plain-summary-too-long",
                            f"{count} words, over the {PLAIN_SUMMARY_MAX_WORDS}-word cap for a "
                            "plain-language status field",
                            field_location,
                        )
                    )
                violations.extend(verdict_violations(value, field_location))

            if not (status.get("not_checked") or "").strip():
                violations.append(
                    Violation(
                        "row-status-understates-open-work",
                        "status.not_checked is empty; a row that lists only what was checked "
                        "reads as an endorsement of everything it left out",
                        f"{location}.status.not_checked",
                    )
                )

    return violations


def check_intro(board: dict) -> list[Violation]:
    intro = board.get("intro")
    if not isinstance(intro, dict):
        return []
    value = intro.get("value")
    if not isinstance(value, str):
        return []
    return verdict_violations(value, "intro.value")


def board_violations(board: dict, validator: Draft202012Validator | None = None) -> list[Violation]:
    """Every check a single board answers to."""
    validator = validator or board_validator()
    violations = [classify(e) for e in validator.iter_errors(board)]
    violations += check_asserted_by_parties(board)
    violations += check_source_quote_locators(board)
    violations += check_intro(board)
    violations += check_rows(board)
    return violations


def collect_board_files(directory: str | Path) -> list[Path]:
    path = Path(directory)
    if not path.is_dir():
        return []
    return sorted(p for p in path.glob("*.yaml"))


def board_summary(board: dict) -> dict:
    """The narrow shape the React shell is allowed to see.

    Same posture as the record index: counts and identifiers, computed here so
    the presentation layer cannot arrive at a different number for how much of
    a board is filled in.
    """
    rows = board.get("rows") or []
    recorded = [r for r in rows if isinstance(r, dict) and r.get("state") == "recorded"]
    return {
        "board_id": board.get("board_id"),
        "title": board.get("title"),
        "as_of": board.get("as_of"),
        "row_count": len(rows),
        "recorded_row_count": len(recorded),
    }


def format_row_location(index: int, *rest: str) -> str:
    return format_path((f"rows[{index}]", *rest))
