import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { canonicalBytes, digestOf, evaluationDigest } from "./canonical.mjs";
import { LIMITS, LIMITS_VERSION } from "./limits.mjs";

export { LIMITS, LIMITS_VERSION };
export const VERIFIER_BUILD = "noticer-public-verifier@0.1.0";
export const SOURCE_DIGEST_COVERS = ["canonical.mjs", "limits.mjs", "packet.mjs", "parse.mjs", "receipt.mjs", "verify.mjs"];
const ARTIFACT_FILES = SOURCE_DIGEST_COVERS;

export function verifierSourceDigest(dir = dirname(fileURLToPath(import.meta.url))) {
  const hash = createHash("sha256");
  for (const name of ARTIFACT_FILES) {
    hash.update(name);
    hash.update("\0");
    hash.update(readFileSync(join(dir, name)));
    hash.update("\0");
  }
  return `sha256:${hash.digest("hex")}`;
}

export const VERIFIER_SOURCE_DIGEST = verifierSourceDigest();

function runtimeIdentity() {
  let lockDigest = "absent";
  try {
    const lockPath = join(dirname(fileURLToPath(import.meta.url)), "..", "package-lock.json");
    lockDigest = `sha256:${createHash("sha256").update(readFileSync(lockPath)).digest("hex")}`;
  } catch {
    lockDigest = "absent";
  }
  return {
    node: process.version,
    package: VERIFIER_BUILD,
    dependency_lock_digest: lockDigest,
    source_digest_does_not_cover: ["node_binary", "npm_dependencies", "operating_system"],
  };
}

const NOT_ESTABLISHED = ["external_write_succeeded", "claim_is_true", "outcome_observed"];

export const POLICIES = {
  "packet.integrity.v1": {
    id: "packet.integrity.v1",
    version: "1",
    vocabulary: "integrity",
    uses_time: false,
    required: ["schema.valid.v1", "references.resolve.v1", "blob.sha256.v1"],
    optional: ["blob.nonempty.v1", "text.exact.v1"],
    missing_bytes: "INCONCLUSIVE",
    decisive_fail: "DENY",
  },
  "artifact.text.exact.v1": {
    id: "artifact.text.exact.v1",
    version: "1",
    vocabulary: "integrity",
    uses_time: false,
    predicate: "text.exact.v1",
    subject_binding: "claim.parameters.observation_id equals the referenced evidence observation_id",
    required: ["schema.valid.v1", "references.resolve.v1", "blob.sha256.v1", "text.exact.v1"],
    optional: ["blob.nonempty.v1"],
    missing_bytes: "INCONCLUSIVE",
    text_mismatch: "DENY",
    note: "Matching bytes to an expected string. Not an external write and not a qualified-control adjudication.",
  },
  "destination.capture.v1": {
    id: "destination.capture.v1",
    version: "1",
    vocabulary: "integrity",
    uses_time: true,
    predicate: "text.exact.v1",
    subject_binding: "claim.parameters.subject and observation_id bind the captured destination",
    freshness: "captured_at within max_age_seconds of the supplied evaluation_time",
    required: ["schema.valid.v1", "references.resolve.v1", "blob.sha256.v1", "text.exact.v1", "freshness.v1"],
    missing_bytes: "INCONCLUSIVE",
    stale: "INCONCLUSIVE",
    note: "The captured destination bytes matched at the supplied time. This does not show that an automation wrote them or that they still match.",
  },
};

export function policyDigest(policyId) {
  return digestOf(canonicalBytes(POLICIES[policyId]));
}

export function verifyPacket(loaded, options = {}) {
  const policyId = options.policyId || "packet.integrity.v1";
  try {
    if (options.injectFault === "before-checks") throw new Error("injected");
    const result = evaluate(loaded, policyId, options);
    if (options.injectFault === "after-checks") return finish(settleFault(result), loaded, options);
    return finish(result, loaded, options);
  } catch {
    return finish(settleFault({
      vocabulary: "integrity",
      policy_id: policyId,
      policy_version: "1",
      verdict: "INCONCLUSIVE",
      completed: false,
      scope: "verifier",
      establishes: [],
      does_not_establish: NOT_ESTABLISHED,
      unknowns: ["INTERNAL_ERROR"],
      reasons: ["INTERNAL_ERROR"],
      next_actions: ["retry_offline_check"],
      checks: [],
      supported: true,
      independently_reproduced: false,
    }), loaded, options);
  }
}

