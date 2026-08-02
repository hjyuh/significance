# Lean evidence adapter (research preview)

Turns a build of an external Lean repository into `formal_artifact`
evidence on a Significance record — or, automatically, into
`external_formal_artifact` evidence (reported, not reproduced) whenever
isolation for that build could not be demonstrated. See `../../SECURITY.md`
for the threat model this design rests on; this file is usage and scope,
not security rationale.

## What's here

| File | Role |
|---|---|
| `Dockerfile`, `fetch.sh`, `build_and_audit.sh` | The untrusted sandbox: builds the pinned commit, runs the axiom audit, network-isolated and resource-limited. |
| `isolation.py` | The fail-closed decision: reads an isolation-evidence JSON, decides whether it was actually demonstrated. |
| `scan_kernel_bypass.py` | Scans `.lean` source for `debug.skipKernelTC` / `debug.skip*`. |
| `ingest.py`, `run_ingest.py` | Trusted-side orchestration: combines the fail-closed decision, the (re-run) kernel-bypass scan, and a human-authored correspondence claim into a Significance evidence fragment. |
| `assemble_isolation_evidence.py` | Runs at the end of the untrusted job to turn what was observed (timeouts, disk caps, filesystem errors in the build log) into `isolation-evidence.json`. |
| `fixtures/` | The four adversarial scenarios named in the design doc, plus a clean-success control. Exercised by `tests/test_lean_adapter.py`. |
| `pending-correspondence/` | Where a maintainer drops `<commit-sha>.json` — see below. |
| `../../.github/workflows/lean-adapter-*.yml` | The two privilege-separated workflows. |

## Using it

1. A maintainer author a correspondence claim for the specific commit
   they intend to submit — the attested statement that a given Lean
   declaration matches a specific informal claim — and saves it as
   `adapters/lean/pending-correspondence/<commit-sha>.json`:
   ```json
   {
     "value": "Theorem foo_bar in Foo/Bar.lean corresponds to Theorem 1.2 of the manuscript.",
     "basis": "author_attestation",
     "asserted_by": "editor-mz",
     "asserted_at": "2026-08-01T00:00:00Z"
   }
   ```
   This adapter never generates this claim itself. Correspondence between
   a formal statement and an informal one is attested, not machine-
   checked — see the standing "What this does not establish" panel every
   rendered record carries.
2. Trigger `lean-adapter-untrusted-build` (`workflow_dispatch`) with the
   repo URL, the exact 40-character commit SHA, the trust profile, and
   the fully-qualified declaration name the audit should run `#print
   axioms` against.
3. On completion, `lean-adapter-trusted-ingest` runs automatically,
   downloads the untrusted job's artifacts, re-clones the pinned commit
   itself (read-only) to re-run the kernel-bypass scan, and — if the
   correspondence file from step 1 exists — opens a pull request adding
   the resulting evidence fragment to `evidence-fragments/<commit>.json`.
   Nothing is committed automatically; a maintainer reviews the PR and
   merges the fragment into the target record's `evidence[]` array by
   hand.

## What "research preview" means here

This has been reviewed, unit-tested at the decision-logic layer, and run
end-to-end once on a GitHub-hosted runner against OpenAI's `ten-proofs`
commit `c510a55434c0935cde446e5a372699a4671438f6`. The maiden successful
run built `NonSoficGroup`, audited the exact named declaration, passed the
`lean_standard_classical` axiom profile, and produced the evidence proposal
in [PR #1](https://github.com/hjyuh/significance/pull/1). Concretely:

- `isolation.py`, `scan_kernel_bypass.py`, and `ingest.py` (the trusted-
  side decision logic) are exercised by `tests/test_lean_adapter.py`
  against synthetic isolation-evidence fixtures covering all four
  adversarial scenarios from the design doc, plus a clean-success
  control. Run `uv run pytest tests/test_lean_adapter.py -v`.
- The real run exercised Docker `--network none`, read-only root,
  CPU/memory/PID limits, the wall-clock/disk monitor, artifact transfer,
  trusted re-scan, and PR creation. It found no kernel-bypass hits or
  unauthorized writes and completed below both resource ceilings.

It remains a research preview: one cooperative repository is not an
adversarial test corpus. Before treating it as hardened, exercise malicious
fixtures on real runners and pin the sandbox base image by digest rather than
tag (third-party Actions are already pinned to full commit SHAs; see Known
limitations in `SECURITY.md`).
