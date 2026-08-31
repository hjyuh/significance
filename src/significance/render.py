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
import unicodedata
import xml.etree.ElementTree as ET
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlencode

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
from significance.semantics import PALOMAR_CAVEAT, verdict_violations
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


def problem_slug(venue: object, problem_id: object) -> str:
    """Stable, filesystem-safe key for a linked problem page."""
    value = unicodedata.normalize(
        "NFKD", f"{venue or 'problem'}-{problem_id or 'unknown'}"
    ).encode("ascii", "ignore").decode().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value).strip("-")
    return value or "problem"


def expositions(record: dict) -> list[dict]:
    """Exposition evidence rows, oldest first. Never a review count."""
    rows = [
        entry
        for entry in record.get("evidence", []) or []
        if isinstance(entry, dict) and entry.get("kind") == "exposition"
    ]
    rows.sort(key=lambda entry: (str(entry.get("date") or ""), str(entry.get("id") or "")))
    return rows


def _day(value: object) -> str | None:
    """The YYYY-MM-DD prefix of a date or date-time, or None."""
    if isinstance(value, (date, datetime)):
        return value.isoformat()[:10]
    if isinstance(value, str) and len(value) >= 10 and value[4] == "-" and value[7] == "-":
        return value[:10]
    return None


def date_vector(record: dict) -> dict:
    """The three component dates a reader needs to date a result, kept apart.

    A single "release date" would be a derived judgement — whichever component
    the site picked would become the date everyone quoted, and the argument
    about which one is right is exactly the argument a record should leave to
    its reader. So the strip shows the components, says where each came from,
    and computes nothing from them. A component nobody has recorded renders as
    a dash; it is never substituted from a neighbouring field (the retrieval
    date is not the preprint date, and a build receipt is not a registry entry).
    """
    manuscript = record.get("manuscript") or {}
    preprint = _day(manuscript.get("published_at"))

    exposition_dates = [_day(entry.get("date")) for entry in expositions(record)]
    exposition_dates = [value for value in exposition_dates if value]

    formalization: str | None = None
    formalization_source: str | None = None
    evidence = [e for e in record.get("evidence", []) or [] if isinstance(e, dict)]
    for kind, source_label, date_of in (
        (
            "formal_artifact",
            "independent build receipt",
            lambda e: _day((e.get("artifact_build") or {}).get("executed_at")),
        ),
        (
            "external_formal_artifact",
            "artifact reported by the source",
            lambda e: _day(e.get("asserted_at")),
        ),
        ("palomar_entry", "Palomar registry entry", lambda e: _day(e.get("date"))),
    ):
        candidates = sorted(
            value for value in (date_of(e) for e in evidence if e.get("kind") == kind) if value
        )
        if candidates:
            formalization, formalization_source = candidates[0], source_label
            break

    return {
        "preprint": preprint,
        "preprint_source": "manuscript metadata" if preprint else None,
        "exposition": min(exposition_dates) if exposition_dates else None,
        "exposition_source": "earliest exposition entry" if exposition_dates else None,
        "formalization": formalization,
        "formalization_source": formalization_source,
    }


def is_published(record: dict) -> bool:
    """A record the public site actually presents as a record.

    Drafts and withdrawn/superseded records are excluded: soliciting an
    expository account of something nobody has approved for publication would
    publish it by the back door.
    """
    return record.get("record_state") == "active" and not record.get("draft")


def derived_exposition_task(record: dict) -> dict | None:
    """The exposition task a published record with no exposition rows implies.

    Derived at build time and written into no YAML, so it disappears by itself
    the day a real exposition row lands — which is the point: a task file that
    had to be deleted by hand would outlive the gap it described. The two
    editor-supplied halves (reader level, effort) are left as [FILL] markers
    rather than guessed, on the board's rule that a filled-looking slot nobody
    filled is worse than an obviously empty one.
    """
    if not is_published(record):
        return None
    if "exposition" in (record.get("suppress_derived_tasks") or []):
        return None
    if expositions(record):
        return None
    claim = ((record.get("claim") or {}).get("text") or {}).get("value") or record["record_id"]
    short_name = claim if len(claim) <= 90 else claim[:87].rstrip() + "…"
    return {
        "task_id": "derived-exposition",
        "task_kind": "exposition",
        "kind": "exposition",
        "status": "open",
        "derived": True,
        "target": (
            f'Write an expository account of the claim in {record["record_id"]} '
            f'— "{short_name}" — for [FILL by editor: intended reader level]'
        ),
        "effort_estimate": "[FILL]",
        "created_by": "significance-editor",
    }


