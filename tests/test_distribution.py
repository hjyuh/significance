"""The five distribution features: help that reaches people who never visit.

The shipped release made the site able to help. These make the help travel --
a paste-able status paragraph, a suggested sentence for whoever is writing
about a claim, an orientation page for the reader who arrived from a headline,
translated summaries, and a stated turnaround on requests.

What the suite guards is the same property in every one of them: a block
written to be copied somewhere this project has no control over must not carry
a verdict, must not exceed the record, and must say who wrote it.
"""

from __future__ import annotations

from html import unescape
from pathlib import Path

from significance.boards import load_board
from significance.export_text import board_row_status_text, record_status_text
from significance.records import load_record
from significance.render import build_site, load_orientation, orientation_violations
from significance.semantics import ACCURATE_WORDING_MAX_WORDS, semantic_violations

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = REPO_ROOT / "records"
EXAMPLE_RECORD = REPO_ROOT / "examples" / "synthetic-ramsey-k7.yaml"
PUBLIC_RECORD_ID = "2026-openai-nonsofic-groups"


def _rules(violations):
    return {v.rule for v in violations}


def _public_record():
    return load_record(RECORDS_DIR / f"{PUBLIC_RECORD_ID}.yaml")


# --- the status paragraph ---------------------------------------------------


def test_status_paragraph_carries_the_four_questions_and_the_link():
    record = _public_record()
    text = record_status_text(record, "https://example.org/records/x/")

    assert record["accurate_wording"]["value"].split()[0] in text
    assert "Checked:" in text
    assert "Not checked:" in text
    assert record["freshness"]["checked_at"] in text
    assert "https://example.org/records/x/" in text
    # The disclaimer travels with it, because the paste arrives somewhere this
    # project cannot add context to afterwards.
    assert "does not judge the mathematics" in text


def test_status_paragraph_omits_the_link_rather_than_guessing_one():
    # A paste carrying a wrong URL is worse than one carrying none: the reader
    # who follows it blames themselves.
    assert "http" not in record_status_text(_public_record(), None)


def test_status_paragraph_falls_back_through_what_the_record_has():
    record = _public_record()
    del record["accurate_wording"]
    assert record["plain_summary"]["claimed"].split()[0] in record_status_text(record)

    del record["plain_summary"]
    # No plain-language blocks at all still produces something useful: the
    # claim and the date are always there.
    text = record_status_text(record)
    assert record["claim"]["text"]["value"] in text
    assert record["freshness"]["checked_at"] in text


def test_status_paragraph_wraps_for_a_comment_box():
    text = record_status_text(_public_record(), "https://example.org/x/")
    for line in text.splitlines():
        # URLs may run over; prose may not.
        assert len(line) <= 76 or line.startswith(("Full record:", "Board:"))


def test_board_row_paragraph_says_nobody_has_looked():
    board = load_board(REPO_ROOT / "boards" / "ten-results.yaml")
    placeholder = next(r for r in board["rows"] if r["state"] == "placeholder")
    text = board_row_status_text(board, placeholder)
    assert "Nobody at Significance has researched this result yet" in text


def test_the_page_renders_the_paragraph_without_a_script(tmp_path):
    # No copy button: these pages ship default-src 'none' with no script, and a
    # button would mean admitting JavaScript to every record page to save one
    # keystroke.
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / PUBLIC_RECORD_ID / "index.html").read_text(encoding="utf-8")

    assert 'class="copy-status-text"' in page
    assert "<script" not in page.lower()
    assert "onclick" not in page.lower()
    assert "navigator.clipboard" not in page


def test_a_board_row_with_no_name_gets_no_paste(tmp_path):
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / "boards" / "ten-results" / "index.html").read_text(encoding="utf-8")
    # One paste block, for the one row that has a name.
    assert page.count("Copy this row into a thread") == 1


# --- suggested accurate wording ---------------------------------------------


def _with_wording(value):
    record = load_record(EXAMPLE_RECORD)
    record["accurate_wording"] = {
        "value": value,
        "basis": "digest",
        "asserted_by": "editor-mz",
        "asserted_at": "2026-07-28T09:00:00Z",
    }
    return record


def test_accurate_wording_is_held_to_a_headline_length():
    record = _with_wording(" ".join(["word"] * (ACCURATE_WORDING_MAX_WORDS + 1)))
    assert _rules(semantic_violations(record)) == {"accurate-wording-too-long"}


def test_accurate_wording_may_not_contain_a_verdict():
    # The field exists to stop overstatement, so a verdict inside it is the
    # exact failure it was built to prevent -- and it is written to be pasted
    # somewhere nobody will see the attribution that would have qualified it.
    record = _with_wording("A correct proof of the seven-point case, checked end to end.")
    assert _rules(semantic_violations(record)) == {"verdict-language"}


