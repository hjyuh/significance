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

export interface MathematicalAssessmentDraft extends EvidenceDraftBase {
  kind: "mathematical_assessment";
  target: string;
  reportUrl: string;
  reportInline: string;
}

export type EvidenceDraft = ExternalFormalArtifactDraft | InformalReviewDraft | MathematicalAssessmentDraft;

export interface AiRoleDraft {
  role: string;
  model: string;
  basis: Basis;
  assertedBy: string;
  locator?: LocatorDraft;
}

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
}

export const AI_PROVENANCE_ROLES = [
  "problem_selection", "literature_search", "conjecture_generation",
  "proof_generation", "criticism", "computation", "formalization",
  "prose_editing", "candidate_generation",
] as const;

export const EMPTY_ATTRIBUTED: AttributedDraft = { value: "", basis: "editorial_inference", assertedBy: "" };

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
  };
}
