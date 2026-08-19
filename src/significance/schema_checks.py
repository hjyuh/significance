"""Maps raw jsonschema errors to named, human-meaningful rule codes.

Structural validity is jsonschema's job (see schema/record.schema.json).
This module exists only to translate its errors into the rule vocabulary
`significance validate` reports, so a user sees "unattributed-assertion"
rather than "'asserted_by' is a required property".
"""

from __future__ import annotations

import re

from significance.pathfmt import format_path
from significance.violations import Violation

_REQUIRED_PROP_RE = re.compile(r"^'([^']+)' is a required property$")

_ATTRIBUTION_FIELDS = {"basis", "asserted_by", "asserted_at"}

# A `required` error is classified by which container's required-list it came
# from, not by field name alone: `asserted_by` is required by both
# attributed_value and execution_receipt, so per-field-name matching alone
# cannot tell the two apart. Fingerprinting the whole required set does.
_ATTRIBUTED_VALUE_REQUIRED = frozenset({"value", "basis", "asserted_by", "asserted_at"})
_EXECUTION_RECEIPT_REQUIRED = frozenset(
    {
        "tool",
        "tool_version",
        "runner_image_digest",
        "executed_at",
        "result",
        "log_sha256",
        "asserted_by",
    }
)
_MANUSCRIPT_REQUIRED = frozenset({"url", "label", "sha256", "retrieved_at"})


def classify(error) -> Violation:
    path = list(error.path)
    container = format_path(path)

    if error.validator == "required":
        m = _REQUIRED_PROP_RE.match(error.message)
        prop = m.group(1) if m else "?"
        location = f"{container}.{prop}" if container != "$" else prop
        required_set = frozenset(error.validator_value or [])

        if required_set == _EXECUTION_RECEIPT_REQUIRED:
            return Violation(
                "bare-machine-result",
                f"execution receipt is missing required field '{prop}'",
                location,
            )
        if path and path[-1] == "correspondence" and prop == "basis":
            return Violation("correspondence-unattested", "correspondence has no basis", location)
        if required_set == _ATTRIBUTED_VALUE_REQUIRED or prop in _ATTRIBUTION_FIELDS:
            return Violation(
                "unattributed-assertion",
                f"value is missing required attribution field '{prop}'",
                location,
            )
        if required_set == _MANUSCRIPT_REQUIRED and prop == "sha256":
            return Violation("missing-manuscript-hash", "manuscript has no sha256", location)
        return Violation("missing-required-field", error.message, location)

    if error.validator == "additionalProperties":
        return Violation("forbidden-field", error.message, container)

    if error.validator == "enum" and path and path[-1] == "basis":
        if "correspondence" in path:
            return Violation(
                "correspondence-unattested",
                "correspondence basis must be an attested value, not machine_result",
                container,
            )
        return Violation("invalid-basis-value", error.message, container)

    if error.validator == "pattern" and path and path[-1] == "record_id":
        return Violation("invalid-record-id-format", error.message, container)

    return Violation("schema-error", error.message, container)


def schema_violations(record: dict, validator) -> list[Violation]:
    return [classify(e) for e in validator.iter_errors(record)]
