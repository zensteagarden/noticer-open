import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash, createPublicKey, verify } from "node:crypto";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";
import { canonicalize, digestOf, evaluationDigest } from "../src/canonical.mjs";
import { parseStrict } from "../src/parse.mjs";
import { loadPacket } from "../src/packet.mjs";
import { verifyPacket, settleFault, VERIFIER_SOURCE_DIGEST, SOURCE_DIGEST_COVERS } from "../src/verify.mjs";
import { LIMITS } from "../src/limits.mjs";
import { generateDevKey, signReceipt, checkReceipt } from "../src/receipt.mjs";

function packet(manifest, blobs = {}) {
  const root = mkdtempSync(join(tmpdir(), "noticer-"));
  mkdirSync(join(root, "blobs"));
  writeFileSync(join(root, "manifest.json"), JSON.stringify(manifest));
  for (const [digest, text] of Object.entries(blobs)) {
    writeFileSync(join(root, "blobs", digest.replace("sha256:", "sha256-")), Buffer.from(text));
  }
  return root;
}

function blob(text) {
  const bytes = Buffer.from(text);
  return { digest: digestOf(bytes), text };
}

test("duplicate keys are rejected", () => {
  assert.throws(() => parseStrict('{"a":1,"a":2}'), /DUPLICATE_KEY/);
});

test("integrity allow does not establish external success", () => {
  const body = blob("ok");
  const root = packet({
    schema_version: "0.1",
    observations: [{ observation_id: "obs-1" }],
    evidence: [{ evidence_id: "ev-1", observation_id: "obs-1", digest: body.digest, byte_length: 2, media_type: "text/plain" }],
    claims: [],
    obligations: [],
  }, { [body.digest]: body.text });
  const result = verifyPacket(loadPacket(root));
  assert.equal(result.verdict, "ALLOW");
  assert.equal(result.vocabulary, "integrity");
  assert.ok(result.does_not_establish.includes("external_write_succeeded"));
  rmSync(root, { recursive: true, force: true });
});

test("empty packet is inconclusive", () => {
  const root = packet({ schema_version: "0.1", observations: [], evidence: [], claims: [], obligations: [] });
  const result = verifyPacket(loadPacket(root));
  assert.equal(result.verdict, "INCONCLUSIVE");
  rmSync(root, { recursive: true, force: true });
});

test("digest mismatch is deny", () => {
  const body = blob("ok");
  const root = packet({
    schema_version: "0.1",
    observations: [{ observation_id: "obs-1" }],
    evidence: [{ evidence_id: "ev-1", observation_id: "obs-1", digest: body.digest, byte_length: 2, media_type: "text/plain" }],
    claims: [],
    obligations: [],
  }, { [body.digest]: "no" });
  const loaded = loadPacket(root);
  assert.equal(loaded.ok, false);
  assert.equal(loaded.code, "DIGEST_MISMATCH");
  rmSync(root, { recursive: true, force: true });
});

test("public adjudication is unsupported and claimant proved is denied", () => {
  const ok = blob("ok");
  const empty = blob("");
  const base = {
    schema_version: "0.1",
    observations: [{ observation_id: "questioned" }, { observation_id: "control" }],
    evidence: [
      { evidence_id: "q", observation_id: "questioned", digest: empty.digest, byte_length: 0, media_type: "text/plain" },
      { evidence_id: "c", observation_id: "control", digest: ok.digest, byte_length: 2, media_type: "text/plain" },
    ],
    claims: [],
    obligations: [],
    adjudication: {
      claim: "automation said success",
      required_outcome: { text: "ok" },
      questioned_observation: "questioned",
      control_observation: "control",
      frozen_rule: "text.exact.v1",
    },
  };
  const root = packet(base, { [empty.digest]: "", [ok.digest]: "ok" });
  const result = verifyPacket(loadPacket(root), { policyId: "adjudication.control.v1" });
  assert.equal(result.verdict, "INCONCLUSIVE");
  assert.equal(result.supported, false);
  assert.equal(result.independently_reproduced, false);
  assert.equal(result.verdict === "PROVED", false);
  rmSync(root, { recursive: true, force: true });

  const authored = packet({ ...base, verdict: "PROVED" });
  assert.equal(verifyPacket(loadPacket(authored)).verdict, "DENY");
  rmSync(authored, { recursive: true, force: true });
});

