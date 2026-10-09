// SPDX-License-Identifier: Apache-2.0
// Read a caller-owned packet directory. Never collect from accounts or act on it.
import { loadPacket, verifyPacket, verifyExit } from "../src/index.mjs";

const [directory, policyId = "packet.integrity.v1", expectedText] = process.argv.slice(2);
if (!directory) {
  console.error("Usage: node examples/check-packet.mjs <packet-directory> [policy-id] [expected-text]");
  process.exitCode = 64;
} else {
  const result = verifyPacket(loadPacket(directory), { policyId, expectedText });
  console.log(JSON.stringify(result, null, 2));
  process.exitCode = verifyExit(result.verdict);
}
