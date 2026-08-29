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

# The lint has to speak every language the strips do.
#
# Found by writing the French translation and watching "la preuve est correcte"
# sail straight through: the English pattern needs a word boundary after
# "correct", and the French adjective agrees with a feminine noun, so one
# character of inflection defeated the whole check. A translated summary is
# exactly where that failure costs most — it is read by fewer reviewers, and
# the reader who would have caught it is the one who does not read English.
#
# Inflected forms are written out rather than derived from stems with optional
# endings, because a loose pattern in a language its maintainer reads less
# fluently produces false refusals nobody present can adjudicate.
_VERDICT_WORDS_BY_LANG = {
    "fr": (
        "correct",
        "correcte",
        "corrects",
        "correctes",
        "exact",
        "exacte",
        "exacts",
        "exactes",
        "vrai",
        "vraie",
        "vrais",
        "vraies",
        "faux",
        "fausse",
        "fausses",
        "prouvé",
        "prouvée",
        "prouvés",
        "prouvées",
        "démontré",
        "démontrée",
        "démontrés",
        "démontrées",
        "vérifié",
        "vérifiée",
        "vérifiés",
        "vérifiées",
        "réfuté",
        "réfutée",
        "réfutés",
        "réfutées",
        "valide",
        "valides",
        "invalide",
        "invalides",
    ),
    "ar": (
        "صحيح",
        "صحيحة",
        "صحيحان",
        "خطأ",
        "خاطئ",
        "خاطئة",
        "مثبت",
        "مثبتة",
        "مبرهن",
        "مبرهنة",
        "مؤكد",
        "مؤكدة",
        "مفند",
        "مفندة",
        "سليم",
        "سليمة",
    ),
}


def _verdict_pattern(words) -> re.Pattern:
    return re.compile(rf"\b({'|'.join(words)})(ly|ness)?\b", re.IGNORECASE | re.UNICODE)


_VERDICT_RE = _verdict_pattern(_VERDICT_WORDS)
_VERDICT_RE_BY_LANG = {
    lang: _verdict_pattern(words) for lang, words in _VERDICT_WORDS_BY_LANG.items()
}


def verdict_violations(text: str, location: str, lang: str = "en") -> list[Violation]:
    """Verdict words found in a plain-language field.

    The English list applies whatever the language, since a French paragraph may
    quote an English headline; the language's own list applies on top. A
    language with no list gets the English check alone, which is weaker than it
    looks — so it is written down here that this is not coverage, and a new
    translation language means a new list.

    Reported per distinct word rather than per occurrence, so a paragraph using
    "correct" three times produces one actionable message instead of three
    identical ones.
    """
    patterns = [_VERDICT_RE]
    base_lang = lang.split("-")[0].lower()
    if base_lang in _VERDICT_RE_BY_LANG:
        patterns.append(_VERDICT_RE_BY_LANG[base_lang])

    found = sorted({m.group(0).lower() for pattern in patterns for m in pattern.finditer(text)})
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

REVIEW_MAP_ENTRY_MAX_WORDS = 120


def check_review_map(record: dict) -> list[Violation]:
    """Keep the reviewer map concrete enough to guide one evening of reading."""
    review_map = record.get("review_map")
    if not isinstance(review_map, dict):
        return []
    violations: list[Violation] = []
    groups = ("main_deduction", "risks", "prerequisites", "needs_checking")
    for group in groups:
        raw = review_map.get(group)
        entries = [raw] if group == "main_deduction" and isinstance(raw, dict) else (raw or [])
        if not isinstance(entries, list):
            continue
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
                continue
            location = (
                f"review_map.{group}"
                if group == "main_deduction"
                else f"review_map.{group}[{index}]"
            )
            count = word_count(entry["text"])
            if count > REVIEW_MAP_ENTRY_MAX_WORDS:
                violations.append(
                    Violation(
                        "review-map-entry-too-long",
                        (
                            f"{count} words, over the "
                            f"{REVIEW_MAP_ENTRY_MAX_WORDS}-word cap for a focused "
                            "reviewer-map entry"
                        ),
                        f"{location}.text",
                    )
                )
            violations.extend(verdict_violations(entry["text"], f"{location}.text"))
    return violations


