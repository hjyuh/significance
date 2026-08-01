"""`significance build records/ -o site/`: a static renderer producing one
stable URL per record (stable, not permanent — GitHub Pages is not
archival).

Security posture: autoescape is on and nothing in these templates ever
uses `|safe` on record-derived data. Autoescaping alone does not stop a
`javascript:` URL from being placed in an href, so every link built from
record data goes through the `safe_href` filter, which allows only
http(s) URLs and otherwise falls back to plain (still-escaped) text. There
is no Markdown or math rendering in v0.1 — prose is shown as escaped plain
text — and no `<script>` anywhere, so the CSP meta tag denies scripts
entirely.
"""

from __future__ import annotations

import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from significance.records import load_record
from significance.validate import collect_yaml_files, validate_paths
from significance.violations import Violation

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_STATIC_DIR = Path(__file__).resolve().parent / "static"

_SAFE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)


def safe_href(url) -> str | None:
    """Only http(s) URLs may become an href. Everything else (javascript:,
    data:, vbscript:, bare garbage) is rejected; callers fall back to
    rendering the value as plain (escaped) text, never as a link."""
    if isinstance(url, str) and _SAFE_URL_RE.match(url):
        return url
    return None


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["safe_href"] = safe_href
    return env


@dataclass
class BuildResult:
    built: list[str] = field(default_factory=list)
    skipped: dict[str, list[Violation]] = field(default_factory=dict)


def build_site(records_dir: str | Path, out_dir: str | Path) -> BuildResult:
    records_dir = Path(records_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    static_out = out_dir / "static"
    static_out.mkdir(parents=True, exist_ok=True)
    for asset in _STATIC_DIR.glob("*"):
        shutil.copy(asset, static_out / asset.name)

    env = _environment()
    record_template = env.get_template("record.html.jinja")
    index_template = env.get_template("index.html.jinja")

    result = BuildResult()
    built_records: list[dict] = []

    # Validated together (not file-by-file) so cross-record checks like
    # duplicate-record-id actually see sibling records.
    violations_by_file: dict[str, list[Violation]] = {}
    for v in validate_paths([str(records_dir)]):
        violations_by_file.setdefault(v.file, []).append(v)

    for f in collect_yaml_files([str(records_dir)]):
        violations = violations_by_file.get(str(f), [])
        if violations:
            result.skipped[str(f)] = violations
            continue

        record = load_record(f)
        record_id = record["record_id"]
        page_dir = out_dir / record_id
        page_dir.mkdir(parents=True, exist_ok=True)
        html = record_template.render(record=record, root_prefix="../")
        (page_dir / "index.html").write_text(html, encoding="utf-8")

        result.built.append(record_id)
        built_records.append(record)

    built_records.sort(key=lambda r: r["record_id"])
    index_html = index_template.render(records=built_records, root_prefix="")
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")

    return result
