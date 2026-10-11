# Significance project state — 8 October 2026

This snapshot accompanies the `codex/contribution-routes` development branch.
It describes code and local validation; a GitHub push is not proof of a deployed
website or working production authentication.

## Public baseline

The last confirmed deployment is `860910c149c5a99f5dd8a21bcdc90a5653de4541` on
`main`, with ten public YAML records and 25 explicit open/taken tasks. The
Erdős #1095 reading map has author-approved publication scope. Four other recent
maps remain unlisted. Records describe claims, sources, evidence and scoped work;
they do not certify mathematics.

## Work included in this branch

- Tasks are grouped by claim with numerical problem order, a jump list,
  open/taken counts, category ordering and full task targets.
- Questions, partial attempts and attestations have independent contribution
  routes. Discussion wording accommodates external hosts.
- `check_category: deslopping` adds **De-slopping / explanation rewrite**. When
  such tasks exist, the index links them to George Coote’s repository workflow.
  The category distinguishes readable adaptations from human-written rewrites;
  it does not imply collaboration, acceptance or mathematical review.
- Task pages have the requested short editor credit and a corrected contribution
  section background.
- A Firebase account/comment prototype is prepared, with a bundled browser
  client, database rules, emulator tests, public-task manifest and CI checks.
- The [6 October public proof-claim census](docs/audits/ep-proof-claim-census-2026-10-06.md)
  and its JSON source snapshot are included. It counted 291 indexed claims on
  213 problems, including 169 with no outside public comment. These are historical
  archive counts, not review or correctness judgments.

## Backend: strictly $0 route, not live

The selected route keeps GitHub Pages and uses Firebase Authentication plus
Firestore on the **Spark** plan. It does not require Cloudflare, Resend, a
purchased domain, SMS authentication or paid Firebase services. Keep billing off;
free quota exhaustion may make a feature unavailable. The verified service
limits and owner setup are in [free-backend.md](docs/free-backend.md).

The prototype supports email registration, verification, login, password reset,
logout, task comments and author deletion. Database rules enforce verified email,
maintainer-seeded task IDs, bounded fields, matching user IDs, timestamps and a
30-second posting cooldown. Moderator deletion is supported by rules and the
Firestore console. Comments do not enter record YAML or evidence counts.

No production Firebase project, web configuration, database or email delivery
has been established. The in-app Firebase console reported an error loading
terms-of-service acceptance status even after retry. A real owner-mediated
project setup and browser/cloud checks are still necessary. The existing
custom-password `feature/accounts-discussion` branch remains separate and is
not deployed by this change. It has a weaker prototype password work factor;
the selected Firebase route does not use it.

## Private material and other checkouts

Two schema-valid local drafts remain excluded from this push and public builds:
the community coordination record and the Erdős #3 / OpenAI family 159 rewrite
starter. Neither has an assigned reviewer, accepted rewrite or funding
commitment. Adding category support does not publish these drafts. Their scope
is described in [deslopping.md](docs/deslopping.md).

The original repository-root checkout is older and has extensive unreconciled
changes. It was not reset, overwritten or included wholesale. The About and
submission-wizard branches contain changes already represented on `main`; do
not merge them based only on differing commit IDs. See the
[checkout reconciliation](docs/reconciliation-2026-10-02.md) before continuing.

## Validation and next steps

Local checks passed: 174 Python tests and Python lint; 31 web tests and production
build; eight Firebase emulator tests covering the account flow and database
authorization. The production fixture guard passed, and the task manifest
contains 25 public tasks and neither private draft. CI also rebuilds the browser
bundle and checks reproducibility. Local emulator checks do not establish
production email delivery, quota behavior or browser compatibility.

Next steps:

1. Review this branch and its GitHub CI before merging. A push to `main` triggers
   the existing GitHub Pages workflow; a feature-branch push does not.
2. Create and configure a free Spark project, deploy the restrictive rules, seed
   only approved public tasks, and test with two ordinary accounts before
   enabling on-site comments.
3. Decide the publication scope for the local rewrite starter and coordination
   draft, following the project's source and author-participation policy.
4. Reconcile remaining original-checkout work separately. Preserve private
   correspondence and avoid inferring author approval or review from silence.
