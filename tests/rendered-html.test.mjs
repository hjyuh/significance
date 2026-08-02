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
  assert.match(record, /does not mechanically determine mathematical truth/i);
  assert.doesNotMatch(record, /mathematically verified|proof verified/i);
});

test("the homepage derives its record facts from the generated index", () => {
  const homepage = readFileSync("app/page.tsx", "utf8");
  const summaries = JSON.parse(readFileSync("public/records/index.json", "utf8"));

  assert.match(homepage, /import generatedRecords from "\.\.\/public\/records\/index\.json"/);
  assert.match(homepage, /records\.length/);
  assert.match(homepage, /records\.map/);
  assert.equal(summaries.length, 1);
  assert.equal(summaries[0].record_id, "2026-openai-nonsofic-groups");
  assert.equal(summaries[0].freshness, "current");
  assert.equal(summaries[0].evidence_count, 1);
  assert.equal(summaries[0].open_invitation_count, 3);

  // Record facts must not be copied into JSX. The generated JSON is their
  // sole interface to React.
  assert.doesNotMatch(
    homepage,
    /2026-openai-nonsofic-groups|2026-08-01|L_F2\(1,2\)|three scoped invitations/,
  );
});
