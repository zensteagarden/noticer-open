import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { loadPacket, verifyPacket, verifyAgainstContract, verifyExit, checkReceipt } from "../src/index.mjs";
import { createSuccessContract } from "../src/intention.mjs";

const root = fileURLToPath(new URL("..", import.meta.url));
const fixture = fileURLToPath(new URL("../fixtures/automation-said-success", import.meta.url));

test("public entry point exposes the offline check without changing verdict semantics", () => {
  const loaded = loadPacket(fixture);
  assert.equal(loaded.ok, true);
  assert.equal(verifyPacket(loaded).verdict, "ALLOW");
  const exact = verifyPacket(loaded, { policyId: "artifact.text.exact.v1" });
  assert.equal(exact.verdict, "DENY");
  assert.equal(verifyExit(exact.verdict), 1);
  assert.equal(checkReceipt({ payload: {}, signature: "" }, { keys: [] }, "2026-10-01T00:00:00Z").issuer_trust, "FAIL");
});

test("public entry point exports contract-bound verification", () => {
  const fixture = fileURLToPath(new URL("../fixtures/intention-guided-success", import.meta.url));
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
  const result = verifyAgainstContract(loadPacket(fixture), contract);
  assert.equal(result.verdict, "ALLOW");
});

test("check-packet example treats expectedText on a non-text policy as usage error", () => {
  const run = spawnSync(process.execPath, [
    "examples/check-packet.mjs",
    "fixtures/intention-guided-success",
    "packet.integrity.v1",
    "report_accessible",
  ], { cwd: root, encoding: "utf8", shell: false });
  assert.equal(run.status, 64, run.stderr || run.stdout);
  assert.match(run.stderr, /expectedText is only valid with artifact\.text\.exact\.v1/);
});

test("the standalone starter example explains both results without claiming an external outcome", () => {
  const run = spawnSync(process.execPath, ["examples/first-check.mjs"], { cwd: root, encoding: "utf8", shell: false });
  assert.equal(run.status, 0, run.stderr);
  assert.match(run.stdout, /Synthetic example/);
  assert.match(run.stdout, /Packet integrity: ALLOW/);
  assert.match(run.stdout, /Exact text: DENY/);
  assert.match(run.stdout, /Neither result proves/);
});

test("packet-from-text helper builds a disclosed exact-text packet", () => {
  const work = mkdtempSync(join(tmpdir(), "noticer-walk-"));
  const artifact = join(work, "report.txt");
  const packet = join(work, "packet");
  writeFileSync(artifact, "report_accessible");
  const built = spawnSync(process.execPath, ["examples/packet-from-text.mjs", artifact, packet], {
    cwd: root,
    encoding: "utf8",
    shell: false,
  });
  assert.equal(built.status, 0, built.stderr || built.stdout);
  assert.match(built.stdout, /claim\.expected "report_accessible"/);
  const allow = spawnSync(process.execPath, [
    "src/cli.mjs", "verify", packet,
    "--policy", "artifact.text.exact.v1",
    "--expected-text", "report_accessible",
  ], { cwd: root, encoding: "utf8", shell: false });
  assert.equal(allow.status, 0, allow.stderr || allow.stdout);
  assert.match(allow.stdout, /ALLOW \(integrity\)/);
  const deny = spawnSync(process.execPath, [
    "src/cli.mjs", "verify", packet,
    "--policy", "artifact.text.exact.v1",
    "--expected-text", "other_text",
  ], { cwd: root, encoding: "utf8", shell: false });
  assert.equal(deny.status, 1, deny.stderr || deny.stdout);
  assert.match(deny.stdout, /DENY \(integrity\)/);
  rmSync(work, { recursive: true, force: true });
});

test("public package allowlist excludes internal history and runtime imports stay public", () => {
  const manifest = JSON.parse(readFileSync(new URL("../package.json", import.meta.url), "utf8"));
  assert.equal(manifest.private, true, "npm publication remains a separate authorized action");
  assert.deepEqual(manifest.dependencies ?? {}, {});
  assert.ok(manifest.files.includes("test"));
  assert.ok(manifest.files.includes("examples"));
  assert.ok(!manifest.files.includes("docs"), "do not publish all internal documentation implicitly");
  for (const path of manifest.files) assert.doesNotMatch(path, /OPEN_CORE_BOUNDARY|BUILD_STATUS|DECISIONS|noticer-service|handoff|\.git/);
  for (const name of readdirSync(new URL("../src/", import.meta.url))) {
    const text = readFileSync(new URL(`../src/${name}`, import.meta.url), "utf8");
    assert.doesNotMatch(text, /from\s+["']\.\.\/|import\(["']\.\.\//, "public runtime must not import its parent or private sibling");
  }
});