test("same captured bytes pass integrity and fail exact text", () => {
  const fixture = fileURLToPath(new URL("../fixtures/automation-said-success", import.meta.url));
  const loaded = loadPacket(fixture);
  const integrity = verifyPacket(loaded, { policyId: "packet.integrity.v1" });
  const exact = verifyPacket(loaded, { policyId: "artifact.text.exact.v1" });
  assert.equal(integrity.verdict, "ALLOW");
  assert.equal(integrity.vocabulary, "integrity");
  assert.ok(integrity.optional_failures.includes("text.exact.v1"));
  assert.equal(exact.verdict, "DENY");
  assert.equal(exact.policy_id, "artifact.text.exact.v1");
  assert.ok(exact.does_not_establish.includes("external_write_succeeded"));
  assert.ok(exact.does_not_establish.includes("outcome_observed"));
  assert.equal(integrity.input_commitment.evaluation_time, null);
  assert.notEqual(integrity.evaluation_digest, exact.evaluation_digest);
});

test("missing required bytes are inconclusive for exact text", () => {
  const body = blob("accepted");
  const manifest = {
    schema_version: "0.1",
    observations: [{ observation_id: "captured-body" }],
    evidence: [{ evidence_id: "body", observation_id: "captured-body", digest: body.digest, byte_length: 8, media_type: "text/plain" }],
    claims: [{ claim_id: "said-ok", predicate: "text.exact.v1", parameters: { expected: "ok", observation_id: "captured-body" }, evidence_refs: ["body"] }],
    obligations: [],
  };
  const root = packet(manifest, {});
  const result = verifyPacket(loadPacket(root), { policyId: "artifact.text.exact.v1" });
  assert.equal(result.verdict, "INCONCLUSIVE");
  rmSync(root, { recursive: true, force: true });
});

test("canonical vectors are independent literals", () => {
  assert.equal(canonicalize({}), "{}");
  assert.equal(canonicalize({ b: 1, a: 2 }), '{"a":2,"b":1}');
  assert.equal(canonicalize(["b", "a"]), '["b","a"]');
  assert.equal(canonicalize({ z: "a\nb" }), '{"z":"a\\nb"}');
});

test("rfc 8032 ed25519 empty-message vector", () => {
  const raw = Buffer.from("d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a", "hex");
  const signature = Buffer.from("e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b", "hex");
  const key = createPublicKey({ key: { kty: "OKP", crv: "Ed25519", x: raw.toString("base64url") }, format: "jwk" });
  assert.equal(verify(null, Buffer.alloc(0), key, signature), true);
});

test("removing an attestation changes input identity", () => {
  const body = blob("ok");
  const manifest = {
    schema_version: "0.1",
    observations: [{ observation_id: "obs-1" }],
    evidence: [{ evidence_id: "ev-1", observation_id: "obs-1", digest: body.digest, byte_length: 2, media_type: "text/plain" }],
    claims: [],
    obligations: [],
  };
  const root = packet(manifest, { [body.digest]: "ok" });
  const before = verifyPacket(loadPacket(root)).evaluation_digest;
  mkdirSync(join(root, "attestations"));
  writeFileSync(join(root, "attestations", "a.json"), JSON.stringify({ attestation_id: "a", signature: "sig-1" }));
  const after = verifyPacket(loadPacket(root)).evaluation_digest;
  assert.notEqual(before, after);
  rmSync(root, { recursive: true, force: true });
});

