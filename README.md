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
- `public/records/index.json`, a deliberately narrow set of validated summaries:
  `records` and `boards`, and nothing the presentation layer could recompute
  differently.

The React/vinext homepage imports that generated JSON and only presents it. It
does not parse YAML, restate record facts, or independently calculate freshness.
The Cloudflare Worker serves the React shell and static Python output; it does
not render record content and declares no database, object-storage, or image
transformation capability.

## Reading a record without knowing the vocabulary

Five things exist so that a stranger with a genuine need can get somewhere
without learning this project's dialect first. None of them renders a verdict,
a score, or a colour-coded truth state; all of them are attributed.

Pages:

- `/request/` — how to ask for a record, with a prefilled GitHub issue and an
  email fallback asking the same three questions. States the consent rule: a
  record about a living person's claim is filed only after they are contacted,
  and a decline is recorded nowhere.
- `/glossary/` — the vocabulary, one sentence per term. Terms are also links
  from the pages where they appear.
- `/boards/ten-results/` — one row per result in the August 2026 release,
  stating what has been checked and what has not. Nine of its ten rows are
  deliberately empty: nothing here evidences those results yet, and an empty
  row means nobody has looked.

Two optional blocks in a record's YAML:

- `plain_summary` — four plain sentences above the dossier: what is claimed,
  what has been checked, what has not, as of when. `basis: digest`, capped at
  60 words a field, and refused if it states a verdict or leaves `not_checked`
  empty while the record carries open invitations.
- `digestions[].kind: plain_language` — a signed paragraph explaining what the
  result says, labelled with the stratum speaking (author, editor, community).
  Strata are rendered separately and never merged.

Open invitations may also carry `how` (what somebody would actually do, pinned
to an exact revision) and `respond` (where the answer goes). Both are optional;
an invitation without them renders exactly as it did before.

`significance validate` checks boards as well as records, choosing by the
`kind: board` discriminator. `significance build` gains `--pages-out` for the
deployed layout, `--boards`, and `--site-config`.

## Repository layout

- `schema/` — the record JSON Schema (draft 2020-12) and its changelog, plus
  `board.schema.json` for status boards.
- `records/` — published, source-inspected claim-state records.
- `boards/` — status boards: one page answering a question across several
  results, holding no evidence of its own.
- `data/` — hand-written non-record data: `site.yaml` (repository URL and
  contact address) and `glossary.yaml`.
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