export function settleFault(partial) {
  const decisive = (partial.checks ?? []).some((item) => item.required && item.status === "FAIL");
  return {
    ...partial,
    verdict: decisive ? "DENY" : "INCONCLUSIVE",
    completed: false,
    reasons: [...new Set([...(partial.reasons ?? []), "INTERNAL_ERROR"])],
  };
}

function evaluate(loaded, policyId, options) {
  if (!loaded.ok) {
    const verdict = loaded.code === "UNSUPPORTED_SCHEMA" ? "INCONCLUSIVE" : "DENY";
    return baseResult(policyId, verdict, "packet", [loaded.code || "MALFORMED_PACKET"], []);
  }
  if (loaded.manifest.verdict != null || loaded.manifest.adjudication?.verdict != null) {
    return baseResult(policyId, "DENY", "claimant-authored-verdict", ["MALFORMED_PACKET"], []);
  }
  if (policyId === "adjudication.control.v1") return unsupportedAdjudication();
  const policy = POLICIES[policyId];
  if (policyId === "artifact.text.exact.v1") return artifactText(loaded, policy);
  if (policyId === "destination.capture.v1") return destinationCapture(loaded, policy, options);
  if (policyId === "packet.integrity.v1") return integrity(loaded, policy);
  return baseResult(policyId, "INCONCLUSIVE", "policy", ["UNSUPPORTED_CHECK"], []);
}

function unsupportedAdjudication() {
  return {
    vocabulary: "adjudication",
    policy_id: "adjudication.control.v1",
    policy_version: "0",
    verdict: "INCONCLUSIVE",
    completed: true,
    supported: false,
    independently_reproduced: false,
    scope: "public-adjudication",
    establishes: [],
    does_not_establish: NOT_ESTABLISHED.concat(["independently_reproduced_outcome"]),
    unknowns: ["ADJUDICATION_UNSUPPORTED"],
    reasons: ["ADJUDICATION_UNSUPPORTED"],
    next_actions: ["use_packet_integrity_or_artifact_text_exact"],
    checks: [],
    issuer_assertion: "not_reproduced",
  };
}

function integrity(loaded, policy) {
  const checks = commonChecks(loaded, false);
  return fromChecks(policy, checks, "packet.integrity");
}

function destinationCapture(loaded, policy, options) {
  const checks = commonChecks(loaded, true);
  const claim = (loaded.manifest.claims ?? []).find((item) => item.predicate === "text.exact.v1");
  const capturedAt = Date.parse(claim?.parameters?.captured_at ?? "");
  const evaluationTime = Date.parse(options.evaluationTime ?? "");
  const maxAge = claim?.parameters?.max_age_seconds;
  if (!claim?.parameters?.subject || !Number.isFinite(capturedAt) || !Number.isFinite(evaluationTime) || typeof maxAge !== "number") {
    checks.push({ check_id: "freshness.v1", status: "UNKNOWN", reason: "MISSING_EVIDENCE", required: true, detail: "time binding" });
  } else if (capturedAt > evaluationTime || evaluationTime - capturedAt > maxAge * 1000) {
    checks.push({ check_id: "freshness.v1", status: "UNKNOWN", reason: "STALE_TRUST", required: true, detail: "outside supplied window" });
  } else {
    checks.push(pass("freshness.v1", claim.parameters.subject));
  }
  const result = fromChecks(policy, checks, claim?.parameters?.subject ?? "destination.capture");
  result.does_not_establish = ["automation_wrote_destination", "destination_still_matches", "external_write_succeeded"];
  if (result.verdict === "ALLOW") result.establishes = ["destination_bytes_matched_at_capture"];
  return result;
}

function artifactText(loaded, policy) {
  const checks = commonChecks(loaded, true);
  return fromChecks(policy, checks, "artifact.text");
}

