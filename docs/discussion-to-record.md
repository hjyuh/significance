# From discussion to a durable record

Significance does not treat a GitHub comment as a review, evidence, or a
mathematical conclusion. Discussion is useful when it identifies a bounded
piece of work; the durable object is created later through the ordinary pull
request workflow.

## The promotion path

```text
reader notices a passage
        ↓
needs-checking issue (one location, one question, one source revision)
        ↓
reviewer takes the task or replies with what they checked
        ↓
maintainer drafts a record entry with the reviewer's identity and basis
        ↓
pull request + validator + human review
        ↓
append-only record update, linked back to the original issue
```

Nothing is promoted automatically. Opening an issue does not create evidence,
assign a reviewer, or change the status of a claim. A maintainer may close an
issue without a record update when the question is too broad, unsupported, or
already represented elsewhere.

## Which issue to use

- **Suggest a focused check** when you identified a passage that needs
  attention but have not checked it yourself. This proposes a `needs_checking`
  entry; it is a reading request, not a verdict.
- **Response to an open invitation** when you actually ran or read the task
  named on a record. Include the exact manuscript hash, commit, or toolchain
  you used. A negative result is still useful.
- **Record request** when a claim has no Significance record yet. This starts
  intake; it does not publish a record.

Use one issue for one bounded question. “Is this whole paper correct?” is not
an actionable task. “Does the proof of Lemma 3.3 use Hypothesis 3.1 at the
point marked on page 8 of PDF hash `…`?” is.

## How a maintainer records the result

The maintainer copies the relevant response into the smallest fitting field:

| What happened | Record object | Required attribution |
| --- | --- | --- |
| A passage still needs attention | `review_map.needs_checking` | named asserter and source issue |
| A person read a bounded passage and reports what they saw | `informal_review` or an attestation | reviewer, scope, source hash, date |
| A person gives a substantive argument about a precise result | `mathematical_assessment` | named asserter, basis, target, report |
| A build, computation, or formal artifact was reproduced | matching evidence kind | machine receipt or explicit external report |

The PR must link the issue and state what was copied, paraphrased, or left out.
The original issue remains a discussion trail; the record is the version-bound,
append-only publication. A short review note must describe the reader's work,
not say merely that a proof is “correct” or “wrong.”

## For a person taking a task

You do not need to edit YAML. Open the invitation's response link and report:

1. the record and task;
2. the exact source revision you used;
3. what you read or ran;
4. what happened, including a failed or inconclusive attempt;
5. links to logs or a report, if available;
6. how you would like to be identified (name or handle).

The maintainer will propose the record change for your review. You can correct
the wording before it is merged. Attribution is not inferred from technical
ability, GitHub activity, or agreement with another reviewer.

## Safety and epistemic boundaries

Claims about people, priority, motives, or mathematical truth do not belong in
the promotion path. A promoted entry records that a named person reported a
bounded piece of work; it does not turn that report into consensus or a
verdict.
