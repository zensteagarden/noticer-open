#!/usr/bin/env node
import { readFileSync } from "node:fs";
import { loadPacket } from "./packet.mjs";
import { verifyPacket, verifyExit } from "./verify.mjs";
import { checkReceipt, loadTrust } from "./receipt.mjs";

const [command, target, ...rest] = process.argv.slice(2);

function flag(name) {
  const index = rest.indexOf(name);
  return index >= 0 ? rest[index + 1] : undefined;
}

function failInvocation(message) {
  console.error(message);
  process.exit(64);
}

function readExpectedText() {
  const index = rest.indexOf("--expected-text");
  if (index < 0) return undefined;
  const value = rest[index + 1];
  if (value === undefined || value.startsWith("-")) {
    failInvocation("--expected-text requires a text value");
  }
  return value;
}

if (!command || command === "--help") {
  console.log(`noticer-check verify <packet> [--policy packet.integrity.v1|artifact.text.exact.v1] [--expected-text <text>] [--json]
noticer-check receipt <receipt.json> --trust <trust.json> [--now <iso>] [--json]
noticer-check explain <result.json>

verify exit 0 means that named policy passed. It does not prove an external write.
receipt exit 0 means the receipt is authentic under the supplied trust snapshot. The evaluation inside it may still be DENY or INCONCLUSIVE.
explain exit 0 means the result was printed. It does not authenticate the result.
import is not implemented. Directory verification is the supported flow.
No exit code authorizes an external action.`);
  process.exit(command ? 0 : 64);
}

try {
  if (command === "verify") {
    if (!target) failInvocation("packet path required");
    const policyId = flag("--policy") || "packet.integrity.v1";
    const expectedText = readExpectedText();
    if (expectedText !== undefined && policyId !== "artifact.text.exact.v1") {
      failInvocation("--expected-text is only valid with --policy artifact.text.exact.v1");
    }
    const loaded = loadPacket(target);
    const result = verifyPacket(loaded, {
      policyId,
      expectedText,
      evaluationTime: flag("--evaluation-time"),
      manifestDigest: loaded.manifestDigest ?? null,
    });
    if (rest.includes("--json")) console.log(JSON.stringify(result));
    else {
      console.log(`policy: ${result.policy_id}`);
      console.log(`${result.verdict} (${result.vocabulary})`);
      console.log(`scope: ${result.scope}`);
      console.log(`establishes: ${result.establishes.join(", ") || "none"}`);
      console.log(`does not establish: ${result.does_not_establish.join(", ")}`);
      console.log(`unknown: ${result.unknowns.join(", ") || "none"}`);
      console.log(`next: ${result.next_actions[0] || "none"}`);
    }
    process.exit(verifyExit(result.verdict));
  }
  if (command === "receipt") {
    if (!target || !flag("--trust")) failInvocation("receipt and --trust required");
    const receipt = loadTrust(readFileSync(target, "utf8"));
    const trust = loadTrust(readFileSync(flag("--trust"), "utf8"));
    const suppliedNow = flag("--now");
    const report = checkReceipt(receipt, trust, suppliedNow || new Date().toISOString());
    report.time_source = suppliedNow ? "supplied" : "process_clock";
    report.authenticates_statement = report.signature_math === true && report.issuer_trust === "PASS";
    report.establishes_current_trust = report.authenticates_statement;
    report.historical_replay_does_not_establish_current_trust = report.reason === "STALE_TRUST";
    report.reproduces_evaluation = false;
    report.contained_evaluation_verdict = receipt.payload?.evaluation_verdict ?? null;
    console.log(JSON.stringify(report));
    process.exit(report.authenticates_statement ? 0 : 1);
  }
  if (command === "explain") {
    if (!target) failInvocation("result path required");
    const result = loadTrust(readFileSync(target, "utf8"));
    console.log("Rendered only. This does not authenticate the result or prove the claim.");
    console.log(`policy: ${result.policy_id}`);
    console.log(`${result.verdict}: checked ${result.scope}. Establishes ${result.establishes?.join(", ") || "nothing named"}. Does not establish ${(result.does_not_establish ?? []).join(", ")}.`);
    process.exit(0);
  }
  if (command === "import") failInvocation("import is not implemented; verify a packet directory");
  failInvocation(`unknown command ${command}`);
} catch (error) {
  console.error(error.message || "process failure");
  process.exit(70);
}
