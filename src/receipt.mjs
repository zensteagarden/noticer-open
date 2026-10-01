import { createHash, sign, verify, generateKeyPairSync, createPublicKey } from "node:crypto";
import { canonicalBytes, digestOf } from "./canonical.mjs";
import { parseStrict } from "./parse.mjs";

const RECEIPT_DOMAIN = Buffer.from("NOTICER-RECEIPT-V1\n", "utf8");
const ATTESTATION_DOMAIN = Buffer.from("NOTICER-ATTESTATION-V1\n", "utf8");

export function signingBytes(domain, payload) {
  return Buffer.concat([domain, canonicalBytes(payload)]);
}

export function signPayload(domain, payload, privateKey) {
  const bytes = signingBytes(domain, payload);
  return sign(null, bytes, privateKey).toString("base64url");
}

export function verifyPayload(domain, payload, publicKey, signature) {
  const bytes = signingBytes(domain, payload);
  const sig = Buffer.from(signature, "base64url");
  return verify(null, bytes, publicKey, sig);
}

export function receiptSigningBytes(payload) {
  return signingBytes(RECEIPT_DOMAIN, payload);
}

export function signReceipt(payload, privateKey) {
  return signPayload(RECEIPT_DOMAIN, payload, privateKey);
}

export function verifyReceiptMath(payload, publicKey, signature) {
  try {
    return verifyPayload(RECEIPT_DOMAIN, payload, publicKey, signature);
  } catch {
    return false;
  }
}

export function publicKeyFromRaw(base64url) {
  return Buffer.from(base64url, "base64url");
}

export function rawFromPublicKey(keyObject) {
  return keyObject.export({ format: "jwk" }).x;
}

export function generateDevKey() {
  const { publicKey, privateKey } = generateKeyPairSync("ed25519");
  return {
    issuer: "noticer.invalid",
    key_id: `dev-${createHash("sha256").update(rawFromPublicKey(publicKey)).digest("hex").slice(0, 16)}`,
    public_key: rawFromPublicKey(publicKey),
    privateKey,
    publicKey,
  };
}

export function checkReceipt(receipt, trustSnapshot, nowIso) {
  const payload = receipt.payload;
  if (!payload || receipt.signature == null) {
    return { signature_math: false, issuer_trust: "FAIL", snapshot_fresh: false, reason: "INVALID_SIGNATURE" };
  }
  if (payload.algorithm !== "Ed25519") {
    return { signature_math: false, issuer_trust: "FAIL", snapshot_fresh: false, reason: "INVALID_SIGNATURE" };
  }
  const key = (trustSnapshot.keys ?? []).find((item) => item.key_id === payload.key_id);
  const revoked = (trustSnapshot.revoked_key_ids ?? []).includes(payload.key_id);
  const fresh = trustSnapshot.valid_until ? trustSnapshot.valid_until >= nowIso : false;
  if (!key) {
    return { signature_math: false, issuer_trust: "UNKNOWN", snapshot_fresh: fresh, reason: "UNKNOWN_KEY" };
  }
  const math = verifyReceiptMath(payload, publicKeyFromDerRaw(key.public_key), receipt.signature);
  if (!math) return { signature_math: false, issuer_trust: "FAIL", snapshot_fresh: fresh, reason: "INVALID_SIGNATURE" };
  if (!fresh) return { signature_math: true, issuer_trust: "FAIL", snapshot_fresh: false, reason: "STALE_TRUST" };
  if (revoked || key.issuer !== payload.issuer) {
    return { signature_math: true, issuer_trust: "FAIL", snapshot_fresh: fresh, reason: "UNTRUSTED_ISSUER" };
  }
  if (payload.issuer === "noticer.invalid" && trustSnapshot.allow_dev !== true) {
    return { signature_math: true, issuer_trust: "FAIL", snapshot_fresh: fresh, reason: "UNTRUSTED_ISSUER" };
  }
  return { signature_math: true, issuer_trust: "PASS", snapshot_fresh: true, reason: null };
}

function publicKeyFromDerRaw(base64url) {
  return createPublicKey({
    key: { kty: "OKP", crv: "Ed25519", x: base64url },
    format: "jwk",
  });
}

export function loadTrust(text) {
  return parseStrict(text);
}

export function hashPayload(payload) {
  return digestOf(canonicalBytes(payload));
}

export { RECEIPT_DOMAIN, ATTESTATION_DOMAIN };
