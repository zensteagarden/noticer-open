// SPDX-License-Identifier: Apache-2.0
import { createInterface } from "node:readline/promises";
import { stdin as input, stdout as output } from "node:process";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { createSuccessContract, confirmSuccessContract, renderSuccessContract } from "../src/intention.mjs";
import { loadPacket, verifyPacket } from "../src/index.mjs";

const here = dirname(fileURLToPath(import.meta.url));

function demoContract() {
  return confirmSuccessContract(createSuccessContract({
    intention: "A customer who paid for a report can actually access the report.",
    requiredOutcome: "The evidence captured for this demonstration says the report is accessible.",
    observableCheck: {
      policyId: "artifact.text.exact.v1",
      statement: "The disclosed evidence bytes must exactly equal report_accessible.",
      expectedText: "report_accessible",
    },
    doesNotEstablish: [
      "that a real payment happened",
      "that a real customer received or opened a report",
      "that the customer felt satisfied",
      "that any external action is authorized",
    ],
  }));
}

function verifyFixture(relativePath) {
  const packet = loadPacket(resolve(here, relativePath));
  return verifyPacket(packet, { policyId: "artifact.text.exact.v1" });
}

function printVerdict(label, result) {
  console.log(`${label}: ${result.verdict}`);
  if (Array.isArray(result.establishes)) {
    for (const item of result.establishes) console.log(`  establishes: ${item}`);
  }
  if (Array.isArray(result.does_not_establish)) {
    for (const item of result.does_not_establish) console.log(`  does not establish: ${item}`);
  }
}

async function runDemo() {
  console.log("NOTICER — guided first-run emulation\n");
  console.log("1. Start with the human intention.\n");
  const contract = demoContract();
  console.log(renderSuccessContract(contract));

  console.log("\n2. Show why a system saying success is not enough.\n");
  const falseGreen = verifyFixture("../fixtures/automation-said-success");
  printVerdict("Automation-said-success packet", falseGreen);

  console.log("\n3. Check a disclosed observation that matches the confirmed proxy.\n");
  const matching = verifyFixture("../fixtures/intention-guided-success");
  printVerdict("Matching disclosed packet", matching);

  console.log("\n4. Explain the boundary.\n");
  console.log("The second ALLOW means the disclosed exact-text check passed. It still does not prove a live customer outcome or authorize an action.");

  if (falseGreen.verdict !== "DENY" || matching.verdict !== "ALLOW") {
    console.error("\nDEMO_RESULT: FAIL");
    process.exitCode = 1;
    return;
  }
  console.log("\nDEMO_RESULT: PASS");
}

async function collectInteractiveAnswers() {
  const prompts = [
    "What are you actually trying to have happen?",
    "What concrete outcome would make you say, 'yes, that worked'?",
    "For this starter, what exact text should the disclosed evidence contain when that proxy is satisfied?",
    "What important thing would that exact-text check still NOT prove?",
    "Does this capture what success means for this check? [y/N]",
  ];

  if (!input.isTTY) {
    let raw = "";
    for await (const chunk of input) raw += chunk;
    const lines = raw.split(/\r?\n/).filter((line) => line.length > 0);
    if (lines.length < prompts.length) {
      throw new Error(`guided input expected ${prompts.length} lines, received ${lines.length}`);
    }
    return {
      intention: lines[0],
      requiredOutcome: lines[1],
      expectedText: lines[2],
      limitation: lines[3],
      answer: lines[4],
    };
  }

  const rl = createInterface({ input, output });
  try {
    return {
      intention: await rl.question(`${prompts[0]}\n> `),
      requiredOutcome: await rl.question(`${prompts[1]}\n> `),
      expectedText: await rl.question(`${prompts[2]}\n> `),
      limitation: await rl.question(`${prompts[3]}\n> `),
      answer: await rl.question(`${prompts[4]}\n> `),
    };
  } finally {
    rl.close();
  }
}

async function runInteractive() {
  console.log("NOTICER — intention before automation\n");
  const { intention, requiredOutcome, expectedText, limitation, answer } = await collectInteractiveAnswers();

  const draft = createSuccessContract({
    intention,
    requiredOutcome,
    observableCheck: {
      policyId: "artifact.text.exact.v1",
      statement: `The disclosed evidence bytes must exactly equal ${JSON.stringify(expectedText.trim())}.`,
      expectedText,
    },
    doesNotEstablish: [limitation, "that any external action is authorized"],
  });

  console.log("Here is the Success Contract draft:\n");
  console.log(renderSuccessContract(draft));
  if (answer.trim().toLowerCase() !== "y" && answer.trim().toLowerCase() !== "yes") {
    console.log("\nNothing was confirmed. Change the wording and try again.");
    return;
  }

  const confirmed = confirmSuccessContract(draft);
  console.log("\nConfirmed Success Contract:\n");
  console.log(JSON.stringify(confirmed, null, 2));
  console.log("\nNext: build or collect a disclosed evidence packet that matches this proxy, then run the public verifier. Confirmation did not authorize any external action.");
}

if (process.argv.includes("--demo")) {
  await runDemo();
} else {
  await runInteractive();
}
