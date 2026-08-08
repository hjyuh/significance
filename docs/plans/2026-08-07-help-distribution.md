# Distributing the help — what comes after the "can a visitor get help?" release

Status: roadmap, nothing here is committed or built. Written the day the
five-feature help release landed on `feature/help-release`, to record what
the next gains actually are and in what order.

## The observation this rests on

The shipped release answered one question: can a visitor get help? Plain-
language strips, a signed explanation of what a result says, a request path,
actionable invitations, a status board, a glossary. All of it makes the site
*able* to help.

Two things it does not address, and they are where the remaining value is.

**Most people who need this help will never visit.** They are in a forum
thread, a Discord, a comment section, asking "is this real?" — and they will
not click through to a registry to find out.

**Help is also a thing you do, not only a thing you build.** The request door
now exists; its worth is set entirely by what happens after somebody knocks.

Everything below is distribution of help rather than capacity for it.

## 1. Help that travels — a copy-status export

A "copy status" control on every record and every board row, yielding a clean
plain-text paragraph: claim, checked, not checked, as of, link. Formatted to
paste into any thread as-is.

This is the thirty-second strip made portable. It turns every reader of the
site into a possible distributor of its help, and turns every answer anyone
gives in the wild into a receipt with a tail — the paste carries the link
back. Roughly an hour of work, and it multiplies the reach of everything
already built, which is why it is first.

Note for whoever builds it: the paragraph is a digest of material already in
the record, so it answers to the same rules as `plain_summary` — attributed,
no verdict language, never claiming more than the record. A copy button is a
rendering of the record, not a new assertion.

## 2. Suggested accurate wording

One line per record: **how to describe this claim accurately.** For example —
"OpenAI has published a claimed proof, formally checked by their own pipeline,
not yet independently reproduced."

Overstatement is the single most common way the public gets hurt by this news
cycle — "AI SOLVES 90-YEAR PROBLEM" — and the reason is rarely bad faith.
Precise language is *work*, and people writing to a deadline will take the
nearest available phrasing. Handing them the sentence is the cheapest possible
intervention on the highest-fan-out population: the people who inform everyone
else.

Note for whoever builds it: this is the field most likely to drift into a
verdict, and the field where a verdict would travel furthest. It should be a
new attributed block under the same lint as the other plain-language blocks,
and its wording should stay a suggestion rather than a mandate — this project
does not tell anyone what to write.

## 3. The evergreen orientation page

Somebody arriving from a news cycle does not need a record first. They need
the *situation* explained: one calm page, "AI and mathematics right now, in
plain words" — what is actually happening, what a Lean certificate does and
does not guarantee, what "independently verified" ought to mean, with links
out to the board and the glossary.

This is the digestion layer applied to the moment rather than to any one
proof, and it can be written honestly at claim-state level. It becomes the
link to give anyone who asks what is going on, which is a thing people now ask
weekly.

## 4. Plain-language strips in Arabic and French

Cheap for this project specifically — the maintainer works in both — and
serving readers essentially nobody else serves: the francophone North African
mathematics community, and Arabic-speaking students meeting these headlines
with no accessible sourcing at all.

Genuinely differentiating, personally authentic, and it plants the format in
those communities before anyone else thinks to. Doing it only for the board
and the largest records is already real help delivered where the supply of
help is thinnest.

Note for whoever builds it: a translated strip is a second `plain_summary`
with its own attribution, not a replacement for the first. Whoever translated
it is the asserter, and the language is part of the record rather than a
presentation setting.

## 5. Help by hand, with a promise attached

The request door exists. What decides its value is the answer.

- **A stated turnaround on requests** — "requests answered within 48 hours" —
  and then honoring it. A fast, careful reply to the *first* stranger is worth
  more than any feature, because that person becomes the story other people
  hear. The number is a decision for the maintainer, not for a build: a
  promise printed on a page and missed is worse than no promise, so it goes on
  `/request/` only when somebody is prepared to keep it.
- **The same for open invitations.** Somebody who takes a task gets a fast,
  grateful, thorough reply.
- **And the oldest form, needing no feature at all:** keep answering questions
  in threads directly, receipts attached. The office-hours behaviour that built
  this project's standing this year *is* the product, delivered by hand. The
  machinery exists so those answers scale and persist. It was never meant to
  replace the answering.

## The honest weighting

The largest available help-event this week still requires zero new code: the
summary post, linking the board, arriving in the threads where the confused
people already are.

Ship the help to where the need is. The site is now good enough to catch
whoever follows it back.
