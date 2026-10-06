#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// One check for the realtor. Builds a packet, asks the trunk, prints one sentence.
import { mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { unpackBundle } from "./unpack.mjs";
import { loadPacket, verifyPacket } from "../../src/index.mjs";

export function checkLine(expected, publicLine) {
  if (typeof expected !== "string" || expected.length === 0) throw new Error("EXPECTED_LINE_REQUIRED");
  if (typeof publicLine !== "string" || publicLine.length === 0) throw new Error("PUBLIC_LINE_REQUIRED");
  const dest = mkdtempSync(join(tmpdir(), "noticer-line-"));
  try {
    unpackBundle({
      plugin_id: "listing-status",
      plugin_version: "0.1.0",
      trunk: "noticer-public-verifier",
      schema_version: "0.1",
      line_kind: "status",
      intention: `The disclosed line is ${expected}.`,
      before_text: publicLine,
      after_text: publicLine,
      expected_before: publicLine,
      expected_after: expected,
      portal_note: "",
      verdict: null,
    }, dest);
    const result = verifyPacket(loadPacket(dest), { policyId: "artifact.text.exact.v1" });
    if (result.verdict === "ALLOW") {
      return { verdict: "ALLOW", sentence: "Match. You can tell the seller." };
    }
    if (result.verdict === "DENY") {
      return { verdict: "DENY", sentence: `Not yet. The page still says ${publicLine}.` };
    }
    return { verdict: result.verdict, sentence: "Not checked. Do not tell the seller from this result." };
  } finally {
    rmSync(dest, { recursive: true, force: true });
  }
}

function arg(name) {
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

if (process.argv[1]?.endsWith("check.mjs")) {
  const expected = arg("--expect");
  const publicLine = arg("--public");
  if (!expected || !publicLine) {
    console.error("usage: node check.mjs --expect <line you meant> --public <line copied from the page>");
    process.exit(64);
  }
  const checked = checkLine(expected, publicLine);
  console.log(checked.sentence);
  process.exit(checked.verdict === "ALLOW" ? 0 : checked.verdict === "DENY" ? 1 : 2);
}
