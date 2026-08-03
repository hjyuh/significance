# Accounts and the discussion layer — design

Status: approved, not yet implemented. See `docs/design.md`,
`docs/moderation.md`, and `SECURITY.md` for the invariants and policies
this builds on — and §9 for the ones it openly amends.

## 1. What this adds, and what it deliberately is not

A comments section on record pages, gated behind registration. Accounts
use username + email + password; a profile page offers an optional
"connect identity" step linking GitHub and/or ORCID.

This is the project's first backend, first database, first stored
credentials, and first stored personal data. `README.md` and
`docs/design.md` currently list accounts and databases as out of scope
for v0.1. That is being reversed deliberately, not quietly — see §9.

What it is not: a replacement for the record format's attributed
evidence. Discussion is discussion. Nothing said in a comment carries
the standing of an `informal_review` or a `mathematical_assessment`,
and nothing in a comment is ever an assertion the record makes.

## 2. The boundary rule

**No comment content ever enters a record.** Concretely, nothing in the
discussion layer reaches `records/*.yaml`, `public/records/index.json`,
or the static record pages the Python renderer produces. The renderer
gains zero awareness that comments exist. Discussion is fetched
client-side from the Worker's API and rendered in a section explicitly
labeled as not part of the record.

The property this preserves is portability: a record consumed by
another tracker is the same record whether or not anyone ever commented
on it. Records stay files; conversation stays conversation.

This is mechanically testable, and the test is worth writing: the output
of `significance build` must be byte-identical with an empty comment
database and a full one. If that test ever fails, the boundary has
leaked.

Corollary: comments are **not** durable in the sense records are. They
live in one database, they are not in git, they are not append-only,
and they do not survive the database. Anything that deserves durability
should be promoted (§7), not left in a comment.

## 3. Authentication versus identity verification

These are separate concerns and the design keeps them separate.

- **Authentication** answers "are you the same person who created this
  account." That is username + email + password.
- **Identity verification** answers "are you specifically this GitHub
  user, this ORCID." That is an optional OAuth link, initiated from the
  profile page, never used as a login method in v1.

The split maps onto the record format's own epistemics.
`verification_method.kind` exists precisely to record what an assertion
is worth, and it already admits `pseudonymous` alongside `orcid`. So an
account with no linked identity is simply a pseudonymous participant.
Participation is not gatekept; provenance is made visible. This is the
same move the record format already makes when it renders a claim with
no evidence as a claim with no evidence rather than refusing it.

Badges therefore reuse the schema's existing vocabulary rather than
inventing a parallel one. A comment displays its author's strongest
verification:

| linked identity | badge              |
|-----------------|--------------------|
| ORCID           | `orcid`            |
| GitHub          | `github_identity`  |
| none            | `pseudonymous`     |

Verified email is the baseline requirement for every account (§4), so
it is not a distinguishing badge and `email_confirmation` is not used
here.

A commenter who is later named as a party in an actual record already
has an established, matching verification method. There is one identity
vocabulary in this project, not two.

## 4. What gates commenting

Register → confirm email → comment. Email verification is required;
`users.email_verified_at` must be non-null for any write to `comments`.
Linking GitHub or ORCID is optional and affects only the badge.

Email is consequently a hard dependency: verification and password
reset both require an outbound mail provider (MailChannels withdrew its
free Workers tier in 2024, so this means an account and an API key with
a service such as Resend or Postmark). This is new operational surface
for a project that previously had none.

## 5. Moderation: the author hides, the moderator deletes

- **Authors hide their own comments.** Reversible, self-service. A
  hidden comment stops rendering publicly and can be unhidden by its
  author. This is `comments.hidden_at`.
- **Moderators delete.** Irreversible, a hard row delete. No tombstone
  is rendered in the thread, and no public moderation log exists.

The assignment is deliberate: the reversible power belongs to the
person whose words they are; the irreversible one to the maintainer.

The public-silence half follows `docs/moderation.md` directly. That
document rejects a visible rejection log on the grounds that it "would
itself function as a public shame mechanism," and requires that any
outreach-tracking mechanism be "structurally incapable of accumulating
a list of people who said no." A hard delete with no tombstone and no
log accumulates nothing about anyone. A conventional
`[comment removed by moderator]` placeholder would violate that stance,
which is why this design does not have one.

The author is told. A single email is sent at deletion; nothing
persistent is written anywhere. This closes the one honest objection to
silent removal — that the affected person is left to wonder — without
creating the durable public mark the policy rules out.

Accepted consequence, stated plainly: hard deletion means there is no
appeal and no audit trail. For a single-maintainer project this is the
right trade, and it is the same trade `moderation.md` already makes for
rejected assessments. It should be revisited if moderation is ever
delegated to more than a handful of people.

## 6. Comment shape

Flat, not threaded. Each comment may carry an optional `anchor` — a
free-text pointer at a spot in the manuscript or record, e.g.
`"Prop 4.2"` — which is more useful here than nested replies and is
what makes clustering possible later. Threading is easy to add and hard
to remove; it stays out of v1.

Bodies are bounded (≤4000 characters), stored and rendered as plain
text with escaping. No HTML, no markdown rendering in v1 — a comment
section is not a place to introduce an XSS surface for a formatting
convenience.

## 7. Promotion is the bridge to the record

A comment that turns out to matter should not stay a comment. The
discussion section offers **promote**, which opens the existing
submission wizard prefilled with the comment's text and anchor as a
draft `informal_review` or `mathematical_assessment` evidence item.

The submitter then goes through the ordinary path: the wizard's
validation, a pull request, CI, and editor review. Nothing is promoted
automatically, and promotion confers no standing by itself — it is a
starting point for a submission, not a shortcut past review.

