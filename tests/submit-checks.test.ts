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
import { buildPrComposeUrl } from "../app/submit/github-link.ts";
import { buildRecord, recordToYaml } from "../app/submit/build-yaml.ts";
import { validateAgainstSchema, validateAgainstSchemaNow } from "../app/submit/schema-validate.ts";
import { emptyWizardState } from "../app/submit/types.ts";
import { computeThirdPartyAttestationGaps } from "../app/submit/attestation-gaps.ts";
import { isSubmissionReady } from "../app/submit/submission-readiness.ts";

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

test("buildPrComposeUrl returns a URL under the length ceiling", () => {
  const result = buildPrComposeUrl("2026-test-example", "schema_version: 1\n");
  assert.equal(result.tooLong, false);
  assert.match(result.url ?? "", /^https:\/\/github\.com\/hjyuh\/significance\/new\/main\?filename=records\/2026-test-example\.yaml&value=/);
});

test("buildPrComposeUrl refuses an oversized record rather than truncating", () => {
  const hugeYaml = "x".repeat(10000);
  const result = buildPrComposeUrl("2026-test-example", hugeYaml);
  assert.equal(result.url, null);
  assert.equal(result.tooLong, true);
});

test("recordToYaml renders actual YAML content (guards against js-yaml's default-export trap)", () => {
  const result = recordToYaml({ a: 1 });
  assert.match(result, /a: 1/);
});

test("validateAgainstSchema returns [] in a plain Node context with no window (SSR-safe by design)", () => {
  assert.equal(typeof window, "undefined");
  assert.deepEqual(validateAgainstSchema({}), []);
});

test("the actual Ajv path accepts a complete record generated by the wizard", () => {
  const state = emptyWizardState();
  state.submitterRole = "author";
  state.submitterPartyId = "author-x";
  state.recordId = "2026-x-topic";
  state.parties = [{
    id: "author-x",
    displayName: "X",
    isPseudonym: false,
    verificationKind: "github_identity",
    verificationIdentifier: "author-x",
  }];
  state.claimText = { value: "A claim.", basis: "author_attestation", assertedBy: "author-x" };
  state.claimScope = { value: "The stated scope.", basis: "author_attestation", assertedBy: "author-x" };
  state.manuscriptUrl = "https://example.org/manuscript.pdf";
  state.manuscriptLabel = "v1";
  state.manuscriptSha256 = "a".repeat(64);
  state.evidence = [{
    id: "ev-artifact",
    kind: "external_formal_artifact",
    repo: "https://example.org/repository",
    commit: "abcdef1",
    description: "A publicly reported artifact.",
    basis: "author_attestation",
    assertedBy: "author-x",
  }];
  state.aiDisclosure = { value: "AI use disclosed.", basis: "author_attestation", assertedBy: "author-x" };

  assert.deepEqual(validateAgainstSchemaNow(buildRecord(state)), []);
});

test("submission readiness requires a role and every browser-side check to pass", () => {
  assert.equal(isSubmissionReady({
    submitterRole: "author",
    schemaErrorCount: 0,
    intraRecordViolationCount: 0,
    attestationGapCount: 0,
  }), true);

  for (const blocked of [
    { submitterRole: null, schemaErrorCount: 0, intraRecordViolationCount: 0, attestationGapCount: 0 },
    { submitterRole: "author" as const, schemaErrorCount: 1, intraRecordViolationCount: 0, attestationGapCount: 0 },
    { submitterRole: "author" as const, schemaErrorCount: 0, intraRecordViolationCount: 1, attestationGapCount: 0 },
    { submitterRole: "third_party" as const, schemaErrorCount: 0, intraRecordViolationCount: 0, attestationGapCount: 1 },
  ]) {
    assert.equal(isSubmissionReady(blocked), false);
  }
});

