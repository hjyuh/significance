# Accounts and comments on a $0 plan

Prepared 8 October 2026; cloud setup updated 11 October 2026. The account/comment
route is configured for a production Firebase project, but is not deployed on
the public site and has not completed the live account test.

## Cloud setup status — 11 October 2026

Project `significance-5565c` remains on Spark. The Significance GitHub Pages web
app is registered, Email/Password is enabled, and `hjyuh.github.io` and
`localhost` are authorized. Email enumeration protection is enabled. The
default Standard Firestore database is in `nam5`; the repository's scoped
`firestore.rules` are published. Its 25 public task documents were checked
against `tasks_manifest.py` through an unauthenticated production read.

The public SDK configuration is included in the static assets. A local browser
preview connects to this project and reads production comments. The owner
reported completing email verification and posted a test comment, which is
visible in the production thread. The eight emulator rules tests pass, including
rejection of unverified accounts and forged authors. Password-reset delivery,
author deletion and the two-account production deletion check remain required
before calling this route ready for public use. Do not treat the emulator
results as completion of that live test.

The discussion UI separates sign-in, registration and password-reset forms,
adapts to narrow screens, and presents comments beside the account panel on
wide screens. “Check verification status” reloads the Firebase user and refreshes
the ID token; it does not mark an email verified. Posting remains protected by
the server-side rules. Display names are self-selected and are not identity
verification or evidence about the mathematics.

Authentication explicitly uses browser-local persistence: users stay signed in
across reloads and browser restarts until sign-out, subject to the browser
allowing storage (private sessions and cleared site data can end a session).
Signed-in users see their public display name and a sign-out control above the
composer; the sign-in/account panel is hidden and the discussion uses the full
available width.

Use the existing GitHub Pages site with Firebase Authentication and Cloud
Firestore on the **Spark** plan. No Cloud Functions, Cloud Run, paid Blaze
upgrade, SMS sign-in, purchased domain, Cloudflare or Resend is required.
Firebase handles email/password credentials, verification and password resets;
Firestore stores only public display names, user IDs and task comments.
Comments never enter the record YAML or evidence counts.

Sources checked:

- [Firebase pricing](https://firebase.google.com/pricing): Spark needs no payment
  method; Firestore includes 1 GiB stored, 50,000 reads/day and 20,000 writes/day.
- [Authentication limits](https://firebase.google.com/docs/auth/limits): email
  verification is capped at 1,000 emails/day and resets at 150 emails/day. Avoid phone/SMS
  authentication, which requires paid billing.
- [Firebase Authentication web setup](https://firebase.google.com/docs/auth/web/start).

Free quotas are limits, not an unlimited service guarantee. Keep the project on
Spark and do not attach billing; if demand exceeds its quotas, comments/auth may
stop working until quota resets. Loading comments reads up to 50 documents per
page visit; refresh is explicit rather than a live subscription.

## Local implementation

`backend/firebase/widget.js` provides registration, verification, login, reset,
logout, posting, reading and author deletion. It bundles to
`src/significance/static/discussion.js`. The task renderer includes its mount
point and module, with a Firebase-specific content security policy on task pages.
Without a public Firebase configuration file, the widget stays unavailable and
the existing contribution links still work.

`firestore.rules` requires a verified email, a maintainer-seeded task, the caller's
own user ID, bounded name/body fields and a server timestamp. Posting updates a
private per-user cooldown in the same atomic write; one comment is allowed per
30 seconds. Account creation abuse and service-wide floods still depend on
Firebase's controls and quotas. Display names are self-selected, not verified
real-world identities. Text is rendered using `textContent`.

Authors may delete their own comments. Maintainers can delete inappropriate
comments using the Firestore console. A `moderators/{UID}` document also grants
delete permission to that verified account; clients cannot appoint moderators.
The widget currently exposes author deletion only, so moderators use the console.
No public user directory or email addresses are stored in Firestore.

## Run the local checks

From `backend/firebase`:

```powershell
npm ci
npm run build
npm test
```

The rules tests use the local Firestore emulator under `demo-significance`;
they do not create cloud resources or contact a production database.

## Owner setup: no purchases

1. Open the [Firebase console](https://console.firebase.google.com/) using your
   Google account and create a project on **Spark**. Do not upgrade to Blaze or
   attach billing. Analytics is optional and unnecessary for this prototype.
2. Register a **Web app**. Copy its public web configuration into
   `src/significance/static/firebase-config.json`, using
   `backend/firebase/config.example.json` as the shape. These web identifiers
   are public; database authorization is enforced by the rules. Never put a
   service-account key or Google account credential into the site.
3. Enable Authentication → Email/Password. Add `hjyuh.github.io` to authorized
   domains. Add `localhost` explicitly for local HTTP testing if it is absent.
   Enable email enumeration protection and review the built-in verification
   and password-reset email templates. Keep the provider's default sender.
4. Create a Firestore database, then replace its rules with `firestore.rules`
   and publish them. Do not leave a database in permissive test mode.
5. Run `uv run python backend/firebase/tasks_manifest.py` at the repository root.
   For each intended public task, create a `tasks/{document_id}` document in the
   Firestore console, with its `record_id` and `task_id` string fields. Private
   drafts are excluded from this manifest. Do not seed private records into a
   production project. Refresh this list as public tasks change.
6. Build the normal public site, inspect it, and deploy only the approved public
   material. The currently prepared Erdős #3 record remains a private draft;
   this setup does not publish it or approve its publication.
7. Test with two ordinary accounts: register, verify, sign in, post, refresh,
   sign out, reset a password, and delete an owned comment. Test moderation in
   the console and check that a second account cannot delete another's comment.

An owner-mediated cloud account test is still required. Local emulator tests
do not prove production delivery, browser
compatibility or quota behavior. The older custom-password account branch stays
separate; it is not merged into this route.
