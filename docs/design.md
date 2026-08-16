# Significance v0.1 — design rationale

Significance makes the claims, evidence, interpretations, and open verification
needs surrounding AI-assisted mathematics attributable, version-bound, and
portable. It mechanically validates provenance and selected evidence
predicates. It does not mechanically determine mathematical truth.

This document describes the implemented v0.1, not a future hosted review
marketplace. The schema is authoritative when an example here is abbreviated.

## 1. Problem and hypothesis

A reader encountering a mathematical preprint cannot cheaply answer:

1. What exactly is claimed, and what is expressly left open?
2. What evidence stands behind the claim, who produced it, and against which
   artifact version?
3. Has anyone reproduced an artifact, reviewed a precise step, connected the
   work to prior literature, or disputed it?

The cost is paid repeatedly because reformulations, partial reads, build
results, and objections usually live in prose, threads, or private notes rather
than in an addressable record.

Significance's hypothesis is that a structured record lets readers recover a
claim's scope, artifact version, and evidence state faster and more accurately
than reading the source alone. That is a hypothesis to test, not a finding.

## 2. Product boundary

Significance ships three things:

- A YAML record format with JSON Schema.
- A CLI: `init`, `validate`, `diff`, and `build`.
- A static renderer that gives each published record a stable URL.

The hosted presentation adds a React/vinext homepage, but not a second record
renderer. Python validation produces both the static record pages and a narrow
JSON index of validated summaries; React only maps that generated index into
the homepage. It does not read YAML or independently assert record state,
freshness, or evidence counts.

It has two deliberately separate layers:

- **Evidence ledger:** machine results or explicitly attributed facts about a
  claim and its artifacts.
- **Digestion layer:** attributed interpretations of what a result means, why
  it may matter, and what verification work remains open.

The two layers have different epistemic status and failure modes. A build
result can be factually wrong; a digestion can be a poor judgment. Neither is a
mathematical verdict.

Significance is not a general verifier, journal, review venue, index of every
AI claim, or summarizer of record. Existing trackers can consume the export
format instead of being replaced by it.

## 3. Assertion provenance

The governing rule is **no unattributed assertion**. Choosing the central
claim, partitioning scope, or judging prior work comparable are interpretive
acts; a source locator does not make them mechanical.

Every non-trivial assertion therefore records:

```yaml
value: "..."
basis: source_quote | author_attestation | editorial_inference | machine_result
asserted_by: party-id
asserted_at: "2026-08-01T00:00:00Z"
locator:
  theorem: "1.2"
  page: 4
```

- `source_quote` establishes that text was copied accurately, not that the
  quoted statement is correct.
- `author_attestation` records what an author explicitly attested.
- `editorial_inference` marks and owns the drafter's interpretation.
- `machine_result` must be backed by an execution receipt where the schema
  treats it as a passed evidence predicate.

Parties may be public or pseudonymous. Their verification method is recorded so
readers can judge what an assertion is worth. Identity verification does not
mean that a party participated in, endorsed, or confirmed the record.

## 4. Record state and freshness

The record's state and its source freshness are separate:

```yaml
record_state: active | superseded | withdrawn
freshness:
  result: current | stale | unknown
  observed_source_version: "v3"
  confirmed_source_version: "v2"
  checked_at: "..."
```

`record_state` describes the record. It never asserts that the mathematics is
correct, refuted, or settled.

Freshness is derived. Immutable source version identifiers take priority over
file hashes because regenerated PDFs can differ without a substantive revision.
If freshness cannot be checked, the result is `unknown`, never silently
`current`.

When a release includes companion files, `manuscript.supplemental_artifacts`
binds each one to its URL, label, SHA-256 hash, and retrieval time. A companion
note is a source artifact, not an independent evidence entry; hashing it keeps
the note and manuscript from drifting under a single mutable release label.

History is append-only in the normal contribution path: existing event IDs and
payloads cannot disappear or change, corrections add new events, and record
versions increase monotonically. CI enforces this against a base record. A
repository administrator can still rewrite Git history; v0.1 does not pretend
otherwise.

## 5. Evidence facets

There is no global truth-status field. Mathematical information is recorded in
typed evidence entries:

- `formal_artifact`: an execution receipt exists, isolation passed, the pinned
  artifact built, an axiom policy ran, and correspondence is separately
  attested.
- `external_formal_artifact`: an artifact is reported but Significance has no
  qualifying execution receipt. It contains no build claim.
- `computational_reproduction`: a computation with a complete receipt.
- `informal_review`: an attributed review that does not claim a global status.
- `mathematical_assessment`: a named party's assessment of a precise target,
  with an author-response channel.

Machine receipts bind the tool and version, runner image digest, execution
time, result, log hash, and asserting automation identity. A manually authored
`result: passed` is rejected.

An execution receipt's `asserted_by` must resolve to a party whose
`verification_method.kind` is `automation` — enforced by
`significance validate`. This is a consistency check, not an authenticity
one: nothing stops a party from self-declaring as `automation`. Binding a
receipt to a real, specific CI run (OIDC/sigstore-style provenance) is a
roadmap item, not implemented in v0.1.

