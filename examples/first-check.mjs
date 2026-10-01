// SPDX-License-Identifier: Apache-2.0
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { loadPacket, verifyPacket } from "../src/index.mjs";

// SYNTHETIC: the packet contains "accepted" but declares an expectation of "ok".
// No account, network call, private service, or model is involved.
const fixture = fileURLToPath(new URL("../fixtures/automation-said-success", import.meta.url));
const loaded = loadPacket(fixture);
const integrity = verifyPacket(loaded, { policyId: "packet.integrity.v1" });
const exact = verifyPacket(loaded, { policyId: "artifact.text.exact.v1" });
assert.equal(integrity.verdict, "ALLOW");
assert.equal(exact.verdict, "DENY");
console.log("Synthetic example: the bytes say accepted; the expected text is ok.");
console.log(`Packet integrity: ${integrity.verdict}. The disclosed bytes match their declared digest.`);
console.log(`Exact text: ${exact.verdict}. Those bytes do not equal the expected text.`);
console.log("Neither result proves that an automation succeeded or authorizes an action.");
console.log("Demo completed: both expected results were reproduced. This is not an ALLOW exit from the verifier CLI.");
