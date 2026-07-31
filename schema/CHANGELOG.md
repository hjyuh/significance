# Schema changelog

Entries track changes within `schema_version: 1` during v0.1 development
(pre-stable; no v0.1 record has shipped outside this repo yet, so additive
tweaks are made in place rather than bumping the generation).

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
