# Accounts and Discussion Layer — Implementation Plan (Phase 0–1)

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stand up the project's first database and a working
username/email/password authentication system, on proven infrastructure,
without touching any record, schema, or static-build behaviour.

**Architecture:** A Drizzle-managed database reached from the existing
Cloudflare Worker, plus API routes under `app/api/`. The Python CLI, the
record schema, `records/*.yaml`, and the static renderer are untouched
and must stay that way — see the boundary rule in
`docs/plans/2026-08-02-accounts-discussion-design.md` §2.

**Tech Stack:** Drizzle ORM + drizzle-kit, Cloudflare D1 (assumed —
see the gate below), Web Crypto (PBKDF2-HMAC-SHA256) for password
hashing, `node:test` + `tsx` for tests, matching the existing suite.

**Design doc:** `docs/plans/2026-08-02-accounts-discussion-design.md`.
Read it first. This plan does not restate its reasoning.

---

## Read this before Task 1

**Task 1 is a gate, not a formality.** Every later task assumes
Cloudflare D1. Nothing in this repository currently declares a database
binding, and the deploy target's actual database is unconfirmed — the
only evidence is that `build/sites-vite-plugin.ts:38-42` packages a
`drizzle/` directory into the deploy output.

If Task 1 shows the platform provides something other than D1
(Postgres, or a differently-named binding), **stop and report**. Tasks
2 onward need revision before they are safe to execute. Do not adapt
them yourself mid-flight.

**Scope of this plan:** Phase 0 (foundation) and Phase 1 (working
auth). Comments, profile pages, OAuth identity linking, and moderation
are deliberately not specified yet — they are outlined at the end and
get their own plan once this infrastructure is proven. Writing precise
code for them now would be speculation resting on Task 1's outcome.

**External prerequisites you cannot create yourself.** These block
specific tasks; surface them to the user early rather than at the point
of failure:

- An outbound email provider account and API key (Resend or Postmark).
  Blocks Task 12 onward. MailChannels' free Workers tier ended in 2024.
- A GitHub OAuth app (Phase 3, not this plan).
- An ORCID OAuth app (Phase 3, not this plan).

---

## Baseline

Before Task 1, confirm a green starting point:

```sh
uv run pytest -q
npm run lint
npm test
```

All three must pass. If they don't, stop and report — do not build on
a red baseline.

---

# Phase 0 — Foundation

## Task 1: Spike — prove a database round-trip (GATE)

**This task's output is throwaway.** Its only purpose is to answer:
can the Worker read and write a database, locally and on a real
deploy? Delete the spike before moving on.

**Files:**
- Temporarily modify: `vite.config.ts`
- Create then delete: `app/api/_spike/route.ts`

**Step 1: Declare a D1 binding**

In `vite.config.ts`, extend `localBindingConfig` (currently lines 8-11):

```ts
const localBindingConfig = {
  main: "./worker/index.ts",
  compatibility_flags: ["nodejs_compat"],
  d1_databases: [
    { binding: "DB", database_name: "significance", database_id: "local" },
  ],
};
```

**Step 2: Write a throwaway route**

Create `app/api/_spike/route.ts`:

```ts
export async function GET(request: Request) {
  const env = (request as unknown as { cf?: unknown; env?: Record<string, unknown> }).env;
  return Response.json({ bindings: env ? Object.keys(env) : null });
}
```

If that shape doesn't expose the environment under this framework
(`vinext`), find how the Worker's `env` reaches a route — check
`worker/index.ts` and vinext's app-router entry — and report what you
found. Discovering the binding-access pattern IS this task's work.

**Step 3: Prove a write and a read**

Once you can reach `env.DB`, run a round-trip:

```ts
await env.DB.prepare("CREATE TABLE IF NOT EXISTS _spike (id INTEGER PRIMARY KEY, v TEXT)").run();
await env.DB.prepare("INSERT INTO _spike (v) VALUES (?)").bind("hello").run();
const { results } = await env.DB.prepare("SELECT v FROM _spike").all();
```

Run `npm run dev`, hit the route, and confirm you get `hello` back.

**Step 4: Report before deleting**

Report explicitly:
- Does `env.DB` exist locally under Miniflare? Did the round-trip work?
- How does a route access `env` in this framework?
- Can you confirm anything about the *deployed* database — does the
  platform provision one, and under what binding name?

**Step 5: Delete the spike**

```sh
rm -rf app/api/_spike
git checkout vite.config.ts
```

Nothing from this task is committed. If the round-trip failed, or the
database is not D1, **stop here and report** — do not proceed to Task 2.

---

## Task 2: Install Drizzle and wire the D1 binding

**Files:**
- Modify: `package.json`, `vite.config.ts`, `worker/index.ts`
- Create: `drizzle.config.ts`

