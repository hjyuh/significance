import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const indexPath = "public/records/index.html";
const recordPath = "public/records/2026-openai-nonsofic-groups/index.html";
const zetaRecordPath = "public/records/2026-anthropic-zeta-two-thirds/index.html";
const rafik653RecordPath = "public/records/2026-rafikzeraoulia-erdos-653/index.html";
const rafik726RecordPath = "public/records/2026-rafikzeraoulia-erdos-726/index.html";
const retiredSyntheticPath = "public/records/2026-sandoval-ramsey-k7/index.html";

test("the public corpus contains only source-inspected records", () => {
  assert.equal(existsSync(indexPath), true);
  assert.equal(existsSync(recordPath), true);
  assert.equal(existsSync(zetaRecordPath), true);
  assert.equal(existsSync(rafik653RecordPath), true);
  assert.equal(existsSync(rafik726RecordPath), true);
  assert.equal(existsSync(retiredSyntheticPath), false);

  const index = readFileSync(indexPath, "utf8");
  assert.match(index, /2026-openai-nonsofic-groups/);
  assert.match(index, /2026-anthropic-zeta-two-thirds/);
  assert.doesNotMatch(index, /Sandoval|2606\.01234|synthetic-ramsey/i);
});

test("the rendered record preserves the project's epistemic boundary", () => {
  const record = readFileSync(recordPath, "utf8");
  assert.match(record, /Published by the source\. Any independent rerun appears as a separate entry\./);
  assert.match(record, /the later formal-artifact entry records that reproduction/i);
  assert.match(record, /Code build<\/span><span class="v">Completed/);
  assert.match(record, /does not independently establish correspondence/i);
  assert.match(record, /does not mechanically determine mathematical truth/i);
  assert.doesNotMatch(record, /mathematically verified|proof verified/i);
});

test("the zeta record separates pinned sources from independent execution", () => {
  const record = readFileSync(zetaRecordPath, "utf8");
  assert.match(record, /<math xmlns="http:\/\/www\.w3\.org\/1998\/Math\/MathML"/);
  assert.match(record, /<mfrac>/);
  assert.match(record, /Summary · for readers/);
  assert.match(record, /Reader summary · Significance/);
  assert.match(record, /Record note · Significance/);
  assert.doesNotMatch(record, /Confirming a description would not confirm the mathematics/);
  assert.match(record, /0\.67250/);
  assert.match(record, /no bearing on the Riemann hypothesis in either direction/i);
  assert.match(record, /Companion:/);
  assert.match(record, /45e0330ad379…/);
  assert.match(record, /has not attached its own execution receipt/i);
  assert.doesNotMatch(record, /Code build<\/span><span class="v">Completed/);
});

test("the homepage derives its record facts from the generated index", () => {
  const homepage = readFileSync("app/page.tsx", "utf8");
  const summaries = JSON.parse(readFileSync("public/records/index.json", "utf8"));

  assert.match(homepage, /import generatedIndex from "\.\.\/public\/records\/index\.json"/);
  assert.match(homepage, /records\.length/);
  assert.match(homepage, /records\.map/);

  // The index carries records and boards. It was a bare array until the board
  // needed somewhere to be linked from, and the rule that the shell may only
  // present generated data left exactly one place to put it.
  assert.deepEqual(Object.keys(summaries).sort(), ["boards", "records"]);
  assert.equal(summaries.records.length, 6);
  const byId = Object.fromEntries(summaries.records.map((record) => [record.record_id, record]));
  assert.equal(byId["2026-openai-nonsofic-groups"].freshness, "current");
  assert.equal(byId["2026-openai-nonsofic-groups"].evidence_count, 2);
  assert.equal(byId["2026-openai-nonsofic-groups"].open_invitation_count, 3);
  assert.equal(byId["2026-anthropic-zeta-two-thirds"].freshness, "current");
  assert.equal(byId["2026-anthropic-zeta-two-thirds"].evidence_count, 1);
  assert.equal(byId["2026-anthropic-zeta-two-thirds"].open_invitation_count, 3);
  assert.equal(byId["2026-rafikzeraoulia-erdos-653"].freshness, "current");
  assert.equal(byId["2026-rafikzeraoulia-erdos-726"].freshness, "current");
  assert.equal(byId["2026-evanbeller-erdos-132"].freshness, "current");

  // Board counts are generated, not counted in JSX: the homepage must not be
  // able to disagree with the board about how much of it is filled in.
  assert.equal(summaries.boards.length, 1);
  assert.equal(summaries.boards[0].board_id, "ten-results");
  assert.equal(summaries.boards[0].row_count, 10);
  assert.equal(summaries.boards[0].recorded_row_count, 1);
  assert.match(homepage, /boards\.map/);
  assert.doesNotMatch(homepage, /ten-results|The ten results/);

  // Record facts must not be copied into JSX. The generated JSON is their
  // sole interface to React.
  assert.doesNotMatch(
    homepage,
    /2026-openai-nonsofic-groups|2026-anthropic-zeta-two-thirds|2026-08-01|2026-08-10|L_F2\(1,2\)|0\.67250|three scoped invitations/,
  );
});

test("the static record index renders display mathematics", () => {
  const index = readFileSync("public/records/index.html", "utf8");
  assert.match(index, /class="claim-math-inline"/);
  assert.match(index, /<mfrac>/);
});
