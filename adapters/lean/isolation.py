"""Fail-closed isolation check.

The untrusted build workflow runs on a GitHub-hosted ephemeral runner with
no write tokens and no secrets in scope. It never talks to the trusted
side directly -- it only emits an isolation-evidence JSON document
alongside its build/axiom-check results, as workflow artifacts. This
module is the trusted side's only judgment call: it never runs untrusted
code, it only reads that JSON and decides, per the design doc's fail-closed
rule, whether isolation was demonstrated.

Anything short of a fully demonstrated, clean report takes the
external_formal_artifact path automatically (see ingest.py) -- nothing
here raises to abort a submission; failure to prove isolation is an
ordinary, expected outcome, not an error.
"""

from __future__ import annotations

from dataclasses import dataclass, field

EXPECTED_RUNNER = "github-hosted-ephemeral"

_RESOURCE_LIMIT_KEYS = ("cpu_enforced", "memory_enforced", "pids_enforced", "disk_enforced")


@dataclass
class FailClosedResult:
    ok: bool
    reasons: list[str] = field(default_factory=list)


def check_isolation(evidence: dict) -> FailClosedResult:
    reasons: list[str] = []

    if evidence.get("runner") != EXPECTED_RUNNER:
        reasons.append(f"runner is {evidence.get('runner')!r}, not {EXPECTED_RUNNER!r}")

    if evidence.get("secrets_in_scope") is not False:
        reasons.append("secrets_in_scope was not demonstrably false")

    network = evidence.get("network") or {}
    if network.get("denied_after_acquisition") is not True:
        reasons.append("network was not demonstrably denied after dependency acquisition")
    egress_attempts = network.get("egress_attempts_after_denial", 1)
    if egress_attempts != 0:
        reasons.append(f"{egress_attempts} network egress attempt(s) recorded after denial")

    limits = evidence.get("resource_limits") or {}
    for key in _RESOURCE_LIMIT_KEYS:
        if limits.get(key) is not True:
            reasons.append(f"resource limit '{key}' was not demonstrably enforced")

    wall_clock = evidence.get("wall_clock") or {}
    if wall_clock.get("enforced") is not True:
        reasons.append("wall-clock limit was not demonstrably enforced")
    if wall_clock.get("terminated_by_timeout"):
        reasons.append("build was terminated by the wall-clock timeout")

    fs = evidence.get("filesystem") or {}
    unauthorized = fs.get("unauthorized_write_attempts") or []
    if unauthorized:
        reasons.append(
            f"unauthorized write attempt(s) outside the build output path: {unauthorized}"
        )

    return FailClosedResult(ok=not reasons, reasons=reasons)