test("a later fault does not erase a decisive deny", () => {
  const partial = settleFault({
    verdict: "DENY",
    reasons: ["CLAIM_MISMATCH"],
    checks: [{ check_id: "text.exact.v1", status: "FAIL", required: true, reason: "CLAIM_MISMATCH" }],
  });
  assert.equal(partial.verdict, "DENY");
  assert.equal(partial.completed, false);
  assert.ok(partial.reasons.includes("INTERNAL_ERROR"));
  const loaded = loadPacket(packet({ schema_version: "0.1", observations: [], evidence: [], claims: [], obligations: [] }));
  const faulted = verifyPacket(loaded, { injectFault: "before-checks" });
  assert.equal(faulted.verdict, "INCONCLUSIVE");
  assert.equal(faulted.completed, false);
});

test("same inputs produce the same evaluation digest", () => {
  const body = blob("ok");
  const manifest = {
    schema_version: "0.1",
    observations: [{ observation_id: "obs-1" }],
    evidence: [{ evidence_id: "ev-1", observation_id: "obs-1", digest: body.digest, byte_length: 2, media_type: "text/plain" }],
    claims: [],
    obligations: [],
  };
  const a = verifyPacket(loadPacket(packet(manifest, { [body.digest]: "ok" })));
  const b = verifyPacket(loadPacket(packet(manifest, { [body.digest]: "ok" })));
  assert.equal(a.evaluation_digest, b.evaluation_digest);
  assert.equal(a.evaluation_digest, evaluationDigest(a));
});

test("receipt trust is separate from signature math", () => {
  const key = generateDevKey();
  const payload = {
    algorithm: "Ed25519",
    issuer: "noticer.invalid",
    key_id: key.key_id,
    evaluation_digest: "sha256:abc",
  };
  const receipt = { payload, signature: signReceipt(payload, key.privateKey) };
  const trust = {
    valid_until: "2099-01-01T00:00:00Z",
    keys: [{ key_id: key.key_id, issuer: "noticer.invalid", public_key: key.public_key }],
    revoked_key_ids: [],
    allow_dev: true,
  };
  const ok = checkReceipt(receipt, trust, "2026-10-01T00:00:00Z");
  assert.equal(ok.signature_math, true);
  assert.equal(ok.issuer_trust, "PASS");
  const untrusted = checkReceipt(receipt, { ...trust, allow_dev: false }, "2026-10-01T00:00:00Z");
  assert.equal(untrusted.signature_math, true);
  assert.equal(untrusted.issuer_trust, "FAIL");
  const stale = checkReceipt(receipt, trust, "2100-01-01T00:00:00Z");
  assert.equal(stale.reason, "STALE_TRUST");
  const tampered = checkReceipt({ ...receipt, payload: { ...payload, evaluation_digest: "sha256:nope" } }, trust, "2026-10-01T00:00:00Z");
  assert.equal(tampered.signature_math, false);
});

