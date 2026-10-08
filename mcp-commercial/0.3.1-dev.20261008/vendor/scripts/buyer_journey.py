# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Reference agent buyer with encrypted, durable order custody.

The custody key is supplied separately by the caller; this tool never creates it.
No credential, challenge, source body or capability is printed. Transfer the
encrypted journal and its custody key through separate private channels. Losing
both the journal's saved intent/capability and a private backup cannot be repaired
by a payment return URL. Never edit the server database to recover access.

Each command is explicit. Preparation does not run a check; running does not pay;
payment does not authorize a downstream action. After an ambiguous payment,
only status/evidence reads are supported until separately reconciled.

Journals contain authenticated ciphertext; the supplied key is never persisted.
An optional receipt export contains only the exact verified response bytes and
is plaintext. It does not include the journal's private access or payment state.
POSIX files use mode 0600. Windows metadata ACL privacy is not asserted. File
flush/atomic replacement and OS locks cover process interruption; power-loss
durability of Windows directory metadata is not independently established.
Handoffs publish a flushed temporary file atomically to a new destination; the
original journal remains intact. Only a read-back-verified handoff is successful.
"""
from __future__ import annotations

import argparse
import base64
from collections import namedtuple
from contextlib import contextmanager
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

_spec = importlib.util.spec_from_file_location("buyer_public_verifier", Path(__file__).resolve().parents[1] / "server/public_verifier.py")
verifier = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(verifier)
Response = namedtuple("Response", "status body headers raw", defaults=(None,))
AAD = b"noticer.buyer-custody.v1"
MAGIC = b"NOTICER-CUSTODY-1\n"
ORDER = re.compile(r"ord_[0-9a-f]{32}\Z")
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
# Two base64 raw responses plus the parsed package fit below this bound.
MAX_JOURNAL_BYTES = 16 * 1024 * 1024


class BuyerError(ValueError):
    """Only fixed local error codes belong in user-visible output."""


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def origin_only(origin):
    try:
        parts = urlsplit(origin)
        if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.path or parts.query or parts.fragment or parts.port not in (None, 443)
                or any(ord(c) < 33 for c in origin)):
            raise ValueError()
        return origin
    except (TypeError, ValueError):
        raise BuyerError("exact_https_origin_required") from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class HttpTransport:
    def __init__(self, origin):
        self.origin = origin_only(origin)
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    def __call__(self, method, path, body=None, headers=None):
        if not path.startswith("/") or path.startswith("//") or "?" in path or "#" in path:
            raise BuyerError("invalid_api_path")
        request = urllib.request.Request(self.origin + path, method=method,
                                         data=canonical(body) if body is not None else None,
                                         headers={"Content-Type": "application/json", **(headers or {})})
        try:
            response = self.opener.open(request, timeout=20)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            if 300 <= response.status < 400:
                raise BuyerError("redirect_refused")
            raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise BuyerError("response_too_large")
            return Response(response.status, json.loads(raw), dict(response.headers), raw)


def publish_new(destination, raw):
    """Atomic no-overwrite publication; never expose a partial handoff file."""
    target, temporary = Path(destination).absolute(), None
    try:
        if target.exists() or target.is_symlink():
            raise ValueError()
        descriptor, temporary = tempfile.mkstemp(prefix=".noticer-handoff-", dir=target.parent)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        # Same-directory hard-link publication is atomic and refuses overwrite.
        os.link(temporary, target)
        if os.name != "nt":
            directory = os.open(target.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        if target.read_bytes() != raw:
            raise ValueError()
    except Exception:
        raise BuyerError("handoff_failed") from None
    finally:
        if temporary is not None:
            Path(temporary).unlink(missing_ok=True)


class EncryptedJournal:
    def __init__(self, path, key):
        if not isinstance(key, bytes) or len(key) != 32:
            raise BuyerError("custody_key_required")
        self.path = Path(path).absolute()
        self.cipher = AESGCM(key)

    @contextmanager
    def locked(self):
        """OS locks release on process death; no stale-lock deletion is needed."""
        if not self.path.parent.is_dir() or self.path.is_symlink():
            raise BuyerError("custody_directory_required")
        lock_path = self.path.with_name(self.path.name + ".lock")
        if lock_path.is_symlink():
            raise BuyerError("custody_lock_unavailable")
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        stream = os.fdopen(descriptor, "r+b")
        acquired = False
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(descriptor).st_size == 0:
                    stream.write(b"\0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            acquired = True
            yield
        except OSError:
            raise BuyerError("custody_storage_unavailable") from None
        finally:
            if acquired:
                if os.name == "nt":
                    stream.seek(0)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            stream.close()

    def load(self):
        try:
            if self.path.is_symlink() or self.path.stat().st_size > MAX_JOURNAL_BYTES:
                raise ValueError()
            raw = self.path.read_bytes()
            if not raw.startswith(MAGIC):
                raise ValueError()
            raw = raw[len(MAGIC):]
            value = json.loads(self.cipher.decrypt(raw[:12], raw[12:], AAD))
            if not isinstance(value, dict) or value.get("schema") != AAD.decode():
                raise ValueError()
            return value
        except Exception:
            raise BuyerError("custody_unavailable") from None

    def save(self, value):
        temporary = None
        try:
            if self.path.is_symlink() or value.get("schema") != AAD.decode():
                raise ValueError()
            nonce = secrets.token_bytes(12)
            raw = MAGIC + nonce + self.cipher.encrypt(nonce, canonical(value), AAD)
            if len(raw) > MAX_JOURNAL_BYTES:
                raise ValueError()
            descriptor, temporary = tempfile.mkstemp(prefix=".noticer-custody-", dir=self.path.parent)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
            if os.name != "nt":
                os.chmod(temporary, 0o600)
            os.replace(temporary, self.path)
            temporary = None
            if os.name != "nt":
                directory = os.open(self.path.parent, os.O_RDONLY)
                try:
                    os.fsync(directory)
                finally:
                    os.close(directory)
            if self.load() != value:
                raise ValueError()
        except Exception:
            raise BuyerError("custody_write_failed") from None
        finally:
            if temporary is not None:
                Path(temporary).unlink(missing_ok=True)

    def handoff(self, destination):
        """Copy encrypted custody; the caller transfers its key separately."""
        with self.locked():
            value = self.load()
            target = Path(destination).absolute()
            if target.exists() or target.is_symlink():
                raise BuyerError("handoff_destination_exists")
            publish_new(target, self.path.read_bytes())
            try:
                raw = target.read_bytes()[len(MAGIC):]
                if json.loads(self.cipher.decrypt(raw[:12], raw[12:], AAD)) != value:
                    raise ValueError()
            except Exception:
                raise BuyerError("handoff_failed") from None


def payment_fields(header):
    # The documented adapter emits quoted fields. Do not accept duplicate fields.
    if not isinstance(header, str) or not header.startswith("Payment ") or len(header) > 16384:
        raise BuyerError("invalid_payment_header")
    fields, position, body = {}, 0, header[8:]
    pair = re.compile(r'\s*([A-Za-z][A-Za-z0-9_-]*)="([^"\\\r\n]*)"\s*(?:, |$)')
    while position < len(body):
        match = pair.match(body, position)
        if not match or match[1] in fields:
            raise BuyerError("invalid_payment_header")
        fields[match[1]] = match[2]
        position = match.end()
    return fields


class BuyerJourney:
    def __init__(self, journal, origin, trusted_key, *, transport=None, expected_build_sha=None):
        self.journal, self.origin = journal, origin_only(origin)
        self.trusted_key = trusted_key
        self.transport = transport or HttpTransport(origin)
        self.expected_build_sha = expected_build_sha

    def _trust(self):
        try:
            if self.trusted_key.get("kty") != "OKP" or self.trusted_key.get("crv") != "Ed25519" or not self.trusted_key.get("kid"):
                raise ValueError()
            Ed25519PublicKey.from_public_bytes(verifier.decode(self.trusted_key["x"]))
            return hashlib.sha256(canonical(self.trusted_key)).hexdigest()
        except Exception:
            raise BuyerError("trusted_public_key_required") from None

    def _state(self, *, capability=True):
        pin = self._trust()
        state = self.journal.load()
        if state.get("origin") != self.origin or state.get("trusted_key_sha256") != pin:
            raise BuyerError("custody_identity_mismatch")
        if state.get("expected_build_sha") != self.expected_build_sha:
            raise BuyerError("custody_build_expectation_changed")
        if capability:
            prepared = state.get("prepared", {})
            if (not ORDER.fullmatch(str(prepared.get("id", "")))
                    or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", str(prepared.get("access_token", "")))):
                raise BuyerError("order_capability_required")
        return state

    def _request(self, method, path, body=None, headers=None, *, accepted=(200,)):
        try:
            response = self.transport(method, path, body, headers or {})
            if response.status not in accepted or not isinstance(response.body, dict):
                raise BuyerError("api_request_rejected")
            return response
        except BuyerError:
            raise
        except Exception:
            raise BuyerError("transport_failed") from None

    def _headers(self, state):
        return {"Authorization": "Bearer " + state["prepared"]["access_token"]}

    def _path(self, state, suffix=""):
        return "/api/receipts/orders/" + state["prepared"]["id"] + suffix

    def _status(self, state):
        value = self._request("GET", self._path(state), headers=self._headers(state)).body
        prepared = state["prepared"]
        if (value.get("id") != prepared["id"] or value.get("scope") != prepared["scope"]
                or value.get("price") != prepared["price"]):
            raise BuyerError("order_binding_changed")
        return value

    @staticmethod
    def _unsubmitted(state):
        if state.get("payment_attempt"):
            raise BuyerError("payment_reconciliation_required")

    def _offer(self, state):
        discovery = self._request("GET", "/.well-known/noticer.json").body
        offer = discovery.get("buyer_offer", {})
        mode = discovery.get("mpp", {}).get("mode")
        price = discovery.get("price", {})
        if (discovery.get("issuer") != self.origin or offer.get("enabled") is not True
                or type(offer.get("free_checks")) is not int or offer["free_checks"] != 10
                or type(price.get("amount")) is not int or price["amount"] != 100 or price.get("currency") != "usd"
                or mode not in ("test", "live") or state.get("payment_mode", mode) != mode):
            raise BuyerError("buyer_offer_changed")
        return mode

    def _challenge_terms(self, state, header, merchant, network):
        fields = payment_fields(header)
        try:
            terms = json.loads(verifier.decode(fields["opaque"]))
            expected = {"order": state["prepared"]["id"], "amount": 100, "currency": "usd",
                        "livemode": state["payment_mode"] == "live", "merchant_account": merchant,
                        "networkId": network, "obligation_hash": state["prepared"]["scope"]["obligation_hash"]}
            request = {k: v for k, v in expected.items() if k in ("order", "amount", "currency", "livemode", "networkId")}
            requested = json.loads(verifier.decode(fields["request"]))
            if (set(fields) != {"id", "realm", "method", "intent", "request", "expires", "opaque"}
                    or not merchant or not network or fields.get("realm") != "noticer-receipts"
                    or fields.get("method") != "stripe" or fields.get("intent") != "charge"
                    or not re.fullmatch(r"[0-9a-f]{64}", fields.get("id", ""))
                    or set(terms) != set(expected) | {"expires_at", "package_sha256"}
                    or any(type(terms.get(k)) is not type(v) or terms.get(k) != v for k, v in expected.items())
                    or canonical(requested) != canonical(request)
                    or type(terms.get("expires_at")) is not int or terms["expires_at"] <= time.time()
                    or fields.get("expires") != str(terms["expires_at"])
                    or not re.fullmatch(r"[0-9a-f]{64}", str(terms.get("package_sha256", "")))):
                raise ValueError()
            return terms
        except Exception:
            raise BuyerError("payment_challenge_binding_rejected") from None

    @staticmethod
    def _summary(state, value):
        result = {"order_id": state["prepared"]["id"], "action_performed": False,
                  "payment_mode": state["payment_mode"]}
        allowed = {"status": {"prepared", "observing", "observation_stalled", "evidence_ready"},
                   "payment_state": {"unpaid", "paid", "refunded", "disputed"},
                   "verdict": {None, "PROVED", "DISPROVED", "INCONCLUSIVE"}}
        for field, choices in allowed.items():
            if field in value and value[field] in choices:
                result[field] = value[field]
        for name in ("price", "amount_due"):
            terms = value.get(name)
            if isinstance(terms, dict) and type(terms.get("amount")) is int and terms.get("currency") == "usd":
                result[name] = {"amount": terms["amount"], "currency": "usd"}
        result["obligation_hash"] = state["prepared"]["scope"]["obligation_hash"]
        return result

    def prepare(self, scope, tenant_key):
        with self.journal.locked():
            pin = self._trust()
            if not isinstance(tenant_key, str) or not tenant_key or any(ord(c) < 33 for c in tenant_key):
                raise BuyerError("buyer_credential_required")
            buyer_pin = hashlib.sha256(tenant_key.encode()).hexdigest()
            if self.journal.path.exists():
                state = self._state(capability=False)
                if state.get("request_scope") != scope or state.get("buyer_sha256") != buyer_pin:
                    raise BuyerError("saved_intent_mismatch")
                if "prepared" in state:
                    self._state()
                    return self._summary(state, self._status(state))
            else:
                state = {"schema": AAD.decode(), "origin": self.origin, "trusted_key_sha256": pin,
                         "expected_build_sha": self.expected_build_sha, "buyer_sha256": buyer_pin,
                         "request_scope": scope, "idempotency_key": secrets.token_hex(32)}
                self.journal.save(state)  # Intent is durable BEFORE the first request.
            state["payment_mode"] = self._offer(state)
            self.journal.save(state)
            prepared = self._request("POST", "/api/receipts/orders", scope,
                                     {"Authorization": "Bearer " + tenant_key, "Idempotency-Key": state["idempotency_key"]},
                                     accepted=(201,)).body
            frozen = prepared.get("scope", {})
            expected = {"core_contract": "noticer.core@1.0.0", "claim_ref": scope["claim_ref"],
                        "claim_type": "automation_step", "required_outcome": scope["questioned"]["extract"],
                        "observer": "commerce_public_json_v1", "questioned": scope["questioned"],
                        "control": scope["control"], "deadline_seconds": scope["deadline_seconds"],
                        "policy": {"on_disproved": "BLOCK", "on_inconclusive": "BLOCK"}}
            expected["obligation_hash"] = "sha256:" + hashlib.sha256(canonical(expected)).hexdigest()
            if (frozen != expected or not ORDER.fullmatch(str(prepared.get("id", "")))
                    or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", str(prepared.get("access_token", "")))
                    or type(prepared.get("price", {}).get("amount")) is not int
                    or prepared["price"] != {"amount": 100, "currency": "usd"}):
                raise BuyerError("prepared_scope_rejected")
            state["prepared"] = {name: prepared[name] for name in ("id", "access_token", "scope", "price")}
            self._status(state)  # A rederived token must actually authorize this order.
            self.journal.save(state)
            return self._summary(state, prepared)

    def confirm(self, obligation_hash):
        with self.journal.locked():
            state = self._state()
            self._unsubmitted(state)
            if obligation_hash != state["prepared"]["scope"]["obligation_hash"]:
                raise BuyerError("explicit_scope_confirmation_required")
            self.journal.save(state)
            result = self._request("POST", self._path(state, "/run"), {"confirmed": True}, self._headers(state), accepted=(200, 202)).body
            if (result.get("id") != state["prepared"]["id"] or result.get("status") != "accepted"
                    or not re.fullmatch(r"ob_[0-9a-f]{32}", str(result.get("check_id", "")))):
                raise BuyerError("run_response_binding_rejected")
            state["confirmed"] = True
            self.journal.save(state)
            return {"check_id": result.get("check_id"), "action_performed": False}

    def status(self):
        with self.journal.locked():
            state = self._state()
            value = self._status(state)
            if (state.get("payment_attempt") and state.get("payment_mode") == "live"
                    and value.get("payment_state") == "unpaid"):
                # This endpoint can only inspect an existing durable attempt;
                # it never consumes a new grant or creates/confirms a payment.
                self._request("GET", self._path(state, "/mpp"), headers=self._headers(state),
                              accepted=(200, 409, 503))
                value = self._status(state)
            return self._summary(state, value)

    def challenge(self, merchant, network):
        with self.journal.locked():
            state = self._state()
            self._unsubmitted(state)
            value = self._status(state)
            if value.get("status") != "evidence_ready" or value.get("amount_due") != state["prepared"]["price"] or value.get("payment_state") != "unpaid":
                raise BuyerError("payment_not_required_or_not_ready")
            response = self._request("POST", self._path(state, "/mpp"), {}, self._headers(state), accepted=(402,))
            header = next((v for k, v in response.headers.items() if k.lower() == "www-authenticate"), "")
            terms = self._challenge_terms(state, header, merchant, network)
            state["challenge_header"], state["challenge_terms"] = header, terms
            self.journal.save(state)
            return {"amount": terms["amount"], "currency": terms["currency"], "payment_mode": state["payment_mode"], "action_performed": False}

    def export_challenge(self, destination):
        """Private issuer handoff contains only the frozen public payment challenge."""
        with self.journal.locked():
            state = self._state()
            self._unsubmitted(state)
            terms = state.get("challenge_terms", {})
            header = state.get("challenge_header", "")
            self._challenge_terms(state, header, terms.get("merchant_account"), terms.get("networkId"))
            target = Path(destination)
            if target.is_symlink():
                raise BuyerError("handoff_destination_exists")
            publish_new(target, canonical({"schema": "noticer.buyer-challenge.v1", "origin": self.origin,
                                           "challenge": header}) + b"\n")
            return {"challenge_exported": True, "action_performed": False}

    def pay_mpp(self, authorization, *, amount, currency):
        with self.journal.locked():
            state = self._state()
            self._unsubmitted(state)
            if type(amount) is not int or {"amount": amount, "currency": currency} != state["prepared"]["price"]:
                raise BuyerError("explicit_price_confirmation_required")
            terms = state.get("challenge_terms", {})
            header = state.get("challenge_header", "")
            if self._challenge_terms(state, header, terms.get("merchant_account"), terms.get("networkId")) != terms:
                raise BuyerError("payment_challenge_binding_rejected")
            challenge = payment_fields(header)
            supplied = payment_fields(authorization)
            if ({k: v for k, v in supplied.items() if k != "credential"} != challenge or not supplied.get("credential")):
                raise BuyerError("payment_credential_binding_rejected")
            self._offer(state)
            value = self._status(state)  # Verify saved capability before any payment.
            if value.get("amount_due") != {"amount": amount, "currency": currency} or value.get("payment_state") != "unpaid":
                raise BuyerError("payment_not_required_or_not_ready")
            state["payment_attempt"] = {"method": "mpp", "state": "submitted_or_unknown"}
            self.journal.save(state)  # No retry is permitted after this durable marker.
            headers = {"Authorization": authorization}
            if state["payment_mode"] == "live":
                headers["X-Noticer-Order-Token"] = state["prepared"]["access_token"]
            self._request("POST", self._path(state, "/mpp"), {}, headers)
            return self._summary(state, self._status(state))

    def retrieve(self, decision_ref, *, output=None):
        with self.journal.locked():
            state = self._state()
            response = self._request("GET", self._path(state, "/evidence"), headers=self._headers(state))
            package, raw = response.body, response.raw
            if not isinstance(raw, bytes) or json.loads(raw) != package:
                raise BuyerError("raw_evidence_required")
            capture = {"sha256": hashlib.sha256(raw).hexdigest(), "raw_base64": base64.b64encode(raw).decode()}
            captures = state.setdefault("retrievals", [])
            if len(captures) < 2:
                captures.append(capture)
            self.journal.save(state)  # Preserve original bytes even if verification fails.
            if captures[0]["sha256"] != capture["sha256"]:
                raise BuyerError("retrieved_bytes_changed")
            if package.get("payload", {}).get("order_id") != state["prepared"]["id"]:
                raise BuyerError("receipt_order_mismatch")
            if state.get("payment_attempt") and hashlib.sha256(canonical(package)).hexdigest() != state["challenge_terms"]["package_sha256"]:
                raise BuyerError("paid_package_binding_rejected")
            scope = state["prepared"]["scope"]
            decision, code = verifier.evaluate_gate(package, self.trusted_key, self.origin,
                scope["claim_ref"], scope["required_outcome"], verifier.DEFAULT_MAX_AGE_SECONDS,
                scope, decision_ref, expected_build_sha=self.expected_build_sha)
            if code == verifier.GATE_EXIT_REJECTED:
                raise BuyerError("receipt_rejected")
            state["package"], state["verification"] = package, decision
            self.journal.save(state)
            if output is not None:
                if decision.get("signature_valid") is not True or decision.get("evidence_valid") is not True:
                    raise BuyerError("receipt_rejected")
                # Export the verified response, never the journal or reserialized JSON.
                # Valid BLOCK/HOLD receipts remain exportable without granting ALLOW.
                try:
                    publish_new(output, raw)
                except BuyerError:
                    raise BuyerError("receipt_export_failed") from None
            return decision


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--journal", type=Path, required=True)
    parser.add_argument("--custody-key-file", type=Path, required=True, help="Existing base64 32-byte key; transfer separately from encrypted journal")
    parser.add_argument("--origin", required=True)
    parser.add_argument("--trusted-key", type=Path, required=True, help="Separately trusted public JWK, never fetched automatically")
    parser.add_argument("--expected-build-sha")
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--scope", type=Path, required=True)
    prepare.add_argument("--tenant-key-file", type=Path, required=True)
    confirm = commands.add_parser("run")
    confirm.add_argument("--confirm-obligation-hash", required=True)
    commands.add_parser("status")
    handoff = commands.add_parser("handoff")
    handoff.add_argument("--output", type=Path, required=True)
    challenge = commands.add_parser("challenge")
    challenge.add_argument("--merchant", required=True)
    challenge.add_argument("--network", required=True)
    challenge_export = commands.add_parser("export-challenge")
    challenge_export.add_argument("--output", type=Path, required=True)
    pay = commands.add_parser("pay-mpp")
    pay.add_argument("--payment-file", type=Path, required=True)
    pay.add_argument("--confirm-amount", type=int, required=True)
    pay.add_argument("--confirm-currency", required=True)
    evidence = commands.add_parser("evidence")
    evidence.add_argument("--decision-ref", required=True)
    evidence.add_argument("--output", type=Path, help="New private plaintext receipt file; exact verified bytes, never overwritten")
    args = parser.parse_args(argv)
    try:
        key = base64.b64decode(args.custody_key_file.read_bytes().strip(), validate=True)
        journey = BuyerJourney(EncryptedJournal(args.journal, key), args.origin,
                               json.loads(args.trusted_key.read_bytes()), expected_build_sha=args.expected_build_sha)
        if args.command == "prepare":
            result = journey.prepare(json.loads(args.scope.read_bytes()), args.tenant_key_file.read_text().strip())
        elif args.command == "run":
            result = journey.confirm(args.confirm_obligation_hash)
        elif args.command == "status":
            result = journey.status()
        elif args.command == "handoff":
            journey.journal.handoff(args.output)
            result = {"custody_exported": True, "action_performed": False}
        elif args.command == "challenge":
            result = journey.challenge(args.merchant, args.network)
        elif args.command == "pay-mpp":
            result = journey.pay_mpp(args.payment_file.read_text().strip(), amount=args.confirm_amount, currency=args.confirm_currency)
        elif args.command == "export-challenge":
            result = journey.export_challenge(args.output)
        else:
            verified = journey.retrieve(args.decision_ref, output=args.output)
            result = {key: verified[key] for key in ("decision", "reason_code", "verdict", "signature_valid", "evidence_valid", "action_performed")}
            if args.output is not None:
                result["receipt_exported"] = True
        print(json.dumps(result, sort_keys=True))
        if args.command == "evidence":
            return {"continue": 0, "block": verifier.GATE_EXIT_BLOCK, "hold": verifier.GATE_EXIT_HOLD}[result["decision"]]
        return 0
    except Exception as error:
        # Never echo server errors, request headers, paths or exception contents.
        code = str(error) if isinstance(error, BuyerError) and re.fullmatch(r"[a-z_]{1,64}", str(error)) else "buyer_operation_failed"
        print(json.dumps({"error": code, "action_performed": False}, sort_keys=True))
        return verifier.GATE_EXIT_REJECTED


if __name__ == "__main__":
    raise SystemExit(main())
