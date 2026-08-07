import Link from "next/link";
import generatedRecords from "../public/records/index.json";

type RecordSummary = {
  record_id: string;
  record_version: number;
  record_state: string;
  claim: string;
  claim_basis: string;
  claim_asserted_by: string;
  freshness: string;
  freshness_checked_at: string | null;
  evidence_count: number;
  open_invitation_count: number;
};

const records = generatedRecords as RecordSummary[];

function countLabel(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

export default function Home() {
  return (
    <main>
      <header className="masthead">
        <Link className="wordmark" href="/" aria-label="Significance home">
          SIGNIFICANCE
        </Link>
        <p>Claim-state records for AI-assisted mathematics</p>
        <nav className="masthead-nav" aria-label="Site">
          <Link href="/submit">Submit a record →</Link>
          {/* Rendered by the Python renderer, not by this shell. The shell
              links to it; it never restates what the page says. */}
          <a href="/request/">Request a record →</a>
        </nav>
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
          Current records — {records.length}
        </p>
        {records.length ? (
          <div className="records-list">
            {records.map((record) => {
              const recordPath = `/records/${record.record_id}/`;
              const checkedDate = record.freshness_checked_at?.slice(0, 10);

              return (
                <a className="record-card" href={recordPath} key={record.record_id}>
                  <div className="record-topline">
                    <span>
                      {record.record_id} / v{record.record_version} / {record.record_state}
                    </span>
                    <span>
                      freshness {record.freshness}
                      {checkedDate ? (
                        <>
                          {" · checked "}
                          <time dateTime={record.freshness_checked_at ?? undefined}>
                            {checkedDate}
                          </time>
                        </>
                      ) : null}
                    </span>
                  </div>
                  <h3>{record.claim}</h3>
                  <p>
                    {record.claim_basis}, asserted by {record.claim_asserted_by}
                    {" · "}
                    {countLabel(record.evidence_count, "evidence entry", "evidence entries")}
                    {" · "}
                    {countLabel(record.open_invitation_count, "open invitation")}
                  </p>
                  <span className="open-record">Open the claim-state record →</span>
                </a>
              );
            })}
          </div>
        ) : (
          <p className="empty-records">No records built.</p>
        )}
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
        <a href="/records/">Browse the record index →</a>
      </footer>
    </main>
  );
}
