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

import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from ruamel.yaml import YAML

from significance.boards import (
    board_summary,
    board_validator,
    board_violations,
    collect_board_files,
    load_board,
)
from significance.records import load_record
from significance.validate import collect_yaml_files, validate_paths
from significance.violations import Violation

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
_STATIC_DIR = Path(__file__).resolve().parent / "static"
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DIR = _REPO_ROOT / "data"

_yaml = YAML(typ="safe")

_SAFE_URL_RE = re.compile(r"^https?://", re.IGNORECASE)

# One "@", something either side, no whitespace and no characters that would
# let a crafted value break out of the mailto URL into extra headers. This is
# not address validation — the real test of an address is that mail to it
# arrives — it is the same narrow question safe_href asks: may this string
# become a link?
_SAFE_EMAIL_RE = re.compile(r"^[^\s@,;<>?&\"']+@[^\s@,;<>?&\"']+\.[^\s@,;<>?&\"']+$")


def safe_href(url) -> str | None:
    """Only http(s) URLs may become an href. Everything else (javascript:,
    data:, vbscript:, bare garbage) is rejected; callers fall back to
    rendering the value as plain (escaped) text, never as a link."""
    if isinstance(url, str) and _SAFE_URL_RE.match(url):
        return url
    return None


def safe_email(address) -> str | None:
    """An address usable in a mailto: link, or None.

    The unset value in data/site.yaml carries a [FILL] marker and fails this,
    which is the intended behaviour: the request page then shows the message
    as copyable text and says the address is not configured, rather than
    rendering a link that goes nowhere.
    """
    if isinstance(address, str) and _SAFE_EMAIL_RE.match(address.strip()):
        return address.strip()
    return None


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["safe_href"] = safe_href
    env.filters["safe_email"] = safe_email
    return env


def load_site_config(path: str | Path | None = None) -> dict:
    """Site-level configuration (repository URL, contact address).

    Missing file is not an error: the auxiliary pages degrade to describing
    what they cannot link to, which is the same posture as an unconfigured
    contact address.
    """
    config_path = Path(path) if path is not None else _DATA_DIR / "site.yaml"
    if not config_path.is_file():
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return _yaml.load(f) or {}


def site_links(
    root_prefix: str,
    *,
    deployed: bool,
    board_ids: list[str] | None = None,
    has_glossary: bool = False,
) -> dict:
    """Where the auxiliary pages live, from the point of view of one page.

    Two layouts, and the difference is forced by where the output goes.

    Self-contained (`significance build records/ -o site/`): everything lands
    under one root, so links are relative and a built directory can be opened
    from the filesystem or served from any prefix.

    Deployed (`-o public/records/ --pages-out public/`): record pages sit
    under /records/ while the auxiliary pages sit at the site root, so no
    relative path spans both reliably and the links are absolute.

    Absolute paths are used only in the layout that requires them, and they
    are site-root paths written here — never derived from a request, which is
    the rule db/config.ts states for the other half of this project.
    """
    boards = board_ids or []
    # Only pages this build actually writes appear here. A nav entry pointing
    # at a page that was not built is a 404 the visitor blames on themselves,
    # and it is the failure mode of adding links to pages that "will exist
    # soon" — so the link and the page arrive together or not at all.
    if deployed:
        links = {
            "records_index": "/records/",
            "request": "/request/",
            "boards": {b: f"/boards/{b}/" for b in boards},
        }
        if has_glossary:
            links["glossary"] = "/glossary/"
        return links

    links = {
        "records_index": f"{root_prefix}index.html",
        "request": f"{root_prefix}request/index.html",
        "boards": {b: f"{root_prefix}boards/{b}/index.html" for b in boards},
    }
    if has_glossary:
        links["glossary"] = f"{root_prefix}glossary/index.html"
    return links


@dataclass
class BuildResult:
    built: list[str] = field(default_factory=list)
    skipped: dict[str, list[Violation]] = field(default_factory=dict)
    #: Auxiliary pages written, by name ("request", "glossary", "board:<id>").
    pages: list[str] = field(default_factory=list)


def _write_page(directory: Path, html: str) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "index.html").write_text(html, encoding="utf-8")


