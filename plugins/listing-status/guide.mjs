#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// Writes a bundle only. Does not verdict.
import { writeFileSync } from "node:fs";

const kinds = new Set(["status", "price", "offer", "disclosure"]);

function arg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

const lineKind = arg("--kind");
const beforeText = arg("--before");
const afterText = arg("--after");
const expectedBefore = arg("--expect-before");
const expectedAfter = arg("--expect-after");
const out = arg("--out");

if (!kinds.has(lineKind) || !beforeText || !afterText || !expectedBefore || !expectedAfter || !out) {
  console.error("usage: node guide.mjs --kind status|price|offer|disclosure --before <text> --after <text> --expect-before <text> --expect-after <text> --out <bundle.json>");
  process.exit(64);
}

const bundle = {
  plugin_id: "listing-status",
  plugin_version: "0.1.0",
  trunk: "noticer-public-verifier",
  schema_version: "0.1",
  line_kind: lineKind,
  intention: `The disclosed ${lineKind} line is ${expectedAfter}.`,
  listing_url: arg("--url") || "",
  portal_note: arg("--note") || "",
  before_text: beforeText,
  after_text: afterText,
  expected_before: expectedBefore,
  expected_after: expectedAfter,
  verdict: null,
};

writeFileSync(out, `${JSON.stringify(bundle, null, 2)}\n`);
console.log(`wrote ${out}`);
console.log("not a verdict; unpack, then run noticer-check verify");
