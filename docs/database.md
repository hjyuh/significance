# Significance as an open research database

Significance is a canonical, open ledger of mathematical claims and the work
around them. The database is the versioned corpus, not the hosted presentation:
`records/*.yaml` is authoritative, Git history is the append-only change log,
and every generated page or export is derived from validated records.

## What a record contains

Each record identifies one claim and the source version it describes. It may
also carry attributed evidence, reviewer maps, open tasks, formalization
handoffs, dependencies, digestions, and history events. These are separate
objects in one record because they answer different questions and must not be
blended into a verdict.

The important distinction is between a fact about an artifact and a person's
reading of it. A build receipt can say that code ran at a pinned revision; it
cannot say that the paper's informal theorem follows. A reviewer can report a
gap in a named passage; Significance records that report without turning it
into a global status.

## Write path

The initial database has a deliberately boring write path:

1. An author, editor, or reader proposes a YAML change through a pull request.
2. The validator checks schema shape, attribution, source locators, references,
   freshness, and append-only history.
3. A maintainer reviews the proposed record change.
4. The static build regenerates HTML, JSON indexes, feeds, and problem views.

Importers may prepare drafts from arXiv, ErdősProblems, Zenodo, or a public
repository, but an importer never publishes a claim on its own. Public records
must identify their source version and who stands behind each non-trivial
assertion.

## Interoperability

The generated JSON and feed are the public API. Other trackers may link to a
record, consume selected fields, or ignore it. No consumer is required to use
Significance's presentation or status vocabulary. Exports preserve attribution,
freshness, and the distinction between reported, reproduced, and reviewed work.

## What is intentionally absent

There is no truth score, ranking, social feed, follower count, or automatic
promotion of a discussion into evidence. Discussion becomes record state only
when a named person submits an attributable, version-bound object through the
ordinary review path. Accounts and hosted persistence are deferred until the
Git-backed workflow has demonstrated regular external use.
