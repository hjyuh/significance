export type SubmitterRole = "author" | "third_party";
export type Basis = "source_quote" | "author_attestation" | "editorial_inference";
// machine_result is deliberately excluded: the wizard never lets a
// submitter hand-author a machine_result value anywhere.
export type VerificationKind = "github_identity" | "orcid" | "email_confirmation" | "pseudonymous";
// automation is deliberately excluded from the wizard's own party-kind
// choices: an automation party is only ever meaningful for the
// execution-receipt-bearing evidence kinds the wizard doesn't support.

export interface LocatorDraft {
  section?: string;
  url?: string;
  quote?: string;
}

// Shared by every place a draft-level basis+locator pair needs checking
// (SubmitWizard.tsx's per-field locator gating, build-yaml.ts's
// locator-inclusion-on-export logic, and the attestation-gap scan). Not
// the same thing as intra-record-checks.ts's own hasLocator, which checks
// post-assembly dict truthiness on the built record — different input
// shape, different job, deliberately not unified with this one.
export function hasLocatorValue(locator: LocatorDraft | undefined): boolean {
  return !!(locator && (locator.section || locator.url || locator.quote));
}

export interface AttributedDraft {
  value: string;
  basis: Basis;
  assertedBy: string;
  locator?: LocatorDraft;
}

export interface PartyDraft {
  id: string;
  isPseudonym: boolean;
  displayName: string;
  verificationKind: VerificationKind;
  verificationIdentifier: string;
}

export interface EvidenceDraftBase {
  id: string;
  basis: Basis;
  assertedBy: string;
  locator?: LocatorDraft;
}

export interface ExternalFormalArtifactDraft extends EvidenceDraftBase {
  kind: "external_formal_artifact";
  repo: string;
  commit: string;
  description: string;
}

export interface InformalReviewDraft extends EvidenceDraftBase {
  kind: "informal_review";
  reviewer: string;
  text: string;
}

export interface SourceInspectionDraft extends EvidenceDraftBase {
  kind: "source_inspection";
  description: string;
}

export interface MathematicalAssessmentDraft extends EvidenceDraftBase {
  kind: "mathematical_assessment";
  target: string;
  reportUrl: string;
  reportInline: string;
}

export type EvidenceDraft = ExternalFormalArtifactDraft | SourceInspectionDraft | InformalReviewDraft | MathematicalAssessmentDraft;

export interface AiRoleDraft {
  role: string;
  model: string;
  basis: Basis;
  assertedBy: string;
  locator?: LocatorDraft;
}

export interface ReviewMapEntryDraft {
  text: string;
  location: string;
  pointer: string;
  reason: string;
  basis: Basis;
  assertedBy: string;
  locator?: LocatorDraft;
}

export type FormalizationStatus = "not_started" | "statement_prepared" | "proof_incomplete" | "artifact_reported" | "artifact_reproduced";

export interface WizardState {
  submitterRole: SubmitterRole | null;
  submitterPartyId: string;
  recordId: string;
  parties: PartyDraft[];
  claimText: AttributedDraft;
  claimScope: AttributedDraft;
  manuscriptUrl: string;
  manuscriptLabel: string;
  manuscriptImmutableVersionId: string;
  manuscriptSha256: string;
  evidence: EvidenceDraft[];
  aiDisclosure: AttributedDraft;
  aiRoles: AiRoleDraft[];
  readerSummary: AttributedDraft;
  checkedSummary: AttributedDraft;
  notCheckedSummary: AttributedDraft;
  mainDeduction: ReviewMapEntryDraft;
  riskPoints: ReviewMapEntryDraft[];
  prerequisites: ReviewMapEntryDraft[];
  needsChecking: ReviewMapEntryDraft[];
  formalizationTarget: AttributedDraft;
  formalizationSystem: AttributedDraft;
  formalizationStatus: FormalizationStatus;
  formalizationRepository: string;
  formalizationCommit: string;
  formalizationToolchain: string;
  formalizationOpenQuestion: AttributedDraft;
}

export const AI_PROVENANCE_ROLES = [
  "problem_selection", "literature_search", "conjecture_generation",
  "proof_generation", "criticism", "computation", "formalization",
  "prose_editing", "candidate_generation",
] as const;

export const EMPTY_ATTRIBUTED: AttributedDraft = { value: "", basis: "editorial_inference", assertedBy: "" };

export const EMPTY_REVIEW_ENTRY: ReviewMapEntryDraft = {
  text: "", location: "", pointer: "", reason: "", basis: "editorial_inference", assertedBy: "",
};

export function emptyWizardState(): WizardState {
  return {
    submitterRole: null,
    submitterPartyId: "",
    recordId: "",
    parties: [],
    claimText: { ...EMPTY_ATTRIBUTED },
    claimScope: { ...EMPTY_ATTRIBUTED },
    manuscriptUrl: "",
    manuscriptLabel: "",
    manuscriptImmutableVersionId: "",
    manuscriptSha256: "",
    evidence: [],
    aiDisclosure: { ...EMPTY_ATTRIBUTED },
    aiRoles: [],
    readerSummary: { ...EMPTY_ATTRIBUTED },
    checkedSummary: { ...EMPTY_ATTRIBUTED },
    notCheckedSummary: { ...EMPTY_ATTRIBUTED },
    mainDeduction: { ...EMPTY_REVIEW_ENTRY },
    riskPoints: [],
    prerequisites: [],
    needsChecking: [],
    formalizationTarget: { ...EMPTY_ATTRIBUTED },
    formalizationSystem: { ...EMPTY_ATTRIBUTED },
    formalizationStatus: "not_started",
    formalizationRepository: "",
    formalizationCommit: "",
    formalizationToolchain: "",
    formalizationOpenQuestion: { ...EMPTY_ATTRIBUTED },
  };
}
