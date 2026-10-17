// Rebuild highlight locations from the pinned PDF. Run from this directory.
import fs from 'node:fs';
import { getDocument, Util } from './pdfjs/pdf.mjs';
Promise.try ??= (callback, ...args) => new Promise(resolve => resolve(callback(...args)));

export const definitions = [
  ['paper', 'Pinned manuscript', 1, 'Quasipolynomial Bounds'],
  ['theorem-1-1', 'Theorem 1.1', 4, 'Theorem 1.1'],
  ['corollary-1-2', 'Corollary 1.2', 4, 'Corollary 1.2'],
  ['section-1-1', '§1.1 · Density thresholds and summability', 5, 'Density thresholds and summability'],
  ['section-1-2', '§1.2 · Prior density bounds', 5, 'Prior density bounds'],
  ['section-1-5', '§1.5 · How to read the proof', 8, 'How to read the proof'],
  ['section-2', '§2 · Polynomial cells and the increment theorem', 8, 'Polynomial cells and the increment theorem'],
  ['section-2-8', '§2.8 · From a cell to the next certificate', 12, 'From a cell to the next certificate'],
  ['theorem-2-1', 'Theorem 2.1 · Triangular increment', 10, 'Theorem 2.1'],
  ['lemma-2-2', 'Lemma 2.2 · Dimension-independent fresh rank', 11, 'Lemma 2.2'],
  ['figure-3', 'Figure 3 · Main proof route', 14, 'Figure 3:'],
  ['section-3', '§3 · Constrained paths', 14, 'Constrained paths and their detection estimates'],
  ['section-4', '§4 · Preparing a cell by rank cuts', 24, 'Preparing a cell by rank cuts'],
  ['proposition-4-1', 'Proposition 4.1', 25, 'Proposition 4.1'],
  ['section-5', '§5 · Detection independent of the current width', 36, 'Detection independent of the current width'],
  ['section-6', '§6 · Forward sampling of a prepared cell', 40, 'Forward sampling of a prepared cell'],
  ['proposition-6-2', 'Proposition 6.2', 42, 'Proposition 6.2'],
  ['section-7', '§7 · Returning the increment', 44, 'Returning the increment: comparison and passive layers'],
  ['proposition-7-8', 'Proposition 7.8', 57, 'Proposition 7.8'],
  ['section-8', '§8 · Active globalization with exact marking', 60, 'Active globalization with exact marking'],
  ['theorem-8-2', 'Theorem 8.2', 61, 'Theorem 8.2'],
  ['section-9', '§9 · Parameter extraction and exact restoration', 69, 'Parameter extraction and exact restoration'],
  ['proposition-9-1', 'Proposition 9.1', 70, 'Proposition 9.1'],
  ['section-10', '§10 · Triangular iteration', 76, 'Triangular iteration'],
  ['proposition-10-2', 'Proposition 10.2 · Triangular dimension bounds', 77, 'Proposition 10.2'],
  ['section-11', '§11 · Weighted consequences', 82, 'Weighted consequences'],
  ['table-1', 'Table 1 · Analytic inputs', 85, 'Table 1:'],
  ['appendices', 'Appendix A · Quantitative conventions and symbols', 86, 'Quantitative conventions and symbols'],
];

const task = getDocument({ data: new Uint8Array(fs.readFileSync(new URL('./manuscript.pdf', import.meta.url))), useSystemFonts: true });
const pdf = await task.promise;
const references = {};
for (const [id, label, pageNumber, needle] of definitions) {
  const page = await pdf.getPage(pageNumber);
  const { items } = await page.getTextContent();
  const match = items.find(item => item.str?.includes(needle));
  if (!match) throw new Error(`Missing reference ${id} on page ${pageNumber}: ${needle}`);
  const viewport = page.getViewport({ scale: 1 });
  const line = items.filter(item => item.str?.trim() && Math.abs(item.transform[5] - match.transform[5]) < 2);
  const rects = line.map(item => {
    const m = Util.transform(viewport.transform, item.transform);
    const height = Math.hypot(m[2], m[3]);
    return [m[4] - 3, m[5] - height - 2, m[4] + item.width + 3, m[5] + 4];
  });
  const left = Math.min(...rects.map(r => r[0]));
  const top = Math.min(...rects.map(r => r[1]));
  const right = Math.max(...rects.map(r => r[2]));
  const bottom = Math.max(...rects.map(r => r[3]));
  references[id] = { label, page: pageNumber, needle, rect: [left / viewport.width, top / viewport.height, (right - left) / viewport.width, (bottom - top) / viewport.height] };
}
fs.writeFileSync(new URL('./references.json', import.meta.url), JSON.stringify({ pageCount: pdf.numPages, references }, null, 2) + '\n');
console.log(`Located ${definitions.length} reference headings across ${pdf.numPages} PDF pages.`);
await task.destroy();
