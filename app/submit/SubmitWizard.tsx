"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { AiRoleDraft, AttributedDraft, Basis, EvidenceDraft, LocatorDraft, PartyDraft, ReviewMapEntryDraft, VerificationKind, WizardState } from "./types";
import { AI_PROVENANCE_ROLES, EMPTY_REVIEW_ENTRY, emptyWizardState } from "./types";
import { buildRecord, recordToYaml } from "./build-yaml";
import { validateAgainstSchema } from "./schema-validate";
import { runIntraRecordChecks } from "./intra-record-checks";
import { buildMailtoUrl, buildPrComposeUrl, triggerYamlDownload } from "./github-link";
import { computeThirdPartyAttestationGaps } from "./attestation-gaps";
import { isSubmissionReady } from "./submission-readiness";

const STEPS = ["role", "claim", "manuscript", "review_map", "parties", "evidence", "provenance", "review"] as const;
type Step = (typeof STEPS)[number];

const BASIS_OPTIONS: Basis[] = ["source_quote", "author_attestation", "editorial_inference"];
const VERIFICATION_OPTIONS: VerificationKind[] = ["github_identity", "orcid", "email_confirmation", "pseudonymous"];

const STEP_LABELS: Record<Step, string> = {
  role: "Your role",
  claim: "Claim",
  manuscript: "Source",
  parties: "People",
  evidence: "Evidence",
  provenance: "AI use",
  review_map: "Reviewer map",
  review: "Review",
};

const BASIS_LABELS: Record<Basis, string> = {
  source_quote: "Quoted from the source",
  author_attestation: "Stated by the author",
  editorial_inference: "Your interpretation",
};

const VERIFICATION_LABELS: Record<VerificationKind, string> = {
  github_identity: "GitHub account",
  orcid: "ORCID",
  email_confirmation: "Confirmed email",
  pseudonymous: "Pseudonymous identity",
};

const EVIDENCE_LABELS: Record<EvidenceDraft["kind"], string> = {
  external_formal_artifact: "Published proof code",
  source_inspection: "Source inspection",
  informal_review: "Written review",
  mathematical_assessment: "Mathematical assessment",
};

function roleLabel(value: string) {
  return ({
    proof_generation: "Developing the proof",
    formalization: "Writing the formal proof",
    prose_editing: "Editing the writing",
    literature_search: "Searching prior work",
    computation: "Running computations",
  } as Record<string, string>)[value] ?? value.replaceAll("_", " ");
}

