import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import test from "node:test";

const indexPath = "public/records/index.html";
const recordPath = "public/records/2026-openai-nonsofic-groups/index.html";
const retiredSyntheticPath = "public/records/2026-sandoval-ramsey-k7/index.html";

test("the public corpus contains only the source-inspected OpenAI record", () => {
  assert.equal(existsSync(indexPath), true);
  assert.equal(existsSync(recordPath), true);
  assert.equal(existsSync(retiredSyntheticPath), false);

  const index = readFileSync(indexPath, "utf8");
  assert.match(index, /2026-openai-nonsofic-groups/);
  assert.doesNotMatch(index, /Sandoval|2606\.01234|synthetic-ramsey/i);
});

test("the rendered record preserves the project's epistemic boundary", () => {
  const record = readFileSync(recordPath, "utf8");
  assert.match(record, /Reported, not reproduced\./);
  assert.match(record, /build<\/span><span class="v">passed/);
  assert.match(record, /does not independently establish correspondence/i);
  assert.match(record, /does not mechanically determine mathematical truth/i);
  assert.doesNotMatch(record, /mathematically verified|proof verified/i);
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
  assert.equal(summaries.records.length, 1);
  assert.equal(summaries.records[0].record_id, "2026-openai-nonsofic-groups");
  assert.equal(summaries.records[0].freshness, "current");
  assert.equal(summaries.records[0].evidence_count, 2);
  assert.equal(summaries.records[0].open_invitation_count, 3);

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
    /2026-openai-nonsofic-groups|2026-08-01|L_F2\(1,2\)|three scoped invitations/,
  );
});
