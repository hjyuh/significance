// Hand-ported subset of src/significance/semantics.py's checks, for
// client-side use before a PR exists to run the real validator against.
// Only checks that are (a) purely intra-record and (b) need no hashing,
// git, or network access are ported here. See
// docs/plans/2026-08-02-submission-wizard-design.md §4 for the full list
// and the checks deliberately NOT ported (uniqueness, append-only).
//
// If semantics.py's check_asserted_by_parties, check_source_quote_locators,
// check_forbidden_language, check_freshness_recomputation, or
// check_execution_receipt_asserted_by_automation change, update this file
// to match — there is no shared source between the two languages.

export interface Violation {
  rule: string;
  message: string;
  location: string;
}

type JsonNode = unknown;

function* walk(node: JsonNode, path: (string | number)[] = []): Generator<[(string | number)[], JsonNode]> {
  yield [path, node];
  if (Array.isArray(node)) {
    for (let i = 0; i < node.length; i++) yield* walk(node[i], [...path, i]);
  } else if (node && typeof node === "object") {
    for (const [k, v] of Object.entries(node as Record<string, unknown>)) yield* walk(v, [...path, k]);
  }
}

function formatPath(path: (string | number)[]): string {
  if (path.length === 0) return "$";
  const parts: string[] = [];
  for (const p of path) {
    if (typeof p === "number") {
      parts.length ? (parts[parts.length - 1] += `[${p}]`) : parts.push(`[${p}]`);
    } else {
      parts.push(p);
    }
  }
  return parts.join(".");
}

function isDict(node: JsonNode): node is Record<string, unknown> {
  return !!node && typeof node === "object" && !Array.isArray(node);
}

export function checkAssertedByParties(record: Record<string, unknown>): Violation[] {
  const parties = isDict(record.parties) ? record.parties : {};
  const violations: Violation[] = [];
  for (const [path, node] of walk(record)) {
    if (!isDict(node)) continue;
    const partyId = node.asserted_by;
    if (typeof partyId === "string" && !Object.hasOwn(parties, partyId)) {
      violations.push({
        rule: "unknown-party",
        message: `asserted_by references undeclared party '${partyId}'`,
        location: formatPath([...path, "asserted_by"]),
      });
    }
  }
  return violations;
}

function hasLocator(v: unknown): boolean {
  // Mirrors Python truthiness: an empty dict is falsy there, but `{}` is
  // truthy in JS, so an empty locator/source object must be treated as
  // "not actually given" rather than passing the check.
  return isDict(v) && Object.keys(v).length > 0;
}

export function checkSourceQuoteLocators(record: Record<string, unknown>): Violation[] {
  const violations: Violation[] = [];
  for (const [path, node] of walk(record)) {
    if (!isDict(node)) continue;
    if (node.basis !== "source_quote") continue;
    if (hasLocator(node.locator) || hasLocator((node as Record<string, unknown>).source)) continue;
    violations.push({
      rule: "source-quote-missing-locator",
      message: "basis is source_quote but no locator (or source) is given",
      location: formatPath(path),
    });
  }
  return violations;
}

const PROSE_KEYS = new Set(["text", "value", "inline", "quote", "description", "note"]);
const FORBIDDEN_WORDS = ["verified", "proven"];

export function checkForbiddenLanguage(record: Record<string, unknown>): Violation[] {
  const violations: Violation[] = [];
  for (const [path, node] of walk(record)) {
    if (!isDict(node)) continue;
    for (const [key, value] of Object.entries(node)) {
      if (!PROSE_KEYS.has(key) || typeof value !== "string") continue;
      const lowered = value.toLowerCase();
      for (const word of FORBIDDEN_WORDS) {
        if (lowered.includes(word)) {
          violations.push({
            rule: "forbidden-language",
            message: `rendered prose contains forbidden word '${word}'`,
            location: formatPath([...path, key]),
          });
        }
      }
    }
  }
  return violations;
}

export function checkFreshnessRecomputation(record: Record<string, unknown>): Violation[] {
  const freshness = record.freshness;
  if (!isDict(freshness)) return [];
  const result = freshness.result;
  const observed = freshness.observed_source_version;
  const confirmed = freshness.confirmed_source_version;
  if (result === "unknown" || observed == null || confirmed == null) return [];

  const recomputed = observed === confirmed ? "current" : "stale";
  if (result === recomputed) return [];
  if (result === "current" && recomputed === "stale") {
    return [{
      rule: "stale-rendered-current",
      message: `observed_source_version (${JSON.stringify(observed)}) != confirmed_source_version ` +
        `(${JSON.stringify(confirmed)}) recomputes to 'stale', but freshness.result is 'current'`,
      location: "freshness.result",
    }];
  }
  return [{
    rule: "derived-value-mismatch",
    message: `freshness.result is ${JSON.stringify(result)} but recomputing from observed/confirmed ` +
      `source versions gives ${JSON.stringify(recomputed)}`,
    location: "freshness.result",
  }];
}

const EXECUTION_RECEIPT_KEYS = [
  "tool", "tool_version", "runner_image_digest", "executed_at", "result", "log_sha256", "asserted_by",
];

export function checkExecutionReceiptAssertedByAutomation(record: Record<string, unknown>): Violation[] {
  const parties = isDict(record.parties) ? record.parties : {};
  const violations: Violation[] = [];
  for (const [path, node] of walk(record)) {
    if (!isDict(node)) continue;
    if (!EXECUTION_RECEIPT_KEYS.every((k) => k in node)) continue;
    const partyId = node.asserted_by;
    const party = typeof partyId === "string" && Object.hasOwn(parties, partyId) ? parties[partyId] : undefined;
    if (!isDict(party)) continue; // unknown-party is checkAssertedByParties's job
    const vm = isDict(party.verification_method) ? party.verification_method : {};
    if (vm.kind !== "automation") {
      violations.push({
        rule: "execution-receipt-not-automation",
        message: `execution_receipt asserted_by '${String(partyId)}' has verification_method.kind ` +
          `${JSON.stringify(vm.kind ?? null)}, expected 'automation'`,
        location: formatPath([...path, "asserted_by"]),
      });
    }
  }
  return violations;
}

export function runIntraRecordChecks(record: Record<string, unknown>): Violation[] {
  return [
    ...checkAssertedByParties(record),
    ...checkSourceQuoteLocators(record),
    ...checkForbiddenLanguage(record),
    ...checkFreshnessRecomputation(record),
    ...checkExecutionReceiptAssertedByAutomation(record),
  ];
}
