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

v0.1, under active development, phase 3 of 5 (static renderer). Schema,
CLI (`init`/`validate`/`diff`), and static site renderer (`build`) all
work; there is no CI yet and the Lean evidence adapter hasn't been built.
See `docs/design.md` for the design rationale.

```
significance init                       # interactively scaffold a new record
significance validate records/          # schema + semantic validation
significance validate r.yaml --base main  # + append-only enforcement against a base ref/file
significance diff a.yaml b.yaml         # semantic diff, flags freshness transitions
significance build records/ -o site/    # static site, one stable URL per record
```

## Repository layout

- `schema/` — the record JSON Schema (draft 2020-12) and its changelog.
- `records/` — example records.
- `src/significance/` — the Python package (`cli.py`, `validate.py`,
  `diff.py`, `init.py`, `render.py`, plus `templates/` and `static/` for
  the renderer).
- `tests/` — schema, CLI, and renderer tests, including
  `tests/fixtures/broken/` (deliberately invalid records) and
  `tests/fixtures/hostile/` (schema-valid records carrying adversarial
  content, for renderer escaping tests).
- `adapters/lean/` — the Lean evidence adapter (phase 4).
- `docs/` — design doc and, in later phases, export/integration and
  moderation policy docs.

## License

Apache-2.0. See `LICENSE`.