**Evidence promotion.** When an `external_formal_artifact` is later backed
by a real build (e.g. via the Lean adapter), add a new `formal_artifact`
evidence item under a new id and record a `history` event noting the
supersession — never mutate the existing item's `kind` in place. Evidence
items are not schema-enforced append-only the way `history[]` is, so
nothing stops an in-place edit, but doing so leaves the record looking
cleanly CI-attested from the start, with the self-reported origin visible
only by reading history. Keeping both items preserves that trail on the
record itself.

Correspondence between a formal declaration and an informal theorem is not
machine-checkable in general. It remains an attested assertion and both
statements should be displayed where readers can compare them.

An assessment may be proposed by anyone but enters the canonical record only
if it targets a precise statement, contains a substantive mathematical
argument, discloses relevant conflicts, avoids personal allegations, permits an
author response, and satisfies the contribution policy. Rejected submissions
do not become a public shame log.

## 6. Digestion and open work

Digestion is the differentiator from a metadata-only index, so v0.1 includes a
minimal attributed form:

```yaml
digestions:
  - audience: general_mathematician
    text: "..."
    basis: editorial_inference
    asserted_by: editor-id
    source_claims: [claim-main]

importance_claims:
  - text: "The manuscript compares the range with ..."
    basis: source_quote
    asserted_by: author-id
    source: {section: "1.1"}

open_invitations:
  - kind: correspondence
    target: "Trace Theorem 1.1 to declaration X."
    created_by: editor-id
    created_at: "..."
```

An invitation may be created by an author, reviewer, or editor. It should be a
bounded task that another person can actually take.

## 7. Lean adapter and trust boundary

The research-preview Lean adapter checks two narrow predicates at a pinned
commit:

1. Does the target compile under the stated toolchain and dependency lock?
2. Does its transitive axiom closure stay within a named, versioned policy such
   as `lean_standard_classical`, `lean_standard_classical_plus_native`, or
   `custom`?

This does not establish informal/formal correspondence, completeness of
hypotheses, mathematical novelty, or truth beyond the reported formal
predicate. A source scan separately rejects `debug.skip*` kernel-bypass options
that axiom closure cannot reveal.

Building an external Lean repository executes untrusted configuration and
dependencies. The adapter therefore separates:

- an untrusted, read-only, network-disabled, resource-limited build workflow;
- a trusted ingest workflow that never executes the target repository and can
  only propose a pull request.

Any missing or contradictory isolation evidence fails closed to
`external_formal_artifact`. The exact threat model and remaining holes are in
[`SECURITY.md`](../SECURITY.md). The adapter remains a research preview until a
real GitHub-hosted end-to-end run exercises the boundary.

## 8. Distribution and adoption

Default discovery for specialist tooling is effectively zero. Distribution has
two routes. Widely circulating organisational claims and major public
announcements may receive editorial records compiled from public evidence; the
record explicitly says whether its authors participated. Ordinary claims by
living individual authors enter through an author request or opt-in. In that
route, the initial mechanic is correction: prepare the record and ask whether
it is accurate rather than asking the author to fill the schema. Undisclosed AI
use is never investigated or alleged.

Records travel through author pages, repositories, forum discussions,
benchmark exports, and existing trackers. A tracker consuming the schema is a
stronger adoption signal than several authors privately correcting drafts.

Significance does not eliminate curation. Its hypothesis is that portable
records and automated invariant checking make each act of curation reusable
across trackers, authors, and readers. If nobody consumes or republishes the
records, it inherits the economics of discontinued manually curated indexes and
should stop.

## 9. Public versus synthetic records

`records/` is the public corpus and must contain only records whose public
sources were actually inspected. Synthetic demonstrations belong in
`examples/` or `tests/fixtures/` and are never rendered by the production
build. Plausible fictional people, identifiers, receipts, or paper IDs must not
appear on public record pages.

## 10. Deliberate deferrals

The following are outside v0.1:

- `refuted` or any global mathematical conclusion, until authority, evidence,
  appeal, and correction policies exist;
- `common_overstatements`, except as a future explicitly authored digestion;
- execution of arbitrary public submissions beyond the reviewed adapter
  boundary;
- reproduction outside Lean;
- cryptographic signing, badges, accounts, databases, hosted paid review, and
  interactive proof explanation.

## 11. Validation criteria

The project should measure rather than assert:

- **Comprehension:** do readers recover scope, version, and evidence state more
  quickly and accurately from a record?
- **Pilot response:** do matched authors correct, link, or publish records?
- **Interoperability:** does an external tracker consume or emit the format?
- **Behavior change:** does a third party take an `open_invitations` target or
  contribute attributable evidence they otherwise would not have produced?

If records never change anyone's behavior, Significance is documentation rather
than infrastructure and should be described that way.

## 12. Prior art

The closest adjacent projects include
[erdosproblems.com](https://www.erdosproblems.com/),
[Open Conjectures](https://openconjectures.org/), and AI-mathematics claim
indexes. Lean-side components include
[`leanprover-community/axiom-audit`](https://github.com/leanprover-community/axiom-audit),
[`leanprover/lean-eval`](https://github.com/leanprover/lean-eval), and
[`leanprover/comparator`](https://github.com/leanprover/comparator).
Significance's intended contribution is portable attributable state and
mechanical record invariants, not another competing list of conjectures.
