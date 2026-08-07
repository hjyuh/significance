"""Cross-field and cross-record semantic rules a single-record JSON Schema
cannot express: attribution resolves to a declared party, source_quote
locators, freshness recomputation, forbidden rendered language,
record_id uniqueness across a repository, and append-only history against
a base revision.
"""

from __future__ import annotations

import re
from collections import defaultdict

from significance.pathfmt import format_path, walk
from significance.violations import Violation

_PROSE_KEYS = {"text", "value", "inline", "quote", "description", "note"}
_FORBIDDEN_WORDS = ("verified", "proven")

# Plain-language blocks get a stricter rule than the record-wide one above,
# and it applies only to them.
#
# The record-wide check bans "verified" and "proven" anywhere in rendered prose.
# It cannot be widened to the words below without breaking legitimate record
# content: a claim's own text may perfectly well be "...if and only if the
# conjecture is false", and a locator quote reproduces whatever the source
# actually said, verdict words and all. Quoting someone else's verdict is
# reporting; writing your own is what this project does not do.
#
# The plain-language blocks are different in kind. They are *ours* — a digest
# written by an editor in their own words, with no locator to answer for — and
# they are the first thing a non-specialist reads, which is exactly where a
# stray "this looks correct" would be taken as the site's finding. So in those
# blocks the words are refused outright.
#
# `valid` and `invalid` are deliberately absent: "a valid locator", "an invalid
# record" are ordinary vocabulary here and banning them would produce false
# refusals in the one place the writer is trying hardest to be plain.
_VERDICT_WORDS = ("correct", "incorrect", "true", "false", "proven", "verified", "refuted")
_VERDICT_RE = re.compile(rf"\b({'|'.join(_VERDICT_WORDS)})(ly|ness)?\b", re.IGNORECASE)


def verdict_violations(text: str, location: str) -> list[Violation]:
    """Verdict words found in a plain-language field.

    Reported per distinct word rather than per occurrence, so a paragraph using
    "correct" three times produces one actionable message instead of three
    identical ones.
    """
    found = sorted({m.group(0).lower() for m in _VERDICT_RE.finditer(text)})
    return [
        Violation(
            "verdict-language",
            f"plain-language field contains the verdict word '{word}'. This block is a "
            "restatement of the record, not a finding about the mathematics — if the source "
            "itself uses this word, quote it in a field that carries a locator instead.",
            location,
        )
        for word in found
    ]


def word_count(text: str) -> int:
    return len(text.split())


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


# Roughly two sentences. The cap is a drafting discipline rather than a
# measurement: the block exists to be read in thirty seconds by somebody who
# does not know this vocabulary, and a paragraph that runs longer has stopped
# being that. Enforced here rather than in the schema because JSON Schema
# cannot count words.
PLAIN_SUMMARY_MAX_WORDS = 60

PLAIN_SUMMARY_FIELDS = ("claimed", "checked", "not_checked")


def check_plain_summary(record: dict) -> list[Violation]:
    """The thirty-second strip may restate the record and may never exceed it."""
    summary = record.get("plain_summary")
    if not isinstance(summary, dict):
        return []

    violations: list[Violation] = []
    for field in PLAIN_SUMMARY_FIELDS:
        value = summary.get(field)
        if not isinstance(value, str):
            continue  # presence and type are the schema's job
        location = f"plain_summary.{field}"
        count = word_count(value)
        if count > PLAIN_SUMMARY_MAX_WORDS:
            violations.append(
                Violation(
                    "plain-summary-too-long",
                    f"{count} words, over the {PLAIN_SUMMARY_MAX_WORDS}-word cap for a "
                    "plain-language summary field",
                    location,
                )
            )
        violations.extend(verdict_violations(value, location))

    # The strip must never claim more than the record. A record carrying open
    # invitations has, by its own account, unfinished work in it; a summary of
    # that record whose "not checked" line is blank has quietly dropped the one
    # part a reader most needs.
    if record.get("open_invitations") and not (summary.get("not_checked") or "").strip():
        violations.append(
            Violation(
                "plain-summary-understates-open-work",
                "the record carries open invitations but plain_summary.not_checked is empty",
                "plain_summary.not_checked",
            )
        )

    return violations


