// SPDX-License-Identifier: Apache-2.0
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import {
  createSuccessContract,
  confirmSuccessContract,
  renderSuccessContract,
  validateSuccessContract,
  verifyAgainstContract,
  verificationOptionsFromContract,
} from "../src/intention.mjs";
import { loadPacket, verifyPacket } from "../src/index.mjs";
import { digestOf } from "../src/canonical.mjs";
import { generateDevKey, signReceipt, checkReceipt } from "../src/receipt.mjs";

const here = dirname(fileURLToPath(import.meta.url));

function sample() {
  return createSuccessContract({
    intention: "Customer can access the report.",
    requiredOutcome: "Disclosed evidence says report_accessible.",
    observableCheck: {
      policyId: "artifact.text.exact.v1",
      statement: "Evidence equals report_accessible.",
      expectedText: "report_accessible",
    },
    doesNotEstablish: ["that a real customer opened the report"],
  });
}

test("success contract keeps intention, proxy, limitation and authorization separate", () => {
  const draft = sample();
  assert.equal(draft.status, "draft");
  assert.match(draft.authorization_note, /does not grant permission/);
  assert.deepEqual(validateSuccessContract(draft), draft);

  const confirmed = confirmSuccessContract(draft);
  assert.equal(confirmed.status, "confirmed_by_user");
  assert.match(renderSuccessContract(confirmed), /Authorization: none granted/);
});

test("success contract rejects unsupported policy and missing limitations", () => {
  assert.throws(() => createSuccessContract({
    intention: "x",
    requiredOutcome: "y",
    observableCheck: { policyId: "hidden.magic.v1", statement: "z" },
    doesNotEstablish: ["limit"],
  }), /unsupported public policy/);

  assert.throws(() => createSuccessContract({
    intention: "x",
    requiredOutcome: "y",
    observableCheck: { policyId: "packet.integrity.v1", statement: "z" },
    doesNotEstablish: [],
  }), /at least one limitation/);
});

test("success contract rejects extra fields and authorization-boundary edits", () => {
  const draft = sample();
  assert.throws(() => validateSuccessContract({ ...draft, learned_truth: true }), /unsupported success-contract field/);
  assert.throws(() => validateSuccessContract({ ...draft, authorization_note: "authorized" }), /authorization_note/);
});

test("guided demo reproduces false-green denial and matching disclosed allow", () => {
  const script = resolve(here, "../examples/guided-first-run.mjs");
  const run = spawnSync(process.execPath, [script, "--demo"], { encoding: "utf8" });
  assert.equal(run.status, 0, run.stderr || run.stdout);
  assert.match(run.stdout, /Automation-said-success packet: DENY/);
  assert.match(run.stdout, /Matching disclosed packet: ALLOW/);
  assert.match(run.stdout, /DEMO_RESULT: PASS/);
});

function writeTextPacket(text) {
  const root = mkdtempSync(join(tmpdir(), "noticer-contract-"));
  mkdirSync(join(root, "blobs"));
  const bytes = Buffer.from(text);
  const digest = digestOf(bytes);
  writeFileSync(join(root, "manifest.json"), JSON.stringify({
    schema_version: "0.1",
    observations: [{ observation_id: "captured-body" }],
    evidence: [{
      evidence_id: "body",
      observation_id: "captured-body",
      digest,
      byte_length: bytes.length,
      media_type: "text/plain",
    }],
    claims: [{
      claim_id: "exact",
      predicate: "text.exact.v1",
      parameters: { expected: text, observation_id: "captured-body" },
      evidence_refs: ["body"],
    }],
    obligations: [],
  }));
  writeFileSync(join(root, "blobs", digest.replace("sha256:", "sha256-")), bytes);
  return root;
}

function sampleContract(expectedText) {
  return createSuccessContract({
    intention: "The recipient can access the report.",
    requiredOutcome: `The disclosed evidence says ${expectedText}.`,
    observableCheck: {
      policyId: "artifact.text.exact.v1",
      statement: `Evidence bytes equal ${expectedText}.`,
      expectedText,
    },
    doesNotEstablish: ["that a real recipient opened the report"],
  });
}

test("caller expected text is bound: matching packet allows, self-consistent mismatch is denied", () => {
  const matchingRoot = writeTextPacket("report_accessible");
  const mismatchRoot = writeTextPacket("accepted");
  const contract = sampleContract("report_accessible");
  const options = verificationOptionsFromContract(contract);
  assert.equal(options.policyId, "artifact.text.exact.v1");
  assert.equal(options.expectedText, "report_accessible");

  const matching = verifyAgainstContract(loadPacket(matchingRoot), contract);
  assert.equal(matching.verdict, "ALLOW");
  assert.equal(matching.input_commitment.caller_expected_text, "report_accessible");
  assert.ok(matching.checks.some((item) => item.check_id === "caller.expected.v1" && item.status === "PASS"));

  const loadedMismatch = loadPacket(mismatchRoot);
  const internal = verifyPacket(loadedMismatch, { policyId: "artifact.text.exact.v1" });
  assert.equal(internal.verdict, "ALLOW", "packet is self-consistent when the caller does not bind an expectation");

  const key = generateDevKey();
  const payload = {
    algorithm: "Ed25519",
    issuer: "noticer.invalid",
    key_id: key.key_id,
    evaluation_digest: internal.evaluation_digest,
    evaluation_verdict: internal.verdict,
  };
  const receipt = { payload, signature: signReceipt(payload, key.privateKey) };
  const trust = {
    valid_until: "2099-01-01T00:00:00Z",
    keys: [{ key_id: key.key_id, issuer: "noticer.invalid", public_key: key.public_key }],
    revoked_key_ids: [],
    allow_dev: true,
  };
  const signed = checkReceipt(receipt, trust, "2026-10-01T00:00:00Z");
  assert.equal(signed.signature_math, true);
  assert.equal(signed.issuer_trust, "PASS");

  const againstContract = verifyAgainstContract(loadedMismatch, contract);
  assert.equal(againstContract.verdict, "DENY");
  assert.ok(againstContract.reasons.includes("CONTRACT_MISMATCH"));
  assert.ok(againstContract.checks.some((item) => item.check_id === "caller.expected.v1" && item.status === "FAIL"));
  assert.equal(againstContract.input_commitment.caller_expected_text, "report_accessible");

  rmSync(matchingRoot, { recursive: true, force: true });
  rmSync(mismatchRoot, { recursive: true, force: true });
});