# The line is written to be pasted into a headline or a forum post, so it has
# to fit in one. Shorter than a plain_summary field on purpose.
ACCURATE_WORDING_MAX_WORDS = 40


def check_accurate_wording(record: dict) -> list[Violation]:
    """The suggested sentence is the one most likely to travel, so it is the
    one held tightest.

    It exists to stop overstatement, which makes a verdict inside it the exact
    failure the field was built to prevent — and unlike the other
    plain-language blocks, this one is written to be copied somewhere this
    project has no control over, where nobody will see the attribution that
    would have qualified it.
    """
    wording = record.get("accurate_wording")
    if not isinstance(wording, dict):
        return []

    value = wording.get("value")
    if not isinstance(value, str):
        return []

    violations = list(verdict_violations(value, "accurate_wording.value"))
    count = word_count(value)
    if count > ACCURATE_WORDING_MAX_WORDS:
        violations.append(
            Violation(
                "accurate-wording-too-long",
                f"{count} words, over the {ACCURATE_WORDING_MAX_WORDS}-word cap. A sentence "
                "somebody can paste into a post has to fit in one",
                "accurate_wording.value",
            )
        )
    return violations


def check_plain_summary_translations(record: dict) -> list[Violation]:
    """A translation is a second summary and answers to the summary's rules.

    Including the one about not exceeding the record: a translation that
    quietly drops the not-checked line is the easiest way for a strip in a
    language the maintainer reads less fluently to become an endorsement.
    """
    summary = record.get("plain_summary")
    if not isinstance(summary, dict):
        return []

    violations: list[Violation] = []
    seen: set[str] = set()
    for index, translation in enumerate(summary.get("translations") or []):
        if not isinstance(translation, dict):
            continue
        lang = translation.get("lang")
        if isinstance(lang, str):
            if lang in seen:
                violations.append(
                    Violation(
                        "duplicate-translation-language",
                        f"two translations declare lang {lang!r}; the page would render both "
                        "and a reader could not tell which one the record stands behind",
                        f"plain_summary.translations[{index}].lang",
                    )
                )
            seen.add(lang)

        for field in PLAIN_SUMMARY_FIELDS:
            value = translation.get(field)
            if not isinstance(value, str):
                continue
            location = f"plain_summary.translations[{index}].{field}"
            count = word_count(value)
            # Word counts do not transfer between scripts -- Arabic says in
            # four words what English says in seven -- so the cap is applied
            # with room rather than exactly, and it is here to catch a
            # translation that grew into an essay, not to police style.
            if count > PLAIN_SUMMARY_MAX_WORDS * 2:
                violations.append(
                    Violation(
                        "plain-summary-too-long",
                        f"{count} words in the {translation.get('lang', '?')} translation, far "
                        f"over the {PLAIN_SUMMARY_MAX_WORDS}-word cap the English fields answer to",
                        location,
                    )
                )
            lang_tag = lang if isinstance(lang, str) else "en"
            violations.extend(verdict_violations(value, location, lang=lang_tag))

    return violations


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


#: The venues an exposition may name. Kept in step with the schema enum; the
#: validator repeats the check so a record built against an older copy of the
#: schema still fails here rather than rendering a venue the templates have no
#: label for.
EXPOSITION_VENUES = ("erdosproblems", "mathematical_discourse", "arxiv", "blog", "other")

_HTTP_URL_RE = re.compile(r"^https?://[^\s]+$", re.IGNORECASE)

#: Rendered with every palomar_entry, from here, never from the record. The
#: registry's own framing of its intake is the load-bearing half: a record that
#: could reword this could quietly upgrade a directory listing into a review.
PALOMAR_CAVEAT = (
    "Palomar intake checks fall short of peer review (registry's own framing); "
    "correspondence with the claimed theorem is not established by this entry."
)


