import * as pdfjs from './pdfjs/pdf.mjs?v=6.4.299';

pdfjs.GlobalWorkerOptions.workerSrc = new URL('./pdfjs/pdf.worker.mjs?v=6.4.299', import.meta.url).href;
const dialog = document.querySelector('#pdf-reader');
const stage = dialog.querySelector('.reader-stage');
const title = dialog.querySelector('#reader-title');
const status = dialog.querySelector('#reader-status');
const pageInput = dialog.querySelector('#reader-page-number');
const total = dialog.querySelector('#reader-page-total');
const previous = dialog.querySelector('#reader-previous');
const next = dialog.querySelector('#reader-next');
const original = dialog.querySelector('#reader-original');
const zoomLabel = dialog.querySelector('#reader-zoom-label');
let documentPromise;
let metadataPromise;
let metadata;
let currentPage = 1;
let currentReference;
let zoom = 1;
let generation = 0;
let rendering;
let opener;
let resizeTimer;

function announce(message, error = false) {
  status.textContent = message;
  status.toggleAttribute('data-error', error);
}

function loadMetadata() {
  return metadataPromise ??= fetch(new URL('./references.json', import.meta.url))
    .then(response => {
      if (!response.ok) throw new Error('Reference index could not be loaded.');
      return response.json();
    });
}

function loadPDF() {
  if (!documentPromise) {
    const task = pdfjs.getDocument({ url: new URL('./manuscript.pdf', import.meta.url).href });
    documentPromise = task.promise.catch(error => {
      documentPromise = undefined;
      throw error;
    });
  }
  return documentPromise;
}

async function renderPage({ scrollToHighlight = true } = {}) {
  const version = ++generation;
  rendering?.cancel();
  announce('Loading the pinned manuscript…');
  try {
    const pdf = await loadPDF();
    if (version !== generation || !dialog.open) return;
    const page = await pdf.getPage(currentPage);
    if (version !== generation || !dialog.open) return;
    const base = page.getViewport({ scale: 1 });
    const padding = parseFloat(getComputedStyle(stage).paddingLeft) * 2;
    const available = Math.max(180, stage.clientWidth - padding - 4);
    const scale = Math.min(available / base.width, 1.65) * zoom;
    const viewport = page.getViewport({ scale });
    const ratio = Math.min(window.devicePixelRatio || 1, 2);
    const canvas = document.createElement('canvas');
    canvas.width = Math.ceil(viewport.width * ratio);
    canvas.height = Math.ceil(viewport.height * ratio);
    canvas.style.width = `${viewport.width}px`;
    canvas.style.height = `${viewport.height}px`;
    canvas.setAttribute('role', 'img');
    canvas.setAttribute('aria-label', `Original manuscript, page ${currentPage}. ${currentReference?.page === currentPage ? currentReference.label + ' heading highlighted.' : ''}`);
    const wrapper = document.createElement('div');
    wrapper.className = 'reader-page';
    wrapper.style.width = `${viewport.width}px`;
    wrapper.style.height = `${viewport.height}px`;
    wrapper.append(canvas);
    const renderTask = page.render({ canvas, viewport, transform: [ratio, 0, 0, ratio, 0, 0] });
    rendering = renderTask;
    await renderTask.promise;
    if (version !== generation || !dialog.open) return;
    rendering = undefined;
    let highlight;
    if (currentReference?.page === currentPage) {
      const [left, top, width, height] = currentReference.rect;
      highlight = document.createElement('div');
      highlight.className = 'pdf-highlight';
      highlight.style.cssText = `left:${left * 100}%;top:${top * 100}%;width:${width * 100}%;height:${height * 100}%`;
      highlight.title = currentReference.label;
      wrapper.append(highlight);
    }
    stage.replaceChildren(wrapper);
    pageInput.value = currentPage;
    pageInput.max = pdf.numPages;
    pageInput.disabled = false;
    total.textContent = `/ ${pdf.numPages}`;
    previous.disabled = currentPage === 1;
    next.disabled = currentPage === pdf.numPages;
    original.href = `manuscript.pdf#page=${currentPage}`;
    zoomLabel.textContent = zoom === 1 ? 'Fit width' : `${Math.round(zoom * 100)}%`;
    if (scrollToHighlight) {
      stage.scrollTop = highlight ? Math.max(0, highlight.offsetTop - stage.clientHeight * 0.25) : 0;
      stage.scrollLeft = 0;
    }
    announce(highlight ? `Page ${currentPage} · ${currentReference.label} — reference heading highlighted in yellow.` : `Page ${currentPage} · Original pinned manuscript.`);
  } catch (error) {
    if (version !== generation || error?.name === 'RenderingCancelledException') return;
    announce('The PDF reader could not load this page. You can still open or download the pinned PDF using the links above.', true);
    console.error('Manuscript reader:', error);
  }
}

async function openReference(link) {
  opener = link;
  if (!dialog.open) dialog.showModal();
  announce('Locating the manuscript reference…');
  title.textContent = 'Pinned manuscript';
  try {
    metadata = await loadMetadata();
    currentReference = metadata.references[link.dataset.pdfRef];
    if (!currentReference) throw new Error('Unknown manuscript reference.');
    currentPage = currentReference.page;
    title.textContent = currentReference.label;
    zoom = 1;
    await renderPage();
  } catch (error) {
    announce('This reference could not be located. Open the pinned PDF directly using the link above.', true);
    console.error('Manuscript reference:', error);
  }
}

document.addEventListener('click', event => {
  const link = event.target.closest('a[data-pdf-ref]');
  if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
  event.preventDefault();
  event.stopPropagation();
  openReference(link);
});
dialog.querySelector('#reader-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('close', () => {
  generation++;
  rendering?.cancel();
  opener?.focus();
});
previous.addEventListener('click', () => { currentPage--; renderPage(); });
next.addEventListener('click', () => { currentPage++; renderPage(); });
pageInput.addEventListener('change', () => {
  const number = Number(pageInput.value);
  if (!Number.isInteger(number) || number < 1 || number > metadata.pageCount) {
    pageInput.value = currentPage;
    announce(`Choose a page from 1 to ${metadata.pageCount}.`, true);
    return;
  }
  currentPage = number;
  renderPage();
});
dialog.querySelector('#reader-zoom-in').addEventListener('click', () => { zoom = Math.min(2.5, zoom + 0.25); renderPage(); });
dialog.querySelector('#reader-zoom-out').addEventListener('click', () => { zoom = Math.max(0.5, zoom - 0.25); renderPage(); });
dialog.querySelector('#reader-fit').addEventListener('click', () => { zoom = 1; renderPage(); });
window.addEventListener('resize', () => {
  clearTimeout(resizeTimer);
  if (dialog.open) resizeTimer = setTimeout(() => renderPage(), 150);
});
