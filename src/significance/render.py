"""`significance build records/ -o site/`: a static renderer producing one
stable URL per record (stable, not permanent — GitHub Pages is not
archival).

Security posture: autoescape is on and record-derived prose is never marked
safe. The only generated markup is MathML created server-side from an optional
LaTeX display field. Autoescaping alone does not stop a
`javascript:` URL from being placed in an href, so every link built from
record data goes through the `safe_href` filter, which allows only
http(s) URLs and otherwise falls back to plain (still-escaped) text. There
is no Markdown and no `<script>` anywhere, so the CSP meta tag denies scripts
entirely. Math conversion happens during the build and needs no browser code.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from latex2mathml.converter import convert as latex_to_mathml
from markupsafe import Markup
from ruamel.yaml import YAML

from significance.boards import (
    FILL_MARKER,
    board_summary,
    board_validator,
    board_violations,
    collect_board_files,
    load_board,
)
from significance.export_text import board_row_status_text, record_status_text
from significance.records import load_record
from significance.semantics import verdict_violations
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
_HASH_RE = re.compile(r"(?<![a-f0-9])([a-f0-9]{40}|[a-f0-9]{64})(?![a-f0-9])", re.IGNORECASE)
_URL_RE = re.compile(r"https?://[^\s]+", re.IGNORECASE)


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


def short_hash(value: object) -> object:
    """Shorten long Git hashes in reader-facing prose; source data stays full."""
    if not isinstance(value, str):
        return value
    return _HASH_RE.sub(lambda match: match.group(1)[:12] + "…", value)


def readable_text(value: object) -> object:
    """Keep instructional prose readable without changing source data."""
    if not isinstance(value, str):
        return value
    shortened = short_hash(value)
    return _URL_RE.sub(lambda match: match.group(0).split("/")[2] + "/…", shortened)


def mathml(latex: object) -> Markup:
    """Convert schema-validated LaTeX to server-rendered MathML.

    The converter creates the markup; record content is never treated as HTML.
    If conversion fails, escaped plain text is safer than a broken build.
    """
    if not isinstance(latex, str):
        return Markup("")
    try:
        return Markup(latex_to_mathml(latex, display="block"))
    except Exception:
        return Markup.escape(latex)


def _environment() -> Environment:
    env = Environment(
        loader=FileSystemLoader(str(_TEMPLATES_DIR)),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    env.filters["safe_href"] = safe_href
    env.filters["safe_email"] = safe_email
    env.filters["short_hash"] = short_hash
    env.filters["readable_text"] = readable_text
    env.filters["mathml"] = mathml
    env.globals["style_version"] = hashlib.sha256(
        _STATIC_DIR.joinpath("style.css").read_bytes()
    ).hexdigest()[:12]
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


def load_glossary(path: str | Path | None = None) -> dict:
    """Term slug -> {term, definition}, or empty when there is no glossary.

    Empty is a working state: the nav omits the page and the term links in the
    record templates fall back to plain text, so a build without a glossary
    produces no dead links and no bare tooltips.
    """
    glossary_path = Path(path) if path is not None else _DATA_DIR / "glossary.yaml"
    if not glossary_path.is_file():
        return {}
    with open(glossary_path, "r", encoding="utf-8") as f:
        document = _yaml.load(f) or {}
    entries = document.get("terms") or []
    return {
        entry["slug"]: entry
        for entry in entries
        if isinstance(entry, dict)
        and isinstance(entry.get("slug"), str)
        and isinstance(entry.get("term"), str)
        and isinstance(entry.get("definition"), str)
    }


def glossary_violations(glossary: dict) -> list[Violation]:
    """Definitions answer to the same verdict rule as the plain-language blocks.

    They are the same kind of writing — ours, in our own words, aimed at
    somebody who has just met the vocabulary — and a definition that slipped a
    verdict in would put it on every page the term appears on.
    """
    violations: list[Violation] = []
    for slug, entry in sorted(glossary.items()):
        violations.extend(verdict_violations(entry["definition"], f"terms[{slug}].definition"))
    return violations


def load_orientation(path: str | Path | None = None) -> dict:
    """The orientation page's content, or {} when there is none."""
    orientation_path = Path(path) if path is not None else _DATA_DIR / "orientation.yaml"
    if not orientation_path.is_file():
        return {}
    with open(orientation_path, "r", encoding="utf-8") as f:
        return _yaml.load(f) or {}


