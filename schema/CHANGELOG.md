# Schema changelog

Entries track changes within `schema_version: 1` during v0.1 development
(pre-stable; no v0.1 record has shipped outside this repo yet, so additive
tweaks are made in place rather than bumping the generation).

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
