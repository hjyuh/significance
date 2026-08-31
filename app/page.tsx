import Link from "next/link";
import generatedIndex from "../public/records/index.json";

type RecordSummary = {
  record_id: string;
  record_version: number;
  record_state: string;
  claim: string;
  claim_mathml: string | null;
  claim_basis: string;
  claim_asserted_by: string;
  freshness: string;
  freshness_checked_at: string | null;
  evidence_count: number;
  open_invitation_count: number;
};

type BoardSummary = {
  board_id: string;
  title: string;
  as_of: string;
  row_count: number;
  recorded_row_count: number;
};

type SiteConfig = {
  maintainer_name: string | null;
  repository_url: string | null;
  contact_email: string | null;
};

// The Python builder is the only source of record and board facts. This shell
// presents what it generated and computes nothing of its own -- including the
// "recorded" counts below, which come from the file rather than from
// counting anything here, so the page cannot arrive at a different number from
// the board it links to.
const generated = generatedIndex as {
  records: RecordSummary[];
  boards: BoardSummary[];
  site: SiteConfig;
};
const records = generated.records;
const boards = generated.boards;
const site = generated.site;

function countLabel(count: number, singular: string, plural = `${singular}s`) {
  return `${count} ${count === 1 ? singular : plural}`;
}

function formatBasis(value: string) {
  return ({
    source_quote: "Quoted from the source",
    author_attestation: "Stated by the author",
    editorial_inference: "Significance's interpretation",
    machine_result: "Automated result",
  } as Record<string, string>)[value] ?? value.replaceAll("_", " ");
}

function formatParty(value: string) {
  if (value === "significance-editor") return "Significance editor";
  if (value === "significance-ci") return "Significance automated check";
  if (value === "claude-paper") return "Claude (paper author)";
  if (value === "openai") return "OpenAI";
  if (value === "anthropic") return "Anthropic";
  return value.replaceAll("-", " ");
}

function formatRecordState(value: string) {
  return ({ active: "Active", current: "Active", stale: "Source changed", superseded: "Superseded", withdrawn: "Withdrawn", draft: "Draft" } as Record<string, string>)[value]
    ?? value.replaceAll("_", " ");
}

function formatFreshness(value: string) {
  return ({ current: "Source current", stale: "Source changed", unknown: "Source not rechecked" } as Record<string, string>)[value]
    ?? value.replaceAll("_", " ");
}