**Step 1: Install**

```sh
npm install drizzle-orm
npm install -D drizzle-kit
```

**Step 2: Make the binding permanent**

Apply the same `d1_databases` change to `vite.config.ts` as in Task 1
Step 1 — this time keeping it.

**Step 3: Declare it on the Worker's Env**

In `worker/index.ts`, extend the interface (currently lines 4-6):

```ts
interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
}
```

`D1Database` comes from `@cloudflare/workers-types`. Note that
`worker/index.ts:5` already has a pre-existing `Cannot find name
'Fetcher'` type error for exactly this reason — the types package isn't
installed. Fix that now:

```sh
npm install -D @cloudflare/workers-types
```

and add to `tsconfig.json`'s `compilerOptions`:

```json
"types": ["@cloudflare/workers-types"]
```

**Step 4: Drizzle config**

Create `drizzle.config.ts`:

```ts
import type { Config } from "drizzle-kit";

export default {
  schema: "./db/schema.ts",
  out: "./drizzle",
  dialect: "sqlite",
  driver: "d1-http",
} satisfies Config;
```

**Step 5: Verify the long-standing tsc error is gone**

Run: `npx tsc --noEmit`
Expected: **zero errors**. The `worker/index.ts` `Fetcher` error that
has been present throughout this repository's recent history should now
be resolved. If other errors appear, report them.

**Step 6: Commit**

```sh
git add package.json package-lock.json vite.config.ts worker/index.ts tsconfig.json drizzle.config.ts
git commit -m "build: add Drizzle and declare the D1 binding"
```

---

## Task 3: Password hashing (TDD)

Pure functions, no database, no framework. Fully testable in isolation
— write the tests first.

**Files:**
- Create: `db/password.ts`
- Create: `tests/password.test.ts`
- Modify: `package.json` (test script)

**Step 1: Write the failing tests**

Create `tests/password.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { hashPassword, verifyPassword } from "../db/password.ts";

test("hashPassword produces a self-describing string, not the password", async () => {
  const hash = await hashPassword("correct horse battery staple");
  assert.match(hash, /^pbkdf2\$\d+\$[A-Za-z0-9+/=]+\$[A-Za-z0-9+/=]+$/);
  assert.doesNotMatch(hash, /correct horse/);
});

test("the same password hashes differently every time (unique salt)", async () => {
  const a = await hashPassword("hunter2");
  const b = await hashPassword("hunter2");
  assert.notEqual(a, b);
});

test("verifyPassword accepts the right password", async () => {
  const hash = await hashPassword("hunter2");
  assert.equal(await verifyPassword("hunter2", hash), true);
});

test("verifyPassword rejects the wrong password", async () => {
  const hash = await hashPassword("hunter2");
  assert.equal(await verifyPassword("hunter3", hash), false);
});

test("verifyPassword rejects a malformed hash instead of throwing", async () => {
  assert.equal(await verifyPassword("hunter2", "not-a-hash"), false);
  assert.equal(await verifyPassword("hunter2", ""), false);
});

test("the iteration count is recoverable from the hash", async () => {
  const hash = await hashPassword("hunter2");
  const iterations = Number(hash.split("$")[1]);
  assert.ok(iterations >= 310_000, `expected >=310000 iterations, got ${iterations}`);
});
```

**Step 2: Run — expect FAIL**

```sh
node --import tsx --test tests/password.test.ts
```
Expected: cannot find module `../db/password.ts`.

**Step 3: Implement**

Create `db/password.ts`:

```ts
// Password hashing for Workers. Native bcrypt/argon2 are unavailable in
// this runtime, so this uses PBKDF2-HMAC-SHA256 via Web Crypto, which
// is. The iteration count is stored in the hash string so it can be
// raised later without invalidating existing hashes.
//
// Format: pbkdf2$<iterations>$<base64 salt>$<base64 derived key>

const DEFAULT_ITERATIONS = 310_000; // OWASP floor for PBKDF2-HMAC-SHA256
const SALT_BYTES = 16;
const KEY_BITS = 256;

const encoder = new TextEncoder();

function toBase64(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes));
}

function fromBase64(value: string): Uint8Array {
  return Uint8Array.from(atob(value), (c) => c.charCodeAt(0));
}

async function derive(password: string, salt: Uint8Array, iterations: number): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey("raw", encoder.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", hash: "SHA-256", salt, iterations },
    key,
    KEY_BITS,
  );
  return new Uint8Array(bits);
}

export async function hashPassword(password: string, iterations = DEFAULT_ITERATIONS): Promise<string> {
  const salt = crypto.getRandomValues(new Uint8Array(SALT_BYTES));
  const derived = await derive(password, salt, iterations);
  return `pbkdf2$${iterations}$${toBase64(salt)}$${toBase64(derived)}`;
}

// Constant-time comparison: always visits every byte, so timing does not
// leak how much of the hash matched.
function timingSafeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a[i] ^ b[i];
  return diff === 0;
}

export async function verifyPassword(password: string, stored: string): Promise<boolean> {
  const parts = stored.split("$");
  if (parts.length !== 4 || parts[0] !== "pbkdf2") return false;
  const iterations = Number(parts[1]);
  if (!Number.isInteger(iterations) || iterations <= 0) return false;
  try {
    const salt = fromBase64(parts[2]);
    const expected = fromBase64(parts[3]);
    const actual = await derive(password, salt, iterations);
    return timingSafeEqual(actual, expected);
  } catch {
    return false; // malformed base64
  }
}
```

