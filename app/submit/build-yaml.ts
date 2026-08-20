import { dump } from "js-yaml";
import type { AttributedDraft, EvidenceDraft, ReviewMapEntryDraft, WizardState } from "./types";
import { hasLocatorValue } from "./types";

function nowIso(): string {
  return new Date().toISOString();
}

function attributedValue(draft: AttributedDraft, nowText: string) {
  const out: Record<string, unknown> = {
    value: draft.value,
    basis: draft.basis,
    asserted_by: draft.assertedBy,
    asserted_at: nowText,
  };
  if (hasLocatorValue(draft.locator)) {
    out.locator = { ...draft.locator };
  }
  return out;
}

function evidenceItem(draft: EvidenceDraft, nowText: string): Record<string, unknown> {
  const base = { id: draft.id, kind: draft.kind, basis: draft.basis, asserted_by: draft.assertedBy, asserted_at: nowText };
  const locator = hasLocatorValue(draft.locator) ? { locator: { ...draft.locator } } : {};
  switch (draft.kind) {
    case "external_formal_artifact":
      return { ...base, repo: draft.repo, ...(draft.commit ? { commit: draft.commit } : {}), description: draft.description, ...locator };
    case "source_inspection":
      return { ...base, description: draft.description, ...locator };
    case "informal_review":
      return { ...base, reviewer: draft.reviewer, text: draft.text, ...locator };
    case "mathematical_assessment": {
      const report: Record<string, string> = {};
      if (draft.reportUrl) report.url = draft.reportUrl;
      if (draft.reportInline) report.inline = draft.reportInline;
      return { ...base, target: draft.target, report, ...locator };
    }
  }
}

function reviewMapEntry(draft: ReviewMapEntryDraft, nowText: string): Record<string, unknown> {
  return {
    text: draft.text,
    ...(draft.location ? { location: draft.location } : {}),
    ...(draft.pointer ? { pointer: draft.pointer } : {}),
    ...(draft.reason ? { reason: draft.reason } : {}),
    basis: draft.basis,
    asserted_by: draft.assertedBy,
    asserted_at: nowText,
    ...(hasLocatorValue(draft.locator) ? { locator: { ...draft.locator } } : {}),
  };
}

export function buildRecord(state: WizardState): Record<string, unknown> {
  const nowText = nowIso();
  const parties: Record<string, unknown> = {};
  for (const p of state.parties) {
    const vm: Record<string, unknown> = { kind: p.verificationKind };
    if (p.verificationIdentifier) vm.identifier = p.verificationIdentifier;
    parties[p.id] = { [p.isPseudonym ? "pseudonym" : "name"]: p.displayName, verification_method: vm };
  }

  return {
    schema_version: 1,
    record_id: state.recordId,
    record_version: 1,
    record_state: "active",
    freshness: { result: "unknown", checked_at: nowText },
    parties,
    claim: {
      id: "claim-main",
      text: attributedValue(state.claimText, nowText),
      scope: attributedValue(state.claimScope, nowText),
    },
    ...(state.readerSummary.value ? {
      plain_summary: {
        claimed: state.readerSummary.value,
        checked: state.checkedSummary.value,
        not_checked: state.notCheckedSummary.value,
        basis: "digest",
        asserted_by: state.readerSummary.assertedBy,
        asserted_at: nowText,
      },
    } : {}),
    ...(state.mainDeduction.text ? {
      review_map: {
        main_deduction: reviewMapEntry(state.mainDeduction, nowText),
        risks: state.riskPoints.map((entry) => reviewMapEntry(entry, nowText)),
        prerequisites: state.prerequisites.map((entry) => reviewMapEntry(entry, nowText)),
        ...(state.needsChecking.length ? { needs_checking: state.needsChecking.map((entry) => reviewMapEntry(entry, nowText)) } : {}),
      },
    } : {}),
    ...(state.formalizationTarget.value ? {
      formalization_handoff: {
        target: attributedValue(state.formalizationTarget, nowText),
        system: attributedValue(state.formalizationSystem, nowText),
        status: state.formalizationStatus,
        ...(state.formalizationOpenQuestion.value ? { open_questions: [attributedValue(state.formalizationOpenQuestion, nowText)] } : {}),
        ...(state.formalizationRepository ? {
          repository: {
            ...(state.formalizationRepository ? { url: state.formalizationRepository } : {}),
            ...(state.formalizationCommit ? { commit: state.formalizationCommit } : {}),
            ...(state.formalizationToolchain ? { toolchain: state.formalizationToolchain } : {}),
          },
        } : {}),
        basis: "editorial_inference",
        asserted_by: state.formalizationTarget.assertedBy,
        asserted_at: nowText,
      },
    } : {}),
    manuscript: {
      url: state.manuscriptUrl,
      label: state.manuscriptLabel,
      ...(state.manuscriptImmutableVersionId ? { immutable_version_id: state.manuscriptImmutableVersionId } : {}),
      sha256: state.manuscriptSha256,
      retrieved_at: nowText,
    },
    evidence: state.evidence.map((e) => evidenceItem(e, nowText)),
    ai_provenance: {
      disclosure: attributedValue(state.aiDisclosure, nowText),
      roles: state.aiRoles.map((r) => ({
        role: r.role,
        model: r.model,
        basis: r.basis,
        asserted_by: r.assertedBy,
        ...(hasLocatorValue(r.locator) ? { locator: { ...r.locator } } : {}),
      })),
    },
    history: [
      { id: "evt-created", type: "created", at: nowText, by: state.submitterPartyId || Object.keys(parties)[0] || "unknown" },
    ],
  };
}

export function recordToYaml(record: Record<string, unknown>): string {
  return dump(record, { noRefs: true, lineWidth: -1 });
}
