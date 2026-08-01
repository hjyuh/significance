import Link from "next/link";

const recordPath = "/records/2026-openai-nonsofic-groups/";

export default function Home() {
  return (
    <main>
      <header className="masthead">
        <Link className="wordmark" href="/" aria-label="Significance home">
          Significance<span>.</span>
        </Link>
        <p>Claim-state records for AI-assisted mathematics</p>
      </header>

      <section className="hero">
        <p className="eyebrow">A public evidence ledger</p>
        <h1>Know exactly what was claimed—and what remains open.</h1>
        <p className="lede">
          Significance makes mathematical claims, artifacts, interpretations,
          and requests for review attributable, version-bound, and portable.
          It records evidence without pretending to settle the mathematics.
        </p>
      </section>

      <section className="records" aria-labelledby="records-heading">
        <div className="section-heading">
          <p className="eyebrow">Current records</p>
          <h2 id="records-heading">One claim, shown honestly</h2>
        </div>
        <a className="record-card" href={recordPath}>
          <div className="record-topline">
            <span className="state">Current</span>
            <span className="date">August 1, 2026</span>
          </div>
          <h3>Nonsofic groups exist</h3>
          <p>
            OpenAI’s manuscript, public Lean artifact, exact version hashes,
            provenance, and three scoped invitations for independent work.
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
