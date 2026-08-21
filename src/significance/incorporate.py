"""Editor-side incorporation of a scoped attestation from an issue or YAML file."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from ruamel.yaml import YAML

from significance.records import load_record, validator
from significance.semantics import semantic_violations


def _read(path: Path) -> dict:
    yaml = YAML(typ="safe")
    value = yaml.load(path.read_text(encoding="utf-8"))
    if isinstance(value, dict) and isinstance(value.get("attestation"), dict):
        return value["attestation"]
    if not isinstance(value, dict):
        raise ValueError("input must be an attestation mapping")
    return value


def _record_path(record_id: str, records_dir: Path) -> Path:
    for path in sorted(records_dir.glob("*.yaml")):
        if load_record(path).get("record_id") == record_id:
            return path
    raise ValueError(f"record not found: {record_id}")


def incorporate_attestation(
    input_path: str | Path, record_id: str, records_dir: str | Path = "records"
) -> Path:
    path = _record_path(record_id, Path(records_dir))
    record = load_record(path)
    attestation = deepcopy(_read(Path(input_path)))
    required = ("id", "task_id", "reviewer", "asserted_at", "method", "finding")
    missing = [key for key in required if not str(attestation.get(key, "")).strip()]
    if missing:
        raise ValueError(f"attestation missing required fields: {', '.join(missing)}")
    if attestation.get("manuscript_sha256") != record.get("manuscript", {}).get("sha256"):
        raise ValueError(
            "attestation manuscript_sha256 does not match the record's current manuscript"
        )
    if attestation.get("reviewer") not in record.get("parties", {}):
        raise ValueError("attestation reviewer must be a declared party before incorporation")
    attestation.setdefault("asserted_by", attestation["reviewer"])
    task = next(
        (
            item
            for item in record.get("open_invitations", [])
            if item.get("task_id") == attestation["task_id"]
        ),
        None,
    )
    if task is None:
        raise ValueError(f"open invitation not found: {attestation['task_id']}")
    if task.get("status", "open") != "open":
        raise ValueError(f"invitation is not open: {attestation['task_id']}")
    if any(item.get("id") == attestation["id"] for item in record.get("attestations", [])):
        raise ValueError(f"attestation id already exists: {attestation['id']}")
    attestation.setdefault("stratum", "community")
    candidate = deepcopy(record)
    candidate.setdefault("attestations", []).append(attestation)
    task_index = next(
        i
        for i, item in enumerate(candidate["open_invitations"])
        if item.get("task_id") == attestation["task_id"]
    )
    candidate["open_invitations"][task_index]["status"] = "done"
    candidate["open_invitations"][task_index]["done_ref"] = attestation["id"]
    candidate.setdefault("history", []).append({
        "id": f"evt-{attestation['id']}",
        "type": "attestation_added",
        "at": attestation["asserted_at"],
        "by": attestation["asserted_by"],
        "note": (
            f"Added scoped attestation for {attestation['task_id']}; source hash matched "
            "the current manuscript."
        ),
    })
    errors = list(validator().iter_errors(candidate)) + semantic_violations(candidate)
    if errors:
        raise ValueError("attestation rejected: " + "; ".join(str(error) for error in errors))
    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        yaml.dump(candidate, handle)
    return path
