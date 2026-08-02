# Submission Wizard Implementation Plan

> **Implementation note (2026-08-02):** The shipped flow deliberately differs
> from early snippets below: downloading an explicitly labelled draft remains
> available at all times, while GitHub/email submission is gated on a selected
> role and zero schema, semantic, or attestation errors. The GitHub URL opens a
> pre-filled new-file editor, not a pull request directly.

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a browser `/submit` wizard that assembles a schema-valid Significance record and hands the submitter a pre-filled GitHub PR, plus the validator-side automation-identity check that makes the wizard's evidence-kind gating an honest promise rather than UI theater.

**Architecture:** Two independent tracks. Track A (Python) closes a real gap in `semantics.py` — machine-result receipts must be asserted by a declared `automation` party, not any party — and fixes every fixture that gap now correctly flags. Track B (TypeScript/React) adds a client-only wizard page to the existing vinext/Next app shell: no backend, no accounts. The wizard imports `schema/record.schema.json` directly (never a second copy) for structural checks via Ajv, hand-ports five specific intra-record semantic checks from `semantics.py` (documented as a deliberate, narrow, sync-tracked exception to "never duplicate the source of truth"), and turns the assembled record into a download, a length-capped GitHub PR-compose link, or an email-with-attachment-reminder.

**Tech Stack:** Python (`jsonschema`, `ruamel.yaml`, `pytest`) for Track A. TypeScript/React 19 in the existing vinext app, `js-yaml` for YAML generation, `ajv`/`ajv-formats` (Draft 2020-12 build) for structural validation, `node:test` + `tsx` for JS-side tests.

**Design doc:** `docs/plans/2026-08-02-submission-wizard-design.md` — read it first; this plan does not re-derive the reasoning, only the steps.

---

## Before you start

Run the full existing suite once to get a clean baseline:

```sh
uv run pytest -q
npm run lint
npm test
```

All three should pass with zero failures before Task 1. If they don't, stop and report — do not build on a red baseline.

---

# Track A — Python: automation-identity check

## Task 1: Add `automation` to the schema's verification-method enum

**Files:**
- Modify: `schema/record.schema.json:114` (the `verification_method.kind` enum inside `$defs.party`)

**Step 1: Make the change**

In `schema/record.schema.json`, find:

```json
            "kind": {
              "type": "string",
              "enum": ["github_identity", "orcid", "email_confirmation", "pseudonymous"]
            },
```

