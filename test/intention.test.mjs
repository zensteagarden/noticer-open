// SPDX-License-Identifier: Apache-2.0
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import {
  createSuccessContract,
  confirmSuccessContract,
  renderSuccessContract,
  validateSuccessContract,
} from "../src/intention.mjs";

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
