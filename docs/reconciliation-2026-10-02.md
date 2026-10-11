# Development reconciliation — 2 October 2026

This local review follows the root `PROJECT-STATE-2026-10-02.md` snapshot.
`git fetch origin` confirmed `origin/main` at
`860910c149c5a99f5dd8a21bcdc90a5653de4541`. It does not establish the state of
the live hosted site or independently check any mathematical claim.

## What the older branches contain

| Checkout / branch | Finding against current `origin/main` | Next action |
| --- | --- | --- |
| Dirty root, `main` at `5a568ef` | Substantial renderer, app, record and generated-output changes. Several overlap later published changes; the local #4 record also has a counterpart in the current public corpus. | Preserve everything. Compare source changes individually against current code before porting; do not copy generated output or replace the current public record with the local variant. |
| `chore/about-page-and-homepage-readability` at `1091329` | Current `main` already has `/about/`, generated site configuration, claim-first cards and board explanations. The branch has older copy and lacks later renderer work. | Do not merge the branch wholesale. No missing About-page implementation was identified. |
| `feature/submission-wizard` at `2e577f5` | Wizard, submission gating and maiden Lean receipt are represented on `main` under different commits, including `2e7354b` and `593dee6`. Current code adds a reviewer-map step and later readability changes. | Keep the checkout until its remaining differences are reviewed; branch-only commit IDs do not imply missing functionality. |
| `feature/accounts-discussion` at `825bdde` | GitHub task discussion is already on `main` (`3ba5928`). Account routes and `db/` code remain separate; current architecture and handoff explicitly exclude accounts and a backend database. | Treat account work as an architecture decision requiring a separate scope, hosting plan and security review. Do not combine it with static-site fixes. |
| `tmp/github-pages-fix` at `d9b2dc2` | Snapshot reports generated-output changes. This pass did not reconcile those files. | Preserve until inspected. |
| `.worktrees/publish-ui` at `860910c` | Clean publication checkout. | Preserve as the confirmed publication baseline. |

## Current local continuation

`.worktrees/contribution-routes`, branch `codex/contribution-routes`, starts from
the fetched `origin/main`. It fixes independently configured task contribution
routes:

- Question and partial-attempt links depend on their own available URLs, rather
  than the scoped-attestation URL. A task can offer discussion without an
  attestation form, or an attestation form without a configured site repository.
- Missing routes render instructions instead of `href="None"` links or references
  to nonexistent controls.
- External discussion threads are described without assuming their host is
  GitHub. Scoped-check instructions use the template when no form is configured.
- Partial-attempt instructions ask for unresolved work in the existing template;
  they no longer imply an `outcome` field absent from that template.

Regression cases cover all four combinations of repository and attestation
configuration, URL-encoded source hash and scope, and the #1095 external forum.
No record YAML, author approval, task participation state or evidence was changed.
No publication or external messages were performed.

Validation for this continuation: 169 Python tests pass, Python lint is clean,
the ten public records validate, and the production fixture and unlisted-page
guards pass. Web lint, the production build and all 31 web tests pass (five
rendered-output tests and 26 submission tests). Generated task pages have been
rebuilt from the changed template; record sources are unchanged.

## Remaining work

### Task-list organization follow-up

The maintainer requested clearer organization of `/tasks/index.html`. The local
continuation groups all 25 actionable tasks under ten claim headings, with a jump
list and per-claim open/taken counts. Numbered venue problems sort numerically;
other claims sort by manuscript label. Within a claim, open tasks sort by check
category (statement, proof, computation, formalization, literature, exposition,
other), preserving source order within a category; taken tasks follow. Full task
targets remain visible. Unfilled effort estimates display as “Not estimated.”
Derived exposition gaps remain a separate disclosure.

Desktop and 390-pixel mobile previews were checked. All task destinations and
claim anchors are covered by regression checks. Validation passes: 171 Python
tests, 31 web tests, both linters, production build, record validation and both
publication guards. This layout has not been deployed.

1. Review this local change before any release, retaining the private-fixture and
   unlisted-page guards.
2. Reconcile remaining dirty-root source changes one feature at a time. Keep all
   private drafts and all current publication history intact.
3. Seek independent scoped reports for the existing review tasks. Author approval
   of a reading map and upstream CI do not complete those tasks.
4. Confirm outreach send dates and policy before calculating silence deadlines.
   This review establishes neither dates nor author responses.
