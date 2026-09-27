#!/usr/bin/env python3
"""Check direct-URL reading maps stay out of normal Significance navigation."""

from __future__ import annotations

import re
import sys
from pathlib import Path

EXPECTED_IDS = ("289", "1095", "1220", "522", "132")
UNLISTED_PATH = "unlisted/recent-proof-claims"


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    if len(sys.argv) != 2:
        fail("usage: assert_unlisted_pages_unlinked.py SITE_DIR")

    site = Path(sys.argv[1])
    unlisted = site / UNLISTED_PATH
    if not unlisted.is_dir():
        fail(f"missing unlisted pages directory: {unlisted}")
    if (unlisted / "index.html").exists():
        fail("unlisted pages must not have a public listing/index page")

    page_paths = []
    for claim_id in EXPECTED_IDS:
        page = unlisted / claim_id / "index.html"
        if not page.is_file():
            fail(f"missing unlisted page for #{claim_id}: {page}")
        html = page.read_text(encoding="utf-8").lower()
        for required in (
            'name="robots" content="noindex,nofollow"',
            "not author-approved",
            "correction or removal request",
        ):
            if required not in html:
                fail(f"#{claim_id} is missing required disclosure: {required}")
        if re.search(r'href=["\'](?:\.\./)?(?:289|1095|1220|522|132)(?:/|["\'])', html):
            fail(f"#{claim_id} links to another unlisted reading map")
        page_paths.append(page)

    # A normal site page, generated feed, or asset must never expose a link to
    # these routes. Ignore the unlisted pages themselves, where the policy text
    # identifies their status and their shared stylesheet is expected.
    for path in site.rglob("*"):
        if not path.is_file() or unlisted in path.parents:
            continue
        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if UNLISTED_PATH in contents:
            fail(f"normal site output links to unlisted pages: {path}")


if __name__ == "__main__":
    main()