**Step 4: Run — expect PASS**

```sh
node --import tsx --test tests/password.test.ts
```
Expected: 6 passing.

**Step 5: Add to the test script**

In `package.json`, append to `scripts.test`:

```
&& node --import tsx --test tests/password.test.ts
```

**Step 6: Measure the CPU cost — this is real, not optional**

The design doc flags that Workers bill CPU time and 310k PBKDF2
iterations is not free. Measure it:

```sh
node --import tsx -e "import('./db/password.ts').then(async (m) => { const t = Date.now(); await m.hashPassword('x'); console.log(Date.now() - t, 'ms'); })"
```

Report the number. If it exceeds ~100ms, flag it — a WASM argon2 build
or a lower iteration count may be needed, and that is a decision for
the user, not for you to make silently.

**Step 7: Commit**

```sh
git add db/password.ts tests/password.test.ts package.json
git commit -m "feat: PBKDF2 password hashing for the Workers runtime"
```

---

## Task 4: Session tokens (TDD)

Also pure. Same pattern: tests first.

**Files:**
- Create: `db/session-token.ts`
- Create: `tests/session-token.test.ts`
- Modify: `package.json`

**Step 1: Write the failing tests**

Create `tests/session-token.test.ts`:

```ts
import assert from "node:assert/strict";
import test from "node:test";
import { newSessionToken, hashSessionToken } from "../db/session-token.ts";

test("newSessionToken returns a long, url-safe, unguessable string", () => {
  const token = newSessionToken();
  assert.match(token, /^[A-Za-z0-9_-]{43}$/); // 32 bytes, base64url, unpadded
});

test("tokens are unique across many draws", () => {
  const seen = new Set(Array.from({ length: 500 }, () => newSessionToken()));
  assert.equal(seen.size, 500);
});

test("hashSessionToken is deterministic", async () => {
  const token = newSessionToken();
  assert.equal(await hashSessionToken(token), await hashSessionToken(token));
});

test("the hash is not the token — a database leak must not yield live sessions", async () => {
  const token = newSessionToken();
  const hash = await hashSessionToken(token);
  assert.notEqual(hash, token);
  assert.ok(!hash.includes(token));
});
```

**Step 2: Run — expect FAIL (module missing)**

**Step 3: Implement**

Create `db/session-token.ts`:

```ts
// Session tokens are random bearer credentials. The raw token goes to
// the client in a cookie; only its SHA-256 is stored, so a database
// leak does not hand an attacker usable sessions.

const TOKEN_BYTES = 32;
const encoder = new TextEncoder();

function toBase64Url(bytes: Uint8Array): string {
  return btoa(String.fromCharCode(...bytes)).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

export function newSessionToken(): string {
  return toBase64Url(crypto.getRandomValues(new Uint8Array(TOKEN_BYTES)));
}

export async function hashSessionToken(token: string): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", encoder.encode(token));
  return toBase64Url(new Uint8Array(digest));
}
```

**Step 4: Run — expect PASS (4 tests)**

**Step 5: Add to `package.json`'s test script, then commit**

```sh
git add db/session-token.ts tests/session-token.test.ts package.json
git commit -m "feat: session token generation and hashed storage"
```

---

## Task 5: Database schema and first migration

**Files:**
- Create: `db/schema.ts`
- Create (generated): `drizzle/*.sql`

**Step 1: Write the schema**

Create `db/schema.ts` with the tables from design §8. Only `users`,
`sessions`, and `email_tokens` in this migration — `comments` and
`identities` belong to later phases and adding them now would be
speculative.

