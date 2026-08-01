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
