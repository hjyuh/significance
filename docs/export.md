# Export format and integration proposal

This document describes Significance's export format and sketches how an
existing claim/problem tracker could, at its own discretion, make use of
it. It is an **integration proposal**, not an offer of a service:
Significance is not asking to be plugged into any tracker, does not
consider non-adoption a failure on a tracker's part, and has no mechanism
by which "declined" or "ignored" would even be recorded anywhere (see
`docs/moderation.md`'s outreach ethics note).

## The export format is the input format

There is no separate export transformation. A record's on-disk YAML file
under `records/` — the thing a human or the Lean adapter authors — is
already exactly what a consumer would want to read: it validates against
[`schema/record.schema.json`](../schema/record.schema.json) (JSON Schema,
draft 2020-12, currently `schema_version: 1`; changes are logged in
[`schema/CHANGELOG.md`](../schema/CHANGELOG.md)). Anything that can parse
YAML or JSON (YAML is close enough to JSON that `ruamel.yaml`'s safe
loader round-trips both) and check it against that schema can consume a
record without going through `significance` at all.

Each valid record additionally gets a rendered page at a **stable URL**
(`significance build` writes `site/<record_id>/index.html`; "stable," not
"permanent" — this repository does not claim archival guarantees, and
neither should anything that links to it). `record_id` is the only part
of that URL a consumer should depend on; everything else about the
rendered page's layout may change between v0.1 minor revisions.

## Machine-readable endpoints

The static build also writes an Atom feed at `/feed.xml`. It contains one
entry per current record and is suitable for polling by a problem tracker;
the entry links to the stable record page and its summary does not imply a
mathematical verdict.

For records linked to a problem, the build writes one grouped JSON endpoint at
`/problems/<venue>-<problem-id>/index.json`. The endpoint has
`export_schema_version: 1`, the original problem URL, and every valid
Significance record associated with that problem. It is grouped rather than
one-file-per-record so consumers do not silently miss a second claim about
the same problem. The JSON preserves the source record, including attribution,
freshness, evidence, and open work; private renderer-only keys are omitted.

## What a consumer would be reading

The fields most relevant to an external tracker, briefly (full detail in
the schema):

- `claim` — the informal statement, attributed (`basis`, `asserted_by`,
  `asserted_at`) and located.
- `manuscript` — url, label, sha256, retrieved_at; `immutable_version_id`
  when the host provides one.
- `evidence[]` — discriminated by `kind`; each carries its own
  attribution and, for machine results, a full execution receipt (tool,
  runner image digest, log hash). Significance is **not a general
  mathematical verifier** — it validates provenance and a narrow set of
  evidence predicates (schema shape, attribution completeness, execution
  receipts, append-only history), nothing more.
- `freshness` — `current` / `stale` / `unknown`, separate from
  `record_state` (`active` / `superseded` / `withdrawn`).
- `ai_provenance` — disclosed AI involvement and role, if any.
- `open_invitations[]` — outstanding requests (e.g. "please formalize
  Theorem 1.2's boundary case"), which a tracker with its own open-tasks
  concept might want to surface directly.
- `formalization_handoff` — an optional handoff packet for formalizers: target,
  system, work state, definitions, prerequisites, code revision, correspondence,
  and open questions, each kept attributable where it carries a claim.

Nothing in a record is permitted to assert that a claim is verified,
correct, or refuted (see the schema's own top-level description and
`docs/design.md`). Any integration that republishes fields from a record
must preserve this: attribution on every surfaced value, freshness state
alongside it, and no rendering that upgrades "a machine result passed" or
"an author asserts correspondence" into a verdict about the mathematics.

## Possible integration shapes

These are options a tracker's maintainers might consider, not a roadmap
Significance is committing to build:

1. **Link-out.** The tracker adds an optional field pointing at a
   record's stable URL for claims where a Significance record exists,
   with no data duplication.
2. **One-way mirror, tracker → Significance.** Someone (an author, an
   editor, a third party per `docs/moderation.md`'s admissibility policy)
   authors a Significance record whose `manuscript` or `evidence[]`
   references the tracker's existing entry. Significance never writes
   back to the tracker.
3. **One-way mirror, Significance → tracker.** The tracker periodically
   reads `records/*.yaml` (or the schema JSON) from this repository and
   surfaces selected fields inside its own UI, under the constraints in
   the previous section.
4. **Nothing.** A tracker is free to conclude records aren't useful to
   it. See the curation-economics paragraph in the [README](../README.md):
   if nobody consumes or republishes the records, the format should
   stop, not be pushed harder.

## The workflow a tracker can expose

The format is designed around the stages that become easy to lose when proof
claims arrive faster than people can read them: generation, verification,
communication, community digestion and acceptance, and canonicalization. A
consumer does not need to reproduce the standalone Significance site to use
that workflow. It can show an author's claim and source version, attach a
reviewer's bounded map of the delicate steps, link to evidence, and leave the
open task beside the original claim. The stages remain separate: a successful
build is not a mathematical review, a clear explanation is not a verification,
and a review is not canonicalization.

This framing follows the workflow discussed in Terence Tao, [“Mathematics in
the age of AI”](https://arxiv.org/abs/2608.16753); it does not imply his
endorsement of Significance.

## Coordinating

There is no dedicated integration channel yet. Open an issue or PR
against this repository to discuss a specific integration; this document
will be updated as concrete integrations, if any, clarify what's
actually useful versus merely possible.
