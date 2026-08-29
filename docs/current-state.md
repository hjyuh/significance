# Significance — current development state

**As of 2026-08-22.** This is a handoff for maintainers and coding models. Read it
before changing the repository. It describes the current state, not a promise of
mathematical correctness or public deployment.

## What Significance is

Significance is an open YAML-to-HTML format and toolchain for making mathematical
claims, evidence, interpretations, reviewer scope, and open verification work
attributable and tied to exact source versions. It helps a mathematician decide
where to start, what has been checked, and what remains open.

The governing invariants are:

- no unattributed assertion;
- source versions and manuscript hashes are explicit;
- author, editor, community, domain-expert, and machine strata are labeled and
  never blended;
- lifecycle and freshness are separate;
- history is append-only;
- evidence is not a truth verdict;
- formal receipts report reproducible execution and declared axioms, not the
  correctness of an informal proof;
- no scores, rankings, verdict colours, or credibility badges;
- no accounts, backend database, or automatic publication of private drafts.

## Architecture and source of truth

- `records/*.yaml` is the public corpus and the only source of public record facts.
- `drafts/records/*.yaml` contains private, unapproved records. It is currently
  untracked locally; keep it out of deployable builds and verify the local ignore
  rules before any commit. Never copy it into a public build without author/editor
  approval.
- `src/significance/` contains the Python schema validator, semantic checks, CLI,
  static renderer, and evidence adapters.
- `src/significance/templates/` contains the HTML templates.
- `public/` is generated output, not a second source of truth.
- `app/` is the React/vinext presentation shell. It imports generated JSON and
  presents it; it does not parse YAML or restate record facts.
- `worker/` serves the shell and static Python output. It has no database or image
  transformation capability.
- `tests/` contains schema, renderer, CLI, security, and deliberately broken
  fixtures. `docs/` contains design, integration, moderation, and handoff notes.

Canonical repository and hosted site:

- repository: <https://github.com/hjyuh/significance>
- site: <https://hjyuh.github.io/significance/>

The hosted site is a static deployment. A generated URL is stable within the
published corpus, but it is not an archival or cryptographic permanence guarantee.

## What is already implemented

The current release includes:

- YAML schema and semantic validation, append-only diffing, and static rendering;
- record lifecycle/freshness handling and version-bound manuscript evidence;
- taken/done/withdrawn invitation state, with stale-task wording but no automatic
  untaking;
- reviewer census and per-reviewer pages, with named scope and strata kept visible;
- `/backlog/`, `/problems/`, `/how-to-file-a-claim/`, `/request/`, and `/submit/`;
- reader-first `review_map` sections: main deduction, delicate steps,
  prerequisites, and bounded needs-checking tasks;
- task pages with direct source-PDF links, readable short hashes, scope,
  prerequisites, effort estimates, and a conditional attestation-form link;
- the scoped-attestation incorporation path, including record-version bumping;
- reviewer display names and normalized public URLs (no doubled slash);
- verdict-lint for review notes and fixtures for malformed provenance, stale
  confirmations, missing hashes, invalid dependencies, and verdict language;
- a Lean evidence adapter that reports build/axiom evidence under a named trust
  profile. It does not prove the attached analytic argument;
- `exposition` and `palomar_entry` evidence for work published elsewhere, the
  per-record component-dates strip, build-derived exposition tasks with
  per-record suppression, and the board's derived digestion column. See
  README §"Exposition and registry evidence" and `schema/CHANGELOG.md`.

Neither new evidence kind is a review and neither is counted as one: the
review-activity block, the reviewer census, and the per-reviewer pages ignore
both. The Palomar caveat is rendered from `semantics.PALOMAR_CAVEAT` with every
registry entry and has no field in the schema, so a record cannot weaken it.

No exposition or Palomar row has been seeded. At build time
<https://www.erdosproblems.com/848> showed "Proof expositions (0)", so the #848
record carries no exposition row and shows the derived task instead; no claim
in this corpus has a Palomar entry. The seeding condition is publication, not
intent — check the venue page again before adding a row.

## Public corpus

The public `records/` directory currently contains four records: the Anthropic
zeta-density claim, OpenAI's non-sofic-groups claim, and Rafik Zeraoulia's Erdős
Problem #653 and #726 records. The two Zeraoulia records were author-reviewed for
wording and scope; they remain records of public claims with independent
verification still open. Their author-supplied risk maps are shown as such.

