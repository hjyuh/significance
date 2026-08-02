# Security

This file is the threat model for the Lean evidence adapter
(`adapters/lean/`, `.github/workflows/lean-adapter-*.yml`) — the one part
of Significance that executes code it does not control. Everything else
in this repository (the schema, CLI, static renderer, React presentation
shell, and minimal static-serving Worker) only processes validated record
data or serves generated assets. The Worker declares no database, object
storage, or image-transformation binding; there is no comparable arbitrary-code
execution boundary there.

To report a vulnerability, open a private security advisory on this
repository rather than a public issue.

## What the adapter does, in one sentence

A maintainer points the adapter at a specific commit of an external Lean
repository; it attempts to build that commit and audit its axioms inside
an isolated sandbox, and records the outcome as evidence on a
Significance record — as `formal_artifact` (reproduced) only if isolation
was demonstrably intact, and as `external_formal_artifact` (reported, not
reproduced) automatically otherwise.

## Trust boundary

Two separate GitHub Actions workflows, on purpose:

- **`lean-adapter-untrusted-build.yml`** runs the untrusted repository's
  code. `permissions: contents: read`, no other permissions, no secrets
  referenced anywhere in the workflow (GitHub does not inject secrets
  into a workflow that doesn't ask for them). It cannot push to this
  repository, comment on anything, or open a PR.
- **`lean-adapter-trusted-ingest.yml`** has `contents: write` and
  `pull-requests: write`, but it never checks out the untrusted repo's
  code and never executes anything from it. It reads the JSON artifacts
  the untrusted workflow produced, separately does its own read-only
  `git clone` of the pinned commit purely to re-run the kernel-bypass
  source scan itself (see below), and opens a pull request — it never
  pushes directly to a protected branch. A human still has to merge it.

The untrusted workflow is triggered by `workflow_dispatch` only, so
triggering a build already requires repository write access; this is a
v0.1 research preview, not a public build-on-demand service.

## What isolation actually rests on

The build-and-audit step runs as `docker run --network none --memory
--cpus --pids-limit --read-only`, with a single writable bind-mounted
output directory. Concretely:

| Property | Mechanism |
|---|---|
| No network during build | `--network none` (structural: the container has no network namespace to attempt egress through) |
| CPU / memory / process-count limits | `--memory`, `--cpus`, `--pids-limit` (cgroup-enforced) |
| No writes outside the output path | `--read-only` root filesystem; only `/workspace/build-out` is writable |
| Wall-clock limit | A host-side poll loop `docker kill`s the container after `WALL_CLOCK_LIMIT_SECONDS` |
| Disk-usage limit | The same poll loop `docker kill`s the container if the writable output directory exceeds a size cap |
| Kernel-bypass options (`debug.skipKernelTC` and any `debug.skip*`) | Source-scanned by `scan_kernel_bypass.py`, independently, on the trusted side |

Dependency acquisition (pulling the Lean/Mathlib toolchain, `lake
update`) happens in a *separate*, earlier container invocation that does
have network access, before the no-network build step runs — see
`fetch.sh`. That earlier step is not itself sandboxed against a
compromised dependency; see Known limitations.

## The fail-closed rule

`isolation.check_isolation()` is the only place this decision is made,
and it is a pure function of a JSON document (`isolation-evidence.json`)
the untrusted job writes describing what it observed about its own
sandboxing. If that document is missing, incomplete, or reports anything
other than a fully clean run — network denial not demonstrated, any
resource limit not enforced, a timeout, an unauthorized write attempt,
the wrong runner type, secrets in scope — the submission is recorded as
`external_formal_artifact` automatically. This is not an error path: it
is the expected, correct outcome for a submission whose isolation could
not be proven, and nothing in the pipeline treats it as a failure that
needs fixing before moving on. See `adapters/lean/fixtures/` for the four
adversarial scenarios named in the design doc, each with a test in
`tests/test_lean_adapter.py` proving it takes this path (or, for the
kernel-bypass case, the separate failing-result path below).

A kernel-bypass hit is handled differently on purpose: `debug.skipKernelTC`
(and any `debug.skip*` option) tells the Lean kernel's typechecker to
*skip*, which means axiom closure — the `#print axioms` mechanism the
audit relies on — structurally cannot see through it. Even a submission
with perfectly demonstrated isolation gets its build and axiom-check
results forced to `failed` if the source contains one, under the named
rule `kernel-bypass-option-detected`. This is deliberately re-checked on
the trusted side against a fresh clone, not trusted from the untrusted
job's own copy of the scan.

## Threats considered

- **Arbitrary code execution via the untrusted repo.** Lake build scripts
  are themselves Lean programs and can do arbitrary computation; this is
  assumed from the start, hence the sandbox rather than any attempt to
  statically vet build scripts.
- **Network exfiltration / C2 from the build.** Denied structurally by
  `--network none` during the build step. The earlier dependency-fetch
  step does have network — see Known limitations.
- **Resource-exhaustion DoS of the runner.** cgroup limits (CPU/memory/
  pids) plus a wall-clock kill and a disk-usage poll.
- **Writing into this repository's working tree.** `--read-only` root
  filesystem; the only writable mount is the build-output directory,
  which is never merged into `records/` automatically (see fail-closed
  rule and the PR-only ingest path).
- **Kernel-bypass options hiding a false proof.** Source-scanned,
  independently, trusted-side. See above.
- **A compromised or malicious base image / elan installer.** See Known
  limitations — this is the weakest link in v0.1.
- **Cross-repository confusion via `workflow_run`.** Guarded by an
  explicit `github.event.workflow_run.repository.full_name ==
  github.repository` check in the trusted workflow, on top of
  `workflow_run`'s existing same-repository scoping.
- **Shell injection via workflow inputs or step outputs.** Every value
  that reaches a `run:` step is passed through `env:` and read as a shell
  variable, never interpolated directly as `${{ ... }}` into script text.
  These values are already maintainer-supplied (triggering the untrusted
  workflow requires repository write access), so this is defense in
  depth against a copy-pasted value containing shell metacharacters,
  not a hole an external attacker could otherwise walk through.
- **Machine-asserted correspondence.** The adapter never generates the
  claim that a Lean statement matches an informal one — the trusted
  workflow refuses to proceed past the "Require a human-authored
  correspondence file" step without one, authored by a maintainer with
  `basis: author_attestation`.

## Known limitations (v0.1 research preview)

- **The sandbox base image is pinned by tag, not by content digest**
  (see the comment at the top of `adapters/lean/Dockerfile`). The
  workflow records the digest that actually resulted from each build
  into the receipt, so what ran is always auditable after the fact, but
  the base layer is not guaranteed reproducible byte-for-byte across
  rebuilds the way a hardcoded digest pin would be. Tightening this
  (e.g. a periodic pin-refresh job) is future work.
- **Third-party GitHub Actions are pinned to full commit SHAs.** The adjacent
  comments retain the reviewed major version for readability. Updating an
  Action requires reviewing and replacing the immutable SHA rather than moving
  a version tag implicitly.
- **The dependency-acquisition step (`fetch.sh`) has network access** and
  is not itself resource- or time-limited the way the build step is —
  it runs `git fetch` and `lake update`/`elan toolchain install` against
  whatever the untrusted repo's manifest points at. A malicious manifest
  could attempt a large or slow download here. This step never executes
  the untrusted repo's own code, though (no build commands run), which
  bounds the blast radius to resource consumption, not code execution.
- **This has not been run.** GitHub-hosted runners, Docker network
  isolation, and cgroup enforcement are not available in the environment
  these files were authored and tested in. `isolation.py`,
  `scan_kernel_bypass.py`, and `ingest.py` — the trusted-side decision
  logic — are unit-tested against synthetic isolation-evidence fixtures
  (`tests/test_lean_adapter.py`) covering all four adversarial scenarios
  named in the design doc. The workflow YAML and shell scripts have been
  syntax-checked (valid YAML, valid bash for every `run:` step) and
  manually reviewed, but not executed end-to-end. Treat this as a
  reviewed design, not a battle-tested one, until it has actually run on
  a real GitHub-hosted runner against a real adversarial repository.
- **The axiom audit's `#print axioms` output parsing is a plain regex**
  over Lean's pretty-printed output, not a structured API call. A future
  Lean/Lake version changing that output format would need this updated;
  it would fail closed to `axiom_result=failed` on a parse miss (no
  bracketed axiom list recognized), not silently pass.
