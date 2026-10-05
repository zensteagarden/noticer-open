import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { unpackBundle } from "./unpack.mjs";
import { loadPacket, verifyPacket } from "../../src/index.mjs";

function packetFrom(bundle) {
  const dest = mkdtempSync(join(tmpdir(), "noticer-listing-"));
  unpackBundle(bundle, dest);
  return dest;
}

const active = {
  plugin_id: "listing-status",
  plugin_version: "0.1.0",
  trunk: "noticer-public-verifier",
  schema_version: "0.1",
  intention: "The disclosed status line is Active · $425,000.",
  listing_url: "https://example.invalid/listing/425",
  portal_note: "Listing marked Active.",
  before_text: "Coming Soon · $425,000",
  after_text: "Active · $425,000",
  expected_before: "Coming Soon · $425,000",
  expected_after: "Active · $425,000",
  verdict: null,
};

test("named status line ALLOW on exact-text and does not prove the MLS accepted it", () => {
  const dest = packetFrom(active);
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

test("portal says Active but the after selection is still Coming Soon: DENY exact, ALLOW integrity", () => {
  const dest = packetFrom({ ...active, after_text: "Coming Soon · $425,000" });
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
    () => unpackBundle({ ...active, verdict: "ALLOW" }, mkdtempSync(join(tmpdir(), "noticer-listing-"))),
    /PRODUCER_MUST_NOT_VERDICT/,
  );
});

test("shipped false-green fixture unpacks to DENY on exact-text", () => {
  const bundle = JSON.parse(readFileSync(new URL("./fixtures/portal-said-active-but-page-says-coming-soon.bundle.json", import.meta.url), "utf8"));
  const dest = packetFrom(bundle);
  try {
    const exact = verifyPacket(loadPacket(dest), { policyId: "artifact.text.exact.v1" });
    assert.equal(exact.verdict, "DENY");
  } finally {
    rmSync(dest, { recursive: true, force: true });
  }
});

test("producer does not import the trunk verifier or an MLS client", () => {
  const source = readFileSync(new URL("./unpack.mjs", import.meta.url), "utf8");
  assert.equal(source.includes("verify.mjs"), false);
  assert.equal(source.includes("verifyPacket"), false);
  assert.equal(source.includes("fetch("), false);
  assert.equal(source.includes("absence_policy: \"none\""), true);
});