def test_the_shipped_wording_names_who_checked_and_what_is_undone():
    value = _public_record()["accurate_wording"]["value"].lower()
    assert "its own pipeline" in value
    assert "has not been traced" in value


# --- translations ------------------------------------------------------------


def test_translations_are_second_summaries_with_their_own_asserter():
    record = _public_record()
    translations = record["plain_summary"]["translations"]
    assert {t["lang"] for t in translations} == {"fr", "ar"}
    for translation in translations:
        assert translation["asserted_by"] in record["parties"]
        assert translation["basis"] == "digest"
        # A translation that quietly drops the not-checked line is the easiest
        # way for a strip in a language the maintainer reads less fluently to
        # become an endorsement.
        assert translation["not_checked"].strip()


def test_a_translation_may_not_carry_a_verdict():
    record = _public_record()
    record["plain_summary"]["translations"][0]["checked"] = "La preuve est correcte."
    assert "verdict-language" in _rules(semantic_violations(record))


def test_two_translations_in_one_language_are_refused():
    record = _public_record()
    translations = record["plain_summary"]["translations"]
    translations.append(dict(translations[0]))
    assert "duplicate-translation-language" in _rules(semantic_violations(record))


def test_translated_strips_render_with_language_and_direction(tmp_path):
    out = tmp_path / "site"
    build_site(RECORDS_DIR, out)
    page = (out / PUBLIC_RECORD_ID / "index.html").read_text(encoding="utf-8")

    assert 'lang="fr"' in page
    # Arabic is right-to-left; the attribution line under it is not.
    assert 'lang="ar" dir="rtl"' in page
    assert 'lang="en" dir="ltr"' in page


# --- orientation -------------------------------------------------------------


def test_orientation_page_explains_the_situation_and_is_attributed(tmp_path):
    out = tmp_path / "site"
    result = build_site(RECORDS_DIR, out)

    assert "orientation" in result.pages
    # Unescaped, because a heading like "What 'independently verified' should
    # mean" is correctly rendered with &#39; and the test is about the content
    # being present, not about the escaping (which other tests cover).
    page = unescape((out / "orientation" / "index.html").read_text(encoding="utf-8"))

    orientation = load_orientation()
    for section in orientation["sections"]:
        assert section["heading"] in page
        assert f'id="{section["id"]}"' in page
    # Every section says whose reading it is: the page makes claims about the
    # world, not findings the site discovered.
    assert page.count("Significance editor") >= len(orientation["sections"])


def test_orientation_separates_what_a_checker_does_from_what_it_does_not():
    orientation = load_orientation()
    ids = [s["id"] for s in orientation["sections"]]
    assert "what-lean-does" in ids
    assert "what-lean-does-not" in ids
    does_not = next(s for s in orientation["sections"] if s["id"] == "what-lean-does-not")
    assert "translation" in does_not["body"]


def test_an_orientation_section_stating_a_verdict_is_refused():
    orientation = load_orientation()
    orientation["sections"][0]["body"] = "Every one of these results is correct."
    assert _rules(orientation_violations(orientation)) == {"verdict-language"}


def test_a_failing_orientation_page_is_skipped_not_rendered(tmp_path):
    out = tmp_path / "site"
    bad = tmp_path / "orientation.yaml"
    bad.write_text(
        'title: "x"\n'
        'as_of: "2026-08-07T00:00:00Z"\n'
        "intro:\n"
        '  value: "These proofs are correct."\n'
        "  basis: digest\n"
        "  asserted_by: significance-editor\n"
        '  asserted_at: "2026-08-07T00:00:00Z"\n'
        "sections: []\n",
        encoding="utf-8",
    )
    result = build_site(RECORDS_DIR, out, orientation_path=bad)

    assert not (out / "orientation").exists()
    assert any(
        v.rule == "verdict-language" for violations in result.skipped.values() for v in violations
    )


# --- the request turnaround --------------------------------------------------


def test_no_turnaround_is_promised_unless_one_is_configured(tmp_path):
    # A turnaround printed on a page and missed is worse than no turnaround, so
    # the page says a number only when somebody is prepared to keep it.
    out = tmp_path / "site"
    config = tmp_path / "site.yaml"
    config.write_text('repository_url: "https://example.org/r"\n', encoding="utf-8")
    build_site(RECORDS_DIR, out, site_config=config)

    page = (out / "request" / "index.html").read_text(encoding="utf-8")
    assert "answered within" not in page


def test_a_configured_turnaround_is_a_promise_about_the_reply(tmp_path):
    out = tmp_path / "site"
    config = tmp_path / "site.yaml"
    config.write_text(
        'repository_url: "https://example.org/r"\nrequest_turnaround: "48 hours"\n',
        encoding="utf-8",
    )
    build_site(RECORDS_DIR, out, site_config=config)

    page = (out / "request" / "index.html").read_text(encoding="utf-8")
    assert "within 48 hours" in page
    assert "promise about the reply, not about the record" in page
