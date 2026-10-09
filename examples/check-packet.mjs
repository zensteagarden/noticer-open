// SPDX-License-Identifier: Apache-2.0
// Read a caller-owned packet directory. Never collect from accounts or act on it.
import { loadPacket, verifyPacket, verifyExit, assertExpectedTextOption } from "../src/index.mjs";

const [directory, policyId = "packet.integrity.v1", expectedText] = process.argv.slice(2);
if (!directory) {
  console.error("Usage: node examples/check-packet.mjs <packet-directory> [policy-id] [expected-text]");
  process.exitCode = 64;
} else {
  try {
    assertExpectedTextOption(policyId, expectedText);
    const options = { policyId };
    if (expectedText !== undefined) options.expectedText = expectedText;
    const result = verifyPacket(loadPacket(directory), options);
    console.log(JSON.stringify(result, null, 2));
    process.exitCode = verifyExit(result.verdict);
  } catch (error) {
    console.error(error.message || "process failure");
    process.exitCode = error instanceof TypeError && String(error.message).includes("expectedText") ? 64 : 70;
  }
}