# One paragraph. Longer than the strip's fields because this one has to
# explain a piece of mathematics rather than report a status, and shorter than
# the existing audience-targeted digestions because those may assume a
# mathematician is reading.
PLAIN_LANGUAGE_MAX_WORDS = 150


def check_plain_language_digestions(record: dict) -> list[Violation]:
    """Plain-language digestions explain meaning; they still may not judge it."""
    violations: list[Violation] = []
    digestions = record.get("digestions")
    if not isinstance(digestions, list):
        return violations

    for index, entry in enumerate(digestions):
        if not isinstance(entry, dict) or entry.get("kind") != "plain_language":
            continue
        text = entry.get("text")
        if not isinstance(text, str):
            continue  # presence and type are the schema's job
        location = f"digestions[{index}].text"
        count = word_count(text)
        if count > PLAIN_LANGUAGE_MAX_WORDS:
            violations.append(
                Violation(
                    "plain-language-too-long",
                    f"{count} words, over the {PLAIN_LANGUAGE_MAX_WORDS}-word cap for a "
                    "plain-language explanation",
                    location,
                )
            )
        violations.extend(verdict_violations(text, location))

    return violations


def check_invitation_instructions(record: dict) -> list[Violation]:
    """`how` is optional; a `how` that is there and says nothing is not.

    The renderer keys its "take this task" affordance off the presence of this
    field, so a blank one produces a button promising instructions that do not
    exist — worse than the plain invitation it replaced.
    """
    violations: list[Violation] = []
    invitations = record.get("open_invitations")
    if not isinstance(invitations, list):
        return violations

    for index, invitation in enumerate(invitations):
        if not isinstance(invitation, dict) or "how" not in invitation:
            continue
        how = invitation.get("how")
        if not isinstance(how, str) or not how.strip():
            violations.append(
                Violation(
                    "empty-invitation-instructions",
                    "open_invitations[].how is present but empty; omit the field entirely "
                    "rather than rendering an actionable task with no instructions",
                    f"open_invitations[{index}].how",
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


_EXECUTION_RECEIPT_KEYS = {
    "tool", "tool_version", "runner_image_digest", "executed_at",
    "result", "log_sha256", "asserted_by",
}


def check_execution_receipt_asserted_by_automation(record: dict) -> list[Violation]:
    """`execution_receipt` is used in three places (evidence_formal_artifact.artifact_build,
    evidence_formal_artifact.axiom_policy.execution, evidence_computational_reproduction.execution)
    with no discriminator key, so this detects the shape rather than a `kind` field: any dict
    carrying every execution_receipt key is treated as one."""
    parties = record.get("parties") or {}
    violations = []
    for path, node in walk(record):
        if not isinstance(node, dict):
            continue
        if not _EXECUTION_RECEIPT_KEYS.issubset(node.keys()):
            continue
        party_id = node.get("asserted_by")
        if not isinstance(party_id, str):
            continue
        party = parties.get(party_id)
        if not isinstance(party, dict):
            continue  # unknown-party is check_asserted_by_parties's job, not this check's
        kind = (party.get("verification_method") or {}).get("kind")
        if kind != "automation":
            violations.append(
                Violation(
                    "execution-receipt-not-automation",
                    f"execution_receipt asserted_by '{party_id}' has verification_method.kind "
                    f"{kind!r}, expected 'automation'",
                    format_path(path + ("asserted_by",)),
                )
            )
    return violations


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
        *check_plain_summary(record),
        *check_plain_language_digestions(record),
        *check_invitation_instructions(record),
        *check_freshness_recomputation(record),
        *check_execution_receipt_asserted_by_automation(record),
    ]
