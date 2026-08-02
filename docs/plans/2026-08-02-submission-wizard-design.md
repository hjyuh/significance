# Submission wizard — design

Status: approved, not yet implemented. See `docs/design.md` and
`docs/moderation.md` for the invariants this builds on.

## 1. Problem

`records/*.yaml` is currently authored by hand or via `significance init`
(local CLI, requires a clone). There is no path for someone without local
tooling — including the primary population this format exists to serve,
third parties recording a claim they didn't author (erdosproblems.com- and
arXiv-tracker-shaped contributors) — to propose a record. The architecture
(files, no accounts, no database, moderation already specified as PR review)
makes the shape of the fix obvious: submission is a pull request, and a
browser wizard's job is to make assembling that PR's file the only thing a
submitter has to think about.

## 2. Step 0: author or third party (structural, not a checklist item)

Before any content field, the wizard asks: **"Are you an author of this
claim, or recording someone else's public work?"** This is not framing copy —
it changes what the rest of the form allows:

- **Author path.** `basis: author_attestation` is available on any
  attributed value without friction. The submitter adds themselves as a
  party in the Parties step and records that party id as the submitter —
  the PR's GitHub identity is checked against it at review time.
  Attribution arrives from the PR plumbing itself, not from anything the
  wizard asserts.
- **Third-party path.** The submitter is not implicitly a claimant on this
  path — if they add themselves as a party in the Parties step, it's as a
  reporter/editor, not an asserting author. Claim and scope basis defaults
  to `source_quote` / `editorial_inference`. If the submitter selects
  `author_attestation` anywhere in the form on this path — i.e. "the
  author told me X" — the
  wizard requires a `locator` (or equivalent pointer: correspondence link,
  public statement URL) before that field validates. There is no way to
  produce a wizard-generated YAML file with an unlocated third-party
  `author_attestation`.

This is the enforcement mechanism for the moderation rule ("asserting
parties must either match the submitter or carry documented consent") that
the original proposal left as a CONTRIBUTING.md checklist item. Recording
someone else's public work is the tool's central use case and needs no
consent; *claiming the author privately told you something* is the one
place third-party submission needs a receipt, and now the form can't be
completed without one.

## 3. Wizard steps and location

`app/submit/page.tsx` (client component) in the existing vinext/Next
app-router shell. No new framework, no backend. Steps after step 0: claim
statement → manuscript (URL, label, immutable version id) → parties →
evidence items → AI provenance → review/export.

State lives in React state; YAML is generated live via `js-yaml` (currently
a transitive dependency only — add as a direct one). "Submit a record" is
linked from `app/page.tsx`'s header.

## 4. Validation: labeled honestly as structural-plus-a-subset, not full

`ajv` + `ajv-formats`, loaded against the actual `schema/record.schema.json`
(imported directly — never a second copy, never drifts from the CLI's
schema), catches shape errors as the submitter types.

That is not full validation, and the wizard says so: a permanent banner
reads **"These are structural checks. Full validation, including
cross-record and attribution rules, runs when the PR opens."** The rules
that decide record admissibility live in `semantics.py`, not the schema, and
porting all of them would silently reintroduce the two-copies-of-the-truth
problem the schema-import already avoids. Instead, port only the subset
that is (a) intra-record, (b) requires no hashing, git, or network access,
and is therefore honestly reproducible client-side:

- `check_asserted_by_parties` — every `asserted_by` resolves to a declared
  party.
- `check_source_quote_locators` — `basis: source_quote` requires a locator.
- `check_forbidden_language` — rejects "verified"/"proven" in rendered
  prose fields.
- `check_freshness_recomputation` — pure string comparison, no I/O.
- The new automation-identity check (§5).

Excluded, and named as excluded in the banner's tooltip: `check_uniqueness`
(needs sibling records — though the wizard *can* cheaply warn on an
`record_id` collision against the existing `public/records/index.json` it
already has in bundle, as a courtesy, not a claim of full uniqueness
checking) and `check_append_only` (needs a base git revision; not
meaningful for a brand-new record and not reproducible without git access
for an edit to an existing one).

These five checks are hand-ported to a small `app/submit/intra-record-checks.ts`.
There is no cross-language codegen here — this is accepted manual-sync debt.
A comment at the top of both `semantics.py` and the new TS file cross-references
the other, so a future change to one is at least locatable from the other.

## 5. Automation-identity check (closes a real gap, honestly scoped)

`docs/design.md` §5 already claims machine receipts bind an "asserting
automation identity," but `semantics.py` enforces no such thing today — a
human party can currently be `asserted_by` on a hand-typed `formal_artifact`
receipt and nothing rejects it.

Fix:
- Add `"automation"` to `verification_method.kind`'s enum (additive to the
  schema).
- Add `check_execution_receipt_asserted_by_automation`: any party
  referenced as `asserted_by` inside an `execution_receipt` must resolve to
  a party whose `verification_method.kind == "automation"`.
- Add `tests/fixtures/broken/execution-receipt-asserted-by-human.yaml`.

