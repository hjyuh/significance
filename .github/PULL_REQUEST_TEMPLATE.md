## What kind of change is this?

- [ ] New record
- [ ] New evidence item on an existing record (version bump)
- [ ] Correction to an existing record (version bump)
- [ ] Non-record change (docs, tooling, schema, CI)

## For a new record or new evidence item

- [ ] I am an author of this claim, **or** I'm recording someone else's
      public work and every `author_attestation` I used has a `locator`
      backing it (see `CONTRIBUTING.md`).
- [ ] `mathematical_assessment` items (if any) satisfy the admissibility
      checklist in `CONTRIBUTING.md` / `docs/moderation.md`.
- [ ] `formal_artifact` / `computational_reproduction` evidence (if any)
      came from CI or the Lean adapter — not hand-typed.
- [ ] `significance validate records/` passes locally.

## For a correction

- [ ] `record_version` increases.
- [ ] Nothing in `history[]` was deleted or mutated — corrections add new
      events.