def _url_violations(
    value: object, rule_missing: str, subject: str, location: str
) -> list[Violation]:
    """A link-shaped evidence entry is its link; without one it points nowhere.

    Presence is checked here rather than in the schema's `required` list so the
    failure has one name instead of two, the same reason `open_invitations[].how`
    is emptiness-checked here.
    """
    if not isinstance(value, str) or not value.strip():
        return [
            Violation(
                rule_missing,
                f"{subject} records no url; the entry exists to point at something published "
                "elsewhere, and without the link it points at nothing",
                location,
            )
        ]
    if not _HTTP_URL_RE.match(value.strip()):
        return [
            Violation(
                rule_missing,
                f"{subject} url {value!r} is not an http(s) URL; the renderer will not link it, "
                "so the entry would render as an exposition nobody can open",
                location,
            )
        ]
    return []


def check_exposition_evidence(record: dict) -> list[Violation]:
    """An exposition entry says a thing was written, where, by whom, and about what.

    It is not a review, so the one field in it that could drift into being one —
    `scope`, which describes coverage — answers to the verdict lint. "Expounds
    the Lean proof" is scope; "expounds the Lean proof, which is correct" is a
    finding this project does not make, in a field nobody would think to check.
    """
    violations: list[Violation] = []
    parties = record.get("parties") or {}
    for index, entry in enumerate(record.get("evidence") or []):
        if not isinstance(entry, dict) or entry.get("kind") != "exposition":
            continue
        location = f"evidence[{index}]"

        violations.extend(
            _url_violations(
                entry.get("url"), "exposition-missing-url", "exposition", location + ".url"
            )
        )

        venue = entry.get("venue")
        if isinstance(venue, str) and venue not in EXPOSITION_VENUES:
            violations.append(
                Violation(
                    "exposition-unknown-venue",
                    f"venue {venue!r} is not one of {list(EXPOSITION_VENUES)}",
                    location + ".venue",
                )
            )
        if venue == "other" and not (entry.get("venue_label") or "").strip():
            violations.append(
                Violation(
                    "exposition-venue-unnamed",
                    "venue is 'other' but venue_label is missing; an exposition from an unnamed "
                    "venue cannot be looked up or asked about",
                    location + ".venue_label",
                )
            )

        author = entry.get("author")
        if isinstance(author, str) and author not in parties:
            violations.append(
                Violation(
                    "unknown-party",
                    f"exposition author references undeclared party {author!r}",
                    location + ".author",
                )
            )

        scope = entry.get("scope")
        if not isinstance(scope, str) or not scope.strip():
            violations.append(
                Violation(
                    "exposition-empty-scope",
                    "scope is empty; an exposition row with no stated coverage invites the "
                    "reader to assume it covers everything",
                    location + ".scope",
                )
            )
        else:
            violations.extend(verdict_violations(scope, location + ".scope"))

        label = entry.get("venue_label")
        if isinstance(label, str) and label.strip():
            violations.extend(verdict_violations(label, location + ".venue_label"))

    return violations


def check_palomar_entries(record: dict) -> list[Violation]:
    """A registry entry is a pointer. The caveat that says so is not in the record."""
    violations: list[Violation] = []
    for index, entry in enumerate(record.get("evidence") or []):
        if not isinstance(entry, dict) or entry.get("kind") != "palomar_entry":
            continue
        location = f"evidence[{index}]"
        violations.extend(
            _url_violations(
                entry.get("url"), "palomar-missing-url", "palomar_entry", location + ".url"
            )
        )
        artifact_ref = entry.get("artifact_ref")
        if isinstance(artifact_ref, str) and artifact_ref.strip():
            violations.extend(verdict_violations(artifact_ref, location + ".artifact_ref"))
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


