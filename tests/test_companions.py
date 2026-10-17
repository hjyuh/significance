"""Publication must preserve source bytes and use the right comment assets."""
import hashlib
import json

import pytest

from significance.companions import ASSETS, ROOT, build_companions, published_companions


@pytest.mark.parametrize("deployed", [False, True])
def test_companion_publication_preserves_reader_and_dedicated_thread(tmp_path, deployed):
    pages = tmp_path / "site"
    static = pages / "records" / "static" if deployed else pages / "static"
    build_companions(pages, static)
    page = pages / "companions" / "family-159"
    html = (page / "index.html").read_text(encoding="utf-8")
    prefix = "../../records/static/" if deployed else "../../static/"
    assert f'src="{prefix}discussion.js"' in html
    assert f'data-config-url="{prefix}firebase-config.json"' in html
    assert 'data-record-id="companion-openai-family-159"' in html
    assert 'data-task-id="discussion"' in html
    assert 'id="comments"' in html
    assert 'id="pdf-reader"' in html
    for asset in ASSETS:
        assert (page / asset).is_file()
    assert not (page / "build-references.mjs").exists()
    assert hashlib.sha256((page / "manuscript.pdf").read_bytes()).hexdigest() == (
        "481eaf7730dc4d581e5270cc4d514c6ee2ec386d5af643cf914e20b4d00c59be"
    )
    refs = json.loads((page / "references.json").read_text())
    assert refs["references"]["theorem-1-1"]["page"] == 4
    assert refs["references"]["proposition-4-1"]["page"] == 25
    assert len(published_companions()) == 1
    assert (ROOT / "drafts/companions/family-159/index.html").is_file()


def test_companion_sources_cannot_escape_approved_directory(tmp_path, monkeypatch):
    from significance import companions

    manifest = tmp_path / "companions.json"
    manifest.write_text(json.dumps([{"slug": "escape", "source": "../outside"}]))
    monkeypatch.setattr(companions, "PUBLISHED", manifest)
    with pytest.raises(ValueError, match="source must stay"):
        published_companions()