```ts
import { sqliteTable, text, integer, uniqueIndex } from "drizzle-orm/sqlite-core";

export const users = sqliteTable("users", {
  id: text("id").primaryKey(),
  username: text("username").notNull(),
  usernameLower: text("username_lower").notNull(),
  email: text("email").notNull(),
  emailLower: text("email_lower").notNull(),
  emailVerifiedAt: integer("email_verified_at", { mode: "timestamp" }),
  passwordHash: text("password_hash").notNull(),
  displayName: text("display_name"),
  isModerator: integer("is_moderator", { mode: "boolean" }).notNull().default(false),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull(),
  deletedAt: integer("deleted_at", { mode: "timestamp" }),
}, (t) => ({
  usernameUnique: uniqueIndex("users_username_lower_unique").on(t.usernameLower),
  emailUnique: uniqueIndex("users_email_lower_unique").on(t.emailLower),
}));

export const sessions = sqliteTable("sessions", {
  id: text("id").primaryKey(),          // the token's SHA-256, never the token
  userId: text("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull(),
  expiresAt: integer("expires_at", { mode: "timestamp" }).notNull(),
});

export const emailTokens = sqliteTable("email_tokens", {
  id: text("id").primaryKey(),          // the token's SHA-256
  userId: text("user_id").notNull().references(() => users.id, { onDelete: "cascade" }),
  purpose: text("purpose", { enum: ["verify", "reset"] }).notNull(),
  createdAt: integer("created_at", { mode: "timestamp" }).notNull(),
  expiresAt: integer("expires_at", { mode: "timestamp" }).notNull(),
  usedAt: integer("used_at", { mode: "timestamp" }),
});
```

Note the `*_lower` columns: SQLite has no case-insensitive unique
constraint, so uniqueness is enforced on a normalised column while the
display form is preserved separately.

**Step 2: Generate the migration**

```sh
npx drizzle-kit generate
```
Expected: a new `.sql` file under `drizzle/`. Read it and confirm it
creates three tables and two unique indexes — do not commit a migration
you have not read.

**Step 3: Apply it locally and verify**

Apply the migration to the local D1 instance (the exact command depends
on what Task 1 established; with Wrangler it is
`npx wrangler d1 execute significance --local --file drizzle/<file>.sql`).
Confirm the tables exist.

**Step 4: Commit**

```sh
git add db/schema.ts drizzle/
git commit -m "feat: users, sessions, and email_tokens schema"
```

---

# Phase 1 — Authentication

Tasks 6–13 cover registration, email verification, login, logout, and
the current-user helper. **These are specified at a lower level of
detail than Phase 0 on purpose**: they depend on how routing and `env`
access actually work in this framework, which Task 1 determines. Expand
each into concrete steps once Task 1 has reported.

## Task 6: Database client helper
`db/client.ts` — wraps `drizzle(env.DB, { schema })`, one place that
knows how to turn a Worker `Env` into a typed Drizzle instance.

## Task 7: Input validation (TDD)
`db/validate.ts` — username rules (length, allowed characters,
reserved names), email shape, password minimum length. Pure functions,
tested in isolation before any route uses them.

## Task 8: Registration endpoint
`POST /api/auth/register`. Hashes the password, inserts the user,
creates a `verify` email token. **Returns an identical response whether
or not the email is already registered** — see design §9 on
enumeration. Rate limited.

## Task 9: Session issue and read
Create a session row, set the cookie (`httpOnly; Secure; SameSite=Lax`),
and a `currentUser(request, env)` helper that resolves a request to a
user or null. Expired sessions are rejected and cleaned up.

## Task 10: Login and logout
`POST /api/auth/login` — verify password, issue a session. Uniform
failure message for both unknown user and bad password. Rate limited.
`POST /api/auth/logout` — delete the session row, clear the cookie.

## Task 11: Origin check on mutations
Shared middleware rejecting state-changing requests whose `Origin` does
not match. `SameSite=Lax` alone is not sufficient CSRF protection.

## Task 12: Email provider integration
**Blocked on the user supplying a provider account and API key.** A
`db/email.ts` wrapper with one `sendEmail` function, the key read from
Worker secrets and never committed. A dry-run mode that logs instead of
sending keeps local development from needing credentials.

## Task 13: Email verification flow
`GET /api/auth/verify?token=…` — validate the token, mark
`email_verified_at`, single-use. Tokens expire. This is what unlocks
commenting in Phase 2.

---

# Not in this plan

Phase 2 (comments API, rendering, author-hide, moderator-delete and its
notification email), Phase 3 (profile page, GitHub and ORCID identity
linking, badges), and Phase 4 (the §2 boundary test, and the
`README.md` / `docs/design.md` / `SECURITY.md` amendments plus the
privacy note) each get their own plan, written once the infrastructure
below them is proven.

One item from Phase 4 is worth stating now so it is not forgotten: the
boundary test asserting that `significance build` output is
byte-identical with an empty and a populated comment database is the
mechanical guarantee that this entire feature has not compromised
record portability. It is the single most important test in the
feature, and it should be written as early as Phase 2 makes it possible.
