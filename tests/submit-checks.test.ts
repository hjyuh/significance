import assert from "node:assert/strict";
import test from "node:test";
import {
  checkAssertedByParties,
  checkSourceQuoteLocators,
  checkForbiddenLanguage,
  checkFreshnessRecomputation,
  checkExecutionReceiptAssertedByAutomation,
  runIntraRecordChecks,
} from "../app/submit/intra-record-checks.ts";

function baseRecord(overrides: Record<string, unknown> = {}) {
  return {
    parties: {
      "author-x": { name: "X", verification_method: { kind: "orcid" } },
      "ci-bot": { name: "ci-bot", verification_method: { kind: "automation" } },
    },
    claim: {
      text: { value: "A claim.", basis: "source_quote", asserted_by: "author-x", asserted_at: "2026-01-01T00:00:00Z", locator: { section: "1" } },
    },
    ...overrides,
  };
}

test("checkAssertedByParties flags an undeclared party", () => {
  const record = baseRecord({
    claim: { text: { value: "x", basis: "editorial_inference", asserted_by: "ghost", asserted_at: "2026-01-01T00:00:00Z" } },
  });
  const violations = checkAssertedByParties(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "unknown-party");
});

test("checkAssertedByParties passes when the party is declared", () => {
  const violations = checkAssertedByParties(baseRecord());
  assert.deepEqual(violations, []);
});

test("checkAssertedByParties flags an asserted_by matching an inherited Object.prototype key", () => {
  const record = baseRecord({
    claim: { text: { value: "x", basis: "editorial_inference", asserted_by: "constructor", asserted_at: "2026-01-01T00:00:00Z" } },
  });
  const violations = checkAssertedByParties(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "unknown-party");
});

test("checkSourceQuoteLocators flags a source_quote with no locator", () => {
  const record = baseRecord({
    claim: { text: { value: "x", basis: "source_quote", asserted_by: "author-x", asserted_at: "2026-01-01T00:00:00Z" } },
  });
  const violations = checkSourceQuoteLocators(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "source-quote-missing-locator");
});

test("checkSourceQuoteLocators flags a source_quote with an empty-object locator", () => {
  const record = baseRecord({
    claim: { text: { value: "x", basis: "source_quote", asserted_by: "author-x", asserted_at: "2026-01-01T00:00:00Z", locator: {} } },
  });
  const violations = checkSourceQuoteLocators(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "source-quote-missing-locator");
});

test("checkForbiddenLanguage flags 'verified' and 'proven' in prose fields", () => {
  const record = baseRecord({
    claim: { text: { value: "This is verified.", basis: "editorial_inference", asserted_by: "author-x", asserted_at: "2026-01-01T00:00:00Z" } },
  });
  const violations = checkForbiddenLanguage(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "forbidden-language");
});

test("checkFreshnessRecomputation flags observed != confirmed rendered as current", () => {
  const record = baseRecord({
    freshness: { result: "current", observed_source_version: "v2", confirmed_source_version: "v1", checked_at: "2026-01-01T00:00:00Z" },
  });
  const violations = checkFreshnessRecomputation(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "stale-rendered-current");
});

test("checkFreshnessRecomputation flags observed == confirmed rendered as stale", () => {
  const record = baseRecord({
    freshness: { result: "stale", observed_source_version: "v1", confirmed_source_version: "v1", checked_at: "2026-01-01T00:00:00Z" },
  });
  const violations = checkFreshnessRecomputation(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "derived-value-mismatch");
});

test("checkFreshnessRecomputation passes when result is unknown", () => {
  const record = baseRecord({ freshness: { result: "unknown", checked_at: "2026-01-01T00:00:00Z" } });
  assert.deepEqual(checkFreshnessRecomputation(record), []);
});

test("checkExecutionReceiptAssertedByAutomation flags a human asserter", () => {
  const record = baseRecord({
    evidence: [
      {
        id: "ev-1",
        kind: "computational_reproduction",
        description: "x",
        execution: {
          tool: "t", tool_version: "1", runner_image_digest: "sha256:" + "a".repeat(64),
          executed_at: "2026-01-01T00:00:00Z", result: "passed",
          log_sha256: "a".repeat(64), asserted_by: "author-x",
        },
      },
    ],
  });
  const violations = checkExecutionReceiptAssertedByAutomation(record);
  assert.equal(violations.length, 1);
  assert.equal(violations[0].rule, "execution-receipt-not-automation");
});

test("checkExecutionReceiptAssertedByAutomation passes when asserted by an automation party", () => {
  const record = baseRecord({
    evidence: [
      {
        id: "ev-1",
        kind: "computational_reproduction",
        description: "x",
        execution: {
          tool: "t", tool_version: "1", runner_image_digest: "sha256:" + "a".repeat(64),
          executed_at: "2026-01-01T00:00:00Z", result: "passed",
          log_sha256: "a".repeat(64), asserted_by: "ci-bot",
        },
      },
    ],
  });
  assert.deepEqual(checkExecutionReceiptAssertedByAutomation(record), []);
});

test("runIntraRecordChecks aggregates all five checks", () => {
  const violations = runIntraRecordChecks(baseRecord());
  assert.deepEqual(violations, []);
});