test("buildRecord passes ai_provenance.roles through with no locator key when none was given", () => {
  const state = emptyWizardState();
  state.aiRoles = [
    { role: "proof_generation", model: "test-model", basis: "author_attestation", assertedBy: "author-x" },
  ];
  const record = buildRecord(state) as { ai_provenance: { roles: Record<string, unknown>[] } };
  assert.equal(record.ai_provenance.roles.length, 1);
  assert.equal(record.ai_provenance.roles[0].basis, "author_attestation");
  assert.ok(!("locator" in record.ai_provenance.roles[0]));
});

test("buildRecord includes a locator on ai_provenance.roles when one was given", () => {
  const state = emptyWizardState();
  state.aiRoles = [
    {
      role: "proof_generation",
      model: "test-model",
      basis: "author_attestation",
      assertedBy: "author-x",
      locator: { url: "https://example.com/correspondence" },
    },
  ];
  const record = buildRecord(state) as { ai_provenance: { roles: Record<string, unknown>[] } };
  assert.deepEqual(record.ai_provenance.roles[0].locator, { url: "https://example.com/correspondence" });
});

test("computeThirdPartyAttestationGaps flags third-party claim.text author_attestation with no locator", () => {
  const state = emptyWizardState();
  state.claimText = { value: "x", basis: "author_attestation", assertedBy: "author-x" };
  const gaps = computeThirdPartyAttestationGaps(state, true);
  assert.equal(gaps.length, 1);
  assert.equal(gaps[0].location, "claim.text");
  assert.equal(gaps[0].rule, "third-party-attestation-missing-locator");
});

test("computeThirdPartyAttestationGaps passes third-party claim.text author_attestation with a locator", () => {
  const state = emptyWizardState();
  state.claimText = {
    value: "x", basis: "author_attestation", assertedBy: "author-x",
    locator: { url: "https://example.com/correspondence" },
  };
  assert.deepEqual(computeThirdPartyAttestationGaps(state, true), []);
});

test("computeThirdPartyAttestationGaps flags a third-party evidence item's author_attestation with no locator", () => {
  const state = emptyWizardState();
  state.evidence = [
    { id: "ev-1", kind: "informal_review", basis: "author_attestation", assertedBy: "author-x", reviewer: "r", text: "t" },
  ];
  const gaps = computeThirdPartyAttestationGaps(state, true);
  assert.equal(gaps.length, 1);
  assert.equal(gaps[0].location, "evidence[0]");
});

test("computeThirdPartyAttestationGaps flags a third-party AI role's author_attestation with no locator", () => {
  const state = emptyWizardState();
  state.aiRoles = [
    { role: "proof_generation", model: "m", basis: "author_attestation", assertedBy: "author-x" },
  ];
  const gaps = computeThirdPartyAttestationGaps(state, true);
  assert.equal(gaps.length, 1);
  assert.equal(gaps[0].location, "ai_provenance.roles[0]");
});

test("computeThirdPartyAttestationGaps is a no-op on the author path, even with unlocated author_attestation everywhere", () => {
  const state = emptyWizardState();
  state.claimText = { value: "x", basis: "author_attestation", assertedBy: "author-x" };
  state.claimScope = { value: "x", basis: "author_attestation", assertedBy: "author-x" };
  state.aiDisclosure = { value: "x", basis: "author_attestation", assertedBy: "author-x" };
  state.evidence = [
    { id: "ev-1", kind: "informal_review", basis: "author_attestation", assertedBy: "author-x", reviewer: "r", text: "t" },
  ];
  state.aiRoles = [
    { role: "proof_generation", model: "m", basis: "author_attestation", assertedBy: "author-x" },
  ];
  assert.deepEqual(computeThirdPartyAttestationGaps(state, false), []);
});

test("computeThirdPartyAttestationGaps does not flag source_quote — that's checkSourceQuoteLocators's job", () => {
  const state = emptyWizardState();
  state.claimText = { value: "x", basis: "source_quote", assertedBy: "author-x" };
  assert.deepEqual(computeThirdPartyAttestationGaps(state, true), []);
});