test("interactive helper shows the proposed contract before asking for confirmation", () => {
  const script = resolve(here, "../examples/guided-first-run.mjs");
  const input = [
    "The recipient can access the report.",
    "The disclosed evidence says report_accessible.",
    "report_accessible",
    "that a real recipient opened the report",
    "y",
    "",
  ].join("\n");
  const run = spawnSync(process.execPath, [script], { encoding: "utf8", input });
  assert.equal(run.status, 0, run.stderr || run.stdout);
  const proposedAt = run.stdout.indexOf("Here is the proposed Success Contract:");
  const confirmAt = run.stdout.indexOf("Does this capture what success means for this check?");
  const confirmedAt = run.stdout.indexOf("Confirmed Success Contract:");
  assert.ok(proposedAt >= 0, run.stdout);
  assert.ok(confirmAt >= 0, run.stdout);
  assert.ok(confirmedAt >= 0, run.stdout);
  assert.ok(proposedAt < confirmAt, "contract must be printed before the confirmation prompt");
  assert.ok(confirmAt < confirmedAt, "confirmation prompt must appear before the confirmed object");
  assert.match(run.stdout, /Human intention: The recipient can access the report\./);
  assert.match(run.stdout, /Public policy: artifact\.text\.exact\.v1/);
  assert.match(run.stdout, /"expected_text": "report_accessible"/);
});

test("expectedText is rejected for policies that do not check it", () => {
  const fixture = resolve(here, "../fixtures/intention-guided-success");
  const loaded = loadPacket(fixture);
  assert.throws(
    () => verifyPacket(loaded, { policyId: "packet.integrity.v1", expectedText: "report_accessible" }),
    /expectedText is only valid with artifact\.text\.exact\.v1/,
  );
  const cli = spawnSync(process.execPath, [
    "src/cli.mjs", "verify", "fixtures/intention-guided-success",
    "--policy", "packet.integrity.v1",
    "--expected-text", "report_accessible",
  ], { cwd: resolve(here, ".."), encoding: "utf8" });
  assert.equal(cli.status, 64, cli.stderr || cli.stdout);
  assert.match(cli.stderr, /only valid with --policy artifact\.text\.exact\.v1/);
});

test("cli rejects --expected-text without a text value", () => {
  const cwd = resolve(here, "..");
  const missing = spawnSync(process.execPath, [
    "src/cli.mjs", "verify", "fixtures/intention-guided-success",
    "--policy", "artifact.text.exact.v1",
    "--expected-text",
  ], { cwd, encoding: "utf8" });
  assert.equal(missing.status, 64, missing.stderr || missing.stdout);
  assert.match(missing.stderr, /--expected-text requires a text value/);

  const flagAsValue = spawnSync(process.execPath, [
    "src/cli.mjs", "verify", "fixtures/intention-guided-success",
    "--policy", "artifact.text.exact.v1",
    "--expected-text", "--json",
  ], { cwd, encoding: "utf8" });
  assert.equal(flagAsValue.status, 64, flagAsValue.stderr || flagAsValue.stdout);
  assert.match(flagAsValue.stderr, /--expected-text requires a text value/);
  assert.equal(flagAsValue.stdout.trim(), "");
});

test("cli binds --expected-text into exact-text verification", () => {
  const cwd = resolve(here, "..");
  const matching = spawnSync(process.execPath, [
    "src/cli.mjs", "verify", "fixtures/intention-guided-success",
    "--policy", "artifact.text.exact.v1",
    "--expected-text", "report_accessible",
  ], { cwd, encoding: "utf8" });
  assert.equal(matching.status, 0, matching.stderr || matching.stdout);
  assert.match(matching.stdout, /ALLOW/);

  const mismatch = spawnSync(process.execPath, [
    "src/cli.mjs", "verify", "fixtures/intention-guided-success",
    "--policy", "artifact.text.exact.v1",
    "--expected-text", "accepted",
    "--json",
  ], { cwd, encoding: "utf8" });
  assert.equal(mismatch.status, 1, mismatch.stderr || mismatch.stdout);
  const result = JSON.parse(mismatch.stdout);
  assert.equal(result.verdict, "DENY");
  assert.ok(result.reasons.includes("CONTRACT_MISMATCH"));
});
