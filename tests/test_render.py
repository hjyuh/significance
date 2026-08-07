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
from pathlib import Path

from significance.records import load_record
from significance.render import build_site, safe_href

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = REPO_ROOT / "records"
EXAMPLE_RECORD = REPO_ROOT / "examples" / "synthetic-ramsey-k7.yaml"
PUBLIC_RECORD_ID = "2026-openai-nonsofic-groups"
BROKEN_DIR = REPO_ROOT / "tests" / "fixtures" / "broken"
HOSTILE_DIR = REPO_ROOT / "tests" / "fixtures" / "hostile"


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

    assert result.built == [PUBLIC_RECORD_ID]
    assert result.skipped == {}
    assert (out / "index.html").exists()
    assert (out / "index.json").exists()
    assert (out / PUBLIC_RECORD_ID / "index.html").exists()
    assert (out / "static" / "style.css").exists()

    source = load_record(RECORDS_DIR / f"{PUBLIC_RECORD_ID}.yaml")
    summaries = json.loads((out / "index.json").read_text(encoding="utf-8"))
    assert summaries == [
        {
            "record_id": source["record_id"],
            "record_version": source["record_version"],
            "record_state": source["record_state"],
            "claim": source["claim"]["text"]["value"],
            "claim_basis": source["claim"]["text"]["basis"],
            "claim_asserted_by": source["claim"]["text"]["asserted_by"],
            "freshness": source["freshness"]["result"],
            "freshness_checked_at": source["freshness"]["checked_at"],
            "evidence_count": len(source["evidence"]),
            "open_invitation_count": len(source["open_invitations"]),
        }
    ]

    record_html = (out / PUBLIC_RECORD_ID / "index.html").read_text(encoding="utf-8")
    assert all(line == line.rstrip() for line in record_html.splitlines())
    assert "Content-Security-Policy" in record_html
    assert "What this does not establish" in record_html
    # No scores/badges/verdict language (word-boundary: "ai_provenance" is a
    # legitimate heading and contains "proven" as a substring).
    lower = record_html.lower()
    for banned in ("verified", "proven", "score", "badge"):
        assert not re.search(rf"\b{banned}\b", lower), banned


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
    assert "href=\"javascript:" not in lower
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
    assert 'href="../static/style.css"' in page
    assert 'href="/request/"' not in page


def test_pages_out_moves_auxiliary_pages_to_the_site_root(tmp_path):
    records_out = tmp_path / "public" / "records"
    pages_out = tmp_path / "public"
    build_site(RECORDS_DIR, records_out, pages_out=pages_out)

    page = (pages_out / "request" / "index.html").read_text(encoding="utf-8")
    # Deployed: record pages live under /records/ and these do not, so no
    # relative path spans both and the links are absolute.
    assert 'href="/records/"' in page
    assert 'href="/records/static/style.css"' in page

    record_page = (records_out / PUBLIC_RECORD_ID / "index.html").read_text(encoding="utf-8")
    assert 'href="/request/"' in record_page


def test_nav_omits_a_page_this_build_did_not_write(tmp_path):
    # A nav entry pointing at a page that was not built is a 404 the visitor
    # blames on themselves. The link and the page arrive together or not at all.
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    index = (out / "index.html").read_text(encoding="utf-8")
    assert "Request a record" in index
    assert "glossary" not in index.lower()


def test_request_page_carries_the_consent_rule_and_the_issue_link(tmp_path):
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / "request" / "index.html").read_text(encoding="utf-8")

    assert "issues/new?template=record-request.yml" in page
    # The moderation policy's outreach rule, restated where a requester will
    # actually meet it rather than only in a docs file they will not read.
    assert "contacted" in page
    assert "no decline list" in page


def test_an_unconfigured_contact_address_produces_no_mailto(tmp_path):
    # A link to an invented address would let somebody believe they had asked
    # when nobody received anything. The message body is offered as text
    # instead, and the page says why.
    out = tmp_path / "site"
    config = tmp_path / "site.yaml"
    config.write_text(
        'repository_url: "https://example.org/repo"\n'
        'contact_email: "[FILL: maintainer address]"\n',
        encoding="utf-8",
    )
    build_site(RECORDS_DIR, out, site_config=config)

    page = (out / "request" / "index.html").read_text(encoding="utf-8")
    assert "mailto:" not in page
    assert "No contact address is configured" in page


def test_a_configured_contact_address_produces_a_templated_mailto(tmp_path):
    out = tmp_path / "site"
    config = tmp_path / "site.yaml"
    config.write_text(
        'repository_url: "https://example.org/repo"\n'
        'contact_email: "records@example.org"\n',
        encoding="utf-8",
    )
    build_site(RECORDS_DIR, out, site_config=config)

    page = (out / "request" / "index.html").read_text(encoding="utf-8")
    assert "mailto:records@example.org?subject=" in page
    # The same three fields as the issue form, in the same order.
    assert "Link%20to%20the%20claim" in page
    assert "Your%20role" in page
    assert "What%20you%20want%20tracked" in page


def test_safe_email_refuses_anything_that_could_break_out_of_a_mailto():
    from significance.render import safe_email

    assert safe_email("records@example.org") == "records@example.org"
    assert safe_email("  records@example.org  ") == "records@example.org"
    assert safe_email("[FILL: maintainer address]") is None
    assert safe_email("records@example.org?bcc=someone@else.test") is None
    assert safe_email("records@example.org&body=x") is None
    assert safe_email("not-an-address") is None
    assert safe_email(None) is None
