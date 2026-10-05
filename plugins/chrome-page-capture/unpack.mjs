#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// Producer only. Digest is computed here from disclosed bytes. No verdict.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const ID = /^[A-Za-z0-9._-]{1,128}$/;

export function unpackBundle(bundle, dest) {
  if (!bundle || bundle.plugin_id !== "chrome-page-capture") {
    throw new Error("MALFORMED_BUNDLE");
  }
  if (bundle.schema_version !== "0.1" || bundle.trunk !== "noticer-public-verifier") {
    throw new Error("MALFORMED_BUNDLE");
  }
  if (typeof bundle.captured_text !== "string" || typeof bundle.expected_text !== "string") {
    throw new Error("MALFORMED_BUNDLE");
  }
  if (typeof bundle.intention !== "string" || bundle.intention.length === 0) {
    throw new Error("MALFORMED_BUNDLE");
  }
  if (bundle.verdict != null) throw new Error("PRODUCER_MUST_NOT_VERDICT");
  const bytes = Buffer.from(bundle.captured_text, "utf8");
  if (bytes.length === 0 || bytes.length > 10 * 1024 * 1024) throw new Error("LIMIT_EXCEEDED");
  const hex = createHash("sha256").update(bytes).digest("hex");
  const manifest = {
    schema_version: "0.1",
    observations: [{ observation_id: "page-capture" }],
    evidence: [{
      evidence_id: "page-text",
      observation_id: "page-capture",
      digest: `sha256:${hex}`,
      byte_length: bytes.length,
      media_type: "text/plain",
    }],
    claims: [{
      claim_id: "page-text-exact",
      predicate: "text.exact.v1",
      parameters: {
        expected: bundle.expected_text,
        observation_id: "page-capture",
      },
      evidence_refs: ["page-text"],
    }],
    obligations: [],
    extensions: {
      plugin_id: "chrome-page-capture",
      plugin_version: "0.1.0",
      intention: bundle.intention,
      page_url: typeof bundle.page_url === "string" ? bundle.page_url : "",
      producer: "packet producer only; verdict belongs to the Noticer trunk",
    },
  };
  if (!ID.test(manifest.observations[0].observation_id)) throw new Error("MALFORMED_BUNDLE");
  mkdirSync(join(dest, "blobs"), { recursive: true });
  writeFileSync(join(dest, "manifest.json"), `${JSON.stringify(manifest, null, 2)}\n`);
  writeFileSync(join(dest, "blobs", `sha256-${hex}`), bytes);
  writeFileSync(join(dest, "README.md"), "Inert packet note. Not evidence. Not a verdict.\n");
  return { digest: `sha256:${hex}`, byte_length: bytes.length };
}

if (import.meta.url === new URL(process.argv[1], "file:").href || process.argv[1]?.endsWith("unpack.mjs")) {
  const [bundlePath, dest] = process.argv.slice(2);
  if (!bundlePath || !dest) {
    console.error("usage: node unpack.mjs <bundle.json> <packet-dir>");
    process.exit(64);
  }
  const bundle = JSON.parse(readFileSync(bundlePath, "utf8"));
  const written = unpackBundle(bundle, dest);
  console.log(`unpacked ${written.digest} (${written.byte_length} bytes)`);
  console.log("not a verdict; run: node src/cli.mjs verify <packet-dir> --policy artifact.text.exact.v1");
}
