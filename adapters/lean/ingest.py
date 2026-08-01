"""Trusted-ingest: turns an untrusted build's outputs into a Significance
evidence entry. This module never runs untrusted code -- it only reads
the JSON artifacts the untrusted build workflow produced (isolation
evidence, build receipt, axiom-check receipt) and, read-only, the checked
-out source tree for the kernel-bypass scan.

Two independent decisions are made here, and they are not the same thing:

1. Was isolation demonstrated at all (isolation.check_isolation)? If not,
   the fail-closed rule applies automatically: the submission is recorded
   as `external_formal_artifact` (reported, not reproduced), regardless
   of what the untrusted build claimed about its own success.
2. Even when isolation WAS demonstrated, does the source contain a
   kernel-bypass option (scan_kernel_bypass.scan_tree)? If so, the build
   and axiom-check results are forced to "failed" -- a bypass hit means
   the kernel typechecker itself cannot be trusted, which is a different
   failure mode than "we couldn't prove the sandbox held."

`correspondence` (the attested claim that the Lean statement matches the
informal one) is supplied by the human submitter, never generated here:
correspondence is attested, not machine-asserted, and this adapter does
not pretend otherwise.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from isolation import check_isolation
from scan_kernel_bypass import RULE as KERNEL_BYPASS_RULE
from scan_kernel_bypass import BypassHit, scan_tree


@dataclass
class IngestResult:
    kind: str  # "formal_artifact" | "external_formal_artifact"
    evidence: dict
    fail_closed_reasons: list[str] = field(default_factory=list)
    rule_violations: list[str] = field(default_factory=list)
    bypass_hits: list[BypassHit] = field(default_factory=list)


def ingest(
    *,
    evidence_id: str,
    repo: str,
    commit: str,
    isolation_evidence: dict,
    build_receipt: dict,
    axiom_execution_receipt: dict,
    trust_profile: str,
    allowlist: list[str],
    allowlist_version: str,
    toolchain_pin: str,
    lockfile_hash: str,
    correspondence: dict,
    asserted_at: str,
    source_root: Path | None = None,
) -> IngestResult:
    fail_closed = check_isolation(isolation_evidence)

    bypass_hits = scan_tree(source_root) if source_root is not None else []
    rule_violations = [KERNEL_BYPASS_RULE] if bypass_hits else []

    build = dict(build_receipt)
    axiom_execution = dict(axiom_execution_receipt)
    if bypass_hits:
        # Axiom closure structurally cannot see through a kernel bypass:
        # force both receipts to a failing result regardless of what the
        # (untrusted) build claimed about itself.
        build["result"] = "failed"
        axiom_execution["result"] = "failed"

    if not fail_closed.ok:
        evidence = {
            "id": evidence_id,
            "kind": "external_formal_artifact",
            "repo": repo,
            "commit": commit,
            "description": (
                "Isolation could not be demonstrated for this submission "
                f"({'; '.join(fail_closed.reasons)}); reported, not reproduced."
            ),
            "basis": "machine_result",
            "asserted_by": "significance-ci",
            "asserted_at": asserted_at,
        }
        return IngestResult(
            kind="external_formal_artifact",
            evidence=evidence,
            fail_closed_reasons=fail_closed.reasons,
            rule_violations=rule_violations,
            bypass_hits=bypass_hits,
        )

    evidence = {
        "id": evidence_id,
        "kind": "formal_artifact",
        "repo": repo,
        "commit": commit,
        "toolchain": {"name": "lean4", "pin_kind": "digest", "pin": toolchain_pin},
        "lockfile_hash": lockfile_hash,
        "artifact_build": build,
        "axiom_policy": {
            "trust_profile": trust_profile,
            "allowlist": allowlist,
            "allowlist_version": allowlist_version,
            "execution": axiom_execution,
        },
        "correspondence": correspondence,
    }
    return IngestResult(
        kind="formal_artifact",
        evidence=evidence,
        rule_violations=rule_violations,
        bypass_hits=bypass_hits,
    )