The first independent Lean receipt is attached to the public OpenAI non-sofic
record. It reports a clean build and axiom profile under its stated toolchain and
profile, while its correspondence note explicitly says that the formal artifact
does not by itself establish correspondence with the manuscript's concrete theorem.

## Private drafts awaiting author review

Two drafts are prepared but are not public:

### Erdős #848 — Alex Chengyu Li (`alexchengyuli`)

The draft records the exact all-`N` claim, the pinned repository PDF and hash, the
separate SSRN artifact, the author's AI-use disclosures without implying that AI
independently proved or verified the result, and three bounded tasks:

1. reproduce the Lean release/cache build at tag `v1.0.5-kernel`;
2. inspect the generated certificate declarations;
3. compare the exact paper statement with the pinned Lean declaration.

The reproduction task includes the author's cache-install procedure and says not
to run `lake update`. Formalization status is `artifact_reported`, not independently
reproduced. The draft remains private pending author review of the wording.

### Erdős #906 — Eric Hou (`erichou`)

The draft uses Eric Hou's canonical externally hosted manuscript PDF and separately
lists arXiv v4 as a companion artifact. It points to the correct repository and
commit, narrows the AI disclosure to the activities stated by the manuscript, and
has three bounded tasks:

1. inspect the small-ball/Jensen step;
2. check Lean-to-analytic correspondence;
3. examine the manuscript's Boas–Reddy comparison.

Formalization status is `artifact_reported`; the Lean report is author-supplied and
does not independently check the analytic proof. This draft also remains private.

Do not publish either draft, add it to a public index/feed, or contact an author
from code changes alone. Publication and outreach require explicit human approval.

## Verification and test status

After the exposition/registry release: `uv run pytest` passes (`167 passed`),
`uv run ruff check src tests adapters/lean` is clean, `npm run lint` is clean,
and `npm test` (records build, `vinext build`, 5 rendered-HTML tests, 26
submit-check tests) is green. `uv run significance validate records/` and the
drafts directory report no violations. Re-run the full suites before committing
or deploying.

On a Linux checkout whose `node_modules/` was installed on Windows, `npm test`
fails before it starts, in `vinext build` and in `tsx`, for missing
`@rolldown/binding-linux-x64-gnu` and `@esbuild/linux-x64`. That is the
platform-binary problem, not a test failure: install the platform packages
(`npm i --no-save` keeps `package-lock.json` untouched) or reinstall
`node_modules/` on the platform you are testing on.

Useful commands from the repository root (the project uses `uv`):

```text
uv run significance validate records/
uv run significance validate drafts/records/ --json
uv run pytest
npm test
```

If the local virtual environment has a Windows `lib64` access issue, use the
isolated dependency invocation documented in the terminal history or install the
project dependencies in a fresh environment; do not weaken validation.

## Current work queue

1. Inspect the working tree and review the generated/public diffs; do not assume
   generated HTML is source.
2. Re-run full Python and JavaScript tests.
3. Commit the reviewed implementation fixes and deploy only the approved public
   corpus to GitHub Pages.
4. Keep #848 and #906 in private preview until each author has approved the exact
   record wording and artifact identity.
5. After approval, invite bounded reviewers with direct PDF links and explicit
   scope; a reviewer should not need to compute a hash before reading.
6. Record independent attestations through the PR/incorporation flow. Label all
   machine receipts and author reports accurately; never upgrade them to proof
   verification.

Outreach is author-first and opt-in. Never send a forum message, direct message,
Zulip post, or email as part of a build task without showing the proposed text to
the user and receiving approval. The Eric Li harvest candidate is a separate person
from Alex Chengyu Li and Eric Hou; verify the source thread and handle before any
message.

## Instructions for the next model

Start by reading this file, `README.md`, `SECURITY.md`, and the relevant design
document. Inspect `git status` before editing. Keep private drafts out of public
builds and feeds. Treat every author/source statement as attributed evidence, not
as an independent finding. Prefer small, test-backed changes. After changes, run
validation and tests, report exactly what changed, and ask before publishing or
sending anything externally.
