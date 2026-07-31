# Moderation policy

## Assessment admissibility

Any named party may **propose** a `mathematical_assessment` evidence item
on any record — authorship of the manuscript is not a prerequisite for
raising a substantive concern about it. Maintainers accept a proposed
assessment into the canonical record only if it satisfies all of the
following:

- **Targets a precise statement.** `target` names a specific numbered
  statement (e.g. "Theorem 1.2"), never the manuscript as a whole.
- **Contains a substantive mathematical argument.** Not a rating, not a
  one-line opinion — an argument another mathematician could follow and
  check.
- **Discloses conflicts.** Any relationship to the author(s) or a
  competing claim on the same result is stated up front, not left for a
  reader to discover.
- **Avoids personal allegations.** The assessment addresses the
  mathematics. Claims about an author's conduct, competence in general,
  or motives are out of scope for this field; take them elsewhere.
- **Permits an author response.** The author may attach a response
  (`author_response[]`) to any assessment targeting their claim, and that
  response is never removable by the assessor or by anyone else. An
  assessment and its response(s) are rendered together, dated, and
  neither is presented as settling the question.
- **Satisfies the contribution policy.** Ordinary repository contribution
  norms apply on top of the above (see the repository's contribution
  guidelines, once written).

Maintainers apply this checklist through ordinary PR review — there is no
separate review body or process for v0.1.

## Rejected assessments do not render anywhere

A rejected proposal simply isn't merged. There is no public log of
rejected assessments, no "common overstatements" list, and nothing in
the rendered site or the record schema distinguishes "never proposed"
from "proposed and rejected." The PR that proposed it remains ordinary
repository history — visible the same way any closed PR is, not
highlighted, indexed, or surfaced as a judgment about the proposer or the
target claim.

This is a deliberate choice, not an oversight: a visible rejection log
would itself function as a public shame mechanism, which is exactly the
kind of unattributed, unqualified judgment invariant 1 (no global truth
status) rules out for the record format. The same reasoning applies to
moderation of proposals about them.

## Outreach ethics

If Significance or its maintainers contact authors about their claims
(to ask about AI-provenance disclosure, invite a correspondence
attestation, or anything else), the following holds without exception:

- **Aggregate outreach statistics may be published** (e.g. "N authors
  contacted, M records created as a result").
- **Authors who decline are never named**, in aggregate statistics, in
  commit history, in code comments, or anywhere else.
- **No decline list exists in any form** — not private, not
  maintainer-only, not for internal tracking purposes. If a mechanism to
  track outreach status is ever built, it must be structurally incapable
  of accumulating a list of people who said no.
