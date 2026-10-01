import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, readdirSync } from "node:fs";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import { loadPacket, verifyPacket, verifyExit, checkReceipt } from "../src/index.mjs";

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

test("the standalone starter example explains both results without claiming an external outcome", () => {
  const run = spawnSync(process.execPath, ["examples/first-check.mjs"], { cwd: root, encoding: "utf8", shell: false });
  assert.equal(run.status, 0, run.stderr);
  assert.match(run.stdout, /Synthetic example/);
  assert.match(run.stdout, /Packet integrity: ALLOW/);
  assert.match(run.stdout, /Exact text: DENY/);
  assert.match(run.stdout, /Neither result proves/);
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
