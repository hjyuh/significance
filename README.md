# Significance

Significance is an open format and toolchain for recording claims, evidence,
interpretations, and open verification needs around AI-assisted mathematics
in a way that is **attributable, version-bound, and portable**.

It is a small reference implementation of a workflow from generated proof to
usable mathematical work: record the claim, make the evidence reproducible,
explain the difficult steps, let named people add bounded review, and preserve
later reuse or canonicalization. The standalone site demonstrates the format;
an existing tracker can link to the pages or consume the YAML directly.

Significance is also an open successor path for the kind of external-data
record that used to sit beside problem pages on ErdősProblems.com. It is not a
replacement for that community or its problem statements: `/problems/` is a
small, attributed index of links into the venue, while each Significance
record carries reusable evidence, digestion, reviewer scope, and open work.

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
threat model, `docs/export.md` / `docs/moderation.md` for the integration
proposal and assessment/outreach policy, and `docs/successor-roadmap.md` for
the staged path from a portable layer to community reuse. `docs/database.md`
describes the canonical corpus, write path, and interoperability boundary.
For a model-readable handoff, see `docs/current-state.md`.

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

- `/request/` — how to ask for or correct a record. One link is required; the
  role and requested attention are short context, and the latter is optional.
  It states the two publication routes: editorial public-interest records for
  widely circulating claims, and author request or opt-in for ordinary claims
  by living individuals. A decline is recorded nowhere.
- `/submit/` — the advanced schema builder for maintainers and technical
  contributors. Authors and readers are directed to `/request/`; they are not
  expected to author provenance fields, party ids, or YAML.
- `/glossary/` — the vocabulary, one sentence per term. Terms are also links
  from the pages where they appear.
- `/reviewers/` — an alphabetical census of named identities with recorded work; reviewer pages contain entries and links, never scores or ranks.
- `/backlog/` — an activity-sorted map of active records, hidden until the configured minimum corpus size is reached.
- `/how-to-file-a-claim/` — a one-page intake standard and copyable template.
- `/problems/` — a partial, portable index of linked venue problems. It is
  generated from `problem_reference` fields; it is not a second problem
  database and makes no claim of complete coverage.
- Record pages begin with a reader summary and `review_map`: the main
  deduction, delicate steps, prerequisites, and needs-checking items.
- `/boards/ten-results/` — one row per result in the August 2026 release,
  stating what has been checked and what has not. Nine of its ten rows are
  deliberately empty: nothing here evidences those results yet, and an empty
  row means nobody has looked.

Two optional blocks in a record's YAML:

- `manuscript.supplemental_artifacts` — hashed companion sources published
  with the main manuscript, such as a concise technical note. They remain
  source artifacts and do not become evidence merely by being listed.
- `plain_summary` — four plain sentences above the dossier: what is claimed,
  what has been checked, what has not, as of when. `basis: digest`, capped at
  60 words a field, and refused if it states a verdict or leaves `not_checked`
  empty while the record carries open invitations.
- `digestions[].kind: plain_language` — a signed paragraph explaining what the
  result says, labelled with the stratum speaking (author, editor, community).
  Strata are rendered separately and never merged.
- `review_map` — an attributed guide to where a reviewer should begin, what
  looks delicate, and what background is needed. It directs reading; it does
  not issue a verdict.
- `formalization_handoff` — an optional, attributed bridge for a formalizer:
  the target statement, formal system, work state, definitions, prerequisites,
  code revision, correspondence note, and smallest open questions. Its state
  describes formalization work, not the mathematics.
- `problem_reference` — an attributed link to the venue problem a record
  concerns (`venue`, stable problem id, URL, and basis). This is the small
  interoperability seam through which a tracker can link out or import a
  record without surrendering its own presentation or editorial control.

Open invitations may also carry `how` (what somebody would actually do, pinned
to an exact revision) and `respond` (where the answer goes). Status is
`open`, `taken`, `done`, or `withdrawn`; taking is attributed and a completed
task points to its evidence. `depends_on` records attributed links to earlier
records or external work. Reviewer attestations carry scope and manuscript
hash, with an optional short review note; strata are displayed separately.