function commonChecks(loaded, textRequired) {
  const checks = [pass("schema.valid.v1", "known schema 0.1")];
  checks.push(references(loaded.manifest));
  checks.push(...blobChecks(loaded).checks);
  checks.push(...textChecks(loaded, textRequired));
  if (loaded.manifest.obligations.length) checks.push({check_id:'obligations.supported.v1',status:'UNKNOWN',reason:'UNSUPPORTED_CHECK',required:true});
  return checks;
}

function fromChecks(policy, checks, scope) {
  const required = checks.filter((item) => item.required);
  const verdict = aggregate(required);
  const passed = required.filter((item) => item.status === "PASS").map((item) => item.check_id);
  return {
    vocabulary: "integrity",
    policy_id: policy.id,
    policy_version: policy.version,
    verdict,
    completed: true,
    supported: true,
    independently_reproduced: verdict === "ALLOW",
    scope,
    establishes: verdict === "ALLOW" ? [...new Set(passed)] : [],
    does_not_establish: NOT_ESTABLISHED,
    unknowns: required.filter((item) => item.status === "UNKNOWN").map((item) => item.reason).filter(Boolean),
    reasons: required.filter((item) => item.status !== "PASS").map((item) => item.reason).filter(Boolean),
    next_actions: verdict === "ALLOW" ? ["read_establishes"] : ["compare_policy_scope"],
    checks,
    optional_failures: checks.filter((item) => !item.required && item.status === "FAIL").map((item) => item.check_id),
  };
}

function baseResult(policyId, verdict, scope, reasons, checks) {
  return {
    vocabulary: "integrity",
    policy_id: policyId,
    policy_version: POLICIES[policyId]?.version ?? "1",
    verdict,
    completed: true,
    supported: true,
    independently_reproduced: false,
    scope,
    establishes: [],
    does_not_establish: NOT_ESTABLISHED,
    unknowns: verdict === "INCONCLUSIVE" ? reasons : [],
    reasons,
    next_actions: ["fix_packet"],
    checks,
  };
}

function textChecks(loaded, required) {
  const claims = (loaded.manifest.claims ?? []).filter((item) => item.predicate === "text.exact.v1");
  if (claims.length === 0) {
    return required ? [{ check_id: "text.exact.v1", status: "UNKNOWN", reason: "MISSING_EVIDENCE", required, detail: "no exact-text claim" }] : [];
  }
  return claims.map((claim) => exactClaim(loaded, claim, required));
}

function exactClaim(loaded, claim, required) {
  const expected = claim.parameters?.expected;
  const ref = claim.evidence_refs?.[0];
  const evidence = (loaded.manifest.evidence ?? []).find((item) => item.evidence_id === ref);
  if (typeof expected !== "string" || !evidence) {
    return { check_id: "text.exact.v1", status: "FAIL", reason: "CLAIM_MISMATCH", required, detail: claim.claim_id };
  }
  if (claim.parameters?.observation_id && claim.parameters.observation_id !== evidence.observation_id) {
    return { check_id: "text.exact.v1", status: "FAIL", reason: "CONFLICTING_EVIDENCE", required, detail: claim.claim_id };
  }
  const bytes = loaded.blobs.get(evidence.digest);
  if (!bytes) {
    return { check_id: "text.exact.v1", status: "UNKNOWN", reason: "MISSING_EVIDENCE", required, detail: claim.claim_id };
  }
  let text;
  try {
    text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
  } catch {
    return { check_id: "text.exact.v1", status: "FAIL", reason: "CLAIM_MISMATCH", required, detail: "invalid-utf8" };
  }
  if (text !== expected) {
    return { check_id: "text.exact.v1", status: "FAIL", reason: "CLAIM_MISMATCH", required, detail: claim.claim_id };
  }
  return pass("text.exact.v1", claim.claim_id, required);
}

function references(manifest) {
  const obs = new Set((manifest.observations ?? []).map((item) => item.observation_id));
  const ev = new Set();
  for (const item of manifest.evidence ?? []) {
    if (ev.has(item.evidence_id) || !obs.has(item.observation_id)) {
      return fail("references.resolve.v1", "CONFLICTING_EVIDENCE");
    }
    ev.add(item.evidence_id);
  }
  for (const claim of manifest.claims ?? []) {
    for (const ref of claim.evidence_refs ?? []) {
      if (!ev.has(ref)) return fail("references.resolve.v1", "CONFLICTING_EVIDENCE");
    }
  }
  return pass("references.resolve.v1", "references resolve");
}

