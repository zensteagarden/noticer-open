# Implemented packet and receipt format

Status: experimental format 0.1. This describes the current implementation, not a complete formal JSON Schema or a promise of future adjudication support. The executable rules live in `src/packet.mjs`, `src/verify.mjs`, `src/parse.mjs`, `src/canonical.mjs` and `src/receipt.mjs`.

## A directory packet

```text
my-packet/
  manifest.json
  blobs/
    sha256-<64 lowercase hexadecimal digits>
  attestations/                optional
    issuer.json
```

A bounded inert `README.md` is also permitted. No other top-level entries are supported. Blobs are raw bytes, not text-normalized or base64 files. Each filename identifies its SHA-256 digest.

The shipped synthetic fixture is a complete example. A manifest has `schema_version: "0.1"` and four arrays: `observations`, `evidence`, `claims` and `obligations`. Keep `obligations` empty: nonempty obligations are not implemented and cannot silently pass. The loader validates some nested fields but does not yet provide comprehensive closed schemas.

An observation names an `observation_id`. Evidence names an `evidence_id`, its `observation_id`, a `digest` in `sha256:<hex>` form, `byte_length`, and `media_type`. IDs use 1 to 128 ASCII letters, digits, periods, underscores or hyphens and must be unique within their kind. Present blobs must be declared, match their digest and match the declared byte length. A reference to unavailable required evidence is not a success.

For exact-text checking, add a claim like:

```json
{
  "claim_id": "expected-body",
  "predicate": "text.exact.v1",
  "parameters": { "expected": "ok", "observation_id": "captured-body" },
  "evidence_refs": ["body"]
}
```

That evidence reference must resolve to the named observation when an observation binding is supplied. The check compares UTF-8 evidence bytes to the exact declared string. A matching digest with different text can pass integrity while failing this claim.

Attestation files are optional JSON inputs with simple `.json` filenames. New producers should use portable, case-distinct, non-device filenames without path separators. Their canonical content, signature field, raw length and name contribute to evaluation input identity. An attestation is not automatically a trusted assertion.

## Results and exit codes

Results expose `policy_id`, `policy_version`, `vocabulary`, `verdict`, `completed`, `scope`, individual checks, `establishes`, `does_not_establish`, `unknowns`, reasons and next actions. Read these fields together.

For `verify`, exit 0 means ALLOW for the chosen policy; 1 means DENY; 2 means INCONCLUSIVE. Invocation errors use 64 and process failures use 70. `explain` only renders result text. It authenticates nothing. Never use the same interpretation for all commands.

`input_commitment` binds the manifest, supplied or missing evidence, attestations, policy, selected context, verifier source digest and resource limits. `evaluation_digest` identifies the resulting evaluation without claiming that the Node binary or whole operating environment was reproduced. Policies that do not use time ignore the process clock.

## Signed receipts and explicit trust

A receipt is `{ "payload": { ... }, "signature": "<base64url>" }`. The payload selects `algorithm: "Ed25519"`, `issuer` and `key_id`; evaluation fields are signed statement data, not independent verification of that evaluation.

Signing bytes are the UTF-8 domain `NOTICER-RECEIPT-V1\n` followed by the implementation's canonical JSON bytes for the payload. Trust snapshots provide `keys` with `key_id`, `issuer` and raw Ed25519 `public_key` in base64url, plus `valid_until` and `revoked_key_ids`. Development keys use `noticer.invalid` and require explicit `allow_dev: true`; do not use that as production trust.

Receipt success authenticates the statement under the supplied trust snapshot. It neither reruns the evidence evaluation nor establishes an external outcome. Trust snapshots must come from a source you already trust. An old replay time does not establish current issuer trust.

## Current bounds

The authoritative constants are exported as `LIMITS`: 1 MiB manifest, 10 MiB per blob, 1 MiB per attestation, 25 MiB packet total, 100 files, parser depth 32 and strings up to 1,000,000 characters. Not every CLI input path has equivalent hardening; see `PUBLIC_SCOPE.md`. Unknown schemas/policies and missing evidence must remain explicit, not be treated as a favorable conclusion.