def task_id(invitation: dict, index: int) -> str:
    """Return the explicit task id, or a stable legacy fallback."""
    return invitation.get("task_id") or f"task-{index + 1}"


def _attestation_yaml(record: dict, invitation: dict, task: str) -> str:
    """Build the reviewer-facing YAML skeleton from record data only."""
    payload = {
        "id": f"att-{task}",
        "task_id": task,
        "reviewer": "[your name or handle]",
        "scope": invitation["target"],
        "manuscript_sha256": record["manuscript"]["sha256"],
        "asserted_at": "[YYYY-MM-DDTHH:MM:SSZ]",
        "method": "[what you actually did: read / rederived / rebuilt / compared]",
        "finding": "[what you checked and found about exactly this scope]",
        "limits": "[what you did not check — optional but encouraged]",
    }
    yaml = YAML()
    from io import StringIO

    output = StringIO()
    yaml.dump(payload, output)
    return output.getvalue()


def _attestation_issue_url(invitation: dict, record: dict, task: str) -> str | None:
    response = (invitation.get("respond") or {}).get("url")
    if not safe_href(response):
        return None
    response = response.replace("template=invitation-response.yml", "template=attestation.yml")
    query = urlencode(
        {
            "title": f"Scoped attestation: {record['record_id']} / {task}",
            "record": record["record_id"],
            "task": task,
            "revision": record["manuscript"]["sha256"],
            "scope": invitation["target"],
        }
    )
    return response + ("&" if "?" in response else "?") + query
_PATH_PART_RE = re.compile(r"[^A-Za-z0-9._-]+")


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


def _configured(value: object) -> str | None:
    """A site.yaml string somebody has actually filled in, or None.

    The shipped values carry [FILL] markers. Treating a marker as a real value
    would put the bracket text on the page, which reads as a bug to a visitor
    and as an answer to a crawler; treating it as absent lets the page say
    plainly that nobody has set this yet.
    """
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text or text.lower().startswith(FILL_MARKER):
        return None
    return text


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


def _jsonable(value: object) -> object:
    """Return record data in the JSON-compatible, public form.

    The renderer adds private ``_`` keys while calculating display state. They
    are implementation details, not part of the portable export. Dates are
    handled here as well so a consumer gets the same values regardless of
    whether a YAML loader represents them as strings or date objects.
    """
    if isinstance(value, dict):
        return {
            str(key): _jsonable(item)
            for key, item in value.items()
            if not str(key).startswith("_")
        }
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _path_part(value: object) -> str:
    """Make a stable, harmless URL path component from external identifiers."""
    text = _PATH_PART_RE.sub("-", str(value)).strip(".-")
    return text or "unknown"


def _problem_key(record: dict) -> tuple[str, str] | None:
    problem = record.get("problem_reference")
    if not isinstance(problem, dict):
        return None
    venue = problem.get("venue")
    problem_id = problem.get("problem_id")
    if not isinstance(venue, str) or not isinstance(problem_id, (str, int)):
        return None
    return venue, str(problem_id)


