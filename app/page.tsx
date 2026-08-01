import Link from "next/link";

const recordPath = "/records/2026-openai-nonsofic-groups/";

export default function Home() {
  return (
    <main>
      <header className="masthead">
        <Link className="wordmark" href="/" aria-label="Significance home">
          SIGNIFICANCE
        </Link>
        <p>Claim-state records for AI-assisted mathematics</p>
      </header>

      <section className="hero">
        <p className="lbl">A public evidence ledger</p>
        <h1>Know exactly what was claimed—and what remains open.</h1>
        <p className="lede">
          Significance makes mathematical claims, artifacts, interpretations,
          and requests for review attributable, version-bound, and portable.
          It records evidence without pretending to settle the mathematics.
        </p>
      </section>

      <section className="records" aria-labelledby="records-heading">
        <p className="lbl" id="records-heading">
          Current records — 1
        </p>
        <a className="record-card" href={recordPath}>
          <div className="record-topline">
            <span>2026-openai-nonsofic-groups / v1 / active</span>
            <span>freshness current · checked 2026-08-01</span>
          </div>
          <h3>
            The unit group L_F2(1,2)× of the binary Leavitt algebra is not
            sofic.
          </h3>
          <p>
            OpenAI’s official manuscript, public Lean artifact—reported here,
            not independently reproduced—exact version hashes, provenance, and
            three scoped invitations for independent work.
          </p>
          <span className="open-record">Open the claim-state record →</span>
        </a>
      </section>

      <section className="principles" aria-label="What a record provides">
        <article>
          <span>01</span>
          <h2>Attributable</h2>
          <p>Every non-trivial statement says who asserted it and on what basis.</p>
        </article>
        <article>
          <span>02</span>
          <h2>Version-bound</h2>
          <p>Hashes and commits prevent reviews from silently drifting across revisions.</p>
        </article>
        <article>
          <span>03</span>
          <h2>Open to correction</h2>
          <p>Specific reproduction, correspondence, and review tasks invite useful work.</p>
        </article>
      </section>

      <footer>
        <p>Significance is a ledger and digestion layer—not a mathematical verdict.</p>
        <a href={recordPath}>Read the first record →</a>
      </footer>
    </main>
  );
}