export default function Home() {
  return (
    <main>
      <header className="masthead">
        <Link className="wordmark" href="/" aria-label="Significance home">
          SIGNIFICANCE
        </Link>
        <p>Clear records for AI-assisted mathematics</p>
        <nav className="masthead-nav" aria-label="Site">
          {/* First, because the question a skeptic arrives with is who is
              behind this — especially an author who got here from a record
              about their own claim. */}
          <Link href="/about">About and contact →</Link>
          <a href="/request/index.html">Request or correct a record →</a>
          {/* Rendered by the Python renderer, not by this shell. The shell
              links to it; it never restates what the page says. */}
          <a href="/orientation/index.html">What is going on →</a>
          <a href="/glossary/index.html">Glossary →</a>
        </nav>
      </header>

      <section className="hero">
        <p className="lbl">Public record</p>
        <h1>See what was claimed, what was checked, and what remains open.</h1>
        <p className="lede">
          Significance shows the exact mathematical claim, the source version,
          what has been checked, who said what, and what still needs review. It
          records evidence without pretending to settle the mathematics.
        </p>
        {/* The primary action still points at /tasks/, because a completed
            external check is the number that matters. What it was missing is
            the size of the ask: a visitor who does not know what "a check"
            costs reads the button as a demand for peer review. */}
        <p className="hero-action-note">
          A check is one bounded passage — pinned to an exact manuscript hash,
          about an afternoon of work, and no claim about the rest of the paper.
        </p>
        <div className="hero-actions" aria-label="Start here">
          <a className="hero-action-primary" href="/tasks/index.html">Take one focused check →</a>
          <a className="hero-action-secondary" href="/request/index.html">Submit or correct a claim</a>
        </div>
        <p className="hero-account-note">No Significance account is needed to read or start. A GitHub account is used only if you choose to report through GitHub.</p>
      </section>

      <section className="records" aria-labelledby="records-heading">
        <p className="lbl" id="records-heading">
          Current records — {records.length}
        </p>
        {records.length ? (
          <div className="records-list">
            {records.map((record) => {
              const recordPath = `/records/${record.record_id}/index.html`;
              const checkedDate = record.freshness_checked_at?.slice(0, 10);

              return (
                <a className="record-card" href={recordPath} key={record.record_id}>
                  {record.claim_mathml ? (
                    <div className="record-card-math" aria-label={record.claim} dangerouslySetInnerHTML={{ __html: record.claim_mathml }} />
                  ) : <h3>{record.claim}</h3>}
                  <p>
                    {formatBasis(record.claim_basis)} · {formatParty(record.claim_asserted_by)}
                    {" · "}
                    {countLabel(record.evidence_count, "evidence entry", "evidence entries")}
                    {" · "}
                    {countLabel(record.open_invitation_count, "open invitation")}
                  </p>
                  {/* Version, state and freshness stay on the card and stop
                      leading it. They are what a reader checks second, after
                      deciding the claim is worth reading at all; freshness in
                      particular has to remain visible, because a record whose
                      source moved says so here or nowhere. */}
                  <div className="record-cardmeta">
                    <span>
                      Record version {record.record_version} · {formatRecordState(record.record_state)}
                    </span>
                    <span>
                      {formatFreshness(record.freshness)}
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
                  <span className="open-record">Open the record →</span>
                </a>
              );
            })}
          </div>
        ) : (
          <p className="empty-records">No records built.</p>
        )}
      </section>

      {boards.length ? (
        <section className="boards" aria-labelledby="boards-heading">
          <p className="lbl" id="boards-heading">
            Status boards
          </p>
          {boards.map((board) => (
                  <a className="board-card" href={`/boards/${board.board_id}/index.html`} key={board.board_id}>
              <h3>{board.title}</h3>
              <p>
                {board.recorded_row_count} of {board.row_count} rows recorded
                {" · as of "}
                <time dateTime={board.as_of}>{board.as_of.slice(0, 10)}</time>
              </p>
              {/* The board page says this too. It has to be said here as well,
                  because the card is what gets seen alone, and "1 of 10 rows"
                  on its own reads as an unfinished page rather than as the
                  result it is. */}
              <p className="board-note">
                An empty row means nobody here has looked at that result yet,
                and nothing more than that.
              </p>
              <span className="open-record">Open the board →</span>
            </a>
          ))}
        </section>
      ) : null}

      <section className="principles" aria-label="What a record provides">
        <article>
          <span>01</span>
          <h2>Traceable</h2>
          <p>Every important statement names who said it and where it came from.</p>
        </article>
        <article>
          <span>02</span>
          <h2>Tied to a version</h2>
          <p>Every review stays attached to the exact paper or code version it covered.</p>
        </article>
        <article>
          <span>03</span>
          <h2>Open to correction</h2>
          <p>Specific reproduction, correspondence, and review tasks invite useful work.</p>
        </article>
        <article>
          <span>04</span>
          <h2>Built to travel</h2>
          <p>Ordinary YAML and stable pages let an existing tracker reuse the record.</p>
        </article>
      </section>

      <footer>
        <p>Significance organizes evidence and explanation. It does not issue mathematical verdicts.</p>
        <p className="footer-who">
          {site.maintainer_name
            ? `Run by ${site.maintainer_name}.`
            : "Run by one maintainer, not yet named on this site."}{" "}
          <Link href="/about">Who runs this, and how to object →</Link>
        </p>
        <a href="/records/index.html">Browse the record index →</a>
        {site.repository_url ? (
          <a href={site.repository_url}>Source and issue tracker →</a>
        ) : null}
        <Link href="/submit">Advanced contributor builder →</Link>
      </footer>
    </main>
  );
}