def _record_date(record: dict) -> str:
    """Choose the newest dated record event for deterministic feed entries."""
    candidates: list[str] = []
    for section in (record.get("freshness", {}), record.get("manuscript", {})):
        for key in ("checked_at", "retrieved_at"):
            value = section.get(key)
            if isinstance(value, str) and value:
                candidates.append(value)
    for key in ("author_relationship", "claim"):
        value = record.get(key, {}).get("asserted_at")
        if isinstance(value, str) and value:
            candidates.append(value)
    for key in ("evidence", "attestations", "open_invitations", "digestions"):
        for item in record.get(key, []) or []:
            if not isinstance(item, dict):
                continue
            for date_key in ("asserted_at", "created_at", "taken_at", "done_at"):
                value = item.get(date_key)
                if isinstance(value, str) and value:
                    candidates.append(value)
    # Atom requires a timestamp. This sentinel is only used for malformed or
    # unusually sparse records; valid records normally have several dates.
    return max(candidates) if candidates else "1970-01-01T00:00:00Z"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(_jsonable(value), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _write_feed(path: Path, records: list[dict], public_url: str | None) -> None:
    """Write a small Atom feed of record changes for polling consumers."""
    atom = "http://www.w3.org/2005/Atom"
    feed = ET.Element(f"{{{atom}}}feed")
    ET.SubElement(feed, f"{{{atom}}}title").text = "Significance records"
    feed_id = f"{public_url.rstrip('/')}/feed.xml" if public_url else "urn:significance:feed"
    ET.SubElement(feed, f"{{{atom}}}id").text = feed_id
    dates = [_record_date(record) for record in records]
    ET.SubElement(feed, f"{{{atom}}}updated").text = max(dates, default="1970-01-01T00:00:00Z")
    if public_url:
        ET.SubElement(
            feed, f"{{{atom}}}link", rel="self", href=f"{public_url.rstrip('/')}/feed.xml"
        )
    for record in records:
        record_id = record["record_id"]
        page_url = f"{public_url.rstrip('/')}/{record_id}/" if public_url else record_id
        entry = ET.SubElement(feed, f"{{{atom}}}entry")
        title = record.get("claim", {}).get("text", {}).get("value", record_id)
        ET.SubElement(entry, f"{{{atom}}}title").text = title
        ET.SubElement(entry, f"{{{atom}}}id").text = page_url
        ET.SubElement(entry, f"{{{atom}}}updated").text = _record_date(record)
        ET.SubElement(entry, f"{{{atom}}}link", href=page_url)
        ET.SubElement(entry, f"{{{atom}}}summary").text = (
            f"Record v{record.get('record_version', '?')}; "
            f"{len(record.get('evidence', []))} evidence entries; "
            f"{len(record.get('open_invitations', []))} open invitations."
        )
    ET.register_namespace("", atom)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(ET.tostring(feed, encoding="utf-8", xml_declaration=True))


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
    has_problems: bool = False,
    has_frontier: bool = False,
    has_intake: bool = True,
    has_feed: bool = False,
    has_tasks: bool = False,
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
        if has_problems:
            links["problems"] = "/problems/index.html"
        if has_frontier:
            links["frontier"] = "/frontier/index.html"
        if has_intake:
            links["intake"] = "/how-to-file-a-claim/index.html"
        if has_feed:
            links["feed"] = "/feed.xml"
        if has_tasks:
            links["tasks"] = "/tasks/index.html"
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
    if has_problems:
        links["problems"] = f"{root_prefix}problems/index.html"
    if has_frontier:
        links["frontier"] = f"{root_prefix}frontier/index.html"
    if has_intake:
        links["intake"] = f"{root_prefix}how-to-file-a-claim/index.html"
    if has_feed:
        links["feed"] = f"{root_prefix}feed.xml"
    if has_tasks:
        links["tasks"] = f"{root_prefix}tasks/index.html"
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
            has_problems=any(r.get("problem_reference") for r in valid_records),
            has_frontier=any(
                any(
                    i.get("status", "open") in {"open", "taken"}
                    for i in r.get("open_invitations", [])
                )
                for r in valid_records
            ),
            has_intake=True,
            has_feed=True,
            has_tasks=any(
                i.get("status", "open") in {"open", "taken"}
                for r in valid_records
                for i in r.get("open_invitations", [])
            )
            or any(derived_exposition_task(r) for r in valid_records),
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
        # GitHub Pages uses the self-contained layout (`-o site/`), where
        # record pages live at the site root.  The hosted preview layout uses
        # `--pages-out` and places them under `/records/`.  Keep share links
        # aligned with the layout that produced the page, and normalize the
        # configured URL so a trailing slash never becomes `//`.
        if public_url:
            site_base = public_url.rstrip("/")
            record_path = f"/records/{record_id}/" if deployed else f"/{record_id}/"
            record_url = f"{site_base}{record_path}"
        else:
            record_url = None
        html = record_template.render(
            record=record,
            record_lookup={r["record_id"]: r for r in valid_records},
            cited_by=cited_by.get(record_id, []),
            glossary=glossary,
            status_text=record_status_text(record, record_url),
            date_vector=date_vector(record),
            palomar_caveat=PALOMAR_CAVEAT,
            root_prefix="../",
            links=links_for("../"),
            task_root=(
                f"/tasks/{record_id}/" if deployed else f"../tasks/{record_id}/"
            ),
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
    # Reviewer and problem detail pages are two levels below the site root in
    # the self-contained layout. They need their own navigation prefix; using
    # the auxiliary-page prefix here makes links such as
    # `reviewers/orientation/` and `problems/glossary/` dead on arrival.
    detail_prefix = "/records/" if deployed else "../../"
    detail_links = links_for(detail_prefix)

    linked_problems = [
        {
            "record_id": record["record_id"],
            "record_version": record["record_version"],
            "claim": record["claim"]["text"]["value"],
            "venue": record["problem_reference"]["venue"],
            "problem_id": record["problem_reference"]["problem_id"],
            "url": record["problem_reference"]["url"],
            "evidence_count": len(record.get("evidence", [])),
            "open_count": sum(
                1 for invitation in record.get("open_invitations", [])
                if invitation.get("status", "open") == "open"
            ),
            "record_href": (
                f"/records/{record['record_id']}/index.html"
                if deployed
                else f"../../{record['record_id']}/index.html"
            ),
        }
        for record in built_records
        if record.get("problem_reference")
    ]
    if linked_problems:
        linked_problems.sort(key=lambda item: (item["venue"], item["problem_id"]))
        grouped_problems: dict[str, dict] = {}
        for item in linked_problems:
            key = problem_slug(item["venue"], item["problem_id"])
            group = grouped_problems.setdefault(
                key,
                {
                    "slug": key,
                    "venue": item["venue"],
                    "problem_id": item["problem_id"],
                    "url": item["url"],
                    "records": [],
                },
            )
            group["records"].append(item)
        for group in grouped_problems.values():
            group["record_count"] = len(group["records"])
            group["evidence_count"] = sum(r["evidence_count"] for r in group["records"])
            group["open_count"] = sum(r["open_count"] for r in group["records"])
        _write_page(
            pages_dir / "problems",
            env.get_template("problems.html.jinja").render(
                problems=linked_problems,
                problem_groups=sorted(
                    grouped_problems.values(),
                    key=lambda item: (item["venue"], item["problem_id"]),
                ),
                root_prefix=pages_prefix,
                links=pages_links,
            ),
        )
        for group in grouped_problems.values():
            _write_page(
                pages_dir / "problems" / group["slug"],
                env.get_template("problem.html.jinja").render(
                    problem=group,
                    root_prefix=detail_prefix,
                    links=detail_links,
                ),
            )
            result.pages.append(f"problem:{group['slug']}")
        result.pages.append("problems")

    # Machine-readable problem exports. These are intentionally separate from
    # the HTML dossier: a tracker can consume the JSON without scraping the
    # presentation, and a problem may have several linked records.
    problem_groups_for_export: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for record in built_records:
        key = _problem_key(record)
        if key is not None:
            problem_groups_for_export[key].append(record)
    for (venue, problem_id), group in sorted(problem_groups_for_export.items()):
        group.sort(key=lambda record: record["record_id"])
        endpoint = pages_dir / "problems" / problem_slug(venue, problem_id) / "index.json"
        payload = {
            "export_schema_version": 1,
            "kind": "significance_problem",
            "venue": venue,
            "problem_id": problem_id,
            "problem_url": group[0]["problem_reference"]["url"],
            "records": [
                {
                    "record_id": record["record_id"],
                    "record": deepcopy(record),
                }
                for record in group
            ],
        }
        _write_json(endpoint, payload)
        result.pages.append(f"problem-json:{problem_slug(venue, problem_id)}")

    # Consumers can poll this without scraping HTML. The feed contains one
    # entry per current record; full evidence remains in the JSON exports.
    _write_feed(pages_dir / "feed.xml", built_records, public_url)
    result.pages.append("feed")

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
        row["display_name"] = (
            (party.get("name") or party.get("pseudonym"))
            if isinstance(party, dict)
            else row["id"].replace("-", " ")
        )
        if party and party.get("affiliation"):
            row["affiliation"] = party["affiliation"]
    reviewer_rows = sorted(reviewer_map.values(), key=lambda x: x["id"].lower())
    _write_page(
        pages_dir / "reviewers",
        env.get_template("reviewers.html.jinja").render(
            reviewers=reviewer_rows,
            root_prefix=pages_prefix,
            links=pages_links,
            public_url=public_url,
        ),
    )
    result.pages.append("reviewers")
    for reviewer in reviewer_rows:
        _write_page(
            pages_dir / "reviewers" / reviewer["id"],
            env.get_template("reviewer.html.jinja").render(
                reviewer=reviewer,
                root_prefix=detail_prefix,
                links=detail_links,
                public_url=public_url,
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

    # Frontier: every currently actionable invitation, grouped only by record
    # and task kind. This is a work queue, not a ranking of claims.
    frontier_rows = []
    for record in built_records:
        for index, invitation in enumerate(record.get("open_invitations", [])):
            status = invitation.get("status", "open")
            if status not in {"open", "taken"}:
                continue
            frontier_rows.append(
                {
                    "record": record,
                    "invitation": invitation,
                    "index": index,
                    "record_href": (
                        f"/records/{record['record_id']}/index.html"
                        if deployed
                        else f"../{record['record_id']}/index.html"
                    ),
                    "task_href": (
                        f"/tasks/{record['record_id']}/{task_id(invitation, index)}/index.html"
                        if deployed
                        else (
                            f"../tasks/{record['record_id']}/"
                            f"{task_id(invitation, index)}/index.html"
                        )
                    ),
                }
            )
    if frontier_rows:
        frontier_rows.sort(
            key=lambda row: (
                row["invitation"].get("status", "open") != "open",
                row["record"]["record_id"],
                row["index"],
            )
        )
        _write_page(
            pages_dir / "frontier",
            env.get_template("frontier.html.jinja").render(
                rows=frontier_rows, root_prefix=pages_prefix, links=pages_links
            ),
        )
        result.pages.append("frontier")

    # Each actionable invitation gets a stable reviewer-facing page. The page
    # is generated entirely from the record so the manuscript hash and scope
    # cannot drift from the task that invited the work.
    task_rows = []
    for record in built_records:
        for index, invitation in enumerate(record.get("open_invitations", [])):
            status = invitation.get("status", "open")
            if status not in {"open", "taken"}:
                continue
            tid = task_id(invitation, index)
            task_rows.append(
                {
                    "record": record,
                    "invitation": invitation,
                    "task_id": tid,
                    "record_href": (
                        f"/records/{record['record_id']}/index.html"
                        if deployed
                        else f"../{record['record_id']}/index.html"
                    ),
                    "task_href": (
                        f"/tasks/{record['record_id']}/{tid}/index.html"
                        if deployed
                        else f"../../tasks/{record['record_id']}/{tid}/index.html"
                    ),
                    "issue_url": _attestation_issue_url(invitation, record, tid),
                    "attestation_yaml": _attestation_yaml(record, invitation, tid),
                }
            )
    # Tasks nobody wrote down, implied by what a published record is missing.
    # They are computed here and never written into a record, so a real
    # exposition row removes one without an edit; and they are kept in their own
    # list so that nothing downstream — the frontier, the reviewer census, the
    # per-task attestation pages — can mistake a gap for somebody's invitation.
    derived_rows = []
    for record in built_records:
        derived = derived_exposition_task(record)
        if derived is None:
            continue
        derived_rows.append(
            {
                "record": record,
                "invitation": derived,
                "task_id": derived["task_id"],
                "derived": True,
                "anchor": f"derived-exposition-{record['record_id']}",
                "record_href": (
                    f"/records/{record['record_id']}/index.html"
                    if deployed
                    else f"../{record['record_id']}/index.html"
                ),
                "task_href": None,
            }
        )
    derived_rows.sort(key=lambda row: row["record"]["record_id"])

    if task_rows or derived_rows:
        task_rows.sort(key=lambda row: (row["record"]["record_id"], row["task_id"]))
        _write_page(
            pages_dir / "tasks",
            env.get_template("tasks.html.jinja").render(
                rows=task_rows,
                derived_rows=derived_rows,
                root_prefix=pages_prefix,
                links=pages_links,
            ),
        )
        result.pages.append("tasks")
        for row in task_rows:
            _write_page(
                pages_dir / "tasks" / row["record"]["record_id"] / row["task_id"],
                env.get_template("task.html.jinja").render(
                    row=row,
                    root_prefix=("/" if deployed else "../../../"),
                    links=links_for("/" if deployed else "../../../"),
                ),
            )
            result.pages.append(f"task:{row['record']['record_id']}:{row['task_id']}")

    # A board page sits two directories below its root (boards/<id>/), so its
    # relative prefix is one level deeper than the other auxiliary pages.
    board_prefix = "/records/" if deployed else "../../"
    board_template = env.get_template("board.html.jinja")
    records_by_id = {record["record_id"]: record for record in built_records}
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
        # The digestion column, derived from exposition evidence rather than
        # stated on the board. A board that carried its own digestion count
        # would be carrying evidence, which is the one thing the board schema
        # exists to prevent; deriving it means the column cannot disagree with
        # the record it links, and cannot outlive it.
        row_digestion = {}
        for row in board["rows"]:
            linked = records_by_id.get(row.get("record")) if row.get("record") else None
            if linked is None:
                continue
            found = expositions(linked)
            rid = linked["record_id"]
            if found:
                row_digestion[row["id"]] = {
                    "count": len(found),
                    "label": f"{len(found)} exposition{'' if len(found) == 1 else 's'}",
                    "href": (
                        f"/records/{rid}/#expositions"
                        if deployed
                        else f"../../{rid}/index.html#expositions"
                    ),
                }
            else:
                has_derived = derived_exposition_task(linked) is not None
                row_digestion[row["id"]] = {
                    "count": 0,
                    "label": "none yet",
                    "href": (
                        (
                            f"/tasks/index.html#derived-exposition-{rid}"
                            if deployed
                            else f"../../tasks/index.html#derived-exposition-{rid}"
                        )
                        if has_derived
                        else None
                    ),
                }
        _write_page(
            pages_dir / "boards" / board["board_id"],
            board_template.render(
                board=board,
                record_links=record_links,
                row_digestion=row_digestion,
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
        # The shell's /about/ page has to name who answers for this site, and
        # it may only present what this builder generated. Every value runs
        # through the same guard the Python pages use: anything still carrying
        # a [FILL] marker, or an address a mailto: link may not hold, arrives
        # as null. The shell then says the channel is not configured yet,
        # which is the one thing worse than no contact line -- a contact line
        # that goes nowhere -- avoided in the same way in both renderers.
        "site": {
            "maintainer_name": _configured(config.get("maintainer_name")),
            "repository_url": safe_href(config.get("repository_url")),
            "contact_email": safe_email(config.get("contact_email")),
        },
    }
    (out_dir / "index.json").write_text(
        json.dumps(index_data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    return result
