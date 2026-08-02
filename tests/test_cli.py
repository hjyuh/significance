"""Phase 2: CLI-level smoke tests for exit codes and --json output."""

from __future__ import annotations

import json
from pathlib import Path

from significance.cli import main

REPO_ROOT = Path(__file__).resolve().parents[1]
RECORDS_DIR = REPO_ROOT / "records"
OPENAI_RECORD = RECORDS_DIR / "2026-openai-nonsofic-groups.yaml"
BROKEN_DIR = REPO_ROOT / "tests" / "fixtures" / "broken"


def test_validate_clean_record_exits_zero(capsys):
    code = main(["validate", str(OPENAI_RECORD)])
    out = capsys.readouterr().out
    assert code == 0
    assert "OK" in out


def test_validate_broken_record_exits_one_with_json(capsys):
    code = main(
        ["validate", str(BROKEN_DIR / "missing-manuscript-hash.yaml"), "--json"]
    )
    out = capsys.readouterr().out
    assert code == 1
    report = json.loads(out)
    assert any(v["rule"] == "missing-manuscript-hash" for v in report)


def test_diff_cli_exits_one_on_append_only_violation(capsys):
    code = main(
        [
            "diff",
            str(BROKEN_DIR / "append-only" / "base.yaml"),
            str(BROKEN_DIR / "append-only" / "deleted-event.yaml"),
        ]
    )
    out = capsys.readouterr().out
    assert code == 1
    assert "history-event-deleted" in out


def test_diff_cli_exits_zero_on_identical_records(capsys):
    p = str(BROKEN_DIR / "append-only" / "base.yaml")
    code = main(["diff", p, p])
    assert code == 0


def test_build_cli_exits_zero_and_writes_site(tmp_path, capsys):
    out = tmp_path / "site"
    expected_records = len(list(RECORDS_DIR.glob("*.yaml")))
    code = main(["build", str(RECORDS_DIR), "-o", str(out)])
    output = capsys.readouterr().out
    assert code == 0
    assert f"Built {expected_records} record" in output
    assert (out / "index.html").exists()


def test_build_cli_exits_one_when_a_record_is_skipped(tmp_path, capsys):
    out = tmp_path / "site"
    code = main(["build", str(BROKEN_DIR / "duplicate-record-id"), "-o", str(out)])
    err = capsys.readouterr().err
    assert code == 1
    assert "duplicate-record-id" in err
