import Link from "next/link";
import type { Metadata } from "next";
import generatedIndex from "../../public/records/index.json";

// Every record on this site insists that a statement names who made it. This
// page is where the site does the same for itself. It is reachable from the
// masthead on purpose: an author who arrives from a record about their own
// claim asks "who is this and what gives them standing" before they read a
// single field, and until this page existed there was nowhere to send them.
//
// The three facts that are not prose come from data/site.yaml, through the
// generated index, guarded the same way the Python-rendered pages guard them:
// a value still carrying a [FILL] marker arrives as null and the page says so,
// rather than printing bracket text or a link that goes nowhere.
type SiteConfig = {
  maintainer_name: string | null;
  repository_url: string | null;
  contact_email: string | null;
};

const site = (generatedIndex as { site: SiteConfig }).site;

export const metadata: Metadata = {
  title: "About Significance — who runs this and how to object",
  description:
    "Who maintains Significance, what it is for, how to reach a person, and what happens when an author objects to a record about their claim.",
};

export default function About() {
  return (
    <main>
      <header className="masthead">
        <Link className="wordmark" href="/" aria-label="Significance home">
          SIGNIFICANCE
        </Link>
        <p>Clear records for AI-assisted mathematics</p>
        <nav className="masthead-nav" aria-label="Site">
          <a href="/records/index.html">Records →</a>
          <a href="/request/index.html">Request or correct a record →</a>
          <a href="/orientation/index.html">What is going on →</a>
          <a href="/glossary/index.html">Glossary →</a>
        </nav>
      </header>

      <section className="hero">
        <p className="lbl">About</p>
        <h1>Who runs this, and what to do if you object.</h1>
        <p className="lede">
          Significance keeps records of mathematical claims: what was claimed,
          which exact version of the source it was claimed in, who asserted
          what, what somebody actually checked, and what nobody has looked at.
          It does not decide whether the mathematics is right, and nothing in
          it ever will.
        </p>
      </section>

      <section className="page-band" aria-labelledby="who-heading">
        <p className="lbl" id="who-heading">Who runs it</p>
        <p className="page-prose">
          {site.maintainer_name ? (
            <>
              Significance is maintained by {site.maintainer_name}. It is not a
              journal, not a society, and not an institution — one person keeps
              it, and the editorial entries on this site are that person&rsquo;s
              judgement, signed as such.
            </>
          ) : (
            <>
              Significance is maintained by one person, and this site does not
              yet print their name — which is a gap, not a policy. It is not a
              journal, not a society, and not an institution, and the editorial
              entries on it are one maintainer&rsquo;s judgement, signed as
              such.
            </>
          )}
        </p>
        <p className="page-prose">
          Every record here carries an attribution for each statement in it.
          That rule is the point of the format, so it applies to the site as
          well: nothing on Significance speaks in an institutional voice it
          does not have.
        </p>
      </section>

      <section className="page-band" aria-labelledby="reach-heading">
        <p className="lbl" id="reach-heading">How to reach a person</p>
        {site.contact_email ? (
          <p className="page-prose">
            Email <a href={`mailto:${site.contact_email}`}>{site.contact_email}</a>.
            A person reads it.
          </p>
        ) : (
          <p className="page-prose">
            No contact address is configured on this site yet. Rather than print
            one that goes nowhere, this page says so: until it is set, the two
            routes below are the working channels.
          </p>
        )}
        <p className="page-prose">
          <a href="/request/index.html">Request or correct a record →</a> is the
          route for anything about a specific record, including taking one down.
          {site.repository_url ? (
            <>
              {" "}
              Everything else — the format, the tooling, a bug on this site —
              belongs in{" "}
              <a href={site.repository_url}>the public repository</a>, where the
              whole history of every record is readable.
            </>
          ) : null}
        </p>
      </section>

      <section className="page-band" aria-labelledby="object-heading">
        <p className="lbl" id="object-heading">If you are an author and you object</p>
        <p className="page-prose">
          Say so and it gets acted on. Concretely, and without exception:
        </p>
        <ul className="page-list">
          <li>
            A record about an individual living author&rsquo;s claim is
            published only after that author asks for it or opts in. A reader
            may suggest one; the suggestion is not permission.
          </li>
          <li>
            A record that is wrong gets corrected, and one that should not exist
            gets withdrawn. Both are ordinary, dated, public events in the
            record&rsquo;s own history, not silent edits.
          </li>
          <li>
            You may attach a response to any assessment of your claim, and
            nobody — not the assessor, not the maintainer — can remove it. The
            assessment and your response render together, and neither is
            presented as settling the question.
          </li>
          <li>
            If you are contacted and you decline, you are never named. No list
            of people who said no exists here in any form, private or otherwise.
          </li>
        </ul>
      </section>

      <section className="page-band" aria-labelledby="editorial-heading">
        <p className="lbl" id="editorial-heading">
          Why a line on your record says &ldquo;Significance&rsquo;s interpretation&rdquo;
        </p>
        <p className="page-prose">
          Because a person here wrote that line, and the record refuses to let
          it pass as anything else. Every statement carries the basis it was
          made on: quoted from your source, stated by you, produced by a
          machine, or inferred by whoever maintains this site. The fourth label
          is the weakest of the four and is marked as such precisely so it
          cannot borrow the authority of the first three. It is a description of
          who is talking, not a claim to know better than you.
        </p>
      </section>

      <section className="page-band" aria-labelledby="reuse-heading">
        <p className="lbl" id="reuse-heading">Reusing the format</p>
        <p className="page-prose">
          The format is portable, so an existing problem tracker can link to or
          consume the same record. Records are ordinary YAML against a published
          schema, and every record and problem page has a stable JSON endpoint
          beside it.{" "}
          {site.repository_url ? (
            <a href={`${site.repository_url}/blob/main/docs/export.md`}>
              The export documentation →
            </a>
          ) : null}
        </p>
      </section>

      <footer>
        <p>
          Significance organizes evidence and explanation. It does not issue
          mathematical verdicts.
        </p>
        <Link href="/">Home →</Link>
        <a href="/records/index.html">Browse the record index →</a>
        {site.repository_url ? (
          <a href={site.repository_url}>Source and issue tracker →</a>
        ) : null}
      </footer>
    </main>
  );
}