This is also the honest answer to "why keep comments ephemeral": the
route from conversation to durable attributed record exists, it runs
through the same gate everything else does, and a human takes
responsibility at the point of crossing.

## 8. Data model

Drizzle-managed SQLite. `build/sites-vite-plugin.ts` already packages a
`drizzle/` directory into the deploy output, so the migration pipeline
exists and is currently unused.

- **users** — `id`, `username` (unique, lowercased for uniqueness),
  `email` (unique, lowercased), `email_verified_at` (nullable; non-null
  required to comment), `password_hash`, `display_name`,
  `is_moderator`, `created_at`, `deleted_at`
- **identities** — `id`, `user_id`, `provider` (`github` | `orcid`),
  `provider_account_id`, `handle`, `verified_at`.
  Unique `(provider, provider_account_id)` so one external account
  cannot verify two site accounts; unique `(user_id, provider)`.
- **sessions** — token stored hashed, `user_id`, `expires_at`,
  `created_at`
- **comments** — `id`, `record_id` (plain text, deliberately not a
  foreign key — records live in git, not in this database), `user_id`,
  `body`, `anchor` (nullable), `created_at`, `hidden_at` (nullable).
  No `deleted_at`: moderator deletion removes the row.
- **email_tokens** — `user_id`, `purpose` (`verify` | `reset`),
  `token_hash`, `expires_at`, `used_at`

Account deletion hard-deletes the user's rows, including their
comments. Storing personal data creates deletion obligations; retaining
the content of someone who asked to leave would cut against them.

## 9. Security and privacy

- **Password hashing.** PBKDF2-HMAC-SHA256 via Web Crypto, per-user
  16-byte salt, iteration count stored alongside each hash. Native
  bcrypt/argon2 are unavailable on Workers.

  **The work factor is deliberately below the OWASP floor, and this
  document will not pretend otherwise.** Measured cost is roughly
  76ms at 310,000 iterations, against a 10ms CPU ceiling on a
  free-tier Worker — about 8x over budget. The default is therefore
  25,000 iterations (~6ms), which is roughly 24x weaker than the
  current OWASP recommendation of 600,000. This was an explicit,
  informed choice to keep the project free to run, not an oversight.

  Three things bound the consequences:

  1. **It is reversible.** Because the iteration count lives in each
     stored hash, raising the default leaves existing hashes verifying
     at their old count while new ones use the higher value. Accounts
     upgrade silently once a rehash-on-verify path exists.
  2. **A server-side pepper compensates.** The PBKDF2 output is
     HMAC-SHA256'd with a secret held in Worker configuration before
     storage, at a cost of microseconds. A database-only breach is
     therefore not exploitable without also compromising the secret,
     which is the specific risk a low iteration count exposes.
  3. **Rate limiting matters more here than the work factor.** Against
     online guessing — the likely threat for a site this size — login
     rate limiting is the real control, and iteration count is
     irrelevant. The work factor only governs offline cracking after a
     dump, which layer 2 already degrades.

  What is honestly given up: against an attacker holding both the
  database and the pepper, weak and reused passwords fall roughly 24x
  faster than they would at the OWASP floor. Users should not reuse
  passwords here. That is true of any site, and more true of this one.

  **Unverified assumption.** The 10ms ceiling is Cloudflare's Workers
  Free limit. This project deploys via OpenAI Sites, whose actual CPU
  limit has not been measured. If Sites provides more headroom, the
  default should be raised — see point 1; nothing about that is
  difficult.
- **Sessions.** 32 random bytes, stored SHA-256'd, so a database leak
  does not hand over live sessions. Cookies `httpOnly; Secure;
  SameSite=Lax`, with an origin check on every mutation.
- **Rate limiting** on registration, login, comment creation, and email
  sends.
- **Enumeration.** Registration and password-reset responses are
  identical whether or not the address is already known.
- **Secrets.** OAuth client secrets and the mail provider API key are
  the project's first runtime secrets. They belong in Worker secrets,
  never in `vite.config.ts` or any committed file.

Documentation that must be amended, openly:

- `README.md` and `docs/design.md` both list accounts and databases as
  out of scope for v0.1. Both are corrected, with the reversal stated
  rather than silently dropped.
- `SECURITY.md` is currently scoped entirely to the Lean adapter's
  threat model. It gains a section covering stored credentials, stored
  personal data, session handling, and the fact that the discussion
  layer is not part of the record and carries none of the record
  format's guarantees.
- A privacy note is required: what is stored, why, and how to delete
  it. The project has never needed one before.

## 10. Out of scope for this iteration

Threaded replies; markdown or LaTeX rendering in comment bodies;
notifications beyond the two transactional emails (verify, reset) and
the deletion notice; OAuth as a login method; moderator roles beyond a
single `is_moderator` flag; comment editing; reactions or voting of any
kind; any aggregate count of comments rendered on the record index or
card, which would turn discussion volume into a score.

The `timeline` and `read_reports` features specified separately remain
separate, remain YAML, and are not replaced by this. The discussion
layer is where conversation happens; those features are where reading
labor becomes durable attributed record content. §7 is the bridge.

## 11. Testing

- The boundary test of §2: `significance build` output is byte-identical
  with an empty and a populated comment database.
- Password hashing round-trip, and a test that the stored hash is not
  the password.
- Session tokens are stored hashed — a test asserting the raw token
  does not appear in the database.
- Email verification genuinely gates comment creation.
- Author-hide is reversible; moderator-delete removes the row.
- Unique constraints on `identities` actually prevent one GitHub
  account from verifying two site accounts.
- Comment bodies are escaped on render; a hostile fixture carrying
  markup is worth adding, mirroring `tests/fixtures/hostile/`.