(this is inside `$defs.party.properties.verification_method.properties.kind`, distinct from the `axiom_trust_profile` enum elsewhere in the file — make sure you're editing the *party* verification kind, not the axiom trust profile). Change it to:

```json
            "kind": {
              "type": "string",
              "enum": ["github_identity", "orcid", "email_confirmation", "pseudonymous", "automation"]
            },
```

**Step 2: Verify the schema itself is still valid Draft 2020-12**

Run: `uv run pytest tests/test_schema.py::test_schema_itself_is_valid_draft_2020_12 -v`
Expected: PASS

**Step 3: Commit**

```sh
git add schema/record.schema.json
git commit -m "schema: add automation verification_method.kind"
```

Do not run the full suite yet — Task 5 does that deliberately, after the next few tasks, so the regression is visible and traceable to one cause.

---

## Task 2: Schema changelog entry

**Files:**
- Modify: `schema/CHANGELOG.md`

**Step 1: Add the entry**

Prepend a new section above the existing `## 1 — 2026-07-31 (Phase 2 addendum)` entry:

```markdown
## 1 — 2026-08-02

Added `automation` to `verification_method.kind`'s enum, so a party
representing CI/an evidence adapter can be declared distinctly from a
human party. Paired with a new `semantics.py` check requiring any
`execution_receipt`'s `asserted_by` to resolve to an `automation` party
(`docs/design.md` §5 already described this as "asserting automation
identity"; nothing enforced it until now).

This is additive for a *new* record written against the *new* schema.
It is **not** backward compatible in the other direction: a record using
`verification_method.kind: automation` will fail validation against any
older copy of this schema. Consumers pinning a schema copy should re-pull
before validating records that use this kind.

This check enforces internal consistency (a receipt's asserter is
declared as automation), not cryptographic authenticity — nothing stops
a party from self-declaring as `automation`. Binding a receipt to a real
CI run (OIDC/sigstore-style provenance) is a roadmap item, not
implemented here.
```

**Step 2: Commit**

```sh
git add schema/CHANGELOG.md
git commit -m "docs: changelog entry for automation verification kind"
```

---

## Task 3: New broken fixture + failing test (RED)

**Files:**
- Create: `tests/fixtures/broken/execution-receipt-asserted-by-human.yaml`
- Modify: `tests/test_validate.py`

**Step 1: Create the fixture**

Copy `tests/fixtures/broken/bare-result-passed-no-receipt.yaml` to the new path, then make exactly two changes to the copy:

1. Change `record_id` to `0000-example-execution-receipt-human` (keep every broken-fixture record_id unique, per `tests/fixtures/README.md` conventions and `check_uniqueness`).
2. Under `evidence[0].axiom_policy.execution`, change `asserted_by: significance-ci` to `asserted_by: author-as`. Leave everything else — including `evidence[0].artifact_build`'s own receipt and its `asserted_by: significance-ci` — untouched, so exactly one execution receipt in the file is misattributed and every other rule in the file stays satisfied.

The relevant block should read:

```yaml
    axiom_policy:
      trust_profile: lean_standard_classical
      allowlist: ["propext", "Classical.choice", "Quot.sound"]
      allowlist_version: "1"
      execution:
        tool: significance-lean
        tool_version: "0.1.0"
        runner_image_digest: "sha256:a67b1bd9119bb55b576dddf936701424ec527e2ec17bd671019a9481e2a8fe68"
        executed_at: "2026-07-20T03:15:00Z"
        result: passed
        log_sha256: "73aaa5071d9f861550d51469cbd89e0a6e5371486fd94c9675281d1cefbd5117"
        asserted_by: author-as
```

`author-as` is already declared in `parties` in the copied file with `verification_method.kind: orcid` — a real, declared, non-automation party, so this doesn't also trip `unknown-party`.

**Step 2: Add the test case**

In `tests/test_validate.py`, add a row to the `@pytest.mark.parametrize` list in `test_single_record_broken_fixture` (around line 28-39):

```python
        ("execution-receipt-asserted-by-human.yaml", "execution-receipt-not-automation"),
```

**Step 3: Run it — expect FAIL**

Run: `uv run pytest tests/test_validate.py -k execution_receipt_asserted_by_human -v`
Expected: FAIL — the parametrized case runs, but `_rules(violations)` is `set()` (empty), not `{"execution-receipt-not-automation"}`, because the check doesn't exist yet.

**Step 4: Commit the fixture and test (still red, on purpose)**

```sh
git add tests/fixtures/broken/execution-receipt-asserted-by-human.yaml tests/test_validate.py
git commit -m "test: add failing case for execution-receipt automation check"
```

---

## Task 4: Implement the check (GREEN for Task 3, regressions expected elsewhere)

**Files:**
- Modify: `src/significance/semantics.py`

**Step 1: Add the check function**

In `src/significance/semantics.py`, add after `check_freshness_recomputation` (which ends around line 107) and before `check_uniqueness`:

```python
_EXECUTION_RECEIPT_KEYS = {
    "tool", "tool_version", "runner_image_digest", "executed_at", "result", "log_sha256", "asserted_by",
}


def check_execution_receipt_asserted_by_automation(record: dict) -> list[Violation]:
    """`execution_receipt` is used in three places (evidence_formal_artifact.artifact_build,
    evidence_formal_artifact.axiom_policy.execution, evidence_computational_reproduction.execution)
    with no discriminator key, so this detects the shape rather than a `kind` field: any dict
    carrying every execution_receipt key is treated as one."""
    parties = record.get("parties") or {}
    violations = []
    for path, node in walk(record):
        if not isinstance(node, dict):
            continue
        if not _EXECUTION_RECEIPT_KEYS.issubset(node.keys()):
            continue
        party_id = node.get("asserted_by")
        party = parties.get(party_id)
        if not isinstance(party, dict):
            continue  # unknown-party is check_asserted_by_parties's job, not this check's
        kind = (party.get("verification_method") or {}).get("kind")
        if kind != "automation":
            violations.append(
                Violation(
                    "execution-receipt-not-automation",
                    f"execution_receipt asserted_by '{party_id}' has verification_method.kind "
                    f"{kind!r}, expected 'automation'",
                    format_path(path + ("asserted_by",)),
                )
            )
    return violations
```

**Step 2: Wire it into `semantic_violations`**

Change the `semantic_violations` function (end of the file) from:

```python
def semantic_violations(record: dict) -> list[Violation]:
    """Single-record semantic checks (no base, no sibling records needed)."""
    return [
        *check_asserted_by_parties(record),
        *check_source_quote_locators(record),
        *check_forbidden_language(record),
        *check_freshness_recomputation(record),
    ]
```

to:

```python
def semantic_violations(record: dict) -> list[Violation]:
    """Single-record semantic checks (no base, no sibling records needed)."""
    return [
        *check_asserted_by_parties(record),
        *check_source_quote_locators(record),
        *check_forbidden_language(record),
        *check_freshness_recomputation(record),
        *check_execution_receipt_asserted_by_automation(record),
    ]
```

**Step 3: Run the Task 3 test — expect PASS now**

Run: `uv run pytest tests/test_validate.py -k execution_receipt_asserted_by_human -v`
Expected: PASS

**Step 4: Run the full Python suite — expect multiple FAILs**

Run: `uv run pytest -q`

Expected: several failures in `test_validate.py` and `test_schema.py` — every fixture built from the shared template (which declares `significance-ci` with `verification_method.kind: github_identity` and then uses `significance-ci` as `asserted_by` on two real execution receipts) now also trips the new check. This is expected, not a bug in the check — Task 5 fixes it. Note the failing test names before moving on, so you can confirm the same set goes green in Task 5's Step 3.

**Step 5: Commit**

```sh
git add src/significance/semantics.py
git commit -m "feat: require execution_receipt asserted_by to be an automation party"
```

---

## Task 5: Fix every fixture the new check now (correctly) flags

**Context:** `significance-ci` is the shared name used across `examples/synthetic-ramsey-k7.yaml`, twelve of the thirteen files in `tests/fixtures/broken/` (all but `unattributed-assertion.yaml`'s missing... actually check — see file list below), the four `tests/fixtures/broken/append-only/*.yaml` variants, and `tests/fixtures/broken/duplicate-record-id/{a,b}.yaml`. All of them declare the party block:

```yaml
  significance-ci:
    name: "significance-ci"
    verification_method:
      kind: github_identity
```

and then use `significance-ci` as `asserted_by` on two real execution receipts (`artifact_build` and `axiom_policy.execution`) inside a `formal_artifact` evidence item. Every one of these files needs exactly one change: that party's `kind` becomes `automation`. Nothing else in any of these files should change — in particular, do **not** touch `editor-mz`'s `kind: github_identity` a few lines above it; that party is a human editor and is correctly `github_identity`.

**Files to fix (14 total):**
- `examples/synthetic-ramsey-k7.yaml`
- `tests/fixtures/broken/bare-result-passed-no-receipt.yaml`
- `tests/fixtures/broken/correspondence-machine-asserted.yaml`
- `tests/fixtures/broken/correspondence-no-basis.yaml`
- `tests/fixtures/broken/derived-value-not-matching-recomputation.yaml`
- `tests/fixtures/broken/missing-manuscript-hash.yaml`
- `tests/fixtures/broken/stale-confirmation-rendered-current.yaml`
- `tests/fixtures/broken/unattributed-assertion.yaml`
- `tests/fixtures/broken/duplicate-record-id/a.yaml`
- `tests/fixtures/broken/duplicate-record-id/b.yaml`
- `tests/fixtures/broken/append-only/base.yaml`
- `tests/fixtures/broken/append-only/deleted-event.yaml`
- `tests/fixtures/broken/append-only/mutated-event.yaml`
- `tests/fixtures/broken/append-only/non-monotonic-version.yaml`

**Step 1: Run the batch fix**

This is a one-time mechanical migration across fixture files that are otherwise near-identical copies of one template — a script is less error-prone than 14 manual edits, since the exact line numbers differ slightly per file but the 4-line block is byte-identical in every one. Run this from the repo root (POSIX shell; on Windows use Git Bash, which this project's tooling already assumes):

```sh
python3 - <<'PY'
from pathlib import Path

files = [
    "examples/synthetic-ramsey-k7.yaml",
    "tests/fixtures/broken/bare-result-passed-no-receipt.yaml",
    "tests/fixtures/broken/correspondence-machine-asserted.yaml",
    "tests/fixtures/broken/correspondence-no-basis.yaml",
    "tests/fixtures/broken/derived-value-not-matching-recomputation.yaml",
    "tests/fixtures/broken/missing-manuscript-hash.yaml",
    "tests/fixtures/broken/stale-confirmation-rendered-current.yaml",
    "tests/fixtures/broken/unattributed-assertion.yaml",
    "tests/fixtures/broken/duplicate-record-id/a.yaml",
    "tests/fixtures/broken/duplicate-record-id/b.yaml",
    "tests/fixtures/broken/append-only/base.yaml",
    "tests/fixtures/broken/append-only/deleted-event.yaml",
    "tests/fixtures/broken/append-only/mutated-event.yaml",
    "tests/fixtures/broken/append-only/non-monotonic-version.yaml",
]

needle = '  significance-ci:\n    name: "significance-ci"\n    verification_method:\n      kind: github_identity\n'
replacement = '  significance-ci:\n    name: "significance-ci"\n    verification_method:\n      kind: automation\n'

for rel in files:
    p = Path(rel)
    text = p.read_text(encoding="utf-8")
    count = text.count(needle)
    assert count == 1, f"{rel}: expected exactly 1 match, found {count}"
    p.write_text(text.replace(needle, replacement), encoding="utf-8")
    print(f"fixed {rel}")
PY
```

Expected output: 14 `fixed <path>` lines, no `AssertionError`. If any file raises the assertion, stop and look at it by hand — it means that file's block doesn't match the expected shape exactly (different indentation or content), and blindly forcing the replace would be wrong.

**Step 2: Diff-review before trusting it**

Run: `git diff --stat`
Expected: exactly 14 files changed, each with `1 insertion(+), 1 deletion(-)`. If any file shows more than a 1-line diff, stop and inspect it — the script should only ever touch the `kind:` line.

**Step 3: Run the full suite — expect all the Task 4 failures to now pass**

Run: `uv run pytest -q`
Expected: PASS, same pass count as the pre-Task-1 baseline plus the one new test from Task 3.

**Step 4: Also run the JS-side rendered-output test**, since it rebuilds from `records/` and `examples/` and asserts on rendered HTML content — the `examples/` change shouldn't affect it (production build never renders `examples/`), but confirm:

Run: `npm test`
Expected: PASS

**Step 5: Commit**

```sh
git add examples/synthetic-ramsey-k7.yaml tests/fixtures
git commit -m "fix: declare significance-ci as an automation party across fixtures"
```

---

## Task 6: `significance init` offers `automation` as a verification kind

**Files:**
- Modify: `src/significance/init.py:106-109`
- Modify: `tests/test_init.py`

**Step 1: Write a test that the new choice is accepted**

In `tests/test_init.py`, add a new test after `test_scaffold_record_produces_schema_valid_record`:

```python
def test_scaffold_accepts_automation_verification_kind():
    answers = list(_ANSWERS)
    # index 4 is the first party's verification method in _ANSWERS
    answers[4] = "automation"
    record = scaffold_record(_canned_prompt(answers))
    assert record["parties"]["author-x"]["verification_method"]["kind"] == "automation"
```

**Step 2: Run it — expect FAIL**

Run: `uv run pytest tests/test_init.py -k automation -v`
Expected: FAIL — `_ask_choice` loops forever asking for a valid choice since `"automation"` isn't in the current list, which in a canned-prompt test manifests as `StopIteration` once the answer iterator runs dry.

**Step 3: Add the choice**

In `src/significance/init.py`, change:

```python
        vm_kind = _ask_choice(
            prompt_fn, "  verification method",
            ["github_identity", "orcid", "email_confirmation", "pseudonymous"],
        )
```

to:

```python
        vm_kind = _ask_choice(
            prompt_fn, "  verification method",
            ["github_identity", "orcid", "email_confirmation", "pseudonymous", "automation"],
        )
```

**Step 4: Run it — expect PASS**

Run: `uv run pytest tests/test_init.py -v`
Expected: PASS (all tests in the file, including the pre-existing one)

**Step 5: Commit**

```sh
git add src/significance/init.py tests/test_init.py
git commit -m "feat: significance init offers automation as a verification kind"
```

---

## Task 7: Design-doc and security-doc notes

**Files:**
- Modify: `docs/design.md` (§5, "Evidence facets")
- Modify: `SECURITY.md`

**Step 1: Add the automation-check caveat and the promotion-path guidance to `docs/design.md`**

In `docs/design.md`, immediately after the paragraph ending "Machine receipts bind the tool and version, runner image digest, execution time, result, log hash, and asserting automation identity. A manually authored `result: passed` is rejected." (§5, "Evidence facets"), insert:

```markdown
An execution receipt's `asserted_by` must resolve to a party whose
`verification_method.kind` is `automation` — enforced by
`significance validate`. This is a consistency check, not an authenticity
one: nothing stops a party from self-declaring as `automation`. Binding a
receipt to a real, specific CI run (OIDC/sigstore-style provenance) is a
roadmap item, not implemented in v0.1.

**Evidence promotion.** When an `external_formal_artifact` is later backed
by a real build (e.g. via the Lean adapter), add a new `formal_artifact`
evidence item under a new id and record a `history` event noting the
supersession — never mutate the existing item's `kind` in place. Evidence
items are not schema-enforced append-only the way `history[]` is, so
nothing stops an in-place edit, but doing so leaves the record looking
cleanly CI-attested from the start, with the self-reported origin visible
only by reading history. Keeping both items preserves that trail on the
record itself.
```

**Step 2: Add a short limitation note to `SECURITY.md`**

Read `SECURITY.md` first to find its "known limitations" or equivalent section, then add (matching whatever heading style the file already uses):

```markdown
### Execution-receipt automation identity is a consistency check, not authenticity

`significance validate` requires any `execution_receipt`'s `asserted_by`
to resolve to a party declared with `verification_method.kind:
automation`. This catches accidental or confused authorship — a human
party can't be the asserter of a machine result — but it is not a
cryptographic guarantee: nothing stops a submitter from declaring
themselves an `automation` party and hand-typing a receipt with
plausible-shaped but fabricated `runner_image_digest`/`log_sha256`
values. Real authenticity would require binding a receipt to a specific
CI workflow run (OIDC/sigstore-style provenance, SLSA-shaped) — not
implemented. PR review is the actual backstop for now.
```

**Step 3: Commit**

```sh
git add docs/design.md SECURITY.md
git commit -m "docs: document the automation-identity check's actual guarantee"
```

---

# Track B — Docs: CONTRIBUTING.md and PR template

## Task 8: `CONTRIBUTING.md`

**Files:**
- Create: `CONTRIBUTING.md`

**Step 1: Write the file**

```markdown
# Contributing a record

Significance records live at `records/<record_id>.yaml` and are proposed
as ordinary GitHub pull requests — there is no separate submission
system, account, or database. The easiest way to build one is the
[submission wizard](/submit): it walks the schema, validates structurally
as you type, and hands you a pre-filled "open as pull request" link so
your GitHub burden is clicking "Propose new file."

You can also write the YAML by hand against `schema/record.schema.json`
(see `significance init` for a guided CLI scaffold) and open the PR
yourself. Whichever path you take, the same review checklist applies.

## Are you an author, or recording someone else's work?

This distinction matters and the wizard asks it up front (see the
[design doc](docs/plans/2026-08-02-submission-wizard-design.md) if you
want the reasoning):

- **You're an author.** You can use `basis: author_attestation` freely
  for what you're personally attesting to. Your PR's GitHub identity
  should match a party in the record — that's how attribution arrives,
  from the PR itself, not from anything the file claims.
- **You're recording someone else's public work** — this is the tool's
  core use case, no permission needed. Use `source_quote` (with a
  locator) or `editorial_inference` for claim/scope. The one thing that
  needs a receipt: if you assert `author_attestation` anywhere — i.e.
  "the author told me X" — attach a `locator` pointing at where/how they
  told you (a correspondence link, a public statement). The wizard
  enforces this structurally; if you're writing YAML by hand, reviewers
  will ask for it.

## Evidence: what you can self-attest, and what you can't

`external_formal_artifact`, `informal_review`, and `mathematical_assessment`
are things a person can honestly assert by hand. `formal_artifact` and
`computational_reproduction` require a machine-generated
`execution_receipt` — produced by CI or the
[Lean adapter](adapters/lean/README.md), never typed by hand. The
validator enforces this (an execution receipt's `asserted_by` must be a
declared `automation` party); the wizard won't even let you fill in
those two kinds' fields.

## Admissibility checklist (`mathematical_assessment` items specifically)

Anyone may propose a `mathematical_assessment` on any record. Before it's
merged, it must (see `docs/moderation.md` for the full rationale):

- [ ] Target a precise numbered statement (e.g. "Theorem 1.2"), not the
      manuscript as a whole.
- [ ] Contain a substantive mathematical argument another mathematician
      could follow and check — not a rating, not a one-line opinion.
- [ ] Disclose any conflict of interest or competing claim up front.
- [ ] Address the mathematics only — no claims about an author's
      conduct, competence, or motives.
- [ ] Leave room for an author response (`author_response[]`), which is
      never removable once attached.

A rejected proposal is simply not merged. There is no public log of
rejections — see `docs/moderation.md`.

## Review

`significance validate` (schema + semantic rules) runs in CI on every
PR. A maintainer applies the checklist above through ordinary PR review —
there's no separate review body for v0.1.
```

**Step 2: Commit**

```sh
git add CONTRIBUTING.md
git commit -m "docs: add CONTRIBUTING.md"
```

(This references `/submit`, built in Track C below, and `docs/plans/2026-08-02-submission-wizard-design.md`, already committed — both paths will resolve once Track C lands.)

---

## Task 9: PR template

**Files:**
- Create: `.github/PULL_REQUEST_TEMPLATE.md`

**Step 1: Write the file**

```markdown
## What kind of change is this?

- [ ] New record
- [ ] New evidence item on an existing record (version bump)
- [ ] Correction to an existing record (version bump)
- [ ] Non-record change (docs, tooling, schema, CI)

## For a new record or new evidence item

- [ ] I am an author of this claim, **or** I'm recording someone else's
      public work and every `author_attestation` I used has a `locator`
      backing it (see `CONTRIBUTING.md`).
- [ ] `mathematical_assessment` items (if any) satisfy the admissibility
      checklist in `CONTRIBUTING.md` / `docs/moderation.md`.
- [ ] `formal_artifact` / `computational_reproduction` evidence (if any)
      came from CI or the Lean adapter — not hand-typed.
- [ ] `significance validate records/` passes locally.

## For a correction

- [ ] `record_version` increases.
- [ ] Nothing in `history[]` was deleted or mutated — corrections add new
      events.
```

**Step 2: Commit**

```sh
git add .github/PULL_REQUEST_TEMPLATE.md
git commit -m "docs: add PR template with admissibility checklist"
```

---

# Track C — TypeScript: the wizard

## Task 10: Add wizard dependencies

**Files:**
- Modify: `package.json`

**Step 1: Install**

```sh
npm install js-yaml ajv ajv-formats
npm install -D @types/js-yaml
```

**Step 2: Confirm versions landed as direct dependencies**

Run: `node -e "const p=require('./package.json'); console.log(p.dependencies['js-yaml'], p.dependencies['ajv'], p.dependencies['ajv-formats'], p.devDependencies['@types/js-yaml'])"`
Expected: four version strings printed, none `undefined`.

**Step 3: Update the `test` script to also run the new JS test file (added in Task 11)**

Change `package.json`'s `scripts.test` from:

```json
    "test": "npm run build && node --test tests/rendered-html.test.mjs",
```

to:

```json
    "test": "npm run build && node --test tests/rendered-html.test.mjs && node --import tsx --test tests/submit-checks.test.ts",
```

**Step 4: Commit**

```sh
git add package.json package-lock.json
git commit -m "build: add js-yaml/ajv for the submission wizard"
```

---

## Task 11: `intra-record-checks.ts` — the five ported semantic checks (TDD)

**Files:**
- Create: `app/submit/intra-record-checks.ts`
- Create: `tests/submit-checks.test.ts`

This ports exactly five checks from `src/significance/semantics.py` — no more. See the design doc §4 for which ones and why. **If `semantics.py` changes one of these five in the future, this file must be updated to match** — that's why both files carry a comment pointing at the other.

**Step 1: Write the failing tests first**

Create `tests/submit-checks.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import {
  checkAssertedByParties,
  checkSourceQuoteLocators,
  checkForbiddenLanguage,
  checkFreshnessRecomputation,
  checkExecutionReceiptAssertedByAutomation,
  runIntraRecordChecks,
} from "../app/submit/intra-record-checks.ts";

function baseRecord(overrides: Record<string, unknown> = {}) {
  return {
    parties: {
      "author-x": { name: "X", verification_method: { kind: "orcid" } },
      "ci-bot": { name: "ci-bot", verification_method: { kind: "automation" } },
    },
    claim: {
      text: { value: "A claim.", basis: "source_quote", asserted_by: "author-x", asserted_at: "2026-01-01T00:00:00Z", locator: { section: "1" } },
    },
    ...overrides,
  };
}

test("checkAssertedByParties flags an undeclared party", () => {
  const record = baseRecord({
    claim: { text: { value: "x", basis: "editorial_inference", asserted_by: "ghost", asserted_at: "2026-01-01T00:00:00Z" } },
  });
  const violations = checkAssertedByParties(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "unknown-party");
});

test("checkAssertedByParties passes when the party is declared", () => {
  const violations = checkAssertedByParties(baseRecord());
  assert.deepEqual(violations, []);
});

test("checkSourceQuoteLocators flags a source_quote with no locator", () => {
  const record = baseRecord({
    claim: { text: { value: "x", basis: "source_quote", asserted_by: "author-x", asserted_at: "2026-01-01T00:00:00Z" } },
  });
  const violations = checkSourceQuoteLocators(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "source-quote-missing-locator");
});

test("checkForbiddenLanguage flags 'verified' and 'proven' in prose fields", () => {
  const record = baseRecord({
    claim: { text: { value: "This is verified.", basis: "editorial_inference", asserted_by: "author-x", asserted_at: "2026-01-01T00:00:00Z" } },
  });
  const violations = checkForbiddenLanguage(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "forbidden-language");
});

test("checkFreshnessRecomputation flags observed != confirmed rendered as current", () => {
  const record = baseRecord({
    freshness: { result: "current", observed_source_version: "v2", confirmed_source_version: "v1", checked_at: "2026-01-01T00:00:00Z" },
  });
  const violations = checkFreshnessRecomputation(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "stale-rendered-current");
});

test("checkFreshnessRecomputation passes when result is unknown", () => {
  const record = baseRecord({ freshness: { result: "unknown", checked_at: "2026-01-01T00:00:00Z" } });
  assert.deepEqual(checkFreshnessRecomputation(record), []);
});

test("checkExecutionReceiptAssertedByAutomation flags a human asserter", () => {
  const record = baseRecord({
    evidence: [
      {
        id: "ev-1",
        kind: "computational_reproduction",
        description: "x",
        execution: {
          tool: "t", tool_version: "1", runner_image_digest: "sha256:" + "a".repeat(64),
          executed_at: "2026-01-01T00:00:00Z", result: "passed",
          log_sha256: "a".repeat(64), asserted_by: "author-x",
        },
      },
    ],
  });
  const violations = checkExecutionReceiptAssertedByAutomation(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "execution-receipt-not-automation");
});

test("checkExecutionReceiptAssertedByAutomation passes when asserted by an automation party", () => {
  const record = baseRecord({
    evidence: [
      {
        id: "ev-1",
        kind: "computational_reproduction",
        description: "x",
        execution: {
          tool: "t", tool_version: "1", runner_image_digest: "sha256:" + "a".repeat(64),
          executed_at: "2026-01-01T00:00:00Z", result: "passed",
          log_sha256: "a".repeat(64), asserted_by: "ci-bot",
        },
      },
    ],
  });
  assert.deepEqual(checkExecutionReceiptAssertedByAutomation(record), []);
});

test("runIntraRecordChecks aggregates all five checks", () => {
  const violations = runIntraRecordChecks(baseRecord());
  assert.deepEqual(violations, []);
});
```

**Step 2: Run it — expect FAIL (module doesn't exist yet)**

Run: `node --import tsx --test tests/submit-checks.test.ts`
Expected: FAIL — cannot find module `../app/submit/intra-record-checks.ts`

**Step 3: Implement**

Create `app/submit/intra-record-checks.ts`:

```ts
// Hand-ported subset of src/significance/semantics.py's checks, for
// client-side use before a PR exists to run the real validator against.
// Only checks that are (a) purely intra-record and (b) need no hashing,
// git, or network access are ported here. See
// docs/plans/2026-08-02-submission-wizard-design.md §4 for the full list
// and the checks deliberately NOT ported (uniqueness, append-only).
//
// If semantics.py's check_asserted_by_parties, check_source_quote_locators,
// check_forbidden_language, check_freshness_recomputation, or
// check_execution_receipt_asserted_by_automation change, update this file
// to match — there is no shared source between the two languages.

export interface Violation {
  rule: string;
  message: string;
  location: string;
}

type JsonNode = unknown;

function* walk(node: JsonNode, path: (string | number)[] = []): Generator<[(string | number)[], JsonNode]> {
  yield [path, node];
  if (Array.isArray(node)) {
    for (let i = 0; i < node.length; i++) yield* walk(node[i], [...path, i]);
  } else if (node && typeof node === "object") {
    for (const [k, v] of Object.entries(node as Record<string, unknown>)) yield* walk(v, [...path, k]);
  }
}

function formatPath(path: (string | number)[]): string {
  if (path.length === 0) return "$";
  const parts: string[] = [];
  for (const p of path) {
    if (typeof p === "number") {
      parts.length ? (parts[parts.length - 1] += `[${p}]`) : parts.push(`[${p}]`);
    } else {
      parts.push(p);
    }
  }
  return parts.join(".");
}

function isDict(node: JsonNode): node is Record<string, unknown> {
  return !!node && typeof node === "object" && !Array.isArray(node);
}

export function checkAssertedByParties(record: Record<string, unknown>): Violation[] {
  const parties = isDict(record.parties) ? record.parties : {};
  const violations: Violation[] = [];
  for (const [path, node] of walk(record)) {
    if (!isDict(node)) continue;
    const partyId = node.asserted_by;
    if (typeof partyId === "string" && !(partyId in parties)) {
      violations.push({
        rule: "unknown-party",
        message: `asserted_by references undeclared party '${partyId}'`,
        location: formatPath([...path, "asserted_by"]),
      });
    }
  }
  return violations;
}

export function checkSourceQuoteLocators(record: Record<string, unknown>): Violation[] {
  const violations: Violation[] = [];
  for (const [path, node] of walk(record)) {
    if (!isDict(node)) continue;
    if (node.basis !== "source_quote") continue;
    if (node.locator || (node as Record<string, unknown>).source) continue;
    violations.push({
      rule: "source-quote-missing-locator",
      message: "basis is source_quote but no locator (or source) is given",
      location: formatPath(path),
    });
  }
  return violations;
}

const PROSE_KEYS = new Set(["text", "value", "inline", "quote", "description", "note"]);
const FORBIDDEN_WORDS = ["verified", "proven"];

export function checkForbiddenLanguage(record: Record<string, unknown>): Violation[] {
  const violations: Violation[] = [];
  for (const [path, node] of walk(record)) {
    if (!isDict(node)) continue;
    for (const [key, value] of Object.entries(node)) {
      if (!PROSE_KEYS.has(key) || typeof value !== "string") continue;
      const lowered = value.toLowerCase();
      for (const word of FORBIDDEN_WORDS) {
        if (lowered.includes(word)) {
          violations.push({
            rule: "forbidden-language",
            message: `rendered prose contains forbidden word '${word}'`,
            location: formatPath([...path, key]),
          });
        }
      }
    }
  }
  return violations;
}

export function checkFreshnessRecomputation(record: Record<string, unknown>): Violation[] {
  const freshness = record.freshness;
  if (!isDict(freshness)) return [];
  const result = freshness.result;
  const observed = freshness.observed_source_version;
  const confirmed = freshness.confirmed_source_version;
  if (result === "unknown" || observed == null || confirmed == null) return [];

  const recomputed = observed === confirmed ? "current" : "stale";
  if (result === recomputed) return [];
  if (result === "current" && recomputed === "stale") {
    return [{
      rule: "stale-rendered-current",
      message: `observed_source_version (${JSON.stringify(observed)}) != confirmed_source_version ` +
        `(${JSON.stringify(confirmed)}) recomputes to 'stale', but freshness.result is 'current'`,
      location: "freshness.result",
    }];
  }
  return [{
    rule: "derived-value-mismatch",
    message: `freshness.result is ${JSON.stringify(result)} but recomputing from observed/confirmed ` +
      `source versions gives ${JSON.stringify(recomputed)}`,
    location: "freshness.result",
  }];
}

const EXECUTION_RECEIPT_KEYS = [
  "tool", "tool_version", "runner_image_digest", "executed_at", "result", "log_sha256", "asserted_by",
];

export function checkExecutionReceiptAssertedByAutomation(record: Record<string, unknown>): Violation[] {
  const parties = isDict(record.parties) ? record.parties : {};
  const violations: Violation[] = [];
  for (const [path, node] of walk(record)) {
    if (!isDict(node)) continue;
    if (!EXECUTION_RECEIPT_KEYS.every((k) => k in node)) continue;
    const partyId = node.asserted_by;
    const party = typeof partyId === "string" ? parties[partyId] : undefined;
    if (!isDict(party)) continue; // unknown-party is checkAssertedByParties's job
    const vm = isDict(party.verification_method) ? party.verification_method : {};
    if (vm.kind !== "automation") {
      violations.push({
        rule: "execution-receipt-not-automation",
        message: `execution_receipt asserted_by '${String(partyId)}' has verification_method.kind ` +
          `${JSON.stringify(vm.kind ?? null)}, expected 'automation'`,
        location: formatPath([...path, "asserted_by"]),
      });
    }
  }
  return violations;
}

export function runIntraRecordChecks(record: Record<string, unknown>): Violation[] {
  return [
    ...checkAssertedByParties(record),
    ...checkSourceQuoteLocators(record),
    ...checkForbiddenLanguage(record),
    ...checkFreshnessRecomputation(record),
    ...checkExecutionReceiptAssertedByAutomation(record),
  ];
}
```

**Step 4: Run the tests — expect PASS**

Run: `node --import tsx --test tests/submit-checks.test.ts`
Expected: PASS, 9 tests

**Step 5: Commit**

```sh
git add app/submit/intra-record-checks.ts tests/submit-checks.test.ts
git commit -m "feat: port intra-record semantic checks for wizard-side validation"
```

---

## Task 12: `schema-validate.ts` — Ajv wired to the real schema

**Files:**
- Create: `app/submit/schema-validate.ts`

**Step 1: Implement**

```ts
import Ajv2020 from "ajv/dist/2020";
import addFormats from "ajv-formats";
import schema from "../../schema/record.schema.json";

// Imports the actual schema file — never a second copy, never drifts
// from the CLI's. Ajv2020 (not the default Ajv export, which is
// draft-07) because the schema declares
// "$schema": "https://json-schema.org/draft/2020-12/schema".
const ajv = new Ajv2020({ allErrors: true, strict: false });
addFormats(ajv);
const validateSchema = ajv.compile(schema);

export interface SchemaError {
  path: string;
  message: string;
}

export function validateAgainstSchema(record: unknown): SchemaError[] {
  const valid = validateSchema(record);
  if (valid) return [];
  return (validateSchema.errors ?? []).map((e) => ({
    path: e.instancePath || "$",
    message: e.message ?? "invalid",
  }));
}
```

**Step 2: Smoke-check it compiles and runs**

There's no dedicated test file for this thin wrapper — Task 19's wizard end-to-end exercises it, and Ajv's own test suite covers Ajv itself. Confirm it at least type-checks and runs:

Run: `node --import tsx -e "import('./app/submit/schema-validate.ts').then(m => console.log(m.validateAgainstSchema({}).length > 0))"`
Expected: prints `true` (an empty object fails the schema's top-level `required` list)

**Step 3: Commit**

```sh
git add app/submit/schema-validate.ts
git commit -m "feat: wizard structural validation against the real record schema"
```

---

## Task 13: `build-yaml.ts`, `types.ts`, `github-link.ts`

**Files:**
- Create: `app/submit/types.ts`
- Create: `app/submit/build-yaml.ts`
- Create: `app/submit/github-link.ts`
- Modify: `tests/submit-checks.test.ts` (add coverage for `github-link.ts`; `build-yaml.ts`/`types.ts` are exercised indirectly by Task 19's manual QA since they're pure data assembly with no branching logic worth a dedicated unit test)

**Step 1: `types.ts` — the wizard's internal form state and the record shape it builds**

```ts
export type SubmitterRole = "author" | "third_party";
export type Basis = "source_quote" | "author_attestation" | "editorial_inference";
// machine_result is deliberately excluded: the wizard never lets a
// submitter hand-author a machine_result value anywhere.
export type VerificationKind = "github_identity" | "orcid" | "email_confirmation" | "pseudonymous";
// automation is deliberately excluded from the wizard's own party-kind
// choices: an automation party is only ever meaningful for the
// execution-receipt-bearing evidence kinds the wizard doesn't support.

export interface LocatorDraft {
  section?: string;
  url?: string;
  quote?: string;
}

export interface AttributedDraft {
  value: string;
  basis: Basis;
  assertedBy: string;
  locator?: LocatorDraft;
}

export interface PartyDraft {
  id: string;
  isPseudonym: boolean;
  displayName: string;
  verificationKind: VerificationKind;
  verificationIdentifier: string;
}

export interface EvidenceDraftBase {
  id: string;
  basis: Basis;
  assertedBy: string;
  locator?: LocatorDraft;
}

export interface ExternalFormalArtifactDraft extends EvidenceDraftBase {
  kind: "external_formal_artifact";
  repo: string;
  commit: string;
  description: string;
}

export interface InformalReviewDraft extends EvidenceDraftBase {
  kind: "informal_review";
  reviewer: string;
  text: string;
}

export interface MathematicalAssessmentDraft extends EvidenceDraftBase {
  kind: "mathematical_assessment";
  target: string;
  reportUrl: string;
  reportInline: string;
}

export type EvidenceDraft = ExternalFormalArtifactDraft | InformalReviewDraft | MathematicalAssessmentDraft;

export interface AiRoleDraft {
  role: string;
  model: string;
  basis: Basis;
  assertedBy: string;
}

export interface WizardState {
  submitterRole: SubmitterRole | null;
  submitterPartyId: string;
  recordId: string;
  parties: PartyDraft[];
  claimText: AttributedDraft;
  claimScope: AttributedDraft;
  manuscriptUrl: string;
  manuscriptLabel: string;
  manuscriptImmutableVersionId: string;
  manuscriptSha256: string;
  evidence: EvidenceDraft[];
  aiDisclosure: AttributedDraft;
  aiRoles: AiRoleDraft[];
}

export const AI_PROVENANCE_ROLES = [
  "problem_selection", "literature_search", "conjecture_generation",
  "proof_generation", "criticism", "computation", "formalization",
  "prose_editing", "candidate_generation",
] as const;

export const EMPTY_ATTRIBUTED: AttributedDraft = { value: "", basis: "editorial_inference", assertedBy: "" };

export function emptyWizardState(): WizardState {
  return {
    submitterRole: null,
    submitterPartyId: "",
    recordId: "",
    parties: [],
    claimText: { ...EMPTY_ATTRIBUTED },
    claimScope: { ...EMPTY_ATTRIBUTED },
    manuscriptUrl: "",
    manuscriptLabel: "",
    manuscriptImmutableVersionId: "",
    manuscriptSha256: "",
    evidence: [],
    aiDisclosure: { ...EMPTY_ATTRIBUTED },
    aiRoles: [],
  };
}
```

**Step 2: `build-yaml.ts` — assemble the record object and stringify it**

```ts
import yaml from "js-yaml";
import type { AttributedDraft, EvidenceDraft, WizardState } from "./types";

function nowIso(): string {
  return new Date().toISOString();
}

function attributedValue(draft: AttributedDraft, nowText: string) {
  const out: Record<string, unknown> = {
    value: draft.value,
    basis: draft.basis,
    asserted_by: draft.assertedBy,
    asserted_at: nowText,
  };
  if (draft.locator && (draft.locator.section || draft.locator.url || draft.locator.quote)) {
    out.locator = { ...draft.locator };
  }
  return out;
}

function evidenceItem(draft: EvidenceDraft, nowText: string): Record<string, unknown> {
  const base = { id: draft.id, kind: draft.kind, basis: draft.basis, asserted_by: draft.assertedBy, asserted_at: nowText };
  const locator = draft.locator && (draft.locator.section || draft.locator.url || draft.locator.quote)
    ? { locator: { ...draft.locator } }
    : {};
  switch (draft.kind) {
    case "external_formal_artifact":
      return { ...base, repo: draft.repo, ...(draft.commit ? { commit: draft.commit } : {}), description: draft.description, ...locator };
    case "informal_review":
      return { ...base, reviewer: draft.reviewer, text: draft.text, ...locator };
    case "mathematical_assessment": {
      const report: Record<string, string> = {};
      if (draft.reportUrl) report.url = draft.reportUrl;
      if (draft.reportInline) report.inline = draft.reportInline;
      return { ...base, target: draft.target, report, ...locator };
    }
  }
}

export function buildRecord(state: WizardState): Record<string, unknown> {
  const nowText = nowIso();
  const parties: Record<string, unknown> = {};
  for (const p of state.parties) {
    const vm: Record<string, unknown> = { kind: p.verificationKind };
    if (p.verificationIdentifier) vm.identifier = p.verificationIdentifier;
    parties[p.id] = { [p.isPseudonym ? "pseudonym" : "name"]: p.displayName, verification_method: vm };
  }

  return {
    schema_version: 1,
    record_id: state.recordId,
    record_version: 1,
    record_state: "active",
    freshness: { result: "unknown", checked_at: nowText },
    parties,
    claim: {
      id: "claim-main",
      text: attributedValue(state.claimText, nowText),
      scope: attributedValue(state.claimScope, nowText),
    },
    manuscript: {
      url: state.manuscriptUrl,
      label: state.manuscriptLabel,
      ...(state.manuscriptImmutableVersionId ? { immutable_version_id: state.manuscriptImmutableVersionId } : {}),
      sha256: state.manuscriptSha256,
      retrieved_at: nowText,
    },
    evidence: state.evidence.map((e) => evidenceItem(e, nowText)),
    ai_provenance: {
      disclosure: attributedValue(state.aiDisclosure, nowText),
      roles: state.aiRoles.map((r) => ({ role: r.role, model: r.model, basis: r.basis, asserted_by: r.assertedBy })),
    },
    history: [
      { id: "evt-created", type: "created", at: nowText, by: state.submitterPartyId || Object.keys(parties)[0] || "unknown" },
    ],
  };
}

export function recordToYaml(record: Record<string, unknown>): string {
  return yaml.dump(record, { noRefs: true, lineWidth: -1 });
}
```

**Step 3: `github-link.ts` — PR-compose link with a length ceiling, plus mailto/download helpers**

```ts
const REPO_URL = "https://github.com/hjyuh/significance";
// GitHub's /new/ compose endpoint has no documented hard limit, but very
// long query strings silently fail or get truncated by browsers/proxies
// well before typical URL-length ceilings (~8k chars). 6000 leaves margin.
const PR_COMPOSE_LENGTH_CEILING = 6000;

export interface PrComposeResult {
  url: string | null;
  tooLong: boolean;
}

export function buildPrComposeUrl(recordId: string, yamlText: string): PrComposeResult {
  // record_id is regex-constrained to [0-9a-z-], so the filename segment
  // never needs percent-encoding; only the YAML content does.
  const filename = `records/${recordId}.yaml`;
  const url = `${REPO_URL}/new/main?filename=${filename}&value=${encodeURIComponent(yamlText)}`;
  if (url.length > PR_COMPOSE_LENGTH_CEILING) {
    return { url: null, tooLong: true };
  }
  return { url, tooLong: false };
}

export function triggerYamlDownload(recordId: string, yamlText: string): void {
  const blob = new Blob([yamlText], { type: "application/yaml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${recordId || "record"}.yaml`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export function buildMailtoUrl(recordId: string): string {
  // Deliberately does NOT put the YAML body in the mailto: link — most
  // mail clients truncate mailto bodies around ~2k characters, which
  // would silently mangle any real record. Caller must trigger the
  // download first; this just reminds the recipient to attach it.
  const subject = encodeURIComponent(`Significance record submission: ${recordId || "untitled"}`);
  const body = encodeURIComponent(
    `A record file (${recordId || "record"}.yaml) should have just downloaded to your computer. ` +
    "Please attach it to this email before sending."
  );
  return `mailto:?subject=${subject}&body=${body}`;
}
```

**Step 4: Add tests for `github-link.ts`'s branching logic**

Append to `tests/submit-checks.test.ts`:

```ts
import { buildPrComposeUrl } from "../app/submit/github-link.ts";

test("buildPrComposeUrl returns a URL under the length ceiling", () => {
  const result = buildPrComposeUrl("2026-test-example", "schema_version: 1\n");
  assert.equal(result.tooLong, false);
  assert.match(result.url ?? "", /^https:\/\/github\.com\/hjyuh\/significance\/new\/main\?filename=records\/2026-test-example\.yaml&value=/);
});

test("buildPrComposeUrl refuses an oversized record rather than truncating", () => {
  const hugeYaml = "x".repeat(10000);
  const result = buildPrComposeUrl("2026-test-example", hugeYaml);
  assert.equal(result.url, null);
  assert.equal(result.tooLong, true);
});
```

**Step 5: Run — expect PASS**

Run: `node --import tsx --test tests/submit-checks.test.ts`
Expected: PASS, 11 tests

**Step 6: Commit**

```sh
git add app/submit/types.ts app/submit/build-yaml.ts app/submit/github-link.ts tests/submit-checks.test.ts
git commit -m "feat: wizard record assembly, YAML output, and PR-compose link"
```

---

## Task 14: `SubmitWizard.tsx` — the component

**Files:**
- Create: `app/submit/SubmitWizard.tsx`
- Create: `app/submit/page.tsx`
- Modify: `app/globals.css` (append wizard styles)
- Modify: `app/page.tsx` (add the "Submit a record" link)

**Step 1: Implement `SubmitWizard.tsx`**

```tsx
"use client";

import { useMemo, useState } from "react";
import type { AttributedDraft, Basis, EvidenceDraft, PartyDraft, VerificationKind, WizardState } from "./types";
import { AI_PROVENANCE_ROLES, emptyWizardState } from "./types";
import { buildRecord, recordToYaml } from "./build-yaml";
import { validateAgainstSchema } from "./schema-validate";
import { runIntraRecordChecks } from "./intra-record-checks";
import { buildMailtoUrl, buildPrComposeUrl, triggerYamlDownload } from "./github-link";

const STEPS = ["role", "claim", "manuscript", "parties", "evidence", "provenance", "review"] as const;
type Step = (typeof STEPS)[number];

const BASIS_OPTIONS: Basis[] = ["source_quote", "author_attestation", "editorial_inference"];
const VERIFICATION_OPTIONS: VerificationKind[] = ["github_identity", "orcid", "email_confirmation", "pseudonymous"];

function slugify(input: string): string {
  return input.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

async function sha256OfFile(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function AttributedFields({
  label, draft, onChange, thirdPartyLocked,
}: {
  label: string;
  draft: AttributedDraft;
  onChange: (next: AttributedDraft) => void;
  thirdPartyLocked: boolean;
}) {
  const needsLocator = draft.basis === "source_quote" ||
    (thirdPartyLocked && draft.basis === "author_attestation");
  return (
    <fieldset className="wizard-fieldset">
      <legend>{label}</legend>
      <label>
        Text
        <textarea value={draft.value} onChange={(e) => onChange({ ...draft, value: e.target.value })} />
      </label>
      <label>
        Basis
        <select
          value={draft.basis}
          onChange={(e) => onChange({ ...draft, basis: e.target.value as Basis })}
        >
          {BASIS_OPTIONS.map((b) => (
            <option key={b} value={b} disabled={thirdPartyLocked && b === "author_attestation" && false}>
              {b}
            </option>
          ))}
        </select>
      </label>
      <label>
        Asserted by (party id)
        <input value={draft.assertedBy} onChange={(e) => onChange({ ...draft, assertedBy: e.target.value })} />
      </label>
      {needsLocator ? (
        <div className="wizard-locator">
          <p className="wizard-hint">
            {draft.basis === "source_quote"
              ? "source_quote requires a locator — where in the source this comes from."
              : "Recording someone else's author_attestation requires a locator pointing at how they told you — a correspondence link or public statement."}
          </p>
          <label>
            Section <input value={draft.locator?.section ?? ""} onChange={(e) => onChange({ ...draft, locator: { ...draft.locator, section: e.target.value } })} />
          </label>
          <label>
            URL <input value={draft.locator?.url ?? ""} onChange={(e) => onChange({ ...draft, locator: { ...draft.locator, url: e.target.value } })} />
          </label>
          <label>
            Quote <input value={draft.locator?.quote ?? ""} onChange={(e) => onChange({ ...draft, locator: { ...draft.locator, quote: e.target.value } })} />
          </label>
        </div>
      ) : null}
    </fieldset>
  );
}

export default function SubmitWizard() {
  const [step, setStep] = useState<Step>("role");
  const [state, setState] = useState<WizardState>(emptyWizardState());
  const [hashing, setHashing] = useState(false);

  const stepIndex = STEPS.indexOf(step);
  const goNext = () => setStep(STEPS[Math.min(stepIndex + 1, STEPS.length - 1)]);
  const goBack = () => setStep(STEPS[Math.max(stepIndex - 1, 0)]);

  const thirdParty = state.submitterRole === "third_party";

  function addParty() {
    const id: PartyDraft = {
      id: "", isPseudonym: false, displayName: "", verificationKind: "github_identity", verificationIdentifier: "",
    };
    setState((s) => ({ ...s, parties: [...s.parties, id] }));
  }

  function updateParty(index: number, next: PartyDraft) {
    setState((s) => ({ ...s, parties: s.parties.map((p, i) => (i === index ? next : p)) }));
  }

  function removeParty(index: number) {
    setState((s) => ({ ...s, parties: s.parties.filter((_, i) => i !== index) }));
  }

  function addEvidence(kind: EvidenceDraft["kind"]) {
    const base = { id: `ev-${state.evidence.length + 1}`, basis: "editorial_inference" as Basis, assertedBy: "" };
    let item: EvidenceDraft;
    if (kind === "external_formal_artifact") item = { ...base, kind, repo: "", commit: "", description: "" };
    else if (kind === "informal_review") item = { ...base, kind, reviewer: "", text: "" };
    else item = { ...base, kind, target: "", reportUrl: "", reportInline: "" };
    setState((s) => ({ ...s, evidence: [...s.evidence, item] }));
  }

  function updateEvidence(index: number, next: EvidenceDraft) {
    setState((s) => ({ ...s, evidence: s.evidence.map((e, i) => (i === index ? next : e)) }));
  }

  function removeEvidence(index: number) {
    setState((s) => ({ ...s, evidence: s.evidence.filter((_, i) => i !== index) }));
  }

  async function onManuscriptFilePicked(file: File | null) {
    if (!file) return;
    setHashing(true);
    try {
      const hash = await sha256OfFile(file);
      setState((s) => ({ ...s, manuscriptSha256: hash }));
    } finally {
      setHashing(false);
    }
  }

  const record = useMemo(() => buildRecord(state), [state]);
  const yamlText = useMemo(() => recordToYaml(record), [record]);
  const schemaErrors = useMemo(() => validateAgainstSchema(record), [record]);
  const intraRecordViolations = useMemo(() => runIntraRecordChecks(record), [record]);
  const prCompose = useMemo(() => buildPrComposeUrl(state.recordId, yamlText), [state.recordId, yamlText]);

  return (
    <main className="wizard">
      <header className="masthead">
        <a className="wordmark" href="/" aria-label="Significance home">SIGNIFICANCE</a>
        <p>Submit a record</p>
      </header>

      <nav className="wizard-steps" aria-label="Submission steps">
        {STEPS.map((s, i) => (
          <span key={s} className={i === stepIndex ? "wizard-step-current" : "wizard-step"}>{i + 1}. {s}</span>
        ))}
      </nav>

      {step === "role" ? (
        <section className="wizard-section">
          <h2>Are you an author of this claim, or recording someone else's public work?</h2>
          <p className="wizard-hint">
            This changes what you can assert without a locator. Recording someone
            else's public work is this tool's core use case and needs no
            permission — the one thing it restricts is claiming, unlocated,
            that an author privately told you something.
          </p>
          <div className="wizard-choice-row">
            <button type="button" onClick={() => setState((s) => ({ ...s, submitterRole: "author" }))} aria-pressed={state.submitterRole === "author"}>
              I am an author
            </button>
            <button type="button" onClick={() => setState((s) => ({ ...s, submitterRole: "third_party" }))} aria-pressed={state.submitterRole === "third_party"}>
              I'm recording someone else's work
            </button>
          </div>
          {state.submitterRole === "author" ? (
            <p className="wizard-hint">Your PR's GitHub identity will be checked against a party you declare below.</p>
          ) : null}
        </section>
      ) : null}

      {step === "claim" ? (
        <section className="wizard-section">
          <h2>Claim</h2>
          <AttributedFields label="Claim text" draft={state.claimText} onChange={(v) => setState((s) => ({ ...s, claimText: v }))} thirdPartyLocked={thirdParty} />
          <AttributedFields label="Scope" draft={state.claimScope} onChange={(v) => setState((s) => ({ ...s, claimScope: v }))} thirdPartyLocked={thirdParty} />
          <label>
            Record id (e.g. 2026-author-topic)
            <input value={state.recordId} onChange={(e) => setState((s) => ({ ...s, recordId: e.target.value }))} />
          </label>
        </section>
      ) : null}

      {step === "manuscript" ? (
        <section className="wizard-section">
          <h2>Manuscript</h2>
          <label>URL <input value={state.manuscriptUrl} onChange={(e) => setState((s) => ({ ...s, manuscriptUrl: e.target.value }))} /></label>
          <label>Label <input value={state.manuscriptLabel} onChange={(e) => setState((s) => ({ ...s, manuscriptLabel: e.target.value }))} /></label>
          <label>Immutable version id (optional, e.g. an arXiv vN) <input value={state.manuscriptImmutableVersionId} onChange={(e) => setState((s) => ({ ...s, manuscriptImmutableVersionId: e.target.value }))} /></label>
          <label>
            Manuscript file (hashed locally — never uploaded)
            <input type="file" onChange={(e) => onManuscriptFilePicked(e.target.files?.[0] ?? null)} />
          </label>
          {hashing ? <p className="wizard-hint">Hashing…</p> : null}
          <label>
            sha256 {" "}
            <input value={state.manuscriptSha256} onChange={(e) => setState((s) => ({ ...s, manuscriptSha256: e.target.value }))} placeholder="Pick a file above, or paste a known hash" />
          </label>
        </section>
      ) : null}

      {step === "parties" ? (
        <section className="wizard-section">
          <h2>Parties</h2>
          {state.parties.map((p, i) => (
            <fieldset className="wizard-fieldset" key={i}>
              <legend>Party {i + 1}</legend>
              <label>Id (lowercase-kebab) <input value={p.id} onChange={(e) => updateParty(i, { ...p, id: slugify(e.target.value) })} /></label>
              <label>
                <input type="checkbox" checked={p.isPseudonym} onChange={(e) => updateParty(i, { ...p, isPseudonym: e.target.checked })} />
                Pseudonymous
              </label>
              <label>{p.isPseudonym ? "Pseudonym" : "Name"} <input value={p.displayName} onChange={(e) => updateParty(i, { ...p, displayName: e.target.value })} /></label>
              <label>
                Verification method
                <select value={p.verificationKind} onChange={(e) => updateParty(i, { ...p, verificationKind: e.target.value as VerificationKind })}>
                  {VERIFICATION_OPTIONS.map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
              </label>
              <label>Identifier <input value={p.verificationIdentifier} onChange={(e) => updateParty(i, { ...p, verificationIdentifier: e.target.value })} /></label>
              <button type="button" onClick={() => removeParty(i)}>Remove</button>
            </fieldset>
          ))}
          <button type="button" onClick={addParty}>Add party</button>
          <label>
            Which party id is you, the submitter?
            <input value={state.submitterPartyId} onChange={(e) => setState((s) => ({ ...s, submitterPartyId: e.target.value }))} />
          </label>
        </section>
      ) : null}

      {step === "evidence" ? (
        <section className="wizard-section">
          <h2>Evidence</h2>
          <div className="wizard-choice-row">
            <button type="button" onClick={() => addEvidence("external_formal_artifact")}>+ external_formal_artifact</button>
            <button type="button" onClick={() => addEvidence("informal_review")}>+ informal_review</button>
            <button type="button" onClick={() => addEvidence("mathematical_assessment")}>+ mathematical_assessment</button>
          </div>
          <div className="wizard-choice-row">
            <span className="wizard-gated" aria-disabled="true" role="button" tabIndex={0}>formal_artifact</span>
            <span className="wizard-gated" aria-disabled="true" role="button" tabIndex={0}>computational_reproduction</span>
          </div>
          <p className="wizard-hint">
            formal_artifact and computational_reproduction require a machine-generated
            execution receipt — produced by CI or the {" "}
            <a href="https://github.com/hjyuh/significance/blob/main/adapters/lean/README.md">Lean adapter</a>,
            not typed by hand.
          </p>

          {state.evidence.map((ev, i) => (
            <fieldset className="wizard-fieldset" key={i}>
              <legend>{ev.kind} — {ev.id}</legend>
              <label>Id <input value={ev.id} onChange={(e) => updateEvidence(i, { ...ev, id: e.target.value })} /></label>
              {ev.kind === "external_formal_artifact" ? (
                <>
                  <label>Repo URL <input value={ev.repo} onChange={(e) => updateEvidence(i, { ...ev, repo: e.target.value })} /></label>
                  <label>Commit (optional) <input value={ev.commit} onChange={(e) => updateEvidence(i, { ...ev, commit: e.target.value })} /></label>
                  <label>Description <textarea value={ev.description} onChange={(e) => updateEvidence(i, { ...ev, description: e.target.value })} /></label>
                </>
              ) : null}
              {ev.kind === "informal_review" ? (
                <>
                  <label>Reviewer (party id) <input value={ev.reviewer} onChange={(e) => updateEvidence(i, { ...ev, reviewer: e.target.value })} /></label>
                  <label>Text <textarea value={ev.text} onChange={(e) => updateEvidence(i, { ...ev, text: e.target.value })} /></label>
                </>
              ) : null}
              {ev.kind === "mathematical_assessment" ? (
                <>
                  <label>Target statement (e.g. "Theorem 1.2") <input value={ev.target} onChange={(e) => updateEvidence(i, { ...ev, target: e.target.value })} /></label>
                  <label>Report URL <input value={ev.reportUrl} onChange={(e) => updateEvidence(i, { ...ev, reportUrl: e.target.value })} /></label>
                  <label>Report inline text <textarea value={ev.reportInline} onChange={(e) => updateEvidence(i, { ...ev, reportInline: e.target.value })} /></label>
                </>
              ) : null}
              <label>
                Basis
                <select value={ev.basis} onChange={(e) => updateEvidence(i, { ...ev, basis: e.target.value as Basis })}>
                  {BASIS_OPTIONS.map((b) => <option key={b} value={b}>{b}</option>)}
                </select>
              </label>
              <label>Asserted by (party id) <input value={ev.assertedBy} onChange={(e) => updateEvidence(i, { ...ev, assertedBy: e.target.value })} /></label>
              <button type="button" onClick={() => removeEvidence(i)}>Remove</button>
            </fieldset>
          ))}
        </section>
      ) : null}

      {step === "provenance" ? (
        <section className="wizard-section">
          <h2>AI provenance</h2>
          <AttributedFields label="Disclosure" draft={state.aiDisclosure} onChange={(v) => setState((s) => ({ ...s, aiDisclosure: v }))} thirdPartyLocked={thirdParty} />
          {state.aiRoles.map((r, i) => (
            <fieldset className="wizard-fieldset" key={i}>
              <legend>Role {i + 1}</legend>
              <label>
                Role
                <select value={r.role} onChange={(e) => setState((s) => ({ ...s, aiRoles: s.aiRoles.map((x, j) => (j === i ? { ...x, role: e.target.value } : x)) }))}>
                  {AI_PROVENANCE_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
                </select>
              </label>
              <label>Model <input value={r.model} onChange={(e) => setState((s) => ({ ...s, aiRoles: s.aiRoles.map((x, j) => (j === i ? { ...x, model: e.target.value } : x)) }))} /></label>
              <label>Asserted by <input value={r.assertedBy} onChange={(e) => setState((s) => ({ ...s, aiRoles: s.aiRoles.map((x, j) => (j === i ? { ...x, assertedBy: e.target.value } : x)) }))} /></label>
              <button type="button" onClick={() => setState((s) => ({ ...s, aiRoles: s.aiRoles.filter((_, j) => j !== i) }))}>Remove</button>
            </fieldset>
          ))}
          <button type="button" onClick={() => setState((s) => ({ ...s, aiRoles: [...s.aiRoles, { role: AI_PROVENANCE_ROLES[0], model: "", basis: "author_attestation", assertedBy: "" }] }))}>
            Add role
          </button>
        </section>
      ) : null}

      {step === "review" ? (
        <section className="wizard-section">
          <h2>Review and export</h2>
          <p className="wizard-banner">
            These are structural checks plus a narrow intra-record subset.
            Full validation, including cross-record and attribution rules,
            runs when the PR opens.
          </p>

          {schemaErrors.length ? (
            <div className="wizard-errors">
              <p>Schema errors ({schemaErrors.length}):</p>
              <ul>{schemaErrors.map((e, i) => <li key={i}>{e.path}: {e.message}</li>)}</ul>
            </div>
          ) : <p className="wizard-ok">No structural schema errors.</p>}

          {intraRecordViolations.length ? (
            <div className="wizard-errors">
              <p>Intra-record check violations ({intraRecordViolations.length}):</p>
              <ul>{intraRecordViolations.map((v, i) => <li key={i}>[{v.rule}] {v.location}: {v.message}</li>)}</ul>
            </div>
          ) : <p className="wizard-ok">No intra-record violations found.</p>}

          <pre className="wizard-yaml">{yamlText}</pre>

          <div className="wizard-actions">
            <button type="button" onClick={() => triggerYamlDownload(state.recordId, yamlText)}>
              Download record.yaml
            </button>

            {prCompose.url ? (
              <>
                <a className="wizard-pr-link" href={prCompose.url} target="_blank" rel="noreferrer">
                  Open as pull request
                </a>
                <p className="wizard-hint">
                  This puts the record's content — including any named parties —
                  in the URL, which lands in browser history and referrer headers.
                  Fine for a record you intend to publish; if it names someone who
                  hasn't confirmed yet, download and open the PR by hand instead.
                </p>
              </>
            ) : (
              <p className="wizard-hint">
                This record is too large for a pre-filled PR link. Download the
                file and open the PR by hand at{" "}
                <a href="https://github.com/hjyuh/significance/new/main">github.com/hjyuh/significance</a>.
              </p>
            )}

            <a href={buildMailtoUrl(state.recordId)}>Email it instead</a>
          </div>
        </section>
      ) : null}

      <div className="wizard-nav">
        <button type="button" onClick={goBack} disabled={stepIndex === 0}>Back</button>
        <button type="button" onClick={goNext} disabled={stepIndex === STEPS.length - 1}>Next</button>
      </div>
    </main>
  );
}
```

**Step 2: `page.tsx`**

Create `app/submit/page.tsx`:

```tsx
import SubmitWizard from "./SubmitWizard";

export const metadata = {
  title: "Submit a record — Significance",
  description: "Assemble a Significance claim-state record and open it as a pull request.",
};

export default function SubmitPage() {
  return <SubmitWizard />;
}
```

**Step 3: Append wizard styles to `app/globals.css`**

```css
.wizard { padding-bottom: 60px; }
.wizard-steps { display: flex; flex-wrap: wrap; gap: 4px 18px; padding: 16px 28px; border-bottom: 1px solid var(--rule); font-size: 11.5px; color: var(--muted); }
.wizard-step-current { color: var(--fg-strong); }
.wizard-section { padding: 28px 28px 20px; }
.wizard-section h2 { font-family: var(--sans); font-size: 1.3rem; color: var(--fg-strong); margin: 0 0 14px; }
.wizard-fieldset { border: 1px solid var(--rule); padding: 16px 18px; margin: 0 0 18px; }
.wizard-fieldset legend { padding: 0 6px; color: var(--muted); font-size: 11.5px; text-transform: uppercase; letter-spacing: 0.1em; }
.wizard-fieldset label, .wizard-section > label { display: block; margin: 10px 0; font-size: 12.5px; color: var(--dim); }
.wizard-fieldset input, .wizard-fieldset textarea, .wizard-fieldset select,
.wizard-section > label input, .wizard-section > label textarea, .wizard-section > label select {
  display: block; width: 100%; margin-top: 4px; background: var(--bg-inset); color: var(--fg); border: 1px solid var(--rule); padding: 8px 10px; font-family: var(--mono); font-size: 12.5px;
}
.wizard-hint { color: var(--muted); font-size: 12px; max-width: 68ch; }
.wizard-choice-row { display: flex; flex-wrap: wrap; gap: 10px; margin: 10px 0; }
.wizard-choice-row button, .wizard-nav button, .wizard-pr-link { background: var(--bg-inset); color: var(--fg); border: 1px solid var(--edge); padding: 8px 14px; font-family: var(--mono); font-size: 12px; text-decoration: none; cursor: pointer; }
.wizard-choice-row button[aria-pressed="true"] { border-color: var(--note); color: var(--note); }
.wizard-gated { display: inline-flex; align-items: center; padding: 8px 14px; border: 1px dashed var(--rule); color: var(--muted); font-size: 12px; }
.wizard-nav { display: flex; justify-content: space-between; padding: 20px 28px; border-top: 1px solid var(--rule); }
.wizard-banner { background: var(--bg-inset); border: 1px solid var(--edge); padding: 12px 16px; color: var(--dim); font-size: 12.5px; }
.wizard-errors { color: #c97b7b; font-size: 12px; }
.wizard-ok { color: var(--note); font-size: 12px; }
.wizard-yaml { background: var(--bg-inset); border: 1px solid var(--rule); padding: 16px; overflow-x: auto; font-size: 11.5px; max-height: 400px; }
.wizard-actions { display: flex; flex-direction: column; gap: 10px; align-items: flex-start; margin-top: 16px; }
```

**Step 4: Link from the homepage header**

In `app/page.tsx`, change the `<header className="masthead">` block from:

```tsx
      <header className="masthead">
        <Link className="wordmark" href="/" aria-label="Significance home">
          SIGNIFICANCE
        </Link>
        <p>Claim-state records for AI-assisted mathematics</p>
      </header>
```

to:

```tsx
      <header className="masthead">
        <Link className="wordmark" href="/" aria-label="Significance home">
          SIGNIFICANCE
        </Link>
        <p>Claim-state records for AI-assisted mathematics</p>
        <Link href="/submit">Submit a record →</Link>
      </header>
```

**Step 5: Type-check and lint**

Run: `npx tsc --noEmit`
Expected: no errors

Run: `npm run lint`
Expected: no errors. If the JSX `disabled={thirdPartyLocked && b === "author_attestation" && false}` line in `AttributedFields` trips a lint rule about a constant condition (it's a placeholder no-op deliberately left inert because the schema doesn't forbid selecting the basis, only requires the locator when it's selected — see Task 14 Step 1's `needsLocator` logic, which is the actual gate) — simplify it to `disabled={false}` or remove the prop entirely if lint flags it; the requirement is enforced by `needsLocator`, not by disabling the option.

**Step 6: Run dev server and manually exercise both submitter-role paths**

Run: `npm run dev`

Manually, in a browser:
- Complete the wizard as "author": confirm no locator is demanded for `author_attestation`.
- Complete the wizard as "third party": select `author_attestation` on the claim text and confirm the locator fields appear and the hint explains why.
- On the evidence step, confirm `formal_artifact`/`computational_reproduction` are visibly present but inert, and that Tab reaches them (confirms `aria-disabled` didn't drop them from tab order the way native `disabled` would).
- Pick a small local file on the manuscript step and confirm a 64-hex-char sha256 appears.
- On review, confirm the banner text, that schema/intra-record errors show for an incomplete record and clear once required fields are filled, that Download produces a `.yaml` file, and that the PR-compose link's caveat text is visible.
- Manually inflate one field (e.g. paste a very long `description`) until `prCompose.url` becomes `null` and confirm the fallback message appears instead of a broken/truncated link.

**Step 7: Commit**

```sh
git add app/submit/SubmitWizard.tsx app/submit/page.tsx app/globals.css app/page.tsx
git commit -m "feat: add the /submit wizard"
```

---

## Task 15: Update `tests/rendered-html.test.mjs`'s homepage assertion

**Files:**
- Modify: `tests/rendered-html.test.mjs`

**Step 1: Check whether the existing homepage test still passes**

Run: `npm test`

The existing test `"the homepage derives its record facts from the generated index"` regex-matches specific substrings of `app/page.tsx` (`records.length`, `records.map`, the `import generatedRecords` line) — adding the `<Link href="/submit">` line shouldn't break any of those regexes, since none of them anchor to exact adjacent content. Confirm this by running the suite rather than assuming it.

Expected: PASS. If it fails, read the failing assertion's regex and adjust only if the added `Link` line genuinely broke an anchor (it shouldn't).

**Step 2: If it passed, no further action.** If you want an explicit regression guard for the new link, add one assertion; otherwise this task is just verification, not new code.

---

## Final verification

Run the entire suite end to end from a clean state:

```sh
uv run pytest -q
uv run ruff check src tests adapters/lean
npm run lint
npm test
node --import tsx --test tests/submit-checks.test.ts
npx tsc --noEmit
```

All must pass. Then re-read `docs/plans/2026-08-02-submission-wizard-design.md` §11 (Testing) and confirm every item there is covered by either an automated test above or the manual QA pass in Task 14 Step 6.
