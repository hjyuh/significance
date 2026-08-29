"""`significance init`: interactive scaffold of a new record.

Design choice: freshness.result is always asked explicitly with no
pre-filled default (invariant 4: "never silently render as current").
Every other field with an obvious safe default (timestamps, empty optional
sections) may default, since defaulting there carries no truth-claim risk.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from ruamel.yaml import YAML

RECORD_ID_RE = re.compile(r"^[0-9]{4}(-[a-z0-9]+){2,}$")
PARTY_ID_RE = re.compile(r"^[a-z][a-z0-9-]*$")
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")

BASIS_CHOICES = ["source_quote", "author_attestation", "editorial_inference", "machine_result"]
ATTESTED_BASIS_CHOICES = ["source_quote", "author_attestation", "editorial_inference"]
EVIDENCE_KINDS = [
    "formal_artifact",
    "external_formal_artifact",
    "computational_reproduction",
    "source_inspection",
    "informal_review",
    "mathematical_assessment",
    "exposition",
    "palomar_entry",
]
#: Offered by name in `init`, and enforced by the schema and validator. Kept in
#: step with `schema/record.schema.json`.
EXPOSITION_VENUES = ["erdosproblems", "mathematical_discourse", "arxiv", "blog", "other"]
LINK_BASIS_CHOICES = ["source_link", "author_attestation"]
AI_ROLES = [
    "problem_selection",
    "literature_search",
    "conjecture_generation",
    "proof_generation",
    "criticism",
    "computation",
    "formalization",
    "prose_editing",
    "candidate_generation",
]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ask(prompt_fn, question, default=None, pattern=None, required=True):
    suffix = f" [{default}]" if default is not None else ""
    while True:
        ans = prompt_fn(f"{question}{suffix}: ").strip()
        if not ans and default is not None:
            ans = default
        if not ans and not required:
            return ""
        if not ans:
            print("A value is required.")
            continue
        if pattern and not pattern.match(ans):
            print(f"'{ans}' does not match the required format ({pattern.pattern}).")
            continue
        return ans


def _ask_choice(prompt_fn, question, choices, default=None):
    choice_str = "/".join(choices)
    while True:
        ans = _ask(prompt_fn, f"{question} ({choice_str})", default=default)
        if ans in choices:
            return ans
        print(f"Please choose one of: {choice_str}")


def _ask_yes_no(prompt_fn, question, default=False):
    default_str = "y" if default else "n"
    ans = prompt_fn(f"{question} (y/n) [{default_str}]: ").strip().lower()
    if not ans:
        return default
    return ans.startswith("y")


def _ask_attribution(prompt_fn, party_ids, label="value", allow_locator=True):
    value = _ask(prompt_fn, f"{label} text")
    basis = _ask_choice(prompt_fn, f"{label} basis", BASIS_CHOICES)
    asserted_by = _ask_choice(prompt_fn, f"{label} asserted_by (party id)", party_ids)
    attributed = {
        "value": value,
        "basis": basis,
        "asserted_by": asserted_by,
        "asserted_at": _now(),
    }
    if allow_locator and basis == "source_quote":
        section = _ask(prompt_fn, "  locator section", default="", required=False)
        quote = _ask(prompt_fn, "  locator quote", default="", required=False)
        locator = {}
        if section:
            locator["section"] = section
        if quote:
            locator["quote"] = quote
        if locator:
            attributed["locator"] = locator
    return attributed


def _scaffold_parties(prompt_fn) -> dict:
    parties: dict[str, dict] = {}
    print("-- Parties (at least one) --")
    while True:
        pid = _ask(prompt_fn, "party id (lowercase-kebab)", pattern=PARTY_ID_RE)
        is_pseudonym = _ask_yes_no(prompt_fn, "  pseudonymous?", default=False)
        name_key = "pseudonym" if is_pseudonym else "name"
        name = _ask(prompt_fn, f"  {name_key}")
        vm_kind = _ask_choice(
            prompt_fn,
            "  verification method",
            ["github_identity", "orcid", "email_confirmation", "pseudonymous", "automation"],
        )
        identifier = _ask(prompt_fn, "  verification identifier", default="", required=False)
        vm = {"kind": vm_kind}
        if identifier:
            vm["identifier"] = identifier
        parties[pid] = {name_key: name, "verification_method": vm}
        if parties and not _ask_yes_no(prompt_fn, "Add another party?", default=False):
            break
    return parties


def _scaffold_claim(prompt_fn, party_ids) -> dict:
    print("-- Claim --")
    claim_id = _ask(prompt_fn, "claim id", default="claim-main")
    text = _ask_attribution(prompt_fn, party_ids, label="claim text")
    scope = _ask_attribution(prompt_fn, party_ids, label="claim scope")
    return {"id": claim_id, "text": text, "scope": scope}


def _scaffold_manuscript(prompt_fn) -> dict:
    print("-- Manuscript --")
    manuscript = {
        "url": _ask(prompt_fn, "manuscript url"),
        "label": _ask(prompt_fn, "manuscript label"),
        "sha256": _ask(prompt_fn, "manuscript sha256", pattern=SHA256_RE),
        "retrieved_at": _ask(prompt_fn, "retrieved_at", default=_now()),
    }
    version_id = _ask(prompt_fn, "immutable_version_id", default="", required=False)
    if version_id:
        manuscript["immutable_version_id"] = version_id
    return manuscript


def _scaffold_freshness(prompt_fn) -> dict:
    print("-- Freshness (no default: pick the true state) --")
    result = _ask_choice(prompt_fn, "freshness result", ["current", "stale", "unknown"])
    freshness = {"result": result, "checked_at": _ask(prompt_fn, "checked_at", default=_now())}
    if result != "unknown":
        freshness["observed_source_version"] = _ask(prompt_fn, "observed_source_version")
        freshness["confirmed_source_version"] = _ask(prompt_fn, "confirmed_source_version")
    return freshness


def _scaffold_evidence_item(prompt_fn, party_ids, index) -> dict:
    kind = _ask_choice(prompt_fn, "evidence kind", EVIDENCE_KINDS)
    eid = _ask(prompt_fn, "evidence id", default=f"ev-{index}")
    item = {"id": eid, "kind": kind}

    if kind == "formal_artifact":
        item["repo"] = _ask(prompt_fn, "  repo url")
        item["commit"] = _ask(prompt_fn, "  commit sha")
        item["toolchain"] = {
            "name": _ask(prompt_fn, "  toolchain name"),
            "pin_kind": _ask_choice(prompt_fn, "  toolchain pin_kind", ["digest", "commit"]),
            "pin": _ask(prompt_fn, "  toolchain pin"),
        }
        item["lockfile_hash"] = _ask(prompt_fn, "  lockfile_hash", pattern=SHA256_RE)
        item["artifact_build"] = _scaffold_receipt(prompt_fn)
        item["axiom_policy"] = {
            "trust_profile": _ask_choice(
                prompt_fn,
                "  axiom trust_profile",
                ["lean_standard_classical", "lean_standard_classical_plus_native", "custom"],
            ),
            "allowlist": [
                s.strip()
                for s in _ask(prompt_fn, "  allowlist (comma-separated)").split(",")
                if s.strip()
            ],
            "allowlist_version": _ask(prompt_fn, "  allowlist_version", default="1"),
            "execution": _scaffold_receipt(prompt_fn),
        }
        correspondence = _ask_attribution(
            prompt_fn, party_ids, label="  correspondence", allow_locator=False
        )
        while correspondence["basis"] not in ATTESTED_BASIS_CHOICES:
            print("Correspondence must be attested (never machine_result). Try again.")
            correspondence = _ask_attribution(
                prompt_fn, party_ids, label="  correspondence", allow_locator=False
            )
        item["correspondence"] = correspondence

    elif kind == "external_formal_artifact":
        item["repo"] = _ask(prompt_fn, "  repo url")
        item["description"] = _ask(prompt_fn, "  description")
        item["basis"] = _ask_choice(prompt_fn, "  basis", BASIS_CHOICES)
        item["asserted_by"] = _ask_choice(prompt_fn, "  asserted_by", party_ids)
        item["asserted_at"] = _now()

    elif kind == "computational_reproduction":
        item["description"] = _ask(prompt_fn, "  description")
        item["execution"] = _scaffold_receipt(prompt_fn)

    elif kind == "source_inspection":
        item["description"] = _ask(
            prompt_fn, "What public sources or version facts were inspected?"
        )
        item.update(_ask_attribution(prompt_fn, party_ids, label="source inspection"))
    elif kind == "informal_review":
        item["reviewer"] = _ask_choice(prompt_fn, "  reviewer (party id)", party_ids)
        item["text"] = _ask(prompt_fn, "  review text")
        item["basis"] = _ask_choice(prompt_fn, "  basis", BASIS_CHOICES)
        item["asserted_by"] = _ask_choice(prompt_fn, "  asserted_by", party_ids)
        item["asserted_at"] = _now()

    elif kind == "exposition":
        # An exposition is not a review, so `init` asks for coverage rather
        # than for an opinion: the scope line is what stops a row that says
        # "an account exists" from being read as "an account approves".
        item["venue"] = _ask_choice(prompt_fn, "  venue", EXPOSITION_VENUES)
        if item["venue"] == "other":
            item["venue_label"] = _ask(prompt_fn, "  venue_label (the venue's name)")
        item["author"] = _ask_choice(prompt_fn, "  author (party id)", party_ids)
        item["date"] = _ask(prompt_fn, "  date the exposition was published (YYYY-MM-DD)")
        item["url"] = _ask(prompt_fn, "  url")
        item["scope"] = _ask(prompt_fn, "  what it covers and what it excludes")
        item["basis"] = _ask_choice(prompt_fn, "  basis", LINK_BASIS_CHOICES)
        item["asserted_by"] = _ask_choice(prompt_fn, "  asserted_by", party_ids)
        item["asserted_at"] = _now()

    elif kind == "palomar_entry":
        # No caveat is asked for. It is rendered from the code with every
        # entry, and a record that could supply one could supply a weaker one.
        item["url"] = _ask(prompt_fn, "  registry entry url")
        item["date"] = _ask(prompt_fn, "  entry date as the registry shows it (YYYY-MM-DD)")
        artifact_ref = _ask(
            prompt_fn, "  what it ties to (declaration, path, commit)", required=False
        )
        if artifact_ref:
            item["artifact_ref"] = artifact_ref
        item["basis"] = _ask_choice(prompt_fn, "  basis", LINK_BASIS_CHOICES)
        item["asserted_by"] = _ask_choice(prompt_fn, "  asserted_by", party_ids)
        item["asserted_at"] = _now()

    elif kind == "mathematical_assessment":
        item["target"] = _ask(prompt_fn, "  target (specific numbered statement)")
        inline = _ask(prompt_fn, "  report text (inline)")
        item["report"] = {"inline": inline}
        item["basis"] = _ask_choice(prompt_fn, "  basis", BASIS_CHOICES)
        item["asserted_by"] = _ask_choice(prompt_fn, "  asserted_by", party_ids)
        item["asserted_at"] = _now()

    return item


def _scaffold_receipt(prompt_fn) -> dict:
    return {
        "tool": _ask(prompt_fn, "  execution tool"),
        "tool_version": _ask(prompt_fn, "  tool_version"),
        "runner_image_digest": _ask(
            prompt_fn,
            "  runner_image_digest",
            pattern=re.compile(r"^sha256:[a-f0-9]{64}$"),
        ),
        "executed_at": _ask(prompt_fn, "  executed_at", default=_now()),
        "result": _ask_choice(prompt_fn, "  result", ["passed", "failed"]),
        "log_sha256": _ask(prompt_fn, "  log_sha256", pattern=SHA256_RE),
        "asserted_by": _ask(prompt_fn, "  receipt asserted_by", default="significance-ci"),
    }


def _scaffold_ai_provenance(prompt_fn, party_ids) -> dict:
    print("-- AI provenance --")
    disclosure = _ask_attribution(prompt_fn, party_ids, label="AI disclosure")
    roles = []
    while _ask_yes_no(prompt_fn, "Add an AI-provenance role?", default=len(roles) == 0):
        role = _ask_choice(prompt_fn, "  role", AI_ROLES)
        model = _ask(prompt_fn, "  model")
        basis = _ask_choice(prompt_fn, "  basis", BASIS_CHOICES)
        asserted_by = _ask_choice(prompt_fn, "  asserted_by", party_ids)
        roles.append({"role": role, "model": model, "basis": basis, "asserted_by": asserted_by})
    return {"disclosure": disclosure, "roles": roles}


def scaffold_record(prompt_fn) -> dict:
    record_id = _ask(
        prompt_fn, "record_id (<year>-<author-slug>-<topic-slug>)", pattern=RECORD_ID_RE
    )
    parties = _scaffold_parties(prompt_fn)
    party_ids = list(parties)
    claim = _scaffold_claim(prompt_fn, party_ids)
    manuscript = _scaffold_manuscript(prompt_fn)
    freshness = _scaffold_freshness(prompt_fn)

    print("-- Evidence (at least one) --")
    evidence = []
    index = 1
    while True:
        evidence.append(_scaffold_evidence_item(prompt_fn, party_ids, index))
        index += 1
        if evidence and not _ask_yes_no(prompt_fn, "Add another evidence item?", default=False):
            break

    ai_provenance = _scaffold_ai_provenance(prompt_fn, party_ids)

    author = party_ids[0]
    history = [{"id": "evt-created", "type": "created", "at": _now(), "by": author}]

    return {
        "schema_version": 1,
        "record_id": record_id,
        "record_version": 1,
        "record_state": "active",
        "freshness": freshness,
        "parties": parties,
        "claim": claim,
        "manuscript": manuscript,
        "evidence": evidence,
        "ai_provenance": ai_provenance,
        "history": history,
    }


def write_record(record: dict, records_dir: Path = Path("records")) -> Path:
    records_dir.mkdir(parents=True, exist_ok=True)
    path = records_dir / f"{record['record_id']}.yaml"
    yaml = YAML()
    yaml.indent(mapping=2, sequence=4, offset=2)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(record, f)
    return path