def orientation_violations(orientation: dict) -> list[Violation]:
    """A page written to calm people down is exactly where a confident sentence
    would do the most damage, so it answers to the same verdict lint as every
    other plain-language block."""
    violations: list[Violation] = []
    intro = orientation.get("intro") or {}
    if isinstance(intro.get("value"), str):
        violations.extend(verdict_violations(intro["value"], "intro.value"))
    for index, section in enumerate(orientation.get("sections") or []):
        if isinstance(section, dict) and isinstance(section.get("body"), str):
            violations.extend(verdict_violations(section["body"], f"sections[{index}].body"))
    return violations


def site_links(
    root_prefix: str,
    *,
    deployed: bool,
    board_ids: list[str] | None = None,
    has_glossary: bool = False,
    has_orientation: bool = False,
    has_reviewers: bool = False,
    has_backlog: bool = False,
    has_intake: bool = True,
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
            "records_index": "/records/index.html",
            "request": "/request/index.html",
            "boards": {b: f"/boards/{b}/index.html" for b in boards},
        }
        if has_glossary:
            links["glossary"] = "/glossary/index.html"
        if has_orientation:
            links["orientation"] = "/orientation/index.html"
        if has_reviewers:
            links["reviewers"] = "/reviewers/index.html"
        if has_backlog:
            links["backlog"] = "/backlog/index.html"
        if has_intake:
            links["intake"] = "/how-to-file-a-claim/index.html"
        return links

    links = {
        "records_index": f"{root_prefix}index.html",
        "request": f"{root_prefix}request/index.html",
        "boards": {b: f"{root_prefix}boards/{b}/index.html" for b in boards},
    }
    if has_glossary:
        links["glossary"] = f"{root_prefix}glossary/index.html"
    if has_orientation:
        links["orientation"] = f"{root_prefix}orientation/index.html"
    if has_reviewers:
        links["reviewers"] = f"{root_prefix}reviewers/index.html"
    if has_backlog:
        links["backlog"] = f"{root_prefix}backlog/index.html"
    if has_intake:
        links["intake"] = f"{root_prefix}how-to-file-a-claim/index.html"
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
    glossary_path: str | Path | None = None,
    orientation_path: str | Path | None = None,
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
    all_record_files = collect_yaml_files([str(records_dir)])
    backlog_enabled = config.get("backlog_enabled", False)

    # Only an http(s) URL may become the link in a pasted paragraph. The
    # shipped value carries a [FILL] marker and fails this, which is the
    # intended behaviour: the paragraph renders without a link rather than with
    # a guessed one.
    public_url = safe_href(config.get("site_url"))

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

    orientation = load_orientation(orientation_path)
    orientation_problems = orientation_violations(orientation) if orientation else []
    if orientation_problems:
        result_skipped_boards[str(orientation_path or _DATA_DIR / "orientation.yaml")] = (
            orientation_problems
        )
        orientation = {}

    glossary = load_glossary(glossary_path)
    glossary_problems = glossary_violations(glossary)
    if glossary_problems:
        # Same rule as a board or a record that does not validate: not
        # rendered. A definition carrying a verdict would put it on every
        # page its term appears on, which is the widest blast radius of
        # anything in this build.
        result_skipped_boards[str(glossary_path or _DATA_DIR / "glossary.yaml")] = glossary_problems
        glossary = {}

    static_out = out_dir / "static"
    static_out.mkdir(parents=True, exist_ok=True)
    for asset in _STATIC_DIR.glob("*"):
        shutil.copy(asset, static_out / asset.name)

    def links_for(prefix: str) -> dict:
        """This build's nav, from the point of view of a page at `prefix`."""
        return site_links(
            prefix,
            deployed=deployed,
            board_ids=board_ids,
            has_glossary=bool(glossary),
            has_orientation=bool(orientation),
            has_reviewers=True,
            has_backlog=bool(
                backlog_enabled
                and len(all_record_files) >= int(config.get("backlog_min_records", 5))
            ),
            has_intake=True,
        )

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

    valid_records = [
        load_record(f)
        for f in collect_yaml_files([str(records_dir)])
        if not violations_by_file.get(str(f))
    ]
    cited_by: dict[str, list[dict]] = {}
    for source in valid_records:
        for dep in source.get("depends_on", []):
            if dep.get("record"):
                cited_by.setdefault(dep["record"], []).append(source)

    for f in collect_yaml_files([str(records_dir)]):
        violations = violations_by_file.get(str(f), [])
        if violations:
            result.skipped[str(f)] = violations
            continue

        record = load_record(f)
        stale_days = int(config.get("stale_task_days", 45))
        for invitation in record.get("open_invitations", []):
            if invitation.get("status", "open") == "taken" and invitation.get("taken_at"):
                try:
                    taken = datetime.fromisoformat(
                        invitation["taken_at"].replace("Z", "+00:00")
                    ).date()
                    invitation["_stale"] = (date.today() - taken).days > stale_days
                except ValueError:
                    invitation["_stale"] = False
        record_id = record["record_id"]
        record_url = f"{public_url}/records/{record_id}/" if public_url else None
        html = record_template.render(
            record=record,
            record_lookup={r["record_id"]: r for r in valid_records},
            cited_by=cited_by.get(record_id, []),
            glossary=glossary,
            status_text=record_status_text(record, record_url),
            root_prefix="../",
            links=links_for("../"),
        )
        _write_page(out_dir / record_id, html)

        result.built.append(record_id)
        built_records.append(record)

    built_records.sort(key=lambda r: r["record_id"])
    index_html = index_template.render(
        records=built_records,
        root_prefix="",
        links=links_for(""),
    )
    (out_dir / "index.html").write_text(index_html, encoding="utf-8")

    # An auxiliary page sits one directory below its own root, so its stylesheet
    # is "../static/…" in the self-contained layout. In the deployed layout the
    # stylesheet lives under the records root, which no relative path reaches
    # from the site root, so it is addressed absolutely.
    pages_prefix = "/records/" if deployed else "../"
    pages_links = links_for("../")

    _write_page(
        pages_dir / "request",
        env.get_template("request.html.jinja").render(
            root_prefix=pages_prefix,
            links=pages_links,
            site=config,
        ),
    )
    result.pages.append("request")

    # Intake standard: deliberately plain and copyable, generated with the same
    # static toolchain as records.
    _write_page(
        pages_dir / "how-to-file-a-claim",
        env.get_template("intake.html.jinja").render(root_prefix=pages_prefix, links=pages_links),
    )
    result.pages.append("how-to-file-a-claim")

    if orientation:
        _write_page(
            pages_dir / "orientation",
            env.get_template("orientation.html.jinja").render(
                orientation=orientation,
                root_prefix=pages_prefix,
                links=pages_links,
            ),
        )
        result.pages.append("orientation")

    if glossary:
        _write_page(
            pages_dir / "glossary",
            env.get_template("glossary.html.jinja").render(
                glossary=glossary,
                terms=sorted(glossary.values(), key=lambda e: e["term"].lower()),
                root_prefix=pages_prefix,
                links=pages_links,
            ),
        )
        result.pages.append("glossary")

    # Build reviewer census from attributed record material. Strata stay labels,
    # never a blended score or ranking.
    reviewer_map: dict[str, dict] = {}
    # The editor identity is a named participant even before they have a
    # review entry; showing the empty census line is more honest than implying
    # the page only exists for people with volume.
    reviewer_map["significance-editor"] = {"id": "significance-editor", "records": []}
    for record in built_records:
        for a in record.get("attestations", []):
            who = a.get("reviewer") or a.get("asserted_by")
            if who:
                reviewer_map.setdefault(who, {"id": who, "records": []})["records"].append(
                    {"record": record, "entry": a, "kind": "attestation"}
                )
        for ev in record.get("evidence", []):
            who = ev.get("reviewer") or ev.get("asserted_by")
            if who and ev.get("kind") in {"informal_review", "mathematical_assessment"}:
                entry = dict(ev)
                if not entry.get("stratum") and (
                    record.get("parties", {})
                    .get(who, {})
                    .get("verification_method", {})
                    .get("kind")
                    == "automation"
                ):
                    entry["stratum"] = "machine"
                reviewer_map.setdefault(who, {"id": who, "records": []})["records"].append(
                    {"record": record, "entry": entry, "kind": "evidence"}
                )
        for oi in record.get("open_invitations", []):
            who = oi.get("taken_by")
            if who:
                entry = dict(oi)
                entry.setdefault(
                    "stratum",
                    "machine"
                    if record.get("parties", {})
                    .get(who, {})
                    .get("verification_method", {})
                    .get("kind")
                    == "automation"
                    else "community",
                )
                reviewer_map.setdefault(who, {"id": who, "records": []})["records"].append(
                    {"record": record, "entry": entry, "kind": "task"}
                )
    for row in reviewer_map.values():
        party = next(
            (
                r.get("parties", {}).get(row["id"])
                for r in built_records
                if row["id"] in r.get("parties", {})
            ),
            None,
        )
        if party and party.get("affiliation"):
            row["affiliation"] = party["affiliation"]
    reviewer_rows = sorted(reviewer_map.values(), key=lambda x: x["id"].lower())
    _write_page(
        pages_dir / "reviewers",
        env.get_template("reviewers.html.jinja").render(
            reviewers=reviewer_rows, root_prefix=pages_prefix, links=pages_links
        ),
    )
    result.pages.append("reviewers")
    for reviewer in reviewer_rows:
        _write_page(
            pages_dir / "reviewers" / reviewer["id"],
            env.get_template("reviewer.html.jinja").render(
                reviewer=reviewer,
                root_prefix=("/records/" if deployed else "../../"),
                links=pages_links,
            ),
        )
        result.pages.append(f"reviewer:{reviewer['id']}")

    if backlog_enabled and len(built_records) >= int(config.get("backlog_min_records", 5)):
        today = date.today()
        rows = []
        for record in built_records:
            if record.get("record_state") != "active":
                continue
            dates = [record.get("manuscript", {}).get("retrieved_at", "")[:10]]
            for a in record.get("attestations", []):
                dates.append(a.get("asserted_at", "")[:10])
            for e in record.get("evidence", []):
                dates.append(e.get("asserted_at", "")[:10])
            for i in record.get("open_invitations", []):
                dates.append(i.get("taken_at", "")[:10] or i.get("created_at", "")[:10])
            dates = [d for d in dates if d]
            last = max(dates) if dates else today.isoformat()
            rows.append(
                {
                    "record": record,
                    "last": last,
                    "days": (today - date.fromisoformat(last)).days,
                    "open": sum(
                        1
                        for i in record.get("open_invitations", [])
                        if i.get("status", "open") == "open"
                    ),
                    "taken": sum(
                        1 for i in record.get("open_invitations", []) if i.get("status") == "taken"
                    ),
                    "reviewers": len(
                        {
                            a.get("reviewer") or a.get("asserted_by")
                            for a in record.get("attestations", [])
                            if a.get("reviewer") or a.get("asserted_by")
                        }
                    ),
                }
            )
        rows.sort(key=lambda x: x["days"], reverse=True)
        _write_page(
            pages_dir / "backlog",
            env.get_template("backlog.html.jinja").render(
                rows=rows, root_prefix=pages_prefix, links=pages_links
            ),
        )
        result.pages.append("backlog")

    # A board page sits two directories below its root (boards/<id>/), so its
    # relative prefix is one level deeper than the other auxiliary pages.
    board_prefix = "/records/" if deployed else "../../"
    board_template = env.get_template("board.html.jinja")
    for board in boards:
        # A records-index URL is a page (and therefore ends in index.html in
        # the self-contained layout), not a directory that record ids may be
        # appended to. Build each destination explicitly so both layouts
        # produce a valid link.
        record_links = {
            row["id"]: (
                f"/records/{row['record']}/" if deployed else f"../../{row['record']}/index.html"
            )
            for row in board["rows"]
            if row.get("record")
        }
        _write_page(
            pages_dir / "boards" / board["board_id"],
            board_template.render(
                board=board,
                record_links=record_links,
                # No paste for a row that has no name yet. "Nobody has
                # looked at this" is a real answer to "is this real?" — but
                # only when the paragraph can say which result it is about,
                # and a placeholder row cannot.
                row_status_text={
                    row["id"]: board_row_status_text(
                        board,
                        row,
                        f"{public_url}/boards/{board['board_id']}/" if public_url else None,
                    )
                    for row in board["rows"]
                    if not row.get("result", "").strip().lower().startswith(FILL_MARKER)
                },
                root_prefix=board_prefix,
                links=links_for(board_prefix),
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
            "claim_mathml": str(mathml(record["claim"].get("display_math", "")))
            if record["claim"].get("display_math")
            else None,
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
