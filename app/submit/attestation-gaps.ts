import type { AttributedDraft, WizardState } from "./types";
import { hasLocatorValue } from "./types";

// Wizard-only enforcement of the design's core consent mechanism: a
// third-party submitter must not be able to export an unlocated
// author_attestation. This can't live in intra-record-checks.ts because
// it needs the submitter's role, which isn't part of the assembled
// record — the record has no notion of "who is submitting this PR."
//
// source_quote is deliberately NOT covered here — that's
// checkSourceQuoteLocators's job in intra-record-checks.ts, which applies
// regardless of submitter role. Keep these two mechanisms' responsibilities
// separate: this one is about consent (a third party vouching for what an
// author privately said), that one is about sourcing (any claim quoting
// a source needs to say where).

export interface AttestationGap {
  rule: string;
  location: string;
  message: string;
}

export function computeThirdPartyAttestationGaps(state: WizardState, thirdParty: boolean): AttestationGap[] {
  if (!thirdParty) return [];
  // Only basis/locator matter here, so this is typed as that narrower
  // shape rather than the full AttributedDraft — EvidenceDraft and
  // AiRoleDraft both have basis/locator but aren't otherwise assignable
  // to AttributedDraft (neither has `value`).
  const fields: { location: string; draft: Pick<AttributedDraft, "basis" | "locator"> }[] = [
    { location: "claim.text", draft: state.claimText },
    { location: "claim.scope", draft: state.claimScope },
    { location: "ai_provenance.disclosure", draft: state.aiDisclosure },
    ...state.evidence.map((e, i) => ({ location: `evidence[${i}]`, draft: e })),
    ...state.aiRoles.map((r, i) => ({ location: `ai_provenance.roles[${i}]`, draft: r })),
  ];
  return fields
    .filter((f) => f.draft.basis === "author_attestation" && !hasLocatorValue(f.draft.locator))
    .map((f) => ({
      rule: "third-party-attestation-missing-locator",
      location: f.location,
      message: "author_attestation from a third-party submitter needs a locator (a correspondence link or public statement) before this can be exported.",
    }));
}
