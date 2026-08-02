"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import type { AiRoleDraft, AttributedDraft, Basis, EvidenceDraft, LocatorDraft, PartyDraft, VerificationKind, WizardState } from "./types";
import { AI_PROVENANCE_ROLES, emptyWizardState } from "./types";
import { buildRecord, recordToYaml } from "./build-yaml";
import { validateAgainstSchema } from "./schema-validate";
import { runIntraRecordChecks } from "./intra-record-checks";
import { buildMailtoUrl, buildPrComposeUrl, triggerYamlDownload } from "./github-link";

const STEPS = ["role", "claim", "manuscript", "parties", "evidence", "provenance", "review"] as const;
type Step = (typeof STEPS)[number];

const BASIS_OPTIONS: Basis[] = ["source_quote", "author_attestation", "editorial_inference"];
const VERIFICATION_OPTIONS: VerificationKind[] = ["github_identity", "orcid", "email_confirmation", "pseudonymous"];

function slugify(input: string): string {
  return input.toLowerCase().trim().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

async function sha256OfFile(file: File): Promise<string> {
  const buf = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", buf);
  return Array.from(new Uint8Array(digest)).map((b) => b.toString(16).padStart(2, "0")).join("");
}

function hasLocator(l?: LocatorDraft): boolean {
  return !!(l && (l.section || l.url || l.quote));
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
          ? "source_quote requires a locator — where in the source this comes from."
          : "Recording someone else's author_attestation requires a locator pointing at how they told you — a correspondence link or public statement."}
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
        Basis
        <select
          value={draft.basis}
          onChange={(e) => onChange({ ...draft, basis: e.target.value as Basis })}
        >
          {BASIS_OPTIONS.map((b) => (
            <option key={b} value={b}>
              {b}
            </option>
          ))}
        </select>
      </label>
      <label>
        Asserted by (party id)
        <input value={draft.assertedBy} onChange={(e) => onChange({ ...draft, assertedBy: e.target.value })} />
      </label>
      {needsLocator ? (
        <LocatorFields basis={draft.basis} locator={draft.locator} onChange={(next) => onChange({ ...draft, locator: next })} />
      ) : null}
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

  // Wizard-only enforcement of the design's core consent mechanism: a
  // third-party submitter must not be able to export an unlocated
  // author_attestation. This can't live in intra-record-checks.ts because
  // it needs state.submitterRole, which isn't part of the assembled
  // record — the record has no notion of "who is submitting this PR."
  const thirdPartyAttestationGaps = useMemo(() => {
    if (!thirdParty) return [];
    // Only basis/locator matter here, so this is typed as that narrower
    // shape rather than the full AttributedDraft — EvidenceDraft and
    // AiRoleDraft (via EvidenceDraftBase and AiRoleDraft itself) both have
    // basis/locator but aren't otherwise assignable to AttributedDraft
    // (neither has `value`).
    const attributedFields: { location: string; draft: Pick<AttributedDraft, "basis" | "locator"> }[] = [
      { location: "claim.text", draft: state.claimText },
      { location: "claim.scope", draft: state.claimScope },
      { location: "ai_provenance.disclosure", draft: state.aiDisclosure },
      ...state.evidence.map((e, i) => ({ location: `evidence[${i}]`, draft: e })),
      ...state.aiRoles.map((r, i) => ({ location: `ai_provenance.roles[${i}]`, draft: r })),
    ];
    return attributedFields
      .filter((f) => f.draft.basis === "author_attestation" && !hasLocator(f.draft.locator))
      .map((f) => ({
        rule: "third-party-attestation-missing-locator",
        location: f.location,
        message: "author_attestation from a third-party submitter needs a locator (a correspondence link or public statement) before this can be exported.",
      }));
  }, [thirdParty, state.claimText, state.claimScope, state.aiDisclosure, state.evidence, state.aiRoles]);

  const canExport = thirdPartyAttestationGaps.length === 0;

  return (
    <main className="wizard">
      <header className="masthead">
        <Link className="wordmark" href="/" aria-label="Significance home">SIGNIFICANCE</Link>
        <p>Submit a record</p>
      </header>

      <nav className="wizard-steps" aria-label="Submission steps">
        {STEPS.map((s, i) => (
          <span key={s} className={i === stepIndex ? "wizard-step-current" : "wizard-step"}>{i + 1}. {s}</span>
        ))}
      </nav>

      {step === "role" ? (
        <section className="wizard-section">
          <h2>Are you an author of this claim, or recording someone else&apos;s public work?</h2>
          <p className="wizard-hint">
            This changes what you can assert without a locator. Recording someone
            else&apos;s public work is this tool&apos;s core use case and needs no
            permission — the one thing it restricts is claiming, unlocated,
            that an author privately told you something.
          </p>
          <div className="wizard-choice-row">
            <button type="button" onClick={() => setState((s) => ({ ...s, submitterRole: "author" }))} aria-pressed={state.submitterRole === "author"}>
              I am an author
            </button>
            <button type="button" onClick={() => setState((s) => ({ ...s, submitterRole: "third_party" }))} aria-pressed={state.submitterRole === "third_party"}>
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
          <h2>Manuscript</h2>
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
            sha256 {" "}
            <input value={state.manuscriptSha256} onChange={(e) => setState((s) => ({ ...s, manuscriptSha256: e.target.value }))} placeholder="Pick a file above, or paste a known hash" />
          </label>
        </section>
      ) : null}

      {step === "parties" ? (
        <section className="wizard-section">
          <h2>Parties</h2>
          {state.parties.map((p, i) => (
            <fieldset className="wizard-fieldset" key={i}>
              <legend>Party {i + 1}</legend>
              <label>Id (lowercase-kebab) <input value={p.id} onChange={(e) => updateParty(i, { ...p, id: slugify(e.target.value) })} /></label>
              <label>
                <input type="checkbox" checked={p.isPseudonym} onChange={(e) => updateParty(i, { ...p, isPseudonym: e.target.checked })} />
                Pseudonymous
              </label>
              <label>{p.isPseudonym ? "Pseudonym" : "Name"} <input value={p.displayName} onChange={(e) => updateParty(i, { ...p, displayName: e.target.value })} /></label>
              <label>
                Verification method
                <select value={p.verificationKind} onChange={(e) => updateParty(i, { ...p, verificationKind: e.target.value as VerificationKind })}>
                  {VERIFICATION_OPTIONS.map((k) => <option key={k} value={k}>{k}</option>)}
                </select>
              </label>
              <label>Identifier <input value={p.verificationIdentifier} onChange={(e) => updateParty(i, { ...p, verificationIdentifier: e.target.value })} /></label>
              <button type="button" onClick={() => removeParty(i)}>Remove</button>
            </fieldset>
          ))}
          <button type="button" onClick={addParty}>Add party</button>
          <label>
            Which party id is you, the submitter?
            <input value={state.submitterPartyId} onChange={(e) => setState((s) => ({ ...s, submitterPartyId: e.target.value }))} />
          </label>
        </section>
      ) : null}

      {step === "evidence" ? (
        <section className="wizard-section">
          <h2>Evidence</h2>
          <div className="wizard-choice-row">
            <button type="button" onClick={() => addEvidence("external_formal_artifact")}>+ external_formal_artifact</button>
            <button type="button" onClick={() => addEvidence("informal_review")}>+ informal_review</button>
            <button type="button" onClick={() => addEvidence("mathematical_assessment")}>+ mathematical_assessment</button>
          </div>
          <div className="wizard-choice-row">
            <span className="wizard-gated" aria-disabled="true" role="button" tabIndex={0}>formal_artifact</span>
            <span className="wizard-gated" aria-disabled="true" role="button" tabIndex={0}>computational_reproduction</span>
          </div>
          <p className="wizard-hint">
            formal_artifact and computational_reproduction require a machine-generated
            execution receipt — produced by CI or the {" "}
            <a href="https://github.com/hjyuh/significance/blob/main/adapters/lean/README.md">Lean adapter</a>,
            not typed by hand.
          </p>

          {state.evidence.map((ev, i) => {
            const needsLocator = needsLocatorFor(ev.basis, thirdParty);
            return (
              <fieldset className="wizard-fieldset" key={i}>
                <legend>{ev.kind} — {ev.id}</legend>
                <label>Id <input value={ev.id} onChange={(e) => updateEvidence(i, { ...ev, id: e.target.value })} /></label>
                {ev.kind === "external_formal_artifact" ? (
                  <>
                    <label>Repo URL <input value={ev.repo} onChange={(e) => updateEvidence(i, { ...ev, repo: e.target.value })} /></label>
                    <label>Commit (optional) <input value={ev.commit} onChange={(e) => updateEvidence(i, { ...ev, commit: e.target.value })} /></label>
                    <label>Description <textarea value={ev.description} onChange={(e) => updateEvidence(i, { ...ev, description: e.target.value })} /></label>
                  </>
                ) : null}
                {ev.kind === "informal_review" ? (
                  <>
                    <label>Reviewer (party id) <input value={ev.reviewer} onChange={(e) => updateEvidence(i, { ...ev, reviewer: e.target.value })} /></label>
                    <label>Text <textarea value={ev.text} onChange={(e) => updateEvidence(i, { ...ev, text: e.target.value })} /></label>
                  </>
                ) : null}
                {ev.kind === "mathematical_assessment" ? (
                  <>
                    <label>Target statement (e.g. &quot;Theorem 1.2&quot;) <input value={ev.target} onChange={(e) => updateEvidence(i, { ...ev, target: e.target.value })} /></label>
                    <label>Report URL <input value={ev.reportUrl} onChange={(e) => updateEvidence(i, { ...ev, reportUrl: e.target.value })} /></label>
                    <label>Report inline text <textarea value={ev.reportInline} onChange={(e) => updateEvidence(i, { ...ev, reportInline: e.target.value })} /></label>
                    {!ev.reportUrl && !ev.reportInline ? (
                      <p className="wizard-hint wizard-warning">A mathematical_assessment needs at least a report URL or inline text — the schema requires one.</p>
                    ) : null}
                  </>
                ) : null}
                <label>
                  Basis
                  <select value={ev.basis} onChange={(e) => updateEvidence(i, { ...ev, basis: e.target.value as Basis })}>
                    {BASIS_OPTIONS.map((b) => <option key={b} value={b}>{b}</option>)}
                  </select>
                </label>
                <label>Asserted by (party id) <input value={ev.assertedBy} onChange={(e) => updateEvidence(i, { ...ev, assertedBy: e.target.value })} /></label>
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
          <h2>AI provenance</h2>
          <AttributedFields label="Disclosure" draft={state.aiDisclosure} onChange={(v) => setState((s) => ({ ...s, aiDisclosure: v }))} thirdPartyLocked={thirdParty} />
          {state.aiRoles.map((r, i) => {
            const needsLocator = needsLocatorFor(r.basis, thirdParty);
            return (
              <fieldset className="wizard-fieldset" key={i}>
                <legend>Role {i + 1}</legend>
                <label>
                  Role
                  <select value={r.role} onChange={(e) => updateAiRole(i, { ...r, role: e.target.value })}>
                    {AI_PROVENANCE_ROLES.map((role) => <option key={role} value={role}>{role}</option>)}
                  </select>
                </label>
                <label>Model <input value={r.model} onChange={(e) => updateAiRole(i, { ...r, model: e.target.value })} /></label>
                <label>
                  Basis
                  <select value={r.basis} onChange={(e) => updateAiRole(i, { ...r, basis: e.target.value as Basis })}>
                    {BASIS_OPTIONS.map((b) => <option key={b} value={b}>{b}</option>)}
                  </select>
                </label>
                <label>Asserted by <input value={r.assertedBy} onChange={(e) => updateAiRole(i, { ...r, assertedBy: e.target.value })} /></label>
                {needsLocator ? (
                  <LocatorFields basis={r.basis} locator={r.locator} onChange={(next) => updateAiRole(i, { ...r, locator: next })} />
                ) : null}
                <button type="button" onClick={() => setState((s) => ({ ...s, aiRoles: s.aiRoles.filter((_, j) => j !== i) }))}>Remove</button>
              </fieldset>
            );
          })}
          <button type="button" onClick={() => setState((s) => ({ ...s, aiRoles: [...s.aiRoles, { role: AI_PROVENANCE_ROLES[0], model: "", basis: "author_attestation", assertedBy: "" }] }))}>
            Add role
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
            <button type="button" disabled={!canExport} onClick={() => triggerYamlDownload(state.recordId, yamlText)}>
              Download record.yaml
            </button>

            {!canExport ? (
              <p className="wizard-hint wizard-warning">Resolve the blocking issues above before exporting.</p>
            ) : prCompose.url ? (
              <>
                <a className="wizard-pr-link" href={prCompose.url} target="_blank" rel="noreferrer">
                  Open as pull request
                </a>
                <p className="wizard-hint">
                  This puts the record&apos;s content — including any named parties —
                  in the URL, which lands in browser history and referrer headers.
                  Fine for a record you intend to publish; if it names someone who
                  hasn&apos;t confirmed yet, download and open the PR by hand instead.
                </p>
              </>
            ) : (
              <p className="wizard-hint">
                This record is too large for a pre-filled PR link. Download the
                file and open the PR by hand at{" "}
                <a href="https://github.com/hjyuh/significance/new/main">github.com/hjyuh/significance</a>.
              </p>
            )}

            <a href={buildMailtoUrl(state.recordId)}>Email it instead</a>
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
