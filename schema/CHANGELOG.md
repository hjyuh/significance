# Schema changelog

## 1 — 2026-08-29

Added two evidence kinds for work published elsewhere, plus the fields the
surfaces derived from them need. All additive within `schema_version: 1`.

`exposition` records that somebody wrote or recorded an account of this work:
`venue` (closed enum: erdosproblems, mathematical_discourse, arxiv, blog,
other), `venue_label` (required by the validator when the venue is `other`),
`author` as a declared party, `date`, `url`, and `scope` — what the exposition
covers and excludes. It is not a review and is not counted as one: the
review-activity block and the reviewer census both ignore this kind.
`significance validate` owns url presence and http(s) form
(`exposition-missing-url`), the venue-label rule (`exposition-venue-unnamed`),
author resolution (`unknown-party`), non-empty scope
(`exposition-empty-scope`), and the verdict lint on `scope` and `venue_label`.

`palomar_entry` records an entry in the Palomar formalization registry: `url`,
`date` as the registry shows it, and an optional `artifact_ref`. There is
deliberately no `caveat` property and `additionalProperties` is false: the
caveat is a fixed label rendered from `semantics.PALOMAR_CAVEAT` with every
entry, so no record can shorten, soften, or omit it. `palomar-missing-url` is
enforced by the validator.

Both kinds take `basis` from a new `link_basis` enum (`source_link`,
`author_attestation`), separate from `basis` so that a link can never stand in
for a quote, a receipt, or an editorial finding. Absent, `source_link` is
assumed by the renderer.

Also added: `manuscript.published_at` (optional `iso_date`, the day the source
says the manuscript version was released — distinct from `retrieved_at`, which
is when this project fetched the file), the shared `iso_date` definition, and
`suppress_derived_tasks: [exposition]`, which turns off the build-derived
exposition task for one record. `open_invitations[].task_kind` gains
`exposition` so an editor-written exposition task validates as the derived ones
render.

Older copies of this schema will reject a record using either new kind; pull
the current schema before validating one.

## 1 — 2026-08-20

Added optional `formalization_handoff`, an attributed bridge from an informal
claim to a formalization target. It records the system, work state, definitions,
prerequisites, repository revision, correspondence note, and open questions.
The state describes formalization work only; it is not a verdict on the
mathematics.

## 1 - 2026-08-12 (draft state)

Added an optional `draft` flag so non-public editorial previews cannot render
as active published records. Draft pages carry a prominent warning and their
index and detail states both read "Editorial draft."

## 1 - 2026-08-12

Added `source_inspection` evidence for bounded public-source, version, and
hash checks. The renderer labels it explicitly as not being a mathematical
review, so locating and pinning a manuscript cannot inflate review counts.

Entries track changes within `schema_version: 1` during v0.1 development
(pre-stable; no v0.1 record has shipped outside this repo yet, so additive
tweaks are made in place rather than bumping the generation).

## 1 — 2026-08-11

Added optional `author_relationship`, an attributed statement describing how
the manuscript author participated in the Significance record. Its status is
limited to public sources only, author-confirmed description,
author-contributed, or author-requested. It describes record provenance and is
never mathematical evidence.

## 1 — 2026-08-10

Added optional `manuscript.supplemental_artifacts[]` entries, each carrying a
URL, label, SHA-256 hash, and retrieval time. This is additive and lets a
record bind a publisher's concise note or technical appendix to the same
release without misclassifying that file as independent evidence.

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

## 1 — 2026-07-31 (Phase 2 addendum)

Added optional `locator` to `evidence_external_formal_artifact`,
`evidence_mathematical_assessment`, `digestion`, and `ai_provenance.roles[]`
items, so `significance validate`'s "every source_quote has a locator" rule
is satisfiable everywhere a `basis` field can appear.

## 1 — 2026-07-31

Initial `schema_version: 1`. Top-level record shape: `schema_version`,
`record_id`, `record_version`, `record_state`, `freshness`, `parties`,
`claim`, `manuscript`, `evidence[]`, `ai_provenance`, `digestions[]`,
`importance_claims[]`, `open_invitations[]`, `history[]`.
## Reviewers, backlog, and trusted work

Added invitation taken/done state, attributed reviewer attestations with
bounded review notes, dependency links, and cross-record validation for their
foreign keys. The renderer now emits reviewer census pages, an optional
activity backlog, reverse cited-by links, and the claim-intake standard.