def check_invitation_state(record: dict) -> list[Violation]:
    violations = []
    evidence_ids = {e.get("id") for e in record.get("evidence") or [] if isinstance(e, dict)}
    attestation_ids = {e.get("id") for e in record.get("attestations") or [] if isinstance(e, dict)}
    for i, invitation in enumerate(record.get("open_invitations") or []):
        if not isinstance(invitation, dict):
            continue
        status = invitation.get("status", "open")
        path = f"open_invitations[{i}]"
        if status == "taken":
            if not invitation.get("taken_by"):
                violations.append(
                    Violation(
                        "taken-without-who",
                        "taken invitation requires taken_by",
                        path + ".taken_by",
                    )
                )
            if not invitation.get("taken_at"):
                violations.append(
                    Violation(
                        "taken-without-date",
                        "taken invitation requires taken_at",
                        path + ".taken_at",
                    )
                )
        if status == "done" and invitation.get("done_ref") not in evidence_ids | attestation_ids:
            violations.append(
                Violation(
                    "done-without-ref",
                    "done invitation requires done_ref resolving to evidence or attestation",
                    path + ".done_ref",
                )
            )
    return violations


def check_invitation_task_kinds(record: dict) -> list[Violation]:
    """Keep the optional task taxonomy closed when an invitation opts in."""
    allowed = {"read_check", "rederive", "reproduce_build", "statement_audit", "exposition"}
    violations = []
    for i, invitation in enumerate(record.get("open_invitations") or []):
        if not isinstance(invitation, dict) or "task_kind" not in invitation:
            continue
        if invitation.get("task_kind") not in allowed:
            violations.append(
                Violation(
                    "task-kind-unknown",
                    (
                        f"task_kind must be one of {sorted(allowed)}, "
                        f"got {invitation.get('task_kind')!r}"
                    ),
                    f"open_invitations[{i}].task_kind",
                )
            )
    return violations


def check_review_notes(record: dict) -> list[Violation]:
    violations = []
    for i, attestation in enumerate(record.get("attestations") or []):
        note = attestation.get("review_note") if isinstance(attestation, dict) else None
        if isinstance(note, str):
            violations.extend(verdict_violations(note, f"attestations[{i}].review_note"))
        for field in ("method", "finding", "limits"):
            value = attestation.get(field) if isinstance(attestation, dict) else None
            if isinstance(value, str):
                violations.extend(verdict_violations(value, f"attestations[{i}].{field}"))
    return violations


def check_dependencies(record: dict, known_ids: set[str] | None = None) -> list[Violation]:
    known_ids = known_ids or set()
    return [
        Violation(
            "depends-on-unknown-record",
            f"dependency references unknown record '{d['record']}'",
            f"depends_on[{i}].record",
        )
        for i, d in enumerate(record.get("depends_on") or [])
        if isinstance(d, dict) and d.get("record") and d["record"] not in known_ids
    ]


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
    "tool",
    "tool_version",
    "runner_image_digest",
    "executed_at",
    "result",
    "log_sha256",
    "asserted_by",
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
                k for k in set(base_event) | set(cur_event) if base_event.get(k) != cur_event.get(k)
            )
            violations.append(
                Violation(
                    "history-event-mutated",
                    f"history event '{event_id}' payload changed in field(s) {changed}",
                    location,
                )
            )

    return violations


def semantic_violations(record: dict, known_ids: set[str] | None = None) -> list[Violation]:
    """Single-record semantic checks (no base, no sibling records needed)."""
    return [
        *check_asserted_by_parties(record),
        *check_source_quote_locators(record),
        *check_forbidden_language(record),
        *check_plain_summary(record),
        *check_plain_summary_translations(record),
        *check_accurate_wording(record),
        *check_plain_language_digestions(record),
        *check_review_map(record),
        *check_exposition_evidence(record),
        *check_palomar_entries(record),
        *check_invitation_instructions(record),
        *check_invitation_state(record),
        *check_invitation_task_kinds(record),
        *check_review_notes(record),
        *(check_dependencies(record, known_ids) if known_ids is not None else []),
        *check_freshness_recomputation(record),
        *check_execution_receipt_asserted_by_automation(record),
    ]
