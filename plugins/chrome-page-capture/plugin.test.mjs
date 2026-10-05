import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { unpackBundle } from "./unpack.mjs";
import { loadPacket, verifyPacket } from "../../src/index.mjs";

function packetFrom(bundle) {
  const dest = mkdtempSync(join(tmpdir(), "noticer-plugin-"));
  unpackBundle(bundle, dest);
  return dest;
}

const match = {
  plugin_id: "chrome-page-capture",
  plugin_version: "0.1.0",
  trunk: "noticer-public-verifier",
  schema_version: "0.1",
  intention: "The page shows ready.",
  expected_text: "ready",
  captured_text: "ready",
  page_url: "https://example.invalid/status",
  verdict: null,
};

test("matching disclosed text is ALLOW on exact-text and does not prove the page", () => {
  const dest = packetFrom(match);
  try {
    const loaded = loadPacket(dest);
    assert.equal(loaded.ok, true);
    const exact = verifyPacket(loaded, { policyId: "artifact.text.exact.v1" });
    assert.equal(exact.verdict, "ALLOW");
    assert.equal(exact.does_not_establish.length > 0, true);
    const integrity = verifyPacket(loaded, { policyId: "packet.integrity.v1" });
    assert.equal(integrity.verdict, "ALLOW");
  } finally {
    rmSync(dest, { recursive: true, force: true });
  }
});

test("automation-said-ready with other bytes is DENY on exact-text and ALLOW on integrity", () => {
  const dest = packetFrom({ ...match, captured_text: "loading", expected_text: "ready" });
  try {
    const loaded = loadPacket(dest);
    assert.equal(loaded.ok, true);
    const exact = verifyPacket(loaded, { policyId: "artifact.text.exact.v1" });
    assert.equal(exact.verdict, "DENY");
    const integrity = verifyPacket(loaded, { policyId: "packet.integrity.v1" });
    assert.equal(integrity.verdict, "ALLOW");
  } finally {
    rmSync(dest, { recursive: true, force: true });
  }
});

test("a producer verdict is refused before the trunk sees it", () => {
  assert.throws(() => unpackBundle({ ...match, verdict: "ALLOW" }, mkdtempSync(join(tmpdir(), "noticer-plugin-"))), /PRODUCER_MUST_NOT_VERDICT/);
});

test("shipped mismatch fixture unpacks to the same split", () => {
  const bundle = JSON.parse(readFileSync(new URL("./fixtures/page-said-ready-but-was-not.bundle.json", import.meta.url), "utf8"));
  const dest = packetFrom(bundle);
  try {
    const exact = verifyPacket(loadPacket(dest), { policyId: "artifact.text.exact.v1" });
    assert.equal(exact.verdict, "DENY");
  } finally {
    rmSync(dest, { recursive: true, force: true });
  }
});

test("extension source does not import the trunk verifier", () => {
  const popup = readFileSync(new URL("./popup.js", import.meta.url), "utf8");
  assert.equal(popup.includes("verify.mjs"), false);
  assert.equal(popup.includes("verifyPacket"), false);
});
