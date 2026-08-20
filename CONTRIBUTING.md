# Contributing a record

Significance records live at `records/<record_id>.yaml` and are proposed
as ordinary GitHub pull requests — there is no separate submission
system, account, or database. The easiest way to build one is the
submission wizard on the project's site (linked from the homepage): it
walks the schema, validates structurally as you type, and hands you a
pre-filled GitHub new-file editor. After you click "Propose new file,"
GitHub guides you through opening the pull request.

You can also write the YAML by hand against `schema/record.schema.json`
(see `significance init` for a guided CLI scaffold) and open the PR
yourself. Whichever path you take, the same review checklist applies.

For authors, the wizard's reviewer-map step is especially useful: name the main
deduction, the steps you consider most delicate, the background a reader needs,
and the passages you most want independently examined. Those answers become
attributed `review_map` entries. Readers can propose an additional anchored
need through the record page's "Suggest another focused check" link; it is
merged only as an attributed pull request. The complete
[discussion-to-record guide](docs/discussion-to-record.md) explains how an
issue or invitation response becomes a version-bound record entry; discussion
is never promoted automatically.

## Are you an author, or recording someone else's work?

This distinction matters and the wizard asks it up front (see the
[design doc](docs/plans/2026-08-02-submission-wizard-design.md) if you
want the reasoning):

- **You're an author.** You can use `basis: author_attestation` freely
  for what you're personally attesting to. Your PR's GitHub identity
  should match a party in the record — that's how attribution arrives,
  from the PR itself, not from anything the file claims.
- **You're recording someone else's public work** — this is the tool's
  core use case, no permission needed. Use `source_quote` (with a
  locator) or `editorial_inference` for claim/scope. The one thing that
  needs a receipt: if you assert `author_attestation` anywhere — i.e.
  "the author told me X" — attach a `locator` pointing at where/how they
  told you (a correspondence link, a public statement). The wizard
  enforces this structurally; if you're writing YAML by hand, reviewers
  will ask for it.

## Evidence: what you can self-attest, and what you can't

`external_formal_artifact`, `informal_review`, and `mathematical_assessment`
are things a person can honestly assert by hand. `formal_artifact` and
`computational_reproduction` are meant to come from a machine-generated
`execution_receipt` — produced by CI or the
[Lean adapter](adapters/lean/README.md), not typed by hand. The validator
requires such a receipt's `asserted_by` to resolve to a party declared as
`automation` — but that's a naming-consistency check, not cryptographic
proof; see `SECURITY.md` for what it doesn't guarantee. The wizard won't
let you fill in those two kinds' fields at all.

## Admissibility checklist (`mathematical_assessment` items specifically)

Anyone may propose a `mathematical_assessment` on any record. Before it's
merged, it must (see `docs/moderation.md` for the full rationale):

- [ ] Target a precise numbered statement (e.g. "Theorem 1.2"), not the
      manuscript as a whole.
- [ ] Contain a substantive mathematical argument another mathematician
      could follow and check — not a rating, not a one-line opinion.
- [ ] Disclose any conflict of interest or competing claim up front.
- [ ] Address the mathematics only — no claims about an author's
      conduct, competence, or motives.
- [ ] Leave room for an author response (`author_response[]`), which is
      never removable once attached.

A rejected proposal is simply not merged. There is no public log of
rejections — see `docs/moderation.md`.

## Review

`significance validate` (schema + semantic rules) runs in CI on every
PR. A maintainer applies the checklist above through ordinary PR review —
there's no separate review body for v0.1.
