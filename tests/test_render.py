"""Phase 3: static renderer tests.

Two concerns: `build` only renders records that actually validate (and
duplicate-record-id, a cross-record check, must still catch a duplicate
even though each file is rendered individually — see the render.py
comment about validating the whole directory up front), and every
record-derived string reaching the page is escaped, including URLs that
Jinja's autoescape alone would not neutralize (a `javascript:` href).
"""

from __future__ import annotations

import re
from pathlib import Path

from significance.render import build_site, safe_href

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = REPO_ROOT / "records"
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

    assert "2026-sandoval-ramsey-k7" in result.built
    assert result.skipped == {}
    assert (out / "index.html").exists()
    assert (out / "2026-sandoval-ramsey-k7" / "index.html").exists()
    assert (out / "static" / "style.css").exists()

    record_html = (out / "2026-sandoval-ramsey-k7" / "index.html").read_text(encoding="utf-8")
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
        (RECORDS_DIR / "2026-sandoval-ramsey-k7.yaml").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    # missing-manuscript-hash.yaml is derived from the same base example, so
    # it shares record_id "2026-sandoval-ramsey-k7" with good.yaml above --
    # give it a distinct id so this test isolates "missing hash", not the
    # (separately tested) duplicate-record-id case.
    bad_text = (BROKEN_DIR / "missing-manuscript-hash.yaml").read_text(encoding="utf-8")
    bad_text = bad_text.replace(
        "record_id: 2026-sandoval-ramsey-k7", "record_id: 2026-bad-example-record"
    )
    assert "2026-bad-example-record" in bad_text
    (records_dir / "bad.yaml").write_text(bad_text, encoding="utf-8")

    result = build_site(records_dir, tmp_path / "site")

    assert result.built == ["2026-sandoval-ramsey-k7"]
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
