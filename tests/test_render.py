"""Phase 3: static renderer tests.

Two concerns: `build` only renders records that actually validate (and
duplicate-record-id, a cross-record check, must still catch a duplicate
even though each file is rendered individually — see the render.py
comment about validating the whole directory up front), and every
record-derived string reaching the page is escaped, including URLs that
Jinja's autoescape alone would not neutralize (a `javascript:` href).
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from significance.boards import load_board
from significance.records import load_record
from significance.render import build_site, load_glossary, mathml, problem_slug, safe_href

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = REPO_ROOT / "records"
EXAMPLE_RECORD = REPO_ROOT / "examples" / "synthetic-ramsey-k7.yaml"
PUBLIC_RECORD_ID = "2026-openai-nonsofic-groups"
PUBLIC_RECORD_IDS = [
    "2026-alexchengyuli-erdos-848",
    "2026-anthropic-zeta-two-thirds",
    PUBLIC_RECORD_ID,
    "2026-rafikzeraoulia-erdos-653",
    "2026-rafikzeraoulia-erdos-726",
]
BROKEN_DIR = REPO_ROOT / "tests" / "fixtures" / "broken"
HOSTILE_DIR = REPO_ROOT / "tests" / "fixtures" / "hostile"
DRAFTS_DIR = REPO_ROOT / "drafts" / "records"


def test_safe_href_allows_only_http_https():
    assert safe_href("https://example.org/x") == "https://example.org/x"
    assert safe_href("http://example.org/x") == "http://example.org/x"
    assert safe_href("javascript:alert(1)") is None
    assert safe_href("data:text/html,<script>alert(1)</script>") is None
    assert safe_href("vbscript:msgbox(1)") is None
    assert safe_href(None) is None
    assert safe_href(123) is None


def test_build_produces_index_and_record_page(tmp_path):
    out = tmp_path / "site"
    result = build_site(RECORDS_DIR, out)

    assert result.built == PUBLIC_RECORD_IDS
    assert result.skipped == {}
    assert (out / "index.html").exists()
    assert (out / "index.json").exists()
    for record_id in PUBLIC_RECORD_IDS:
        assert (out / record_id / "index.html").exists()
    assert (out / "static" / "style.css").exists()

    summaries = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert sorted(summaries) == ["boards", "records"]
    sources = [load_record(RECORDS_DIR / f"{record_id}.yaml") for record_id in PUBLIC_RECORD_IDS]
    assert summaries["records"] == [
        {
            "record_id": source["record_id"],
            "record_version": source["record_version"],
            "record_state": source["record_state"],
            "claim": source["claim"]["text"]["value"],
            "claim_mathml": str(mathml(source["claim"].get("display_math", "")))
            if source["claim"].get("display_math")
            else None,
            "claim_basis": source["claim"]["text"]["basis"],
            "claim_asserted_by": source["claim"]["text"]["asserted_by"],
            "freshness": source["freshness"]["result"],
            "freshness_checked_at": source["freshness"]["checked_at"],
            "evidence_count": len(source["evidence"]),
            "open_invitation_count": len(source["open_invitations"]),
        }
        for source in sources
    ]

    record_html = (out / PUBLIC_RECORD_ID / "index.html").read_text(encoding="utf-8")
    assert all(line == line.rstrip() for line in record_html.splitlines())
    assert "Content-Security-Policy" in record_html
    assert "Limits" in record_html
    assert "Author involvement" in record_html
    assert "Review activity" in record_html
    assert "Formalization handoff" in record_html
    assert "Paper/code correspondence" in record_html
    assert "OpenAI did not participate in or confirm this Significance record" in record_html
    assert "Math assessments</dt><dd>0" in record_html
    assert "Summary" in record_html and "Significance" in record_html
    assert "Record note" in record_html and "Significance" in record_html
    assert "Confirming a description would not confirm the mathematics" not in record_html
    lower = record_html.lower()
    for banned in ("verified", "proven", "score", "badge"):
        assert not re.search(rf"\b{banned}\b", lower), banned


def test_problem_pages_and_frontier_are_generated_with_resolving_links(tmp_path):
    out = tmp_path / "site"
    result = build_site(RECORDS_DIR, out)

    assert "problems" in result.pages
    assert "problem:erdosproblems-com-653" in result.pages
    assert "frontier" in result.pages
    problem_index = (out / "problems" / "index.html").read_text(encoding="utf-8")
    problem_page = (
        out / "problems" / "erdosproblems-com-653" / "index.html"
    ).read_text(encoding="utf-8")
    frontier = (out / "frontier" / "index.html").read_text(encoding="utf-8")
    assert "problems/erdosproblems-com-653/index.html" in problem_index
    assert "../2026-rafikzeraoulia-erdos-653/index.html" in problem_page
    assert "../2026-rafikzeraoulia-erdos-653/index.html" in frontier
    assert "A task someone can pick up" in frontier


def test_deployed_problem_and_frontier_links_target_records_root(tmp_path):
    records_out = tmp_path / "public" / "records"
    pages_out = tmp_path / "public"
    build_site(RECORDS_DIR, records_out, pages_out=pages_out)
    problem_page = (
        pages_out / "problems" / "erdosproblems-com-653" / "index.html"
    ).read_text(encoding="utf-8")
    frontier = (pages_out / "frontier" / "index.html").read_text(encoding="utf-8")
    assert "/records/2026-rafikzeraoulia-erdos-653/index.html" in problem_page
    assert "/records/2026-rafikzeraoulia-erdos-653/index.html" in frontier


def test_problem_slug_is_stable_and_ascii():
    assert problem_slug("ErdősProblems.com", "653") == "erdosproblems-com-653"


def test_build_produces_problem_json_and_atom_feed(tmp_path):
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)

    problem_json = out / "problems" / "erdosproblems-com-653" / "index.json"
    assert problem_json.exists()
    payload = json.loads(problem_json.read_text(encoding="utf-8"))
    assert payload["export_schema_version"] == 1
    assert payload["kind"] == "significance_problem"
    assert payload["venue"] == "ErdősProblems.com"
    assert payload["problem_id"] == "653"
    assert payload["records"][0]["record_id"] == "2026-rafikzeraoulia-erdos-653"
    assert "_stale" not in problem_json.read_text(encoding="utf-8")

    feed = ET.parse(out / "feed.xml")
    atom = "{http://www.w3.org/2005/Atom}"
    assert feed.getroot().tag == f"{atom}feed"
    entries = feed.findall(f"{atom}entry")
    assert len(entries) == len(PUBLIC_RECORD_IDS)
    ids = {entry.findtext(f"{atom}id") for entry in entries}
    assert all(any(record_id in entry_id for record_id in PUBLIC_RECORD_IDS) for entry_id in ids)


def test_nested_pages_keep_navigation_at_site_root(tmp_path):
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)

    for path in (
        out / "problems" / "erdosproblems-com-653" / "index.html",
        out / "reviewers" / "significance-ci" / "index.html",
    ):
        html = path.read_text(encoding="utf-8")
        assert 'href="../../orientation/index.html"' in html
        assert 'href="../../static/style.css?v=' in html
        assert 'href="../../feed.xml"' in html
        assert 'href="../orientation/index.html"' not in html


def test_scoped_task_pages_and_index_are_generated(tmp_path):
    out = tmp_path / "site"
    result = build_site(RECORDS_DIR, out)
    assert "tasks" in result.pages
    task_index = (out / "tasks" / "index.html").read_text(encoding="utf-8")
    task_page = (
        out
        / "tasks"
        / "2026-rafikzeraoulia-erdos-653"
        / "restricted-center-incidence"
        / "index.html"
    ).read_text(encoding="utf-8")
    assert "5 bounded tasks" in task_index or "bounded tasks" in task_index
    assert "a87ca77b143fd6382ce3882fbef2320c3d037ed92d4128fe078689784bfc4147" in task_page
    assert "Open attestation form" in task_page
    assert "State what you checked and found" in task_page
    assert "restricted-center-incidence" in task_page


def test_source_inspection_does_not_count_as_written_review(tmp_path):
    # Living-author drafts are kept outside the public repository. When the
    # private fixture bundle is absent (as it is in a clean checkout), the
    # public corpus cannot exercise this privacy-only rendering assertion.
    draft_fixture = DRAFTS_DIR / "2026-zeraoulia-erdos-653.yaml"
    if not draft_fixture.exists():
        return
    out = tmp_path / "draft-site"
    result = build_site(DRAFTS_DIR, out)

    assert result.skipped == {}
    page = (out / "2026-zeraoulia-erdos-653" / "index.html").read_text(encoding="utf-8")
    assert "Source inspection" in page
    assert "This is not a mathematical review." in page
    assert "Written reviews</dt><dd>0" in page
    assert "Non-public editorial draft." in page
    assert "Publication state</dt><dd>Editorial draft" in page


def test_build_skips_invalid_records_but_still_builds_valid_ones(tmp_path):
    records_dir = tmp_path / "records"
    records_dir.mkdir()
    (records_dir / "good.yaml").write_text(
        EXAMPLE_RECORD.read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # Give the broken fixture a distinct id so this test remains focused on
    # the missing hash rather than cross-record identity.
    bad_text = (BROKEN_DIR / "missing-manuscript-hash.yaml").read_text(encoding="utf-8")
    bad_text = bad_text.replace(
        "record_id: 0000-example-synthetic-ramsey-k7", "record_id: 2026-bad-example-record"
    )
    assert "2026-bad-example-record" in bad_text
    (records_dir / "bad.yaml").write_text(bad_text, encoding="utf-8")

    result = build_site(records_dir, tmp_path / "site")

    assert result.built == ["0000-example-synthetic-ramsey-k7"]
    assert str(records_dir / "bad.yaml") in result.skipped
    assert result.skipped[str(records_dir / "bad.yaml")][0].rule == "missing-manuscript-hash"


def test_build_skips_both_duplicate_record_id_files(tmp_path):
    # Regression test: build() used to validate each file in isolation, so
    # the cross-record duplicate-record-id check never saw sibling records
    # and silently built two pages that would collide at the same URL.
    result = build_site(BROKEN_DIR / "duplicate-record-id", tmp_path / "site")

    assert result.built == []
    assert len(result.skipped) == 2
    for violations in result.skipped.values():
        assert any(v.rule == "duplicate-record-id" for v in violations)


def test_hostile_content_is_fully_escaped(tmp_path):
    out = tmp_path / "site"
    result = build_site(HOSTILE_DIR, out)
    assert result.built == ["2026-hostile-example"]

    html = (out / "2026-hostile-example" / "index.html").read_text(encoding="utf-8")
    lower = html.lower()

    # No literal tag ever survives unescaped. (The substring "onerror=alert"
    # legitimately appears as inert text once its surrounding angle brackets
    # are escaped -- what actually matters is that no unescaped "<" precedes it.)
    assert "<script" not in lower
    assert "<img src=x onerror=" not in lower

    # The record contains several javascript: URLs; none may become a live link.
    assert 'href="javascript:' not in lower
    assert "javascript:alert" in html  # present, but only as escaped plain text

    # Math notation is shown as inert plain text, not interpreted.
    assert "e^{i\\pi}+1=0" in html or "e^{i\\pi}+1=0$" in html

    # Escaped forms of the payloads are present (proof escaping actually ran).
    assert "&lt;script&gt;" in html
    assert "&lt;img" in html

    assert "Content-Security-Policy" in html
    assert "script-src" not in html.lower() or "'none'" in html  # no permissive script-src


# --- auxiliary pages (Feature 3 onward) -------------------------------------
#
# /request/, and the two output layouts every auxiliary page has to work in.


def test_request_page_is_built_beside_the_records_by_default(tmp_path):
    out = tmp_path / "site"
    result = build_site(RECORDS_DIR, out)

    assert "request" in result.pages
    page = (out / "request" / "index.html").read_text(encoding="utf-8")
    # Self-contained: every link is relative, so the directory works when
    # opened from disk or served from any prefix.
    assert 'href="../index.html"' in page
    assert 'href="../static/style.css?v=' in page
    assert 'href="/request/"' not in page


def test_pages_out_moves_auxiliary_pages_to_the_site_root(tmp_path):
    records_out = tmp_path / "public" / "records"
    pages_out = tmp_path / "public"
    build_site(RECORDS_DIR, records_out, pages_out=pages_out)

    page = (pages_out / "request" / "index.html").read_text(encoding="utf-8")
    # Deployed: record pages live under /records/ and these do not, so no
    # relative path spans both and the links are absolute.
    assert 'href="/records/index.html"' in page
    assert 'href="/records/static/style.css?v=' in page

    record_page = (records_out / PUBLIC_RECORD_ID / "index.html").read_text(encoding="utf-8")
    assert 'href="/request/index.html"' in record_page


def test_nav_omits_a_page_this_build_did_not_write(tmp_path):
    # A nav entry pointing at a page that was not built is a 404 the visitor
    # blames on themselves. The link and the page arrive together or not at all.
    out = tmp_path / "site"
    build_site(
        RECORDS_DIR,
        out,
        glossary_path=tmp_path / "absent.yaml",
        boards_dir=tmp_path / "none",
    )
    index = (out / "index.html").read_text(encoding="utf-8")

    assert "Request or correct a record" in index  # built, so linked
    assert "glossary" not in index.lower()  # not built, so not linked
    assert "boards/" not in index

    # And with both present, both are linked.
    full = tmp_path / "full"
    build_site(RECORDS_DIR, full)
    full_index = (full / "index.html").read_text(encoding="utf-8")
    assert "glossary/index.html" in full_index
    assert "boards/ten-results/index.html" in full_index


def test_request_page_carries_the_consent_rule_and_the_issue_link(tmp_path):
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / "request" / "index.html").read_text(encoding="utf-8")

    assert "issues/new?template=record-request.yml" in page
    # The moderation policy's outreach rule, restated where a requester will
    # actually meet it rather than only in a docs file they will not read.
    assert "author request or opt-in" in page
    assert "no decline list" in page


def test_an_unconfigured_contact_address_produces_no_mailto(tmp_path):
    # A link to an invented address would let somebody believe they had asked
    # when nobody received anything. The message body is offered as text
    # instead, and the page says why.
    out = tmp_path / "site"
    config = tmp_path / "site.yaml"
    config.write_text(
        'repository_url: "https://example.org/repo"\ncontact_email: "[FILL: maintainer address]"\n',
        encoding="utf-8",
    )
    build_site(RECORDS_DIR, out, site_config=config)

    page = (out / "request" / "index.html").read_text(encoding="utf-8")
    assert "mailto:" not in page
    assert "No contact address is configured" not in page
    assert "Reply directly to that message" in page
    assert "Silence is never represented as" in page


def test_a_configured_contact_address_produces_a_templated_mailto(tmp_path):
    out = tmp_path / "site"
    config = tmp_path / "site.yaml"
    config.write_text(
        'repository_url: "https://example.org/repo"\ncontact_email: "records@example.org"\n',
        encoding="utf-8",
    )
    build_site(RECORDS_DIR, out, site_config=config)

    page = (out / "request" / "index.html").read_text(encoding="utf-8")
    assert "mailto:records@example.org?subject=" in page
    # The same three fields as the issue form, in the same order.
    assert "Link%20to%20the%20claim" in page
    assert "Your%20role" in page
    assert "Optional%20%E2%80%94%20what%20should%20change%20or%20receive%20attention" in page


def test_safe_email_refuses_anything_that_could_break_out_of_a_mailto():
    from significance.render import safe_email

    assert safe_email("records@example.org") == "records@example.org"
    assert safe_email("  records@example.org  ") == "records@example.org"
    assert safe_email("[FILL: maintainer address]") is None
    assert safe_email("records@example.org?bcc=someone@else.test") is None
    assert safe_email("records@example.org&body=x") is None
    assert safe_email("not-an-address") is None
    assert safe_email(None) is None


def test_take_this_task_appears_only_where_instructions_exist(tmp_path):
    # The affordance is keyed off `how`. A record whose invitations carry none
    # renders exactly as it did before the feature: no button over an empty
    # task, which promises help that is not there.
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / PUBLIC_RECORD_ID / "index.html").read_text(encoding="utf-8")

    record = load_record(RECORDS_DIR / f"{PUBLIC_RECORD_ID}.yaml")
    with_how = [i for i in record["open_invitations"] if i.get("how")]
    assert len(with_how) == 3
    assert page.count("Take this task") == sum(
        1 for i in with_how if i.get("status", "open") == "open"
    )
    assert "Report what you found" in page


def test_invitation_instructions_name_the_revision_the_record_pins(tmp_path):
    # The point of the instructions is that somebody can act on them without
    # asking us anything. That means the exact commit and the toolchain, and
    # both must be the ones this record already carries rather than a second,
    # drifting copy.
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / PUBLIC_RECORD_ID / "index.html").read_text(encoding="utf-8")

    record = load_record(RECORDS_DIR / f"{PUBLIC_RECORD_ID}.yaml")
    formal = next(e for e in record["evidence"] if e["kind"] == "formal_artifact")
    assert formal["commit"] in page
    assert formal["toolchain"]["pin"][7:19] in page
    assert record["manuscript"]["sha256"][:12] in page


# --- status boards (Feature 5) ----------------------------------------------


def test_board_renders_with_its_rows_and_is_linked_from_the_index(tmp_path):
    out = tmp_path / "site"
    result = build_site(RECORDS_DIR, out)

    assert "board:ten-results" in result.pages
    page = (out / "boards" / "ten-results" / "index.html").read_text(encoding="utf-8")

    board = load_board(REPO_ROOT / "boards" / "ten-results.yaml")
    assert board["title"] in page
    for row in board["rows"]:
        assert row["result"] in page

    recorded = next(row for row in board["rows"] if row.get("record"))
    assert f'href="../../{recorded["record"]}/index.html"' in page
    assert "index.html2026-" not in page

    summaries = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert summaries["boards"] == [
        {
            "board_id": "ten-results",
            "title": board["title"],
            "as_of": board["as_of"],
            "row_count": len(board["rows"]),
            "recorded_row_count": len([r for r in board["rows"] if r["state"] == "recorded"]),
        }
    ]


def test_board_states_no_verdict_and_uses_no_status_colour(tmp_path):
    # Every colour-coded status light is a verdict wearing a colour, which is
    # the one thing this project does not render. The rows say what was
    # checked in words or say nothing.
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / "boards" / "ten-results" / "index.html").read_text(encoding="utf-8").lower()

    for word in ("verified", "refuted", "confirmed", "passed ✓", "status-green", "status-red"):
        assert word not in page, f"board page contains {word!r}"
    assert "empty row means nobody has looked" in page


def test_placeholder_rows_say_so_rather_than_being_hidden(tmp_path):
    # Nine empty rows is the honest picture of how much of the release anyone
    # here has examined. A board showing only its one filled row would be more
    # flattering and much less useful.
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / "boards" / "ten-results" / "index.html").read_text(encoding="utf-8")

    board = load_board(REPO_ROOT / "boards" / "ten-results.yaml")
    placeholders = [r for r in board["rows"] if r["state"] == "placeholder"]
    assert len(placeholders) == 9
    assert page.count("Nobody here has researched this result yet") == len(placeholders)


def test_an_invalid_board_is_skipped_rather_than_rendered(tmp_path):
    # Same rule as an invalid record: a page rendered from a document nobody
    # checked is worse than a missing page, because it looks the same as a
    # checked one.
    boards_dir = tmp_path / "boards"
    boards_dir.mkdir()
    (boards_dir / "broken.yaml").write_text(
        "kind: board\nschema_version: 1\nboard_id: broken\n", encoding="utf-8"
    )
    out = tmp_path / "site"
    result = build_site(RECORDS_DIR, out, boards_dir=boards_dir)

    assert not (out / "boards" / "broken").exists()
    assert any("broken.yaml" in f for f in result.skipped)
    assert not any(p.startswith("board:") for p in result.pages)


# --- glossary ----------------------------------------------------------------


def test_glossary_page_lists_every_term_with_an_anchor(tmp_path):
    out = tmp_path / "site"
    result = build_site(RECORDS_DIR, out)

    assert "glossary" in result.pages
    page = (out / "glossary" / "index.html").read_text(encoding="utf-8")

    glossary = load_glossary()
    assert len(glossary) >= 17
    for slug, entry in glossary.items():
        assert f'id="term-{slug}"' in page
        assert entry["definition"].split()[0] in page


def test_terms_in_a_record_page_are_keyboard_reachable_links(tmp_path):
    # Not <abbr title>: a title tooltip is unreachable by keyboard in every
    # major browser, so it fails exactly the readers most likely to need the
    # definition. A link is focusable, needs no JavaScript, and still gives the
    # hover definition to a mouse user.
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / PUBLIC_RECORD_ID / "index.html").read_text(encoding="utf-8")

    assert 'class="term"' in page
    assert "<abbr" not in page
    glossary = load_glossary()
    definition = glossary["claim"]["definition"].strip()
    assert f'href="../glossary/index.html#term-claim" title="{definition}"' in page


def test_a_build_without_a_glossary_has_no_dead_term_links(tmp_path):
    out = tmp_path / "site"
    missing = tmp_path / "no-glossary.yaml"
    build_site(RECORDS_DIR, out, glossary_path=missing)

    assert not (out / "glossary").exists()
    page = (out / PUBLIC_RECORD_ID / "index.html").read_text(encoding="utf-8")
    assert 'class="term"' not in page
    assert "glossary" not in page.lower()
    # And the label the term would have carried is still there as plain text.
    assert "Evidence" in page


def test_a_definition_stating_a_verdict_is_refused(tmp_path):
    # Widest blast radius in the build: a definition carrying a verdict would
    # put it on every page its term appears on.
    out = tmp_path / "site"
    bad = tmp_path / "glossary.yaml"
    bad.write_text(
        "terms:\n"
        "  - slug: claim\n"
        "    term: claim\n"
        '    definition: "A statement the site has checked and found correct."\n',
        encoding="utf-8",
    )
    result = build_site(RECORDS_DIR, out, glossary_path=bad)

    assert not (out / "glossary").exists()
    assert any(
        v.rule == "verdict-language" for violations in result.skipped.values() for v in violations
    )


def test_placeholder_fill_slots_never_reach_the_page(tmp_path):
    # The [FILL] artifact slots exist so an editor can see which values a row
    # wants. They are not for readers: the renderer's placeholder branch prints
    # the row's name and the "nobody has looked" line and nothing else, so the
    # page never shows a half-filled table of markers.
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / "boards" / "ten-results" / "index.html").read_text(encoding="utf-8")

    board = load_board(REPO_ROOT / "boards" / "ten-results.yaml")
    placeholders = [r for r in board["rows"] if r["state"] == "placeholder"]
    # One marker per row, from its name slot -- not three.
    assert page.count("[FILL: verify from release]") == len(placeholders)
    assert "Manuscript" not in page.split("Nobody here has researched")[1]
