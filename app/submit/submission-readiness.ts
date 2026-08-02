import type { SubmitterRole } from "./types";

export interface SubmissionReadinessInput {
  submitterRole: SubmitterRole | null;
  schemaErrorCount: number;
  intraRecordViolationCount: number;
  attestationGapCount: number;
}

/**
 * Downloading a draft is always allowed, but handing a record to a review
 * channel is only honest once every check available in the browser passes.
 */
export function isSubmissionReady(input: SubmissionReadinessInput): boolean {
  return input.submitterRole !== null
    && input.schemaErrorCount === 0
    && input.intraRecordViolationCount === 0
    && input.attestationGapCount === 0;
}
