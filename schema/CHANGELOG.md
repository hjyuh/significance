# Schema changelog

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
