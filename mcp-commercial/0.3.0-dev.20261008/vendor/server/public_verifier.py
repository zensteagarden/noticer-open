# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Verify a downloaded Noticer package with a separately trusted public key.

Usage: python public_verifier.py receipt.json --key trusted-key.json
       --issuer https://exact-noticer-origin --claim-ref record-id
       --rule '$.status == "active"' --scope confirmed-scope.json
       --max-age-seconds 2700 --decision-ref exact-next-action
       [--expected-build-sha deploy-sha]

Fail-closed decision mode is the default. The reference is caller-local
correlation and is not signed by Noticer. The command emits one stable, unsigned
local JSON decision and exits 0 only for a valid, fresh PROVED receipt whose core
gate is ALLOW. It never performs the downstream action.

Authenticity-only mode requires --verify-only. That mode can exit 0 for any valid
verdict and never authorizes a downstream action.

This verifier uses no Noticer server code and takes no action on the result.
Requires cryptography. A signature authenticates the issuer, not source honesty.
"""
import argparse
import base64
from datetime import datetime, timezone
import hashlib
import json
import re
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey


GATE_SCHEMA = "noticer.relying-decision/1.0"
GATE_POLICY = "noticer.valid-fresh-proved-only/1.0"
GATE_EXIT_CONTINUE = 0
GATE_EXIT_BLOCK = 20
GATE_EXIT_HOLD = 21
GATE_EXIT_REJECTED = 22
DEFAULT_MAX_AGE_SECONDS = 2700
_DECISION_REF = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}\Z")


def decode(value):
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def canonical(value, ascii=False):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=ascii,
                      allow_nan=False).encode()


def at_path(value, path):
    if not re.fullmatch(r"\$\.[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", path):
        raise ValueError("Unsupported rule path")
    for name in path[2:].split("."):
        value = value[name]
    return value


def check_predicate(snapshot, rule):
    path, expected = rule.split(" == ", 1)
    expected = json.loads(expected)
    actual = at_path(snapshot, path)
    return type(actual) is type(expected) and actual == expected


def verify(package, key, issuer, claim_ref, rule, max_age_seconds, scope, expected_build_sha=None):
    payload = package["payload"]
    raw = decode(package["payload_base64"])
    if raw != canonical(payload):
        raise ValueError("Package representations disagree")
    signature = package["signature"]
    if key.get("kty") != "OKP" or key.get("crv") != "Ed25519" or signature.get("alg") != "Ed25519" or signature.get("key_id") != key.get("kid"):
        raise ValueError("Wrong signature algorithm or trusted key")
    Ed25519PublicKey.from_public_bytes(decode(key["x"])).verify(decode(signature["value"]), raw)
    if payload.get("schema") != "noticer.evidence-package/1.0" or payload["issuer"] != issuer:
        raise ValueError("Unexpected issuer or schema")
    # Read signed build identity only from the package; callers cannot override it.
    build_sha = payload.get("build_sha")
    if not isinstance(build_sha, str) or not build_sha.strip() or build_sha.strip().lower() == "unbound":
        raise ValueError("Signed package is missing a bound build_sha")
    if expected_build_sha is not None and build_sha != expected_build_sha:
        raise ValueError("Signed build_sha does not match expected deploy SHA")
    receipt = dict(payload["receipt"])
    digest = receipt.pop("receipt_hash")
    if digest != "sha256:" + hashlib.sha256(canonical(receipt, ascii=True)).hexdigest():
        raise ValueError("Core receipt checksum mismatch")
    if receipt["claim_ref"] != claim_ref or receipt["required_outcome"] != rule or receipt["questioned"]["extract"] != rule:
        raise ValueError("Receipt does not cover the requested decision")
    authority = {k: scope[k] for k in ("core_contract", "claim_ref", "claim_type", "required_outcome", "observer", "questioned", "control", "deadline_seconds", "policy")}
    if "freshness_window_seconds" in scope:
        authority["freshness_window_seconds"] = scope["freshness_window_seconds"]
    scope_hash = "sha256:" + hashlib.sha256(canonical(authority)).hexdigest()
    if scope_hash != scope["obligation_hash"] or scope_hash != receipt["obligation_hash"]:
        raise ValueError("Receipt does not match the caller's confirmed scope")
    for field in ("claim_ref", "claim_type", "required_outcome", "observer", "policy", "core_contract"):
        if receipt[field] != scope[field]:
            raise ValueError("Receipt authority differs from the confirmed scope")
    for side in ("questioned", "control"):
        for field, expected in scope[side].items():
            if receipt[side].get(field) != expected:
                raise ValueError("Receipt target differs from the confirmed scope")
    if receipt.get("core_integrity_valid") is not True or receipt.get("core_contract") != "noticer.core@1.0.0":
        raise ValueError("Unsupported or invalid core contract")
    if receipt["policy"] != {"on_inconclusive": "BLOCK", "on_disproved": "BLOCK"}:
        raise ValueError("Unexpected policy")
    now = datetime.now(timezone.utc)

    def require_fresh(timestamp):
        when = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        age = (now - when).total_seconds()
        if max_age_seconds < 0 or age < -5 or age > max_age_seconds:
            raise ValueError("Evidence is outside the caller's freshness limit")

    require_fresh(receipt["observed_at"])
    if payload["observed_at"] != receipt["observed_at"]:
        raise ValueError("Package observation time differs from its receipt")
    if receipt["verdict"] not in ("PROVED", "DISPROVED", "INCONCLUSIVE"):
        raise ValueError("Invalid verdict")
    for side in ("questioned", "control"):
        observation = receipt[side]
        if "response_body_base64" in observation:
            body = base64.b64decode(observation["response_body_base64"], validate=True)
            if observation["evidence_hash"] != "sha256:" + hashlib.sha256(body).hexdigest():
                raise ValueError("Evidence snapshot checksum mismatch")
        elif observation["predicate_result"] is not None:
            raise ValueError("Decisive observation has no inspectable source snapshot")
        if observation["predicate_result"] is not None:
            require_fresh(observation["observed_at"])
            snapshot = json.loads(body)
            if observation["http_status"] != 200 or check_predicate(snapshot, observation["extract"]) is not observation["predicate_result"]:
                raise ValueError("Source snapshot does not support the predicate")
            if side == "questioned" and at_path(snapshot, observation["claim_id_path"]) != claim_ref:
                raise ValueError("Source snapshot belongs to a different record")
    q, c = receipt["questioned"]["predicate_result"], receipt["control"]["predicate_result"]
    verdict = receipt["verdict"]
    if verdict == "PROVED" and (q is not True or c is not True or receipt["gate"] != "ALLOW"):
        raise ValueError("Unsupported positive verdict")
    if verdict == "DISPROVED" and (q is not False or c is not True or receipt["gate"] != "BLOCK"):
        raise ValueError("Unsupported negative verdict")
    if verdict == "INCONCLUSIVE" and receipt["gate"] != "BLOCK":
        raise ValueError("Uncertainty cannot authorize continuation")
    return {"signature_valid": True, "evidence_valid": True, "verdict": verdict,
            "claim_ref": claim_ref, "observed_at": receipt["observed_at"],
            "build_sha": build_sha, "downstream_action_authorized": False}


def _gate_record(decision_ref, decision, reason_code, *, verification=None, receipt=None):
    """Return the stable relying-decision shape without performing an action."""
    verification = verification or {}
    receipt = receipt or {}
    return {
        "schema": GATE_SCHEMA,
        "policy": GATE_POLICY,
        "decision_output_binding": "local_unsigned",
        "decision_ref": decision_ref,
        "decision_ref_binding": "caller_local_not_signed",
        "decision": decision,
        "reason_code": reason_code,
        "verdict": verification.get("verdict"),
        "claim_ref": verification.get("claim_ref"),
        "obligation_hash": receipt.get("obligation_hash"),
        "receipt_hash": receipt.get("receipt_hash"),
        "observed_at": verification.get("observed_at"),
        "signature_valid": verification.get("signature_valid") is True,
        "evidence_valid": verification.get("evidence_valid") is True,
        "action_performed": False,
    }


def _decision_from_verified(verification, receipt, decision_ref):
    """Map internal verified evidence to one fixed fail-closed decision and exit."""
    if not isinstance(decision_ref, str) or not _DECISION_REF.fullmatch(decision_ref):
        return _gate_record(None, "hold", "decision_ref_invalid"), GATE_EXIT_REJECTED
    if not isinstance(verification, dict) or not isinstance(receipt, dict):
        return _gate_record(decision_ref, "hold", "receipt_rejected"), GATE_EXIT_REJECTED
    if verification.get("signature_valid") is not True or verification.get("evidence_valid") is not True:
        return _gate_record(decision_ref, "hold", "receipt_rejected"), GATE_EXIT_REJECTED
    if (verification.get("claim_ref") != receipt.get("claim_ref") or
            verification.get("observed_at") != receipt.get("observed_at")):
        return _gate_record(decision_ref, "hold", "receipt_rejected"), GATE_EXIT_REJECTED
    verdict = verification.get("verdict")
    if verdict == "PROVED" and receipt.get("gate") == "ALLOW":
        return (_gate_record(decision_ref, "continue", "valid_proved_receipt",
                             verification=verification, receipt=receipt), GATE_EXIT_CONTINUE)
    if verdict == "DISPROVED" and receipt.get("gate") == "BLOCK":
        return (_gate_record(decision_ref, "block", "valid_disproved_receipt",
                             verification=verification, receipt=receipt), GATE_EXIT_BLOCK)
    if verdict == "INCONCLUSIVE" and receipt.get("gate") == "BLOCK":
        return (_gate_record(decision_ref, "hold", "valid_inconclusive_receipt",
                             verification=verification, receipt=receipt), GATE_EXIT_HOLD)
    return _gate_record(decision_ref, "hold", "receipt_rejected"), GATE_EXIT_REJECTED


def evaluate_gate(package, key, issuer, claim_ref, rule, max_age_seconds, scope, decision_ref,
                 expected_build_sha=None):
    """Return (stable decision JSON, exit code) after verifying the package."""
    if not isinstance(decision_ref, str) or not _DECISION_REF.fullmatch(decision_ref):
        return _gate_record(None, "hold", "decision_ref_invalid"), GATE_EXIT_REJECTED
    try:
        verification = verify(package, key, issuer, claim_ref, rule, max_age_seconds, scope,
                              expected_build_sha=expected_build_sha)
        return _decision_from_verified(verification, package["payload"]["receipt"], decision_ref)
    except Exception:
        return _gate_record(decision_ref, "hold", "receipt_rejected"), GATE_EXIT_REJECTED


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--issuer", required=True)
    parser.add_argument("--claim-ref", required=True)
    parser.add_argument("--rule", required=True)
    parser.add_argument("--scope", type=Path, required=True, help="Frozen scope saved from the prepare-order response, before observation")
    parser.add_argument("--max-age-seconds", type=int, default=DEFAULT_MAX_AGE_SECONDS)
    parser.add_argument("--expected-build-sha", default=None,
                        help="Optional expected deploy SHA to compare against the signed build_sha; does not override the signed value")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--verify-only", action="store_true", help="Verify authenticity and evidence only; does not emit a relying decision")
    mode.add_argument("--gate", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--decision-ref", help="Caller-local next-action reference, not signed by Noticer; required unless --verify-only is used (1-256 safe ASCII characters)")
    args = parser.parse_args()
    if args.verify_only and args.decision_ref is not None:
        parser.error("--decision-ref cannot be used with --verify-only")
    if not args.verify_only:
        try:
            result, exit_code = evaluate_gate(
                json.loads(args.receipt.read_text()), json.loads(args.key.read_text()),
                args.issuer, args.claim_ref, args.rule, args.max_age_seconds,
                json.loads(args.scope.read_text()), args.decision_ref,
                expected_build_sha=args.expected_build_sha,
            )
        except Exception:
            safe_ref = args.decision_ref if isinstance(args.decision_ref, str) and _DECISION_REF.fullmatch(args.decision_ref) else None
            result = _gate_record(safe_ref, "hold", "receipt_rejected" if safe_ref else "decision_ref_invalid")
            exit_code = GATE_EXIT_REJECTED
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        raise SystemExit(exit_code)
    try:
        print(json.dumps(verify(json.loads(args.receipt.read_text()), json.loads(args.key.read_text()),
                                args.issuer, args.claim_ref, args.rule, args.max_age_seconds,
                                json.loads(args.scope.read_text()),
                                expected_build_sha=args.expected_build_sha)))
    except Exception as error:
        raise SystemExit("Evidence rejected: " + type(error).__name__)
