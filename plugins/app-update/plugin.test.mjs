import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { unpackBundle } from "./unpack.mjs";
import { loadPacket, verifyPacket } from "../../src/index.mjs";

function packetFrom(bundle) {
  const dest = mkdtempSync(join(tmpdir(), "noticer-update-"));
  unpackBundle(bundle, dest);
  return dest;
}

const shipped = {
  plugin_id: "app-update",
  plugin_version: "0.1.0",
  trunk: "noticer-public-verifier",
  schema_version: "0.1",
  intention: "The disclosed after text is ready.",
  release_note: "Status is now ready.",
  before_text: "loading",
  after_text: "ready",
  expected_before: "loading",
  expected_after: "ready",
  verdict: null,
};

test("named before and after bytes ALLOW on exact-text and do not prove a release", () => {
  const dest = packetFrom(shipped);
  try {
    const loaded = loadPacket(dest);
    assert.equal(loaded.ok, true);
    const exact = verifyPacket(loaded, { policyId: "artifact.text.exact.v1" });
    assert.equal(exact.verdict, "ALLOW");
    assert.equal(exact.does_not_establish.includes("external_write_succeeded"), true);
    const integrity = verifyPacket(loaded, { policyId: "packet.integrity.v1" });
    assert.equal(integrity.verdict, "ALLOW");
  } finally {
    rmSync(dest, { recursive: true, force: true });
  }
});

test("release note says ready but after bytes are still loading: DENY exact, ALLOW integrity", () => {
  const dest = packetFrom({ ...shipped, after_text: "loading" });
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
  assert.throws(
    () => unpackBundle({ ...shipped, verdict: "ALLOW" }, mkdtempSync(join(tmpdir(), "noticer-update-"))),
    /PRODUCER_MUST_NOT_VERDICT/,
  );
});

test("shipped false-green fixture unpacks to DENY on exact-text", () => {
  const bundle = JSON.parse(readFileSync(new URL("./fixtures/release-said-ready-but-after-was-loading.bundle.json", import.meta.url), "utf8"));
  const dest = packetFrom(bundle);
  try {
    const exact = verifyPacket(loadPacket(dest), { policyId: "artifact.text.exact.v1" });
    assert.equal(exact.verdict, "DENY");
  } finally {
    rmSync(dest, { recursive: true, force: true });
  }
});

test("producer does not import the trunk verifier", () => {
  const source = readFileSync(new URL("./unpack.mjs", import.meta.url), "utf8");
  assert.equal(source.includes("verify.mjs"), false);
  assert.equal(source.includes("verifyPacket"), false);
  assert.equal(source.includes("absence_policy: \"none\""), true);
});
