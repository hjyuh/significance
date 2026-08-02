"""CLI wrapper around ingest.ingest() for the trusted-ingest workflow step.
Reads the untrusted build's JSON artifacts and a human-supplied
correspondence file, writes the resulting evidence fragment (plus a short
report of what was decided and why) as JSON to --out.

This script itself must never be given anything from the untrusted job
beyond the JSON/text artifacts it explicitly reads below, and it never
executes anything from the checked-out source tree -- scan_tree() only
reads file contents.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ingest import ingest


def _load_json(path: str) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-id", required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--isolation-evidence", required=True, help="path to isolation-evidence.json"
    )
    parser.add_argument("--build-receipt", required=True, help="path to build-receipt.json")
    parser.add_argument(
        "--axiom-execution-receipt", required=True, help="path to axiom-execution.json"
    )
    parser.add_argument("--trust-profile", required=True)
    parser.add_argument("--allowlist", required=True, help="comma-separated axiom allowlist")
    parser.add_argument("--allowlist-version", required=True)
    parser.add_argument(
        "--toolchain-pin", required=True, help="resolved sha256 digest of the build image"
    )
    parser.add_argument("--lockfile-hash", required=True)
    parser.add_argument(
        "--correspondence", required=True, help="path to a human-authored correspondence.json"
    )
    parser.add_argument("--asserted-at", required=True)
    parser.add_argument(
        "--source-root",
        required=True,
        help="read-only checkout to scan for kernel-bypass options",
    )
    parser.add_argument("--out", required=True)
    args = parser.parse_args(argv)

    result = ingest(
        evidence_id=args.evidence_id,
        repo=args.repo,
        commit=args.commit,
        isolation_evidence=_load_json(args.isolation_evidence),
        build_receipt=_load_json(args.build_receipt),
        axiom_execution_receipt=_load_json(args.axiom_execution_receipt),
        trust_profile=args.trust_profile,
        allowlist=[a.strip() for a in args.allowlist.split(",") if a.strip()],
        allowlist_version=args.allowlist_version,
        toolchain_pin=args.toolchain_pin,
        lockfile_hash=args.lockfile_hash,
        correspondence=_load_json(args.correspondence),
        asserted_at=args.asserted_at,
        source_root=Path(args.source_root),
    )

    Path(args.out).write_text(
        json.dumps(
            {
                "kind": result.kind,
                "evidence": result.evidence,
                "fail_closed_reasons": result.fail_closed_reasons,
                "rule_violations": result.rule_violations,
                "bypass_hits": [h.__dict__ for h in result.bypass_hits],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"decision: {result.kind}", file=sys.stderr)
    if result.fail_closed_reasons:
        print("fail-closed reasons:", file=sys.stderr)
        for r in result.fail_closed_reasons:
            print(f"  - {r}", file=sys.stderr)
    if result.rule_violations:
        print("rule violations:", file=sys.stderr)
        for r in result.rule_violations:
            print(f"  - {r}", file=sys.stderr)

    # Non-zero exit on a rule violation (e.g. kernel-bypass-option-detected)
    # is what actually "fails the audit" in CI terms -- it breaks the
    # trusted-ingest job step, distinct from the fail-closed kind decision,
    # which is not itself an error (recording as external_formal_artifact
    # is the correct, successful outcome for a submission that can't prove
    # isolation).
    return 1 if result.rule_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
