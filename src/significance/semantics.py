"""Cross-field and cross-record semantic rules a single-record JSON Schema
cannot express: attribution resolves to a declared party, source_quote
locators, freshness recomputation, forbidden rendered language,
record_id uniqueness across a repository, and append-only history against
a base revision.
"""

from __future__ import annotations

from collections import defaultdict

from significance.pathfmt import format_path, walk
from significance.violations import Violation

_PROSE_KEYS = {"text", "value", "inline", "quote", "description", "note"}
_FORBIDDEN_WORDS = ("verified", "proven")


def check_asserted_by_parties(record: dict) -> list[Violation]:
    parties = record.get("parties") or {}
    violations = []
    for path, node in walk(record):
        if not isinstance(node, dict):
            continue
        party_id = node.get("asserted_by")
        if isinstance(party_id, str) and party_id not in parties:
            violations.append(
                Violation(
                    "unknown-party",
                    f"asserted_by references undeclared party '{party_id}'",
                    format_path(path + ("asserted_by",)),
                )
            )
    return violations


def check_source_quote_locators(record: dict) -> list[Violation]:
    violations = []
    for path, node in walk(record):
        if not isinstance(node, dict):
            continue
        if node.get("basis") != "source_quote":
            continue
        if node.get("locator") or node.get("source"):
            continue
        violations.append(
            Violation(
                "source-quote-missing-locator",
                "basis is source_quote but no locator (or source) is given",
                format_path(path),
            )
        )
    return violations


def check_forbidden_language(record: dict) -> list[Violation]:
    violations = []
    for path, node in walk(record):
        if not isinstance(node, dict):
            continue
        for key, value in node.items():
            if key not in _PROSE_KEYS or not isinstance(value, str):
                continue
            lowered = value.lower()
            for word in _FORBIDDEN_WORDS:
                if word in lowered:
                    violations.append(
                        Violation(
                            "forbidden-language",
                            f"rendered prose contains forbidden word '{word}'",
                            format_path(path + (key,)),
                        )
                    )
    return violations


def check_freshness_recomputation(record: dict) -> list[Violation]:
    freshness = record.get("freshness")
    if not isinstance(freshness, dict):
        return []
    result = freshness.get("result")
    observed = freshness.get("observed_source_version")
    confirmed = freshness.get("confirmed_source_version")
    if result == "unknown" or observed is None or confirmed is None:
        return []

    recomputed = "current" if observed == confirmed else "stale"
    if result == recomputed:
        return []
    if result == "current" and recomputed == "stale":
        return [
            Violation(
                "stale-rendered-current",
                f"observed_source_version ({observed!r}) != confirmed_source_version "
                f"({confirmed!r}) recomputes to 'stale', but freshness.result is 'current'",
                "freshness.result",
            )
        ]
    return [
        Violation(
            "derived-value-mismatch",
            f"freshness.result is {result!r} but recomputing from observed/confirmed "
            f"source versions gives {recomputed!r}",
            "freshness.result",
        )
    ]


def check_uniqueness(loaded: list[tuple[str, dict]]) -> list[Violation]:
    groups: dict[str, list[str]] = defaultdict(list)
    for file, record in loaded:
        rid = record.get("record_id")
        if isinstance(rid, str):
            groups[rid].append(file)

    violations = []
    for rid, files in groups.items():
        if len(files) <= 1:
            continue
        for file in files:
            others = [f for f in files if f != file]
            violations.append(
                Violation(
                    "duplicate-record-id",
                    f"record_id '{rid}' is also used by {others}",
                    "record_id",
                    file=file,
                )
            )
    return violations


def check_append_only(current: dict, base: dict) -> list[Violation]:
    if current == base:
        # Nothing changed: there is no new revision to hold to a monotonic
        # version bump, and no history to have mutated or dropped anything from.
        return []

    violations = []

    cur_version = current.get("record_version")
    base_version = base.get("record_version")
    if isinstance(cur_version, int) and isinstance(base_version, int):
        if cur_version <= base_version:
            violations.append(
                Violation(
                    "non-monotonic-record-version",
                    f"record_version {cur_version} does not exceed base version {base_version}",
                    "record_version",
                )
            )

    base_events = {e["id"]: e for e in base.get("history", []) if "id" in e}
    cur_events = {e["id"]: e for e in current.get("history", []) if "id" in e}

    for event_id, base_event in base_events.items():
        location = f"history[id={event_id}]"
        if event_id not in cur_events:
            violations.append(
                Violation(
                    "history-event-deleted",
                    f"history event '{event_id}' present in base is missing here",
                    location,
                )
            )
            continue
        cur_event = cur_events[event_id]
        if cur_event != base_event:
            changed = sorted(
                k
                for k in set(base_event) | set(cur_event)
                if base_event.get(k) != cur_event.get(k)
            )
            violations.append(
                Violation(
                    "history-event-mutated",
                    f"history event '{event_id}' payload changed in field(s) {changed}",
                    location,
                )
            )

    return violations


def semantic_violations(record: dict) -> list[Violation]:
    """Single-record semantic checks (no base, no sibling records needed)."""
    return [
        *check_asserted_by_parties(record),
        *check_source_quote_locators(record),
        *check_forbidden_language(record),
        *check_freshness_recomputation(record),
    ]
