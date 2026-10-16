// SPDX-License-Identifier: Apache-2.0
// Run from the repository root after the walkthrough packet exists:
//   node examples/walkthrough-contract.mjs
import { loadPacket, verifyAgainstContract } from "../src/index.mjs";
import { createSuccessContract } from "../src/intention.mjs";

const contract = createSuccessContract({
  intention: "The recipient can access the report.",
  requiredOutcome: "The disclosed evidence says report_accessible.",
  observableCheck: {
    policyId: "artifact.text.exact.v1",
    statement: "Evidence bytes equal report_accessible.",
    expectedText: "report_accessible",
  },
  doesNotEstablish: ["that a real recipient opened the report"],
});

const result = verifyAgainstContract(
  loadPacket("/tmp/noticer-walkthrough/packet"),
  contract,
);
console.log(result.verdict);
