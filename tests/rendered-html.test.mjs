import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
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

test("the homepage summary stays faithful to the published corpus", () => {
  const homepage = readFileSync("app/page.tsx", "utf8");
  const sourceRecord = readFileSync(
    "records/2026-openai-nonsofic-groups.yaml",
    "utf8",
  );
  const publishedRecords = readdirSync("records").filter((name) =>
    name.endsWith(".yaml"),
  );
  const invitations = sourceRecord
    .split("\nopen_invitations:\n", 2)[1]
    .split("\nhistory:\n", 1)[0]
    .match(/^  - kind:/gm);

  assert.equal(publishedRecords.length, 1);
  assert.match(homepage, /Current records — 1/);
  assert.match(
    homepage,
    /The unit group L_F2\(1,2\)× of the binary Leavitt algebra is not\s+sofic\./,
  );
  assert.match(sourceRecord, /The unit group L_F2\(1,2\)×/);
  assert.equal(invitations?.length, 3);
  assert.match(homepage, /three scoped invitations/);
  assert.match(homepage, /not independently reproduced/);
  assert.doesNotMatch(homepage, />Nonsofic groups exist</);
});