Readers can suggest a single anchored `needs_checking` item through the GitHub
issue template linked on record pages. It becomes part of a record only through
the ordinary attributed pull-request review.
The [discussion-to-record guide](docs/discussion-to-record.md) explains how a
focused issue or invitation response becomes a version-bound review,
assessment, or evidence entry; discussion is never promoted automatically.

`significance validate` checks boards as well as records, choosing by the
`kind: board` discriminator. `significance build` gains `--pages-out` for the
deployed layout, `--boards`, and `--site-config`.

## Exposition and registry evidence

Two evidence kinds record that something exists elsewhere. Both are pointers.
Neither is a review, and neither is counted as one anywhere on the site: the
review-activity block, the reviewer census, and the per-reviewer pages all
ignore them.

- `exposition` — somebody wrote or recorded an account of this work: a
  per-problem exposition on erdosproblems.com, a Mathematical Discourse video,
  an arXiv note, a blog post. The entry carries the venue (a closed enum, with
  `venue_label` required when the venue is `other`), the expositor as a
  declared party, the date, the URL, and a `scope` line saying what the
  exposition covers and what it leaves out — "expounds the Lean proof;
  paper-Lean correspondence excluded". `scope` is verdict-linted, because it is
  the field most likely to drift from describing coverage into reporting an
  outcome. What an exposition deliberately does not claim: that the exposition
  is accurate, that the claim is right, or that anyone checked either.
- `palomar_entry` — this claim's formalization has an entry in the Palomar
  registry. It carries the entry URL, the entry date as the registry shows it,
  and an optional `artifact_ref`. Every rendered entry is accompanied by a
  fixed caveat, which lives in the code and not in any record so that no record
  can shorten, reword, or omit it: *Palomar intake checks fall short of peer
  review (registry's own framing); correspondence with the claimed theorem is
  not established by this entry.* The schema has no `caveat` property and
  forbids extra ones.

Both kinds default to `basis: source_link`, a basis that exists so a link can
never stand in for a quote, a receipt, or an editorial finding.

Three related surfaces derive from them and store nothing of their own:

- **Component dates.** Each record page shows a `preprint / exposition /
  formalization` strip, with an unrecorded component rendered as a dash and
  never substituted from a neighbouring field (`manuscript.retrieved_at` is not
  a publication date; `manuscript.published_at` is the optional field that is).
  No effective release date is computed or displayed — the components are shown
  and the reader applies whatever rule they like.
- **Derived exposition tasks.** A published record with no exposition row gains
  an auto-generated task on `/tasks/`, marked as derived and carrying `[FILL]`
  markers for the reader level and effort an editor supplies. It is generated
  at build time and written into no YAML, so it disappears by itself when a
  real exposition row lands. A record may opt out with
  `suppress_derived_tasks: [exposition]`, which suppresses a solicitation and
  nothing else.
- **The board digestion column.** "n expositions", linking to the record's
  evidence, or "none yet", linking to the derived task where there is one.
  Derived from the linked record so the column cannot disagree with it.

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
  record-summary JSON. `public/problems/` is the generated linked-problem
  index.
- `tests/` — schema, CLI, and renderer tests, including
  `tests/fixtures/broken/` (deliberately invalid records) and
  `tests/fixtures/hostile/` (schema-valid records carrying adversarial
  content, for renderer escaping tests).
- `adapters/lean/` — the Lean evidence adapter (research preview) and its
  fixtures; see `adapters/lean/README.md`.
- `docs/` — `design.md` (rationale), `export.md` (integration proposal
  for existing trackers), `moderation.md` (assessment admissibility and
  outreach ethics), and `plans/` (design notes and roadmaps, dated; nothing
  in there is committed or built unless it says so).
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
## Taking a check

Open [the task list](https://hjyuh.github.io/significance/tasks/) and choose one bounded task. Its page pins the manuscript hash, scope, entry points, prerequisites, and estimated effort. Use the pre-filled GitHub issue to report what you actually checked and found; do not write a verdict about the whole proof.

## Incorporating an attestation

An editor reviews the issue, adds the contributor as a declared party, and saves the scoped YAML attestation. Run `significance incorporate-attestation attestation.yaml --record <record-id>`; the command rejects a stale manuscript hash, verdict language, unknown task, or undeclared reviewer, then marks the task done and appends history. Review the diff and commit it normally—nothing auto-publishes.
