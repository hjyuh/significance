# Family 159 companion demo

This editorial companion is approved for publication through
`data/published-companions.json`. `index.html` is its source. The Python site
build copies an explicit asset list to `/companions/family-159/`, adjusting
the shared comments assets for the flat Pages and local app layouts.
The companion is separate from the YAML claim records and evidence counts.
The older `/author-review/` path remains a local preview only.
Serve over HTTP; ES modules and the PDF worker do not run from `file://`.
The server must serve `.mjs` as JavaScript (`text/javascript`).

Comments reuse the site's account, verified-email and moderation rules. The
dedicated Firestore registry document is
`tasks/companion-openai-family-159__discussion`, with `record_id` set to
`companion-openai-family-159` and `task_id` set to `discussion`. The approved
entry is also listed by `backend/firebase/tasks_manifest.py`; the owner console
registered it on October 17, 2026. It is not a mathematical review task.

The original manuscript is displayed without modification. `reader.js` renders
it in a native modal dialog using locally bundled PDF.js 6.4.299 (legacy build,
from the official `pdfjs-dist` package). PDF.js's license is in `pdfjs/LICENSE`.
There is no CDN dependency. Without JavaScript, reference links open the PDF
with a page fragment and the download remains available.

## Source provenance

- OpenAI, *Quasipolynomial Bounds for Arithmetic Progressions*, September 23, 2026.
- Repository: https://github.com/openai/math
- Revision: `fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`
- Path: `preprints/Quasipolynomial-Bounds-for-Arithmetic-Progressions-September-23-2026/paper.pdf`
- SHA-256: `481eaf7730dc4d581e5270cc4d514c6ee2ec386d5af643cf914e20b4d00c59be`
- Original repository license: `manuscript-LICENSE` (Apache 2.0).

## Reference highlights

Run `node build-references.mjs` from this directory to rebuild `references.json`.
The build checks that each of the 28 reference headings occurs on its specified
PDF page, then records normalized bounding rectangles from the PDF text geometry.
It fails on a missing heading. These are reference locations, not proof checks.
The viewer highlights the heading line, rather than claiming to mark every page
of a multi-section passage. Page navigation and zoom preserve the pinned source.

Links use `data-pdf-ref` keys from this index; their `href` remains a usable
direct PDF link. The PDF itself and the generated coordinates must be updated
together if a different source version is chosen.

## Browser checks, October 17, 2026

Confirmed opening the full PDF, a highlighted Theorem 1.1 on page 4,
Proposition 4.1 on page 25 (from within a collapsed proof-map stage), Table 1
on page 85, previous/next page navigation, zoom, and closing with Escape.
These checks validate navigation and presentation, not the manuscript's proof.