def build_site(
    records_dir: str | Path,
    out_dir: str | Path,
    *,
    pages_out: str | Path | None = None,
    site_config: str | Path | None = None,
    boards_dir: str | Path | None = None,
) -> BuildResult:
    records_dir = Path(records_dir)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Auxiliary pages (/request/, /glossary/, /boards/…) default to living
    # beside the record pages, so a plain `build` still produces a site whose
    # every link resolves. The deployed layout passes --pages-out to put them
    # at the site root instead; see site_links for why that changes the links.
    pages_dir = Path(pages_out) if pages_out is not None else out_dir
    deployed = pages_dir.resolve() != out_dir.resolve()
    pages_dir.mkdir(parents=True, exist_ok=True)

    result_skipped_boards: dict[str, list[Violation]] = {}

    config = load_site_config(site_config)

    # Boards are resolved before anything renders, because every page's nav
    # needs to know which ones exist. A board that does not validate is skipped
    # exactly as an invalid record is: the same rule, for the same reason --
    # a page rendered from a document nobody checked is worse than a missing
    # page, because it looks the same as a checked one.
    boards_path = Path(boards_dir) if boards_dir is not None else _REPO_ROOT / "boards"
    boards: list[dict] = []
    board_schema = board_validator()
    for board_file in collect_board_files(boards_path):
        board = load_board(board_file)
        board_problems = board_violations(board, board_schema)
        if board_problems:
            for v in board_problems:
                v.file = str(board_file)
            result_skipped_boards[str(board_file)] = board_problems
            continue
        boards.append(board)
    boards.sort(key=lambda b: b["board_id"])
    board_ids = [b["board_id"] for b in boards]

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
        html = record_template.render(
            record=record,
            root_prefix="../",
            links=site_links("../", deployed=deployed, board_ids=board_ids),
        )
        _write_page(out_dir / record_id, html)

        result.built.append(record_id)
        built_records.append(record)

    built_records.sort(key=lambda r: r["record_id"])
    index_html = index_template.render(
        records=built_records,
        root_prefix="",
        links=site_links("", deployed=deployed, board_ids=board_ids),
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")

    # An auxiliary page sits one directory below its own root, so its stylesheet
    # is "../static/…" in the self-contained layout. In the deployed layout the
    # stylesheet lives under the records root, which no relative path reaches
    # from the site root, so it is addressed absolutely.
    pages_prefix = "/records/" if deployed else "../"
    pages_links = site_links("../", deployed=deployed, board_ids=board_ids)

    _write_page(
        pages_dir / "request",
        env.get_template("request.html.jinja").render(
            root_prefix=pages_prefix,
            links=pages_links,
            site=config,
        ),
    )
    result.pages.append("request")

    # A board page sits two directories below its root (boards/<id>/), so its
    # relative prefix is one level deeper than the other auxiliary pages.
    board_prefix = "/records/" if deployed else "../../"
    board_template = env.get_template("board.html.jinja")
    for board in boards:
        _write_page(
            pages_dir / "boards" / board["board_id"],
            board_template.render(
                board=board,
                root_prefix=board_prefix,
                links=site_links(board_prefix, deployed=deployed, board_ids=board_ids),
            ),
        )
        result.pages.append(f"board:{board['board_id']}")
    result.skipped.update(result_skipped_boards)

    # This is the only record-data interface consumed by the React homepage.
    # Keeping it beside the Python-rendered index makes validation and record
    # selection Python's responsibility; the JS layer only presents the
    # already-validated summaries and cannot invent a second freshness state.
    record_summaries = [
        {
            "record_id": record["record_id"],
            "record_version": record["record_version"],
            "record_state": record["record_state"],
            "claim": record["claim"]["text"]["value"],
            "claim_basis": record["claim"]["text"]["basis"],
            "claim_asserted_by": record["claim"]["text"]["asserted_by"],
            "freshness": record.get("freshness", {}).get("result", "unknown"),
            "freshness_checked_at": record.get("freshness", {}).get("checked_at"),
            "evidence_count": len(record.get("evidence", [])),
            "open_invitation_count": len(record.get("open_invitations", [])),
        }
        for record in built_records
    ]

    # Shape change: this file was a bare array of record summaries and is now
    # an object with `records` and `boards`. The React shell has to be able to
    # link the board, and the rule that it may only present what this builder
    # generated leaves exactly one place to put that — here. A second generated
    # file would have been the smaller diff and the worse answer: two files
    # mean two loading paths and an eventual disagreement about which one is
    # current.
    index_data = {
        "records": record_summaries,
        "boards": [board_summary(board) for board in boards],
    }
    (out_dir / "index.json").write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return result