function blobChecks(loaded) {
  const checks = [];
  const evidence = loaded.manifest.evidence ?? [];
  if (evidence.length === 0) {
    checks.push({ check_id: "blob.sha256.v1", status: "UNKNOWN", reason: "MISSING_EVIDENCE", required: true, detail: "no evidence" });
    return { checks };
  }
  for (const item of evidence) {
    const bytes = loaded.blobs.get(item.digest);
    if (!bytes) {
      checks.push({ check_id: "blob.sha256.v1", status: "UNKNOWN", reason: "MISSING_EVIDENCE", required: true, detail: item.evidence_id });
      continue;
    }
    if (bytes.length !== item.byte_length || digestOf(bytes) !== item.digest) {
      checks.push(fail("blob.sha256.v1", "DIGEST_MISMATCH"));
      continue;
    }
    checks.push(pass("blob.sha256.v1", item.evidence_id));
    checks.push(bytes.length > 0
      ? pass("blob.nonempty.v1", item.evidence_id, false)
      : { ...fail("blob.nonempty.v1", "EMPTY_EVIDENCE"), required: false });
  }
  return { checks };
}

function aggregate(required) {
  if (required.some((item) => item.status === "FAIL")) return "DENY";
  if (required.some((item) => item.status === "UNKNOWN") || required.length === 0) return "INCONCLUSIVE";
  if (required.every((item) => item.status === "PASS")) return "ALLOW";
  return "INCONCLUSIVE";
}

function pass(check_id, detail, required = true) {
  return { check_id, status: "PASS", reason: null, detail, required };
}

function fail(check_id, reason) {
  return { check_id, status: "FAIL", reason, required: true };
}

function inputCommitment(loaded, policyId, options) {
  const policy = POLICIES[policyId];
  const evidence = (loaded?.manifest?.evidence ?? []).map((item) => {
    const bytes = loaded.blobs?.get(item.digest);
    return {
      evidence_id: item.evidence_id,
      expected_digest: item.digest,
      expected_length: item.byte_length,
      available: Boolean(bytes),
      actual_digest: bytes ? digestOf(bytes) : null,
      actual_length: bytes ? bytes.length : null,
    };
  }).sort((a, b) => (a.evidence_id < b.evidence_id ? -1 : 1));
  const attestations = (loaded?.attestations ?? []).map((item) => ({
    name: item.name,
    canonical_digest: digestOf(canonicalBytes(item.value)),
    raw_length: item.raw_length,
    signature: item.value?.signature ?? null,
  }));
  return {
    version: "input.v1",
    manifest_digest: loaded?.manifestDigest ?? null,
    evidence,
    attestations,
    policy_id: policyId,
    policy_version: policy?.version ?? null,
    policy_digest: policy ? policyDigest(policyId) : null,
    verifier_build: VERIFIER_BUILD,
    verifier_source_digest: VERIFIER_SOURCE_DIGEST,
    source_digest_covers: SOURCE_DIGEST_COVERS,
    trust_snapshot_digest: options.trustSnapshotDigest ?? null,
    limits_version: LIMITS_VERSION,
    limits_digest: digestOf(canonicalBytes(LIMITS)),
    evaluation_time: policy?.uses_time ? (options.evaluationTime ?? null) : null,
    request_context_digest: options.requestContextDigest ?? null,
  };
}

function finish(result, loaded, options) {
  const evaluation = {
    ...result,
    packet_only: true,
    input_commitment: inputCommitment(loaded?.ok ? loaded : { ...loaded, blobs: loaded?.blobs ?? new Map(), attestations: [] }, result.policy_id, options),
  };
  evaluation.evaluation_digest = evaluationDigest(evaluation);
  evaluation.runtime_identity = runtimeIdentity();
  return evaluation;
}

export function verifyExit(verdict) {
  if (verdict === "ALLOW") return 0;
  if (verdict === "DENY") return 1;
  if (verdict === "INCONCLUSIVE") return 2;
  return 70;
}