test("cli commands do not share a success meaning", () => {
  const fixture = fileURLToPath(new URL("../fixtures/automation-said-success", import.meta.url));
  const cwd = fileURLToPath(new URL("..", import.meta.url));
  const integrity = spawnSync("node", ["src/cli.mjs", "verify", fixture, "--json"], { cwd, encoding: "utf8" });
  const exact = spawnSync("node", ["src/cli.mjs", "verify", fixture, "--policy", "artifact.text.exact.v1"], { cwd, encoding: "utf8" });
  assert.equal(integrity.status, 0);
  assert.match(integrity.stdout, /packet.integrity.v1/);
  assert.equal(exact.status, 1);
  assert.match(exact.stdout, /policy: artifact.text.exact.v1/);
  assert.match(exact.stdout, /external_write_succeeded/);

  const key = generateDevKey();
  const receiptPath = join(tmpdir(), `receipt-${key.key_id}.json`);
  const trustPath = join(tmpdir(), `trust-${key.key_id}.json`);
  const payload = { algorithm: "Ed25519", issuer: "noticer.invalid", key_id: key.key_id, evaluation_verdict: "DENY" };
  writeFileSync(receiptPath, JSON.stringify({ payload, signature: signReceipt(payload, key.privateKey) }));
  writeFileSync(trustPath, JSON.stringify({
    valid_until: "2099-01-01T00:00:00Z",
    keys: [{ key_id: key.key_id, issuer: "noticer.invalid", public_key: key.public_key }],
    revoked_key_ids: [],
    allow_dev: true,
  }));
  const receipt = spawnSync("node", ["src/cli.mjs", "receipt", receiptPath, "--trust", trustPath, "--now", "2026-10-01T00:00:00Z"], { cwd, encoding: "utf8" });
  assert.equal(receipt.status, 0);
  const receiptJson = JSON.parse(receipt.stdout);
  assert.equal(receiptJson.contained_evaluation_verdict, "DENY");
  assert.equal(receiptJson.reproduces_evaluation, false);

  const explained = join(tmpdir(), `explain-${key.key_id}.json`);
  writeFileSync(explained, JSON.stringify({ policy_id: "artifact.text.exact.v1", verdict: "DENY", scope: "artifact.text", establishes: [], does_not_establish: ["external_write_succeeded"] }));
  const explain = spawnSync("node", ["src/cli.mjs", "explain", explained], { cwd, encoding: "utf8" });
  assert.equal(explain.status, 0);
  assert.match(explain.stdout, /does not authenticate/);
  const imported = spawnSync("node", ["src/cli.mjs", "import", "x.zip"], { cwd, encoding: "utf8" });
  assert.equal(imported.status, 64);
});

test("committed limits are the limits that are enforced", () => {
  const root = mkdtempSync(join(tmpdir(), "noticer-limit-"));
  writeFileSync(join(root, "manifest.json"), Buffer.alloc(LIMITS.max_manifest_bytes + 1, 0x20));
  assert.equal(loadPacket(root).code, "LIMIT_EXCEEDED");
  rmSync(root, { recursive: true, force: true });

  const body = blob("ok");
  const crowded = packet({
    schema_version: "0.1",
    observations: [{ observation_id: "obs-1" }],
    evidence: [{ evidence_id: "ev-1", observation_id: "obs-1", digest: body.digest, byte_length: 2, media_type: "text/plain" }],
    claims: [],
    obligations: [],
  }, { [body.digest]: "ok" });
  mkdirSync(join(crowded, "blobs"), { recursive: true });
  for (let i = 0; i < LIMITS.max_files; i += 1) {
    writeFileSync(join(crowded, "blobs", `sha256-${i.toString(16).padStart(64, "0")}`), Buffer.from("x"));
  }
  assert.equal(loadPacket(crowded).code, "LIMIT_EXCEEDED");
  rmSync(crowded, { recursive: true, force: true });
});

test("source digest does not claim to cover the runtime", () => {
  const dir = fileURLToPath(new URL("../src/", import.meta.url));
  const hash = createHash("sha256");
  for (const name of ["canonical.mjs", "limits.mjs", "packet.mjs", "parse.mjs", "receipt.mjs", "verify.mjs"]) {
    hash.update(name);
    hash.update("\0");
    hash.update(readFileSync(join(dir, name)));
    hash.update("\0");
  }
  const expected = `sha256:${hash.digest("hex")}`;
  assert.equal(VERIFIER_SOURCE_DIGEST, expected);
  const body = blob("ok");
  const root = packet({
    schema_version: "0.1",
    observations: [{ observation_id: "obs-1" }],
    evidence: [{ evidence_id: "ev-1", observation_id: "obs-1", digest: body.digest, byte_length: 2, media_type: "text/plain" }],
    claims: [],
    obligations: [],
  }, { [body.digest]: "ok" });
  const result = verifyPacket(loadPacket(root));
  assert.equal(result.input_commitment.verifier_source_digest, expected);
  assert.deepEqual(result.input_commitment.source_digest_covers, SOURCE_DIGEST_COVERS);
  assert.ok(result.runtime_identity.source_digest_does_not_cover.includes("node_binary"));
  assert.equal(result.evaluation_digest, evaluationDigest(result));
  rmSync(root, { recursive: true, force: true });
});
