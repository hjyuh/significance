"""Explicitly approved editorial companions, separate from claim records."""
from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PUBLISHED = ROOT / "data" / "published-companions.json"
ASSETS = ("index.html", "reader.js", "reader.css", "references.json", "manuscript.pdf",
          "manuscript-LICENSE", "pdfjs/pdf.mjs", "pdfjs/pdf.worker.mjs", "pdfjs/LICENSE")


def published_companions() -> list[dict]:
    if not PUBLISHED.exists():
        return []
    entries = json.loads(PUBLISHED.read_text(encoding="utf-8"))
    for entry in entries:
        if not re.fullmatch(r"[a-z0-9-]+", entry["slug"]):
            raise ValueError("Invalid companion slug")
        source = (ROOT / entry["source"]).resolve()
        if not source.is_relative_to((ROOT / "drafts" / "companions").resolve()):
            raise ValueError("Companion source must stay within the companion directory")
    return entries


def build_companions(pages_dir: Path, static_dir: Path) -> None:
    for entry in published_companions():
        source = ROOT / entry["source"]
        target = pages_dir / "companions" / entry["slug"]
        for asset in ASSETS:
            destination = target / asset
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / asset, destination)
        # Local app and flat Pages builds keep the shared assets in different places.
        prefix = Path(os.path.relpath(static_dir, target)).as_posix()
        html = (target / "index.html").read_text(encoding="utf-8")
        html = html.replace("../../records/static/", prefix + "/")
        (target / "index.html").write_text(html, encoding="utf-8")
