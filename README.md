# Significance

Significance is an open format and toolchain for recording claims, evidence,
interpretations, and open verification needs around AI-assisted mathematics
in a way that is **attributable, version-bound, and portable**.

It mechanically validates provenance and a narrow set of evidence
predicates (schema shape, attribution completeness, execution receipts,
append-only history). **It does not mechanically determine mathematical
truth**, and no field or rendered element in a Significance record is
permitted to assert that a claim is verified, correct, or refuted. The
Lean evidence adapter is not a general mathematical verifier — it
performs narrow evidence checks (a build reproduces, an axiom closure
stays within a declared trust profile), not a judgment on the
mathematics itself.

> Significance does not eliminate curation. Its hypothesis is that portable
> records and automated invariant checking make each act of curation
> reusable across trackers, authors and readers. If nobody consumes or
> republishes the records, it inherits the retired wiki's economics and
> should stop.

## Status

v0.1, with the schema, CLI, static record renderer, React/vinext presentation
shell, research-preview Lean evidence adapter, and CI implemented. See
`docs/design.md` for the design rationale, `SECURITY.md` for the Lean adapter's
threat model, and `docs/export.md` / `docs/moderation.md` for the integration
proposal and assessment/outreach policy.

```
significance init                       # interactively scaffold a new record
significance validate records/          # schema + semantic validation
significance validate r.yaml --base main  # + append-only enforcement against a base ref/file
significance diff a.yaml b.yaml         # semantic diff, flags freshness transitions
significance build records/ -o site/    # static site; one stable URL per record, e.g. site/<record_id>/
```

Each record's rendered page has a **stable** URL, not a permanent one —
GitHub Pages is not an archival service, and this README does not claim
otherwise.

## Rendering ownership

`records/*.yaml` is the single source of record facts. The Python renderer is
the sole owner of record selection, validation, and record-page rendering. It
produces:

- static record pages and their static index under `public/records/` for the
  hosted app (or another directory supplied with `-o`); and
- `public/records/index.json`, a deliberately narrow list of validated record
  summaries.

The React/vinext homepage imports that generated JSON and only presents it. It
does not parse YAML, restate record facts, or independently calculate freshness.
The Cloudflare Worker serves the React shell and static Python output; it does
not render record content and declares no database, object-storage, or image
transformation capability.

## Repository layout

- `schema/` — the record JSON Schema (draft 2020-12) and its changelog.
- `records/` — published, source-inspected claim-state records.
- `examples/` — explicitly synthetic schema demonstrations; production builds
  never render this directory.
- `src/significance/` — the Python package (`cli.py`, `validate.py`,
  `diff.py`, `init.py`, `render.py`, plus `templates/` and `static/` for
  the renderer).
- `app/` — the React/vinext presentation shell. Its homepage consumes only the
  Python-generated `public/records/index.json`.
- `worker/` — the minimal Cloudflare Worker entry point that serves the vinext
  shell and static assets.
- `build/` — the small Sites packaging plugin; deployment identity is local
  metadata and is not committed.
- `public/records/` — generated static record pages, index, stylesheet, and
  record-summary JSON.
- `tests/` — schema, CLI, and renderer tests, including
  `tests/fixtures/broken/` (deliberately invalid records) and
  `tests/fixtures/hostile/` (schema-valid records carrying adversarial
  content, for renderer escaping tests).
- `adapters/lean/` — the Lean evidence adapter (research preview) and its
  fixtures; see `adapters/lean/README.md`.
- `docs/` — `design.md` (rationale), `export.md` (integration proposal
  for existing trackers), `moderation.md` (assessment admissibility and
  outreach ethics).
- `.github/workflows/` — CI (lint, test, validate, build, deploy Pages on
  `main`) and the two privilege-separated Lean adapter workflows.
- `SECURITY.md` — the Lean adapter's threat model and known limitations.

## Development

```sh
uv sync
uv run pytest -q
uv run ruff check src tests adapters/lean

npm ci
npm run dev       # prebuilds public/records/, then starts vinext
npm run lint
npm test          # rebuilds records + app, then runs rendered-output guards
```

`npm run build` always runs the Python record build first, so the homepage and
record pages are generated from the same validated input. A local
`.openai/hosting.json` is used only when deploying through Sites; it is ignored
by Git and is not required for an ordinary local build.

## Out of scope for v0.1

A `refuted` field or any global conclusion; `common_overstatements`;
richer digestion taxonomies; reproduction outside Lean; cryptographic
signing; badges, hosted services, accounts, databases, interactive proof
explainers; comprehension test tooling; anything resembling a
paid-reviewer service.

## License

Apache-2.0. See `LICENSE`.
