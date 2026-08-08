"""The status paragraph: this project's help, in a form that travels.

The people most in need of what a record holds are not on this site. They are
in a forum thread, a Discord, a comment section, asking whether something is
real, and they will not click through to a registry to find out. What reaches
them is what somebody else pastes into the thread.

So every record and every filled board row renders a short plain-text block
built to be pasted as-is: what is claimed, what has been checked, what has not,
as of when, and a link back. It is the thirty-second strip made portable, and
it turns each answer given in the wild into something with a tail — the paste
carries the link, so whoever reads it can arrive here and see the rest.

**It asserts nothing new.** Every line is a restatement of material already in
the record, which is what lets it inherit the record's attribution rather than
needing its own: the paragraph names who said it and links where they said it.
The same rules as `plain_summary` therefore apply upstream, in the validator,
before any of this runs.

**No clipboard button, and that is a deliberate trade.** The rendered pages
ship `Content-Security-Policy: default-src 'none'` with no script anywhere, so
a copy button would mean admitting JavaScript to every record page to save one
keystroke. The block is rendered selectable instead, in a monospace box that
makes its boundaries obvious. If a button is ever wanted badly enough, the
thing to weigh is a script-src exception on this one page against what the
strict policy currently buys.
"""

from __future__ import annotations

#: Kept short enough to survive a Discord message and a Hacker News comment box
#: without being folded, and long enough to carry the not-checked line, which
#: is the line most likely to be dropped by somebody summarising in a hurry.
WRAP_WIDTH = 76


def _wrap(text: str, width: int = WRAP_WIDTH) -> list[str]:
    """Greedy wrap.

    `textwrap` would do this and would also collapse the paragraph's internal
    structure in ways that differ by Python version; this is four lines and
    behaves identically everywhere, which matters for a string that is compared
    byte-for-byte in the suite.
    """
    words = text.split()
    if not words:
        return []
    lines = [words[0]]
    for word in words[1:]:
        if len(lines[-1]) + 1 + len(word) <= width:
            lines[-1] = f"{lines[-1]} {word}"
        else:
            lines.append(word)
    return lines


def _paragraph(label: str, body: str) -> list[str]:
    if not body or not body.strip():
        return []
    return [*_wrap(f"{label} {body.strip()}"), ""]


def record_status_text(record: dict, url: str | None = None) -> str:
    """The paste-ready status of one record.

    Falls back through what the record actually has: the suggested wording if
    there is one, then the plain summary, then the claim itself. A record with
    none of the plain-language blocks still produces something useful rather
    than nothing, because the claim and the freshness date are always there.
    """
    summary = record.get("plain_summary") or {}
    wording = (record.get("accurate_wording") or {}).get("value")
    freshness = record.get("freshness") or {}

    lines: list[str] = []

    headline = wording or summary.get("claimed") or record["claim"]["text"]["value"]
    lines.extend(_wrap(headline.strip()))
    lines.append("")

    lines.extend(_paragraph("Checked:", summary.get("checked", "")))
    lines.extend(_paragraph("Not checked:", summary.get("not_checked", "")))

    status_line = f"As of {freshness.get('checked_at', 'unknown')}"
    if freshness.get("result"):
        status_line += f" (freshness: {freshness['result']})"
    lines.append(status_line)

    # The link is what makes the paste a receipt rather than an assertion:
    # whoever reads it can come and check. Omitted rather than faked when no
    # public URL is configured — see data/site.yaml.
    if url:
        lines.append(f"Full record: {url}")

    lines.append("Significance records evidence. It does not judge the mathematics.")

    return "\n".join(lines).strip() + "\n"


def board_row_status_text(board: dict, row: dict, url: str | None = None) -> str:
    """The paste-ready status of one board row.

    "Nobody has looked at this yet" is a real answer to "is this real?", and
    this produces one — but the renderer asks for it only where the row has a
    name, because a paragraph that cannot say which result it is about is not
    an answer to anything. A board row still carrying its [FILL] marker gets no
    paste.
    """
    lines: list[str] = [*_wrap(row.get("result", "").strip()), ""]

    if row.get("state") == "placeholder":
        lines.extend(
            _wrap(
                "Nobody at Significance has researched this result yet. "
                "There is no claim, no link and no status recorded for it. "
                "An empty row means nobody has looked, not that nothing is there."
            )
        )
    else:
        claim = (row.get("claim") or {}).get("value")
        if claim:
            lines.extend(_wrap(claim.strip()))
            lines.append("")
        status = row.get("status") or {}
        lines.extend(_paragraph("Checked:", status.get("checked", "")))
        lines.extend(_paragraph("Not checked:", status.get("not_checked", "")))
        if status.get("as_of"):
            lines.append(f"As of {status['as_of']}")

    if url:
        lines.append(f"Board: {url}")
    lines.append("Significance records evidence. It does not judge the mathematics.")

    return "\n".join(lines).strip() + "\n"