function slugify(input: string): string {
  return input.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

async function sha256OfFile(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

// Shared by AttributedFields and the ai_provenance.roles fieldset below —
// same rule everywhere an attributed value can carry basis+locator:
// source_quote always needs one, and a third-party submitter's
// author_attestation needs one too.
function needsLocatorFor(basis: Basis, thirdPartyLocked: boolean): boolean {
  return basis === "source_quote" || (thirdPartyLocked && basis === "author_attestation");
}

function LocatorFields({
  basis, locator, onChange,
}: {
  basis: Basis;
  locator: LocatorDraft | undefined;
  onChange: (next: LocatorDraft) => void;
}) {
  return (
    <div className="wizard-locator">
      <p className="wizard-hint">
        {basis === "source_quote"
          ? "Add a precise location showing where this appears in the source."
          : "Add a link to the public statement or correspondence where the author said this."}
      </p>
      <label>
        Section <input value={locator?.section ?? ""} onChange={(e) => onChange({ ...locator, section: e.target.value })} />
      </label>
      <label>
        URL <input value={locator?.url ?? ""} onChange={(e) => onChange({ ...locator, url: e.target.value })} />
      </label>
      <label>
        Quote <input value={locator?.quote ?? ""} onChange={(e) => onChange({ ...locator, quote: e.target.value })} />
      </label>
    </div>
  );
}

function AttributedFields({
  label, draft, onChange, thirdPartyLocked,
}: {
  label: string;
  draft: AttributedDraft;
  onChange: (next: AttributedDraft) => void;
  thirdPartyLocked: boolean;
}) {
  const needsLocator = needsLocatorFor(draft.basis, thirdPartyLocked);
  return (
    <fieldset className="wizard-fieldset">
      <legend>{label}</legend>
      <label>
        Text
        <textarea value={draft.value} onChange={(e) => onChange({ ...draft, value: e.target.value })} />
      </label>
      <label>
        Where this information comes from
        <select
          value={draft.basis}
          onChange={(e) => onChange({ ...draft, basis: e.target.value as Basis })}
        >
          {BASIS_OPTIONS.map((b) => (
            <option key={b} value={b}>
              {BASIS_LABELS[b]}
            </option>
          ))}
        </select>
      </label>
      <label>
        Attributed to (person id)
        <input value={draft.assertedBy} onChange={(e) => onChange({ ...draft, assertedBy: e.target.value })} />
      </label>
      {needsLocator ? (
        <LocatorFields basis={draft.basis} locator={draft.locator} onChange={(next) => onChange({ ...draft, locator: next })} />
      ) : null}
    </fieldset>
  );
}

function ReviewEntryFields({
  label, entry, onChange, thirdPartyLocked, allowReason,
}: {
  label: string;
  entry: ReviewMapEntryDraft;
  onChange: (next: ReviewMapEntryDraft) => void;
  thirdPartyLocked: boolean;
  allowReason?: boolean;
}) {
  const needsLocator = needsLocatorFor(entry.basis, thirdPartyLocked);
  return (
    <fieldset className="wizard-fieldset">
      <legend>{label}</legend>
      <label>What should a reader examine? <textarea value={entry.text} onChange={(e) => onChange({ ...entry, text: e.target.value })} /></label>
      <label>Paper location <input value={entry.location} onChange={(e) => onChange({ ...entry, location: e.target.value })} placeholder="e.g. Theorem 1.1, Section 3" /></label>
      <label>Pointer or prerequisite <input value={entry.pointer} onChange={(e) => onChange({ ...entry, pointer: e.target.value })} /></label>
      {allowReason ? <label>Why does this matter? <input value={entry.reason} onChange={(e) => onChange({ ...entry, reason: e.target.value })} /></label> : null}
      <label>Who is asserting this? <input value={entry.assertedBy} onChange={(e) => onChange({ ...entry, assertedBy: e.target.value })} /></label>
      <label>Basis<select value={entry.basis} onChange={(e) => onChange({ ...entry, basis: e.target.value as Basis })}>{BASIS_OPTIONS.map((b) => <option key={b} value={b}>{BASIS_LABELS[b]}</option>)}</select></label>
      {needsLocator ? <LocatorFields basis={entry.basis} locator={entry.locator} onChange={(next) => onChange({ ...entry, locator: next })} /> : null}
    </fieldset>
  );
}

export default function SubmitWizard() {
  const [step, setStep] = useState<Step>("role");
  const [state, setState] = useState<WizardState>(emptyWizardState());
  const [hashing, setHashing] = useState(false);
  const [hashError, setHashError] = useState<string | null>(null);

  const stepIndex = STEPS.indexOf(step);
  const goNext = () => setStep(STEPS[Math.min(stepIndex + 1, STEPS.length - 1)]);
  const goBack = () => setStep(STEPS[Math.max(stepIndex - 1, 0)]);

  const thirdParty = state.submitterRole === "third_party";

  function chooseSubmitterRole(role: "author" | "third_party") {
    setState((s) => {
      if (role !== "author") return { ...s, submitterRole: role };
      const authorBasis = <T extends { basis: Basis }>(entry: T): T => ({ ...entry, basis: "author_attestation" });
      return {
        ...s,
        submitterRole: role,
        readerSummary: authorBasis(s.readerSummary),
        checkedSummary: authorBasis(s.checkedSummary),
        notCheckedSummary: authorBasis(s.notCheckedSummary),
        mainDeduction: authorBasis(s.mainDeduction),
        riskPoints: s.riskPoints.map(authorBasis),
        prerequisites: s.prerequisites.map(authorBasis),
        needsChecking: s.needsChecking.map(authorBasis),
      };
    });
  }

  function addParty() {
    const id: PartyDraft = {
      id: "", isPseudonym: false, displayName: "", verificationKind: "github_identity", verificationIdentifier: "",
    };
    setState((s) => ({ ...s, parties: [...s.parties, id] }));
  }

  function updateParty(index: number, next: PartyDraft) {
    setState((s) => ({ ...s, parties: s.parties.map((p, i) => (i === index ? next : p)) }));
  }

  function removeParty(index: number) {
    setState((s) => ({ ...s, parties: s.parties.filter((_, i) => i !== index) }));
  }

  function addEvidence(kind: EvidenceDraft["kind"]) {
    const base = { id: `ev-${state.evidence.length + 1}`, basis: "editorial_inference" as Basis, assertedBy: "" };
    let item: EvidenceDraft;
    if (kind === "external_formal_artifact") item = { ...base, kind, repo: "", commit: "", description: "" };
    else if (kind === "source_inspection") item = { ...base, kind, description: "" };
    else if (kind === "informal_review") item = { ...base, kind, reviewer: "", text: "" };
    else item = { ...base, kind, target: "", reportUrl: "", reportInline: "" };
    setState((s) => ({ ...s, evidence: [...s.evidence, item] }));
  }

  function updateEvidence(index: number, next: EvidenceDraft) {
    setState((s) => ({ ...s, evidence: s.evidence.map((e, i) => (i === index ? next : e)) }));
  }

  function removeEvidence(index: number) {
    setState((s) => ({ ...s, evidence: s.evidence.filter((_, i) => i !== index) }));
  }

  function updateAiRole(index: number, next: AiRoleDraft) {
    setState((s) => ({ ...s, aiRoles: s.aiRoles.map((r, i) => (i === index ? next : r)) }));
  }

  async function onManuscriptFilePicked(file: File | null) {
    if (!file) return;
    setHashing(true);
    setHashError(null);
    try {
      const hash = await sha256OfFile(file);
      setState((s) => ({ ...s, manuscriptSha256: hash }));
    } catch (err) {
      setHashError(err instanceof Error ? err.message : "Could not hash this file — paste a known hash instead.");
    } finally {
      setHashing(false);
    }
  }

  const record = useMemo(() => buildRecord(state), [state]);
  const yamlText = useMemo(() => recordToYaml(record), [record]);
  const schemaErrors = useMemo(() => validateAgainstSchema(record), [record]);
  const intraRecordViolations = useMemo(() => runIntraRecordChecks(record), [record]);
  const prCompose = useMemo(() => buildPrComposeUrl(state.recordId, yamlText), [state.recordId, yamlText]);

  const thirdPartyAttestationGaps = useMemo(
    () => computeThirdPartyAttestationGaps(state, thirdParty),
    [state, thirdParty]
  );

  const canSubmit = isSubmissionReady({
    submitterRole: state.submitterRole,
    schemaErrorCount: schemaErrors.length,
    intraRecordViolationCount: intraRecordViolations.length,
    attestationGapCount: thirdPartyAttestationGaps.length,
  });

  return (
    <main className="wizard">
      <header className="masthead">
        <Link className="wordmark" href="/" aria-label="Significance home">SIGNIFICANCE</Link>
        <p>Advanced record builder</p>
      </header>

      <section className="wizard-section wizard-banner">
        <h2>For maintainers and technical contributors</h2>
        <p>
          Authors and readers do not need to use this advanced builder. Start with the{" "}
          <a href="/request/">short request or correction page</a>; maintainers can turn ordinary prose into a complete record.
        </p>
      </section>

      <nav className="wizard-steps" aria-label="Submission steps">
        {STEPS.map((s, i) => (
          <span key={s} className={i === stepIndex ? "wizard-step-current" : "wizard-step"}>{i + 1}. {STEP_LABELS[s]}</span>
        ))}
      </nav>

      {step === "role" ? (
        <section className="wizard-section">
          <h2>Are you an author of this claim, or recording someone else&apos;s public work?</h2>
          <p className="wizard-hint">
            This changes which statements need a public source link. Records about public work
            can be drafted from public sources. Claims by living individual authors need an
            author request or permission before the public page is published. Private
            correspondence must always include a link or other precise reference.
          </p>
          <div className="wizard-choice-row">
            <button type="button" onClick={() => chooseSubmitterRole("author")} aria-pressed={state.submitterRole === "author"}>
              I am an author
            </button>
            <button type="button" onClick={() => chooseSubmitterRole("third_party")} aria-pressed={state.submitterRole === "third_party"}>
              I&apos;m recording someone else&apos;s work
            </button>
          </div>
          {state.submitterRole === "author" ? (
            <p className="wizard-hint">Your PR&apos;s GitHub identity will be checked against a party you declare below.</p>
          ) : null}
        </section>
      ) : null}

      {step === "claim" ? (
        <section className="wizard-section">
          <h2>Claim</h2>
          <AttributedFields label="Claim text" draft={state.claimText} onChange={(v) => setState((s) => ({ ...s, claimText: v }))} thirdPartyLocked={thirdParty} />
          <AttributedFields label="Scope" draft={state.claimScope} onChange={(v) => setState((s) => ({ ...s, claimScope: v }))} thirdPartyLocked={thirdParty} />
          <label>
            Record id (e.g. 2026-author-topic)
            <input value={state.recordId} onChange={(e) => setState((s) => ({ ...s, recordId: e.target.value }))} />
          </label>
        </section>
      ) : null}

      {step === "manuscript" ? (
        <section className="wizard-section">
          <h2>Source document</h2>
          <label>URL <input value={state.manuscriptUrl} onChange={(e) => setState((s) => ({ ...s, manuscriptUrl: e.target.value }))} /></label>
          <label>Label <input value={state.manuscriptLabel} onChange={(e) => setState((s) => ({ ...s, manuscriptLabel: e.target.value }))} /></label>
          <label>Immutable version id (optional, e.g. an arXiv vN) <input value={state.manuscriptImmutableVersionId} onChange={(e) => setState((s) => ({ ...s, manuscriptImmutableVersionId: e.target.value }))} /></label>
          <label>
            Manuscript file (hashed locally — never uploaded)
            <input type="file" onChange={(e) => onManuscriptFilePicked(e.target.files?.[0] ?? null)} />
          </label>
          {hashing ? <p className="wizard-hint">Hashing…</p> : null}
          {hashError ? <p className="wizard-hint wizard-warning">{hashError}</p> : null}
          <label>
            File fingerprint (SHA-256) {" "}
            <input value={state.manuscriptSha256} onChange={(e) => setState((s) => ({ ...s, manuscriptSha256: e.target.value }))} placeholder="Pick a file above, or paste a known hash" />
          </label>
        </section>
      ) : null}

      {step === "review_map" ? (
        <section className="wizard-section">
          <h2>What should a reviewer do with this paper?</h2>
          <p className="wizard-hint">These answers become the record&apos;s “Start here” section. Authors are the best source for delicate steps; readers can add further needs later.</p>
          <AttributedFields label="One sentence for a general reader" draft={state.readerSummary} onChange={(v) => setState((s) => ({ ...s, readerSummary: v }))} thirdPartyLocked={thirdParty} />
          <AttributedFields label="What has been checked so far" draft={state.checkedSummary} onChange={(v) => setState((s) => ({ ...s, checkedSummary: v }))} thirdPartyLocked={thirdParty} />
          <AttributedFields label="What remains open" draft={state.notCheckedSummary} onChange={(v) => setState((s) => ({ ...s, notCheckedSummary: v }))} thirdPartyLocked={thirdParty} />
          <ReviewEntryFields label="Main deduction" entry={state.mainDeduction} onChange={(v) => setState((s) => ({ ...s, mainDeduction: v }))} thirdPartyLocked={thirdParty} />
          <ReviewEntryFields label="Most delicate step or risk" entry={state.riskPoints[0] ?? EMPTY_REVIEW_ENTRY} onChange={(v) => setState((s) => ({ ...s, riskPoints: [v] }))} thirdPartyLocked={thirdParty} allowReason />
          <ReviewEntryFields label="Background a reviewer needs" entry={state.prerequisites[0] ?? EMPTY_REVIEW_ENTRY} onChange={(v) => setState((s) => ({ ...s, prerequisites: [v] }))} thirdPartyLocked={thirdParty} />
          <ReviewEntryFields label="Optional: a specific thing that needs checking" entry={state.needsChecking[0] ?? EMPTY_REVIEW_ENTRY} onChange={(v) => setState((s) => ({ ...s, needsChecking: [v] }))} thirdPartyLocked={thirdParty} allowReason />
          <fieldset className="wizard-fieldset">
            <legend>Optional: formalization handoff</legend>
            <p className="wizard-hint">Give a formalizer a starting point: the target, system, code revision, and smallest open question. This describes formalization work, not the mathematics.</p>
            <AttributedFields label="Formalization target" draft={state.formalizationTarget} onChange={(v) => setState((s) => ({ ...s, formalizationTarget: v }))} thirdPartyLocked={thirdParty} />
            <AttributedFields label="Formal system" draft={state.formalizationSystem} onChange={(v) => setState((s) => ({ ...s, formalizationSystem: v }))} thirdPartyLocked={thirdParty} />
            <label>Work state<select value={state.formalizationStatus} onChange={(e) => setState((s) => ({ ...s, formalizationStatus: e.target.value as typeof s.formalizationStatus }))}><option value="not_started">Not started</option><option value="statement_prepared">Statement prepared</option><option value="proof_incomplete">Proof incomplete</option><option value="artifact_reported">Artifact reported</option><option value="artifact_reproduced">Artifact reproduced</option></select></label>
            <label>Repository URL<input value={state.formalizationRepository} onChange={(e) => setState((s) => ({ ...s, formalizationRepository: e.target.value }))} placeholder="https://github.com/..." /></label>
            <label>Commit or version<input value={state.formalizationCommit} onChange={(e) => setState((s) => ({ ...s, formalizationCommit: e.target.value }))} /></label>
            <label>Toolchain<input value={state.formalizationToolchain} onChange={(e) => setState((s) => ({ ...s, formalizationToolchain: e.target.value }))} placeholder="Lean 4 + Mathlib" /></label>
            <AttributedFields label="Smallest open formalization question" draft={state.formalizationOpenQuestion} onChange={(v) => setState((s) => ({ ...s, formalizationOpenQuestion: v }))} thirdPartyLocked={thirdParty} />
          </fieldset>
        </section>
      ) : null}

      {step === "parties" ? (
        <section className="wizard-section">
          <h2>People and organizations</h2>
          {state.parties.map((p, i) => (
            <fieldset className="wizard-fieldset" key={i}>
              <legend>Person or organization {i + 1}</legend>
              <label>Internal id <input value={p.id} onChange={(e) => updateParty(i, { ...p, id: slugify(e.target.value) })} /></label>
              <label>
                <input type="checkbox" checked={p.isPseudonym} onChange={(e) => updateParty(i, { ...p, isPseudonym: e.target.checked })} />
                Pseudonymous
              </label>
              <label>{p.isPseudonym ? "Pseudonym" : "Name"} <input value={p.displayName} onChange={(e) => updateParty(i, { ...p, displayName: e.target.value })} /></label>
              <label>
                Verification method
                <select value={p.verificationKind} onChange={(e) => updateParty(i, { ...p, verificationKind: e.target.value as VerificationKind })}>
                  {VERIFICATION_OPTIONS.map((k) => <option key={k} value={k}>{VERIFICATION_LABELS[k]}</option>)}
                </select>
              </label>
              <label>Identifier <input value={p.verificationIdentifier} onChange={(e) => updateParty(i, { ...p, verificationIdentifier: e.target.value })} /></label>
              <button type="button" onClick={() => removeParty(i)}>Remove</button>
            </fieldset>
          ))}
          <button type="button" onClick={addParty}>Add a person or organization</button>
          <label>
            Which internal id represents you?
            <input value={state.submitterPartyId} onChange={(e) => setState((s) => ({ ...s, submitterPartyId: e.target.value }))} />
          </label>
        </section>
      ) : null}

      {step === "evidence" ? (
        <section className="wizard-section">
          <h2>Evidence</h2>
          <div className="wizard-choice-row">
            <button type="button" onClick={() => addEvidence("external_formal_artifact")}>+ Published proof code</button>
            <button type="button" onClick={() => addEvidence("source_inspection")}>+ Source inspection</button>
            <button type="button" onClick={() => addEvidence("informal_review")}>+ Written review</button>
            <button type="button" onClick={() => addEvidence("mathematical_assessment")}>+ Mathematical assessment</button>
          </div>
          <div className="wizard-choice-row">
            <span className="wizard-gated" aria-disabled="true" role="button" tabIndex={0}>Reproduced formal proof</span>
            <span className="wizard-gated" aria-disabled="true" role="button" tabIndex={0}>Reproduced computation</span>
          </div>
          <p className="wizard-hint">
            Reproduced results require an execution receipt produced by an automated check or the {" "}
            <a href="https://github.com/hjyuh/significance/blob/main/adapters/lean/README.md">Lean adapter</a>,
            not typed by hand.
          </p>

          {state.evidence.map((ev, i) => {
            const needsLocator = needsLocatorFor(ev.basis, thirdParty);
            return (
              <fieldset className="wizard-fieldset" key={i}>
                <legend>{EVIDENCE_LABELS[ev.kind]} — {ev.id}</legend>
                <label>Internal id <input value={ev.id} onChange={(e) => updateEvidence(i, { ...ev, id: e.target.value })} /></label>
                {ev.kind === "external_formal_artifact" ? (
                  <>
                    <label>Repo URL <input value={ev.repo} onChange={(e) => updateEvidence(i, { ...ev, repo: e.target.value })} /></label>
                    <label>Commit (optional) <input value={ev.commit} onChange={(e) => updateEvidence(i, { ...ev, commit: e.target.value })} /></label>
                    <label>Description <textarea value={ev.description} onChange={(e) => updateEvidence(i, { ...ev, description: e.target.value })} /></label>
                  </>
                ) : null}
                {ev.kind === "source_inspection" ? (
                  <label>What was inspected <textarea value={ev.description} onChange={(e) => updateEvidence(i, { ...ev, description: e.target.value })} /></label>
                ) : null}
                {ev.kind === "informal_review" ? (
                  <>
                    <label>Reviewer (person id) <input value={ev.reviewer} onChange={(e) => updateEvidence(i, { ...ev, reviewer: e.target.value })} /></label>
                    <label>Text <textarea value={ev.text} onChange={(e) => updateEvidence(i, { ...ev, text: e.target.value })} /></label>
                  </>
                ) : null}
                {ev.kind === "mathematical_assessment" ? (
                  <>
                    <label>Target statement (e.g. &quot;Theorem 1.2&quot;) <input value={ev.target} onChange={(e) => updateEvidence(i, { ...ev, target: e.target.value })} /></label>
                    <label>Report URL <input value={ev.reportUrl} onChange={(e) => updateEvidence(i, { ...ev, reportUrl: e.target.value })} /></label>
                    <label>Report inline text <textarea value={ev.reportInline} onChange={(e) => updateEvidence(i, { ...ev, reportInline: e.target.value })} /></label>
                    {!ev.reportUrl && !ev.reportInline ? (
                      <p className="wizard-hint wizard-warning">A mathematical assessment needs either a report link or written report.</p>
                    ) : null}
                  </>
                ) : null}
                <label>
                  Where this information comes from
                  <select value={ev.basis} onChange={(e) => updateEvidence(i, { ...ev, basis: e.target.value as Basis })}>
                    {BASIS_OPTIONS.map((b) => <option key={b} value={b}>{BASIS_LABELS[b]}</option>)}
                  </select>
                </label>
                <label>Attributed to (person id) <input value={ev.assertedBy} onChange={(e) => updateEvidence(i, { ...ev, assertedBy: e.target.value })} /></label>
                {needsLocator ? (
                  <LocatorFields basis={ev.basis} locator={ev.locator} onChange={(next) => updateEvidence(i, { ...ev, locator: next })} />
                ) : null}
                <button type="button" onClick={() => removeEvidence(i)}>Remove</button>
              </fieldset>
            );
          })}
        </section>
      ) : null}

      {step === "provenance" ? (
        <section className="wizard-section">
          <h2>How AI was used</h2>
          <AttributedFields label="What the source discloses" draft={state.aiDisclosure} onChange={(v) => setState((s) => ({ ...s, aiDisclosure: v }))} thirdPartyLocked={thirdParty} />
          {state.aiRoles.map((r, i) => {
            const needsLocator = needsLocatorFor(r.basis, thirdParty);
            return (
              <fieldset className="wizard-fieldset" key={i}>
                <legend>Role {i + 1}</legend>
                <label>
                  Role
                  <select value={r.role} onChange={(e) => updateAiRole(i, { ...r, role: e.target.value })}>
                    {AI_PROVENANCE_ROLES.map((role) => <option key={role} value={role}>{roleLabel(role)}</option>)}
                  </select>
                </label>
                <label>Model <input value={r.model} onChange={(e) => updateAiRole(i, { ...r, model: e.target.value })} /></label>
                <label>
                  Where this information comes from
                  <select value={r.basis} onChange={(e) => updateAiRole(i, { ...r, basis: e.target.value as Basis })}>
                    {BASIS_OPTIONS.map((b) => <option key={b} value={b}>{BASIS_LABELS[b]}</option>)}
                  </select>
                </label>
                <label>Attributed to (person id) <input value={r.assertedBy} onChange={(e) => updateAiRole(i, { ...r, assertedBy: e.target.value })} /></label>
                {needsLocator ? (
                  <LocatorFields basis={r.basis} locator={r.locator} onChange={(next) => updateAiRole(i, { ...r, locator: next })} />
                ) : null}
                <button type="button" onClick={() => setState((s) => ({ ...s, aiRoles: s.aiRoles.filter((_, j) => j !== i) }))}>Remove</button>
              </fieldset>
            );
          })}
          <button type="button" onClick={() => setState((s) => ({ ...s, aiRoles: [...s.aiRoles, { role: AI_PROVENANCE_ROLES[0], model: "", basis: "author_attestation", assertedBy: "" }] }))}>
            Add another use
          </button>
        </section>
      ) : null}

      {step === "review" ? (
        <section className="wizard-section">
          <h2>Review and export</h2>
          <p className="wizard-banner">
            These are structural checks plus a narrow intra-record subset. Not checked here (they need sibling
            records or git history this browser doesn&apos;t have): record_id uniqueness, append-only history.
            Full validation, including those, runs when the PR opens.
          </p>

          {thirdPartyAttestationGaps.length ? (
            <div className="wizard-errors">
              <p>Blocking: unlocated third-party attestations ({thirdPartyAttestationGaps.length}):</p>
              <ul>{thirdPartyAttestationGaps.map((v, i) => <li key={i}>{v.location}: {v.message}</li>)}</ul>
            </div>
          ) : null}

          {schemaErrors.length ? (
            <div className="wizard-errors">
              <p>Schema errors ({schemaErrors.length}):</p>
              <ul>{schemaErrors.map((e, i) => <li key={i}>{e.path}: {e.message}</li>)}</ul>
            </div>
          ) : <p className="wizard-ok">No structural schema errors.</p>}

          {intraRecordViolations.length ? (
            <div className="wizard-errors">
              <p>Intra-record check violations ({intraRecordViolations.length}):</p>
              <ul>{intraRecordViolations.map((v, i) => <li key={i}>[{v.rule}] {v.location}: {v.message}</li>)}</ul>
            </div>
          ) : <p className="wizard-ok">No intra-record violations found.</p>}

          <pre className="wizard-yaml">{yamlText}</pre>

          <div className="wizard-actions">
            <button type="button" onClick={() => triggerYamlDownload(state.recordId, yamlText)}>
              Download draft YAML
            </button>

            {!canSubmit ? (
              <p className="wizard-hint wizard-warning">
                You can keep the draft, but resolve every issue above before submitting it.
              </p>
            ) : prCompose.url ? (
              <>
                <a className="wizard-pr-link" href={prCompose.url} target="_blank" rel="noreferrer">
                  Continue submission on GitHub
                </a>
                <p className="wizard-hint">
                  GitHub opens a pre-filled new-file editor. After you propose the
                  file, GitHub will guide you through creating the pull request. {" "}
                  This puts the record&apos;s content — including any named parties —
                  in the URL, which lands in browser history and referrer headers.
                  Fine for a record you intend to publish; if it names someone who
                  hasn&apos;t confirmed yet, download and open the PR by hand instead.
                </p>
              </>
            ) : (
              <p className="wizard-hint">
                This record is too large for a pre-filled GitHub editor link.
                Download the file and propose it by hand at{" "}
                <a href="https://github.com/hjyuh/significance/new/main">github.com/hjyuh/significance</a>.
              </p>
            )}

            {canSubmit ? <a href={buildMailtoUrl(state.recordId)}>Email the valid record instead</a> : null}
          </div>
        </section>
      ) : null}

      <div className="wizard-nav">
        <button type="button" onClick={goBack} disabled={stepIndex === 0}>Back</button>
        <button type="button" onClick={goNext} disabled={stepIndex === STEPS.length - 1}>Next</button>
      </div>
    </main>
  );
}
