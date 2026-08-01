"""Phase 4: Lean evidence adapter tests.

These exercise the trusted-ingest side only -- the fail-closed decision
(isolation.py), the kernel-bypass source scanner (scan_kernel_bypass.py),
and how ingest.py combines them into an evidence fragment. Actually
executing an untrusted Lean build inside a network-isolated, resource-
limited GitHub-hosted runner is not something this test environment can
do; that half of the adapter (the untrusted-build workflow and its
Docker-based isolation) is reviewed as YAML, not exercised here. See
adapters/lean/README.md for what is and isn't covered.

Covers all four adversarial fixtures named in the design doc, plus a
clean-success control to prove the fail-closed path doesn't also
swallow legitimate submissions.
"""

from __future__ import annotations

import json
from pathlib import Path

from ingest import ingest
from isolation import check_isolation
from scan_kernel_bypass import scan_tree

FIXTURES = Path(__file__).resolve().parents[1] / "adapters" / "lean" / "fixtures"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _ingest_from_fixture(name: str, source_root: Path | None = None):
    d = FIXTURES / name
    isolation_evidence = _load(d / "isolation-evidence.json")
    build_receipt = _load(d / "build-receipt.json") if (d / "build-receipt.json").exists() else {
        "tool": "significance-lean",
        "tool_version": "0.1.0",
        "runner_image_digest": "sha256:" + "0" * 64,
        "executed_at": "2026-07-31T00:00:00Z",
        "result": "failed",
        "log_sha256": "0" * 64,
        "asserted_by": "significance-ci",
    }
    axiom_execution_path = d / "axiom-execution.json"
    axiom_execution = (
        _load(axiom_execution_path) if axiom_execution_path.exists() else dict(build_receipt)
    )
    correspondence = (
        _load(d / "correspondence.json")
        if (d / "correspondence.json").exists()
        else {
            "value": "n/a",
            "basis": "author_attestation",
            "asserted_by": "author-as",
            "asserted_at": "2026-07-31T00:00:00Z",
        }
    )
    return ingest(
        evidence_id="ev-test",
        repo="https://github.com/example/repo",
        commit="a" * 40,
        isolation_evidence=isolation_evidence,
        build_receipt=build_receipt,
        axiom_execution_receipt=axiom_execution,
        trust_profile="lean_standard_classical",
        allowlist=["propext", "Classical.choice", "Quot.sound"],
        allowlist_version="1",
        toolchain_pin="sha256:" + "a" * 64,
        lockfile_hash="b" * 64,
        correspondence=correspondence,
        asserted_at="2026-07-31T00:10:00Z",
        source_root=(
            source_root
            if source_root is not None
            else (d / "src" if (d / "src").exists() else None)
        ),
    )


def test_clean_success_is_formal_artifact():
    result = _ingest_from_fixture("clean-success")
    assert result.kind == "formal_artifact"
    assert result.fail_closed_reasons == []
    assert result.rule_violations == []
    assert result.evidence["artifact_build"]["result"] == "passed"
    assert result.evidence["axiom_policy"]["execution"]["result"] == "passed"
    assert result.evidence["kind"] == "formal_artifact"


def test_network_egress_attempt_fails_closed():
    result = _ingest_from_fixture("network-egress-attempt")
    assert result.kind == "external_formal_artifact"
    assert any("egress" in r for r in result.fail_closed_reasons)
    assert result.evidence["kind"] == "external_formal_artifact"
    assert result.evidence["basis"] == "machine_result"
    assert result.evidence["asserted_by"] == "significance-ci"
    assert "artifact_build" not in result.evidence  # no build claims for a reported artifact


def test_wall_clock_timeout_fails_closed():
    result = _ingest_from_fixture("wall-clock-timeout")
    assert result.kind == "external_formal_artifact"
    assert any("timeout" in r for r in result.fail_closed_reasons)


def test_record_path_write_fails_closed():
    result = _ingest_from_fixture("record-path-write")
    assert result.kind == "external_formal_artifact"
    assert any("unauthorized write" in r for r in result.fail_closed_reasons)
    assert any("records/2026-attacker-fake.yaml" in r for r in result.fail_closed_reasons)


def test_kernel_bypass_source_forces_failing_result():
    result = _ingest_from_fixture("kernel-bypass-source")
    # Isolation was clean here -- this is the "failing outcome" case, not
    # the fail-closed-to-external-formal-artifact case.
    assert result.fail_closed_reasons == []
    assert result.kind == "formal_artifact"
    assert result.rule_violations == ["kernel-bypass-option-detected"]
    assert result.evidence["artifact_build"]["result"] == "failed"
    assert result.evidence["axiom_policy"]["execution"]["result"] == "failed"
    assert len(result.bypass_hits) == 1
    assert result.bypass_hits[0].option == "debug.skipKernelTC"


def test_scan_kernel_bypass_is_clean_on_ordinary_source():
    hits = scan_tree(FIXTURES / "clean-success" / "src")
    assert hits == []


def test_scan_kernel_bypass_matches_any_debug_skip_option(tmp_path):
    (tmp_path / "Weird.lean").write_text(
        "set_option debug.skipDefEq true\ntheorem x : True := trivial\n",
        encoding="utf-8",
    )
    hits = scan_tree(tmp_path)
    assert len(hits) == 1
    assert hits[0].option == "debug.skipDefEq"
    assert hits[0].line == 1


def test_scan_kernel_bypass_ignores_dependency_and_build_trees(tmp_path):
    (tmp_path / "Submission.lean").write_text("theorem x : True := trivial\n", encoding="utf-8")
    for excluded in (".lake", ".git", "build", "dist"):
        dependency_dir = tmp_path / excluded / "packages" / "dependency"
        dependency_dir.mkdir(parents=True)
        (dependency_dir / "Unsafe.lean").write_text(
            "set_option debug.skipKernelTC true\n",
            encoding="utf-8",
        )

    assert scan_tree(tmp_path) == []


def test_check_isolation_ok_requires_every_field_correct():
    clean = _load(FIXTURES / "clean-success" / "isolation-evidence.json")
    assert check_isolation(clean).ok

    tampered = dict(clean)
    tampered["secrets_in_scope"] = True
    assert not check_isolation(tampered).ok

    tampered2 = json.loads(json.dumps(clean))
    tampered2["resource_limits"]["memory_enforced"] = False
    assert not check_isolation(tampered2).ok


def test_missing_isolation_evidence_fails_closed():
    result = check_isolation({})
    assert not result.ok
    assert len(result.reasons) >= 1
