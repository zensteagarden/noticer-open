#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// Producer only. Two disclosed snapshots. No absence policy. No verdict.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

function sha256(bytes) {
  return createHash("sha256").update(bytes).digest("hex");
}

function evidence(id, observationId, bytes) {
  const hex = sha256(bytes);
  return {
    record: {
      evidence_id: id,
      observation_id: observationId,
      digest: `sha256:${hex}`,
      byte_length: bytes.length,
      media_type: "text/plain",
    },
    hex,
    bytes,
  };
}

export function unpackBundle(bundle, dest) {
  if (!bundle || bundle.plugin_id !== "app-update") throw new Error("MALFORMED_BUNDLE");
  if (bundle.schema_version !== "0.1" || bundle.trunk !== "noticer-public-verifier") {
    throw new Error("MALFORMED_BUNDLE");
  }
  if (typeof bundle.intention !== "string" || bundle.intention.length === 0) {
    throw new Error("MALFORMED_BUNDLE");
  }
  if (typeof bundle.before_text !== "string" || typeof bundle.after_text !== "string") {
    throw new Error("MALFORMED_BUNDLE");
  }
  if (typeof bundle.expected_before !== "string" || typeof bundle.expected_after !== "string") {
    throw new Error("MALFORMED_BUNDLE");
  }
  if (bundle.verdict != null) throw new Error("PRODUCER_MUST_NOT_VERDICT");
  const before = Buffer.from(bundle.before_text, "utf8");
  const after = Buffer.from(bundle.after_text, "utf8");
  if (before.length === 0 || after.length === 0) throw new Error("LIMIT_EXCEEDED");
  if (before.length > 10 * 1024 * 1024 || after.length > 10 * 1024 * 1024) {
    throw new Error("LIMIT_EXCEEDED");
  }
  const beforeEvidence = evidence("before-text", "before-capture", before);
  const afterEvidence = evidence("after-text", "after-capture", after);
  const manifest = {
    schema_version: "0.1",
    observations: [
      { observation_id: "before-capture" },
      { observation_id: "after-capture" },
    ],
    evidence: [beforeEvidence.record, afterEvidence.record],
    claims: [
      {
        claim_id: "before-text-exact",
        predicate: "text.exact.v1",
        parameters: { expected: bundle.expected_before, observation_id: "before-capture" },
        evidence_refs: ["before-text"],
      },
      {
        claim_id: "after-text-exact",
        predicate: "text.exact.v1",
        parameters: { expected: bundle.expected_after, observation_id: "after-capture" },
        evidence_refs: ["after-text"],
      },
    ],
    obligations: [],
    extensions: {
      plugin_id: "app-update",
      plugin_version: "0.1.0",
      intention: bundle.intention,
      release_note: typeof bundle.release_note === "string" ? bundle.release_note : "",
      producer: "packet producer only; verdict belongs to the Noticer trunk",
      absence_policy: "none",
    },
  };
  mkdirSync(join(dest, "blobs"), { recursive: true });
  writeFileSync(join(dest, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  writeFileSync(join(dest, "blobs", `sha256-${beforeEvidence.hex}`), beforeEvidence.bytes);
  writeFileSync(join(dest, "blobs", `sha256-${afterEvidence.hex}`), afterEvidence.bytes);
  writeFileSync(join(dest, "README.md"), "Inert packet note. Not evidence. Not a verdict. No absence check.\n");
  return {
    before_digest: beforeEvidence.record.digest,
    after_digest: afterEvidence.record.digest,
  };
}

if (process.argv[1]?.endsWith("unpack.mjs")) {
  const [bundlePath, dest] = process.argv.slice(2);
  if (!bundlePath || !dest) {
    console.error("usage: node unpack.mjs <bundle.json> <packet-dir>");
    process.exit(64);
  }
  const bundle = JSON.parse(readFileSync(bundlePath, "utf8"));
  const written = unpackBundle(bundle, dest);
  console.log(`unpacked before ${written.before_digest}`);
  console.log(`unpacked after ${written.after_digest}`);
  console.log("not a verdict; run: node src/cli.mjs verify <packet-dir> --policy artifact.text.exact.v1");
}
