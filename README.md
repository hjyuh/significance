# Significance

Significance is an open format and toolchain for recording claims, evidence,
interpretations, and open verification needs around AI-assisted mathematics
in a way that is **attributable, version-bound, and portable**.

It mechanically validates provenance and a narrow set of evidence
predicates (schema shape, attribution completeness, execution receipts,
append-only history). **It does not mechanically determine mathematical
truth**, and no field or rendered element in a Significance record is
permitted to assert that a claim is verified, correct, or refuted.

## Status

v0.1, under active development, phase 1 of 5 (schema + example record).
Not yet installable or usable end to end — there is no CLI or renderer yet.
See `docs/design.md` for the design rationale.

## Repository layout

- `schema/` — the record JSON Schema (draft 2020-12) and its changelog.
- `records/` — example records.
- `src/significance/` — the Python package.
- `tests/` — schema and (in later phases) CLI/renderer tests, including
  `tests/fixtures/broken/` for deliberately invalid records.
- `adapters/lean/` — the Lean evidence adapter (phase 4).
- `docs/` — design doc and, in later phases, export/integration and
  moderation policy docs.

## License

Apache-2.0. See `LICENSE`.
