const REPO_URL = "https://github.com/hjyuh/significance";
// GitHub's /new/ file-editor endpoint has no documented hard limit, but very
// long query strings silently fail or get truncated by browsers/proxies
// well before typical URL-length ceilings (~8k chars). 6000 leaves margin.
const PR_COMPOSE_LENGTH_CEILING = 6000;

export interface PrComposeResult {
  url: string | null;
  tooLong: boolean;
}

export function buildPrComposeUrl(recordId: string, yamlText: string): PrComposeResult {
  // record_id is regex-constrained to [0-9a-z-], so the filename segment
  // never needs percent-encoding; only the YAML content does.
  const filename = `records/${recordId}.yaml`;
  const url = `${REPO_URL}/new/main?filename=${filename}&value=${encodeURIComponent(yamlText)}`;
  if (url.length > PR_COMPOSE_LENGTH_CEILING) {
    return { url: null, tooLong: true };
  }
  return { url, tooLong: false };
}

export function triggerYamlDownload(recordId: string, yamlText: string): void {
  const blob = new Blob([yamlText], { type: "application/yaml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${recordId || "record"}.yaml`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Revoking in the same tick as .click() is a documented Firefox gotcha:
  // the download is queued asynchronously, and an immediate revoke can
  // race it and silently drop the download. Defer to the next macrotask,
  // as FileSaver.js and similar libraries do.
  setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function buildMailtoUrl(recordId: string): string {
  // Deliberately does NOT put the YAML body in the mailto: link — most
  // mail clients truncate mailto bodies around ~2k characters, which
  // would silently mangle any real record. Caller must trigger the
  // download first; this just reminds the recipient to attach it.
  const subject = encodeURIComponent(`Significance record submission: ${recordId || "untitled"}`);
  const body = encodeURIComponent(
    `A record file (${recordId || "record"}.yaml) should have just downloaded to your computer. ` +
    "Please attach it to this email before sending."
  );
  return `mailto:?subject=${subject}&body=${body}`;
}
