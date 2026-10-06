import { test } from "node:test";
import assert from "node:assert/strict";
import { checkLine } from "./check.mjs";

test("matching public line tells the realtor they can tell the seller", () => {
  const checked = checkLine("Price · $425,000", "Price · $425,000");
  assert.equal(checked.verdict, "ALLOW");
  assert.equal(checked.sentence, "Match. You can tell the seller.");
});

test("old public price tells the realtor not yet", () => {
  const checked = checkLine("Price · $425,000", "Price · $450,000");
  assert.equal(checked.verdict, "DENY");
  assert.equal(checked.sentence, "Not yet. The page still says Price · $450,000.");
});