**What this check is and isn't.** It enforces *consistency*, not
*authenticity*. Nothing stops a submitter from declaring themselves a party
with `verification_method.kind: "automation"` — the check catches confusion
and accidental misuse, not a determined bad actor. Real authenticity needs
something a submitter can't self-mint: an OIDC/sigstore-style binding of the
receipt to a specific CI workflow run (SLSA-shaped provenance). That's
deferred to roadmap and must be written up as future work, not implied as
already solved. `docs/design.md`, the schema changelog, and `SECURITY.md`
must describe this check as "requires a declared automation identity," never
as "prevents fabricated receipts."

**Changelog direction.** Adding the enum value is additive for *new*
records against the *new* schema. It is not backward compatible in the
other direction: a record using `verification_method.kind: automation` will
be rejected by any validator still pinned to the previous schema copy. The
`schema/CHANGELOG.md` entry states this explicitly, since "additive" reads
as unconditionally safe if left unqualified.

## 6. Evidence step: visible-but-gated

All five evidence kinds are listed. `informal_review`,
`mathematical_assessment`, and `external_formal_artifact` are selectable.
`formal_artifact` and `computational_reproduction` require an
`execution_receipt` no human can honestly hand-type, so they render with
`aria-disabled="true"` and a no-op click handler — **not** the native
`disabled` attribute, which would drop the control (and its explanatory
text) out of tab order and screen-reader reach. Explanatory copy: *"Requires
a machine-generated execution receipt — produced by CI or the Lean adapter,
not typed by hand,"* linking to `adapters/lean/README.md`.

## 7. Output actions

- **Download draft (primary).** Produces the `.yaml` file. Always available,
  with no length limits or URL exposure; the file remains explicitly a draft
  while any browser-side check is failing.
- **Continue submission on GitHub (secondary, with an inline caveat).** Enabled
  only after schema, semantic, role, and third-party attestation checks pass. It builds
  `https://github.com/hjyuh/significance/new/main?filename=records/<id>.yaml&value=<url-encoded-yaml>`.
  This opens GitHub's pre-filled new-file editor; after the user proposes the
  file, GitHub guides them through opening the pull request.
  Below the button: *"This puts the record's content — including any named
  parties — in the URL, which lands in browser history and referrer
  headers. Fine for a record you intend to publish; if it names someone who
  hasn't confirmed yet, download and open the PR by hand instead."* If the
  encoded URL would exceed a safe length ceiling (empirically ~7-8k chars
  across browsers; wizard checks against 6000 as a margin), this button
  disables in favor of the download path with a one-line reason, rather
  than silently truncating content.
- **Email fallback.** Triggers the download, then opens a `mailto:` with a
  short instructional body ("A record file just downloaded — attach it to
  this email before sending") — not the YAML content itself, which
  truncates hard (~2k chars) in most mail clients and would silently mangle
  any real record.

## 8. Promotion path: `external_formal_artifact` → `formal_artifact`

Structurally already possible with zero schema/validator changes: only
`history[]` is append-only-enforced, not `evidence[]`, so a version bump
can add a new evidence item freely. The open question the original proposal
left as a side effect of the schema — mutate the existing item in place, or
add-and-mark-superseded — is decided here, as editorial convention (not
code, not wizard scope):

**Decision: never mutate an existing evidence item's kind. Add the new
`formal_artifact` item under a new id, and add a `history` event
(`type: evidence-superseded`, `note` naming both evidence ids) recording
the supersession.** Rationale: mutating in place leaves the record looking
cleanly CI-attested from the start, with the self-reported origin visible
only by reading `history[]` — the same "does the record itself show its own
trail" property `record_state`/`freshness` are designed around elsewhere in
this format. This is added as editorial guidance in `docs/design.md` §5,
not as a new schema field or validator rule — evidence items gain no new
`superseded`/`status` field in v1.

## 9. Docs

- `CONTRIBUTING.md` (new, repo root): the submission flow, the admissibility
  checklist from `docs/moderation.md` restated as a PR template checklist,
  and the consent rule — now largely *enforced* by §2, documented here for
  the hand-YAML path that bypasses the wizard entirely.
- `.github/PULL_REQUEST_TEMPLATE.md`: the same checklist.
- `SECURITY.md`: short addition noting the automation-identity check's
  actual guarantee (consistency, not authenticity) and pointing at the
  deferred OIDC/sigstore roadmap item.
- `docs/design.md` §5: the promotion-path editorial guidance from §8 above.

## 10. Explicitly not building

Accounts, a hosted validation service, server-side PR creation, any change
to who can merge, a `superseded` field on evidence items, OIDC/sigstore
receipt binding (roadmap only).

## 11. Testing

- Python: `tests/test_schema.py` / `tests/test_validate.py` gain cases for
  the new enum value and the automation-identity check, plus the new broken
  fixture.
- JS: a focused test (extending `tests/rendered-html.test.mjs` or a new
  file) exercises the ported intra-record checks against known-good and
  known-broken YAML to catch drift between `semantics.py` and
  `intra-record-checks.ts` — not full parity, just a canary.
- Manual: run the dev server, complete the wizard end-to-end on both the
  author and third-party paths, confirm the GitHub editor link opens with a
  pre-filled file, confirm the length-ceiling fallback triggers on an
  oversized record, confirm `aria-disabled` controls are screen-reader
  reachable.
