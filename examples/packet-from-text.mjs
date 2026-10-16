// SPDX-License-Identifier: Apache-2.0
// Build a disclosed exact-text packet from a local text file. No network, account, or private service.
import { createHash } from "node:crypto";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { basename, resolve } from "node:path";

const [artifactPath, packetDir, claimExpected] = process.argv.slice(2);
if (!artifactPath || !packetDir) {
  console.error("Usage: node examples/packet-from-text.mjs <artifact.txt> <packet-dir> [claim-expected-text]");
  process.exitCode = 64;
} else {
  const bytes = readFileSync(artifactPath);
  const digest = `sha256:${createHash("sha256").update(bytes).digest("hex")}`;
  const expected = claimExpected ?? bytes.toString("utf8");
  const root = resolve(packetDir);
  mkdirSync(resolve(root, "blobs"), { recursive: true });
  writeFileSync(resolve(root, "blobs", digest.replace("sha256:", "sha256-")), bytes);
  writeFileSync(resolve(root, "manifest.json"), `${JSON.stringify({
    schema_version: "0.1",
    observations: [{ observation_id: "artifact" }],
    evidence: [{
      evidence_id: "body",
      observation_id: "artifact",
      digest,
      byte_length: bytes.length,
      media_type: "text/plain",
    }],
    claims: [{
      claim_id: "exact-text",
      predicate: "text.exact.v1",
      parameters: { expected, observation_id: "artifact" },
      evidence_refs: ["body"],
    }],
    obligations: [],
  }, null, 2)}\n`);
  console.log(`wrote packet ${root} from ${basename(artifactPath)}`);
  console.log(`digest ${digest}`);
  console.log(`claim.expected ${JSON.stringify(expected)}`);
}
