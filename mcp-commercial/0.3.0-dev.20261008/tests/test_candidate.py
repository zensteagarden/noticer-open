# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Offline fixtures only. No real keys, orders, payments, or source observations.

The production Adapter runs against an in-memory protocol fixture.
All socket connections are rejected, including SDK protocol tests.
"""
import asyncio
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from mcp.server.fastmcp.exceptions import ToolError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import commercial_mcp as m

TENANT = "fixture_tenant_" + "T" * 40
CAPABILITY = "F" * 64
ORDER = "ord_" + "1" * 32
CHECK = "ob_" + "2" * 32
BUILD = "fixture-build-20261008"
PRIVATE_MARKER = "PRIVATE_EVIDENCE_DO_NOT_RETURN"

def b64(raw):
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")

def scope():
    return {"claim_ref": "record-123", "questioned": {"url": "https://example.com/records/record-123", "extract": '$.status == "active"', "claim_id_path": "$.id"},
        "control": {"url": "https://example.com/records/control", "extract": '$.status == "active"'},
        "deadline_seconds": 60, "authorized_public_read": True}

def frozen(request):
    value = {"core_contract": "noticer.core@1.0.0", "claim_ref": request["claim_ref"], "claim_type": "automation_step",
        "required_outcome": request["questioned"]["extract"], "observer": "commerce_public_json_v1",
        "questioned": deepcopy(request["questioned"]), "control": deepcopy(request["control"]),
        "deadline_seconds": request["deadline_seconds"], "policy": {"on_disproved": "BLOCK", "on_inconclusive": "BLOCK"}}
    value["obligation_hash"] = "sha256:" + hashlib.sha256(m.buyer.canonical(value)).hexdigest()
    return value

class FakeService:
    def __init__(self):
        self.calls = []
        self.scope = frozen(scope())
        self.stage = "prepared"
        self.verdict = "PROVED"
        self.amount = 0
        self.available = True
        self.reobserve = False
        self.drop_prepare = False
        self.drop_run = False
        self.package = None
        self.status_overrides = {}
        self.offer = {"schema": "noticer.purchase/1.0", "issuer": m.ORIGIN, "payments_available": False,
            "price": {"amount": 100, "currency": "usd"}, "mpp": {"mode": "live"},
            "buyer_offer": {"enabled": True, "free_checks": 5, "existing_buyer_free_checks": 10,
                "free_checks_applies_to": "new_buyers", "anonymous_trial_available": False,
                "assignment": "first_eligible_package_finalization", "inconclusive_consumes_allowance": False}}
        self.private = Ed25519PrivateKey.from_private_bytes(bytes(range(32)))
        self.key = {"kty": "OKP", "crv": "Ed25519", "kid": "fixture-only", "x": b64(self.private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))}

    def sign(self, verdict="PROVED", age=0):
        observed = (datetime.now(timezone.utc) - timedelta(seconds=age)).isoformat()
        receipt = deepcopy(self.scope)
        receipt.update(observed_at=observed, verdict=verdict, gate="ALLOW" if verdict == "PROVED" else "BLOCK", core_integrity_valid=True)
        for side in ("questioned", "control"):
            result = (verdict == "PROVED") if side == "questioned" else True
            if verdict == "INCONCLUSIVE":
                result = None
            receipt[side].update(predicate_result=result, observed_at=observed, http_status=200)
            if result is not None:
                raw = json.dumps({"id": "record-123" if side == "questioned" else "control", "status": "active" if result else "inactive", "private": PRIVATE_MARKER}).encode()
                receipt[side].update(response_body_base64=base64.b64encode(raw).decode(), evidence_hash="sha256:" + hashlib.sha256(raw).hexdigest())
        receipt["receipt_hash"] = "sha256:" + hashlib.sha256(m.buyer.verifier.canonical(receipt, ascii=True)).hexdigest()
        payload = {"schema": "noticer.evidence-package/1.0", "issuer": m.ORIGIN, "order_id": ORDER,
            "build_sha": BUILD, "observed_at": observed, "receipt": receipt}
        raw = m.buyer.canonical(payload)
        self.package = {"payload": payload, "payload_base64": b64(raw), "signature": {"alg": "Ed25519", "key_id": "fixture-only", "value": b64(self.private.sign(raw))}}
        self.verdict = verdict
        self.stage = "evidence_ready"
        return self.package

    def __call__(self, method, path, body=None, headers=None):
        headers = headers or {}
        self.calls.append((method, path, deepcopy(body), deepcopy(headers)))
        if path == "/.well-known/noticer.json":
            assert "Authorization" not in headers
            value = deepcopy(self.offer)
        elif path == "/api/receipts/account":
            assert headers["Authorization"] == "Bearer " + TENANT
            # Deliberately NOT a proposed account contract; production cannot infer balance.
            value = {"unknown_server_fields": True, "access_token": CAPABILITY, "private": PRIVATE_MARKER}
        elif path == "/api/receipts/orders":
            assert headers["Authorization"] == "Bearer " + TENANT
            assert len(headers["Idempotency-Key"]) == 64
            self.scope = frozen(body)
            if self.drop_prepare:
                self.drop_prepare = False
                raise TimeoutError(TENANT + CAPABILITY + PRIVATE_MARKER)
            value = {"id": ORDER, "access_token": CAPABILITY, "scope": deepcopy(self.scope), "price": {"amount": 100, "currency": "usd"}, "status": "prepared"}
            return m.buyer.Response(201, value, {}, m.buyer.canonical(value))
        else:
            assert headers["Authorization"] == "Bearer " + CAPABILITY
            assert path.startswith("/api/receipts/orders/" + ORDER)
            if path.endswith("/run"):
                assert method == "POST" and body == {"confirmed": True}
                self.stage = "observing"
                if self.drop_run:
                    self.drop_run = False
                    raise TimeoutError(CAPABILITY)
                value = {"id": ORDER, "check_id": CHECK, "status": "accepted"}
                return m.buyer.Response(202, value, {}, m.buyer.canonical(value))
            elif path.endswith("/evidence"):
                value = deepcopy(self.package)
            else:
                value = {"id": ORDER, "scope": deepcopy(self.scope), "price": {"amount": 100, "currency": "usd"},
                    "status": self.stage, "verdict": self.verdict if self.stage == "evidence_ready" else None,
                    "amount_due": {"amount": self.amount, "currency": "usd"}, "payment_state": "unpaid",
                    "evidence_available": self.available and self.stage == "evidence_ready", "reobserve_required": self.reobserve,
                    "payment_available": False, "entitlement": {"decision": ("inconclusive_free" if self.verdict == "INCONCLUSIVE" else "trial_free") if self.amount == 0 else "payment_required"},
                    "access_token": CAPABILITY, "private": PRIVATE_MARKER}
        if path == "/api/receipts/orders/" + ORDER:
            value.update(self.status_overrides)
            for k in list(value):
                if value[k] == "_MISSING_": del value[k]
        return m.buyer.Response(200, value, {}, m.buyer.canonical(value))

class CandidateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.service = FakeService()
        self.clock = 100.0
        self.adapter = self.make()
        for target in ("socket.socket.connect", "socket.socket.connect_ex", "socket.create_connection"):
            blocked = patch(target, side_effect=AssertionError("Network forbidden in offline tests"))
            blocked.start()
            self.addCleanup(blocked.stop)

    def make(self, cls=m.Adapter):
        return cls(self.tmp.name, b"fixture_custody_key_not_real_12345"[:32], TENANT, self.service.key,
            transport=self.service, expected_build_sha=BUILD, clock=lambda: self.clock)

    def prepare(self):
        result = self.adapter.prepare("check", scope())
        self.clock += 3
        return result

    def ready(self, verdict="PROVED", age=0):
        prepared = self.prepare()
        self.adapter.run("check", prepared["obligation_hash"], True, True)
        self.service.sign(verdict, age)

    def test_default_account_unknown_fields_never_exposed(self):
        result = self.make(m.Adapter).account()
        self.assertTrue(result["account_authenticated"])
        self.assertIsNone(result["remaining_free_checks"])
        self.assertFalse(result["account_contract_verified"])
        self.assertNotIn(PRIVATE_MARKER, json.dumps(result))
        self.assertNotIn(CAPABILITY, json.dumps(result))

    def test_unknown_account_contract_does_not_block_no_spend_prepare(self):
        result = self.prepare()
        self.assertIsNone(result["remaining_free_checks"])
        self.assertIn("separate USD 1 approval", result["confirmation_notice"])
        self.assertIn("may consume", result["confirmation_notice"])
        self.assertFalse(any(x[1] == "/api/receipts/account" for x in self.service.calls))

    def test_no_spend_terms_must_be_explicitly_confirmed(self):
        result = self.prepare()
        with self.assertRaisesRegex(m.buyer.BuyerError, "no_spend_terms_confirmation_required"):
            self.adapter.run("check", result["obligation_hash"], True, False)
        self.assertFalse(any(x[1].endswith("/run") for x in self.service.calls))

    def test_setup_public_no_credential_no_account_guess(self):
        result = self.make(m.Adapter).setup()
        self.assertFalse(result["payments_available"])
        self.assertFalse(result["payment_supported_by_adapter"])
        self.assertFalse(result["account_contract_verified"])

    def test_prepare_correct_auth_frozen_scope_and_private_custody(self):
        result = self.prepare()
        self.assertEqual(result["frozen_scope"], frozen(scope()))
        self.assertTrue(result["confirmation_required"])
        self.assertFalse(result["allowance_reserved"])
        self.assertFalse(any(x[1].endswith("/run") for x in self.service.calls))
        raw = (Path(self.tmp.name) / "check.vault").read_bytes()
        self.assertNotIn(CAPABILITY.encode(), raw)
        self.assertNotIn(TENANT.encode(), raw)
        self.assertNotIn(CAPABILITY, json.dumps(result))
        self.assertEqual((Path(self.tmp.name) / "check.vault").stat().st_mode & 0o777, 0o600)

    def test_lost_prepare_recovers_same_idempotency_after_restart(self):
        self.service.drop_prepare = True
        with self.assertRaisesRegex(m.buyer.BuyerError, "transport_failed"):
            self.adapter.prepare("check", scope())
        self.adapter = self.make()
        self.prepare()
        posts = [x for x in self.service.calls if x[:2] == ("POST", "/api/receipts/orders")]
        self.assertEqual(len(posts), 2)
        self.assertEqual(posts[0][3]["Idempotency-Key"], posts[1][3]["Idempotency-Key"])

    def test_changed_scope_cannot_reuse_label(self):
        self.prepare()
        changed = scope()
        changed["deadline_seconds"] = 30
        with self.assertRaisesRegex(m.buyer.BuyerError, "saved_intent_mismatch"):
            self.adapter.prepare("check", changed)

    def test_lost_run_reuses_order_capability(self):
        result = self.prepare()
        self.service.drop_run = True
        with self.assertRaisesRegex(m.buyer.BuyerError, "transport_failed"):
            self.adapter.run("check", result["obligation_hash"], True, True)
        again = self.adapter.run("check", result["obligation_hash"], True, True)
        self.assertEqual(again["check_id"], CHECK)
        runs = [x for x in self.service.calls if x[1].endswith("/run")]
        self.assertEqual(runs[0], runs[1])

    def test_confirmation_false_never_calls_network(self):
        self.prepare()
        before = len(self.service.calls)
        with self.assertRaisesRegex(m.buyer.BuyerError, "explicit_scope_confirmation_required"):
            self.adapter.run("check", "anything", False)
        self.assertEqual(len(self.service.calls), before)

    def test_wrong_scope_hash_never_runs(self):
        self.prepare()
        with self.assertRaisesRegex(m.buyer.BuyerError, "explicit_scope_confirmation_required"):
            self.adapter.run("check", "sha256:" + "0" * 64, True, True)
        self.assertFalse(any(x[1].endswith("/run") for x in self.service.calls))

    def test_no_buyer_cohort_inferred_from_public_five_ten_offer(self):
        result = self.prepare()
        state = self.adapter.journey("check").journal.load()
        self.assertEqual(state["commercial_policy"]["tenant_eligibility"], "unknown")
        self.assertIsNone(result["remaining_free_checks"])
        self.assertFalse(self.adapter.account()["account_contract_verified"])

    def test_offer_changes_rejected(self):
        for field, value in (("free_checks", 10), ("existing_buyer_free_checks", 20), ("free_checks_applies_to", "everyone"), ("anonymous_trial_available", True)):
            with self.subTest(field=field):
                original = deepcopy(self.service.offer)
                self.service.offer["buyer_offer"][field] = value
                with self.assertRaisesRegex(m.buyer.BuyerError, "buyer_offer_changed"):
                    self.adapter.prepare("offer_" + field, scope())
                self.service.offer = original

    def test_saved_offer_snapshot_cannot_change_during_prepare_retry(self):
        self.service.drop_prepare = True
        with self.assertRaises(m.buyer.BuyerError):
            self.adapter.prepare("check", scope())
        journey = self.adapter.journey("check")
        state = journey.journal.load(); state["commercial_policy"]["price"]["amount"] = 500
        journey.journal.save(state)
        with self.assertRaisesRegex(m.buyer.BuyerError, "saved_offer_policy_changed"):
            self.adapter.prepare("check", scope())

    def test_private_url_and_query_and_control_rejected_before_network(self):
        for url in ("https://127.0.0.1/record-123", "https://example.com/record-123?token=secret", "https://user:password@example.com/record-123"):
            bad = scope(); bad["questioned"]["url"] = url
            with self.assertRaisesRegex(m.buyer.BuyerError, "invalid_scope"):
                self.adapter.prepare("bad", bad)
        bad = scope(); bad["control"]["url"] = bad["questioned"]["url"]
        with self.assertRaises(m.buyer.BuyerError): self.adapter.prepare("bad", bad)
        self.assertEqual(self.service.calls, [])

    def test_scope_authorization_must_be_true(self):
        bad = scope(); bad["authorized_public_read"] = False
        with self.assertRaisesRegex(m.buyer.BuyerError, "explicit_read_authorization_required"):
            self.adapter.prepare("bad", bad)
        self.assertEqual(self.service.calls, [])

    def test_label_path_injection_rejected(self):
        with self.assertRaisesRegex(m.buyer.BuyerError, "invalid_check_label"):
            self.adapter.status("../../secret")
        self.assertEqual(self.service.calls, [])

    def test_status_throttled_and_verdict_unverified(self):
        self.ready()
        result = self.adapter.status("check")
        self.assertEqual(result["verdict"], "PROVED")
        self.assertFalse(result["verdict_verified"])
        with self.assertRaisesRegex(m.buyer.BuyerError, "poll_too_soon"):
            self.adapter.status("check")

    def test_prepare_internal_status_also_rate_limited(self):
        self.adapter.prepare("check", scope())
        with self.assertRaisesRegex(m.buyer.BuyerError, "poll_too_soon"):
            self.adapter.status("check")

    def test_paid_required_returns_terms_no_checkout_or_payment(self):
        self.ready(); self.service.amount = 100; self.service.available = False
        result = self.adapter.status("check")
        self.assertTrue(result["payment_required"])
        self.assertEqual(result["amount_due"], {"amount": 100, "currency": "usd"})
        self.assertEqual(result["entitlement"], {"decision": "payment_required"})
        self.assertFalse(result["payment_supported_by_adapter"])
        self.clock += 3
        with self.assertRaisesRegex(m.buyer.BuyerError, "payment_required"):
            self.adapter.receipt("check", "next-action")
        self.assertFalse(any(x[1].endswith(("/checkout", "/mpp", "/evidence")) for x in self.service.calls))

    def test_transport_refuses_all_payment_and_owner_routes(self):
        transport = m.NoPaymentTransport(self.service)
        for method, path in (("POST", "/api/receipts/orders/" + ORDER + "/checkout"), ("POST", "/api/receipts/orders/" + ORDER + "/mpp"), ("GET", "/api/receipts/orders/" + ORDER + "/mpp"), ("GET", "/v1/agent/setup"), ("GET", "https://evil.example/")):
            with self.assertRaisesRegex(m.buyer.BuyerError, "safe_protocol_route_required"):
                transport(method, path)
        self.assertEqual(self.service.calls, [])

    def test_verified_proved_twice_same_bytes_no_raw_evidence_or_secret(self):
        self.ready()
        result = self.adapter.receipt("check", "release/next-action")
        self.clock += 3
        again = self.adapter.receipt("check", "release/next-action")
        self.assertEqual(result, again)
        self.assertEqual(result["decision"], "continue")
        self.assertEqual(result["exit_code"], 0)
        self.assertTrue(result["signature_valid"] and result["evidence_valid"])
        self.assertFalse(result["action_performed"])
        output = json.dumps(result)
        for secret in (CAPABILITY, TENANT, PRIVATE_MARKER, "response_body_base64", "payload_base64"):
            self.assertNotIn(secret, output)

    def test_valid_negative_receipts_never_continue(self):
        for verdict, decision, code in (("DISPROVED", "block", 20), ("INCONCLUSIVE", "hold", 21)):
            with self.subTest(verdict=verdict):
                # Separate encrypted order labels and fake-service instance per subtest.
                self.service = FakeService(); self.adapter = self.make()
                with tempfile.TemporaryDirectory() as other:
                    self.adapter.directory = Path(other)
                    self.ready(verdict)
                    result = self.adapter.receipt("check", "next-action")
                    self.assertEqual((result["decision"], result["exit_code"]), (decision, code))
                    self.assertFalse(result["action_performed"])

    def test_stale_receipt_fails_closed(self):
        self.ready(age=3000)
        with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_rejected"):
            self.adapter.receipt("check", "next-action")

    def test_tampered_receipt_fails_closed(self):
        self.ready()
        self.service.package["payload"]["receipt"]["gate"] = "BLOCK"
        with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_rejected"):
            self.adapter.receipt("check", "next-action")

    def test_wrong_trusted_key_fails_without_accepting_package_key(self):
        self.ready()
        self.adapter.trusted_key = {**self.service.key, "kid": "not-the-trusted-key"}
        with self.assertRaisesRegex(m.buyer.BuyerError, "custody_identity_mismatch"):
            self.adapter.receipt("check", "next-action")

    def test_signed_wrong_build_fails_closed(self):
        self.ready()
        self.service.package["payload"]["build_sha"] = "wrong-build"
        raw = m.buyer.canonical(self.service.package["payload"])
        self.service.package["payload_base64"] = b64(raw)
        self.service.package["signature"]["value"] = b64(self.service.private.sign(raw))
        with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_rejected"):
            self.adapter.receipt("check", "next-action")

    def test_changed_retrieval_bytes_fails_closed(self):
        self.ready()
        self.adapter.receipt("check", "next-action")
        self.service.package["extra"] = "changed"
        self.clock += 3
        with self.assertRaisesRegex(m.buyer.BuyerError, "retrieved_bytes_changed"):
            self.adapter.receipt("check", "next-action")

    def test_stale_ungranted_requires_reobservation_never_checkout(self):
        self.ready(); self.service.reobserve = True
        with self.assertRaisesRegex(m.buyer.BuyerError, "reobservation_required"):
            self.adapter.receipt("check", "next-action")
        self.assertFalse(any(x[1].endswith("/evidence") for x in self.service.calls))

    def test_status_scope_drift_rejected(self):
        self.prepare()
        self.service.scope["deadline_seconds"] = 120
        with self.assertRaisesRegex(m.buyer.BuyerError, "order_binding_changed"):
            self.adapter.status("check")

    def test_mcp_tools_list_schemas_have_no_credential_or_payment_arguments(self):
        server = m.make_server(self.make(m.Adapter))
        tools = asyncio.run(server.list_tools())
        self.assertEqual(len(tools), 6)
        names = {x.name for x in tools}
        self.assertNotIn("noticer_pay", names)
        schemas = json.dumps([x.inputSchema for x in tools])
        for forbidden in ("tenant_key", "access_token", "payment_file", "authorization", "trusted_key"):
            self.assertNotIn(forbidden, schemas)

    def test_mcp_error_is_error_not_successful_empty_or_continue_result(self):
        server = m.make_server(self.adapter)
        bad = scope(); bad["authorized_public_read"] = False
        with self.assertRaisesRegex(ToolError, "explicit_read_authorization_required"):
            asyncio.run(server.call_tool("noticer_prepare_receipt", {"check_label": "check", "scope": bad}))

    def test_exception_never_echoes_secret_in_mcp_error(self):
        adapter = self.make(m.Adapter)
        adapter._get = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError(TENANT + CAPABILITY + PRIVATE_MARKER))
        server = m.make_server(adapter)
        with self.assertRaises(ToolError) as caught:
            asyncio.run(server.call_tool("noticer_commercial_account", {}))
        self.assertEqual(str(caught.exception), "Error executing tool noticer_commercial_account: operation_failed")

    def test_startup_missing_configuration_returns_nonzero_without_secrets(self):
        env = dict(os.environ); env.pop("NOTICER_COMMERCIAL_CONFIG_FILE", None)
        run = subprocess.run([sys.executable, str(Path(m.__file__))], env=env, capture_output=True, text=True)
        self.assertEqual(run.returncode, 2)
        self.assertEqual(run.stdout, "")
        self.assertEqual(run.stderr, "Noticer commercial configuration missing or invalid.\n")


    def test_existing_order_keeps_frozen_scope_price_without_guessing_account(self):
        result = self.prepare()
        original = self.adapter.journey("check").journal.load()["prepared"]
        self.service.offer["price"]["amount"] = 500
        again = self.adapter.prepare("check", scope())
        self.assertEqual(again["price"], {"amount": 100, "currency": "usd"})
        self.adapter.run("check", result["obligation_hash"], True, True)
        self.assertEqual(self.adapter.journey("check").journal.load()["prepared"], original)

    def test_legacy_prepared_journal_uses_original_frozen_order_unchanged(self):
        result = self.prepare()
        journey = self.adapter.journey("check")
        state = journey.journal.load(); del state["commercial_policy"]
        original = deepcopy(state["prepared"])
        journey.journal.save(state)
        self.adapter.run("check", result["obligation_hash"], True, True)
        saved = journey.journal.load()
        self.assertEqual(saved["prepared"], original)
        self.assertNotIn("commercial_policy", saved)

    def test_mcp_wire_error_flag_and_sanitized_success(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        server = m.make_server(self.make(m.Adapter))
        async def exercise():
            async with create_connected_server_and_client_session(server) as client:
                tools = await client.list_tools()
                self.assertEqual(len(tools.tools), 6)
                result = await client.call_tool("noticer_commercial_account", {})
                self.assertFalse(result.isError)
                self.assertIsNone(result.structuredContent["remaining_free_checks"])
                result = await client.call_tool("noticer_run_receipt", {"check_label": "check", "obligation_hash": "none", "confirmed": False, "no_spend_terms_confirmed": False})
                self.assertTrue(result.isError)
                text = json.dumps(result.model_dump())
                self.assertIn("explicit_scope_confirmation_required", text)
                for secret in (TENANT, CAPABILITY, PRIVATE_MARKER):
                    self.assertNotIn(secret, text)
        asyncio.run(exercise())

    def test_mcp_wire_verification_failure_is_error(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        self.ready(age=3000)
        async def exercise():
            async with create_connected_server_and_client_session(m.make_server(self.adapter)) as client:
                result = await client.call_tool("noticer_get_verified_receipt", {"check_label": "check", "decision_ref": "next-action"})
                self.assertTrue(result.isError)
                self.assertIn("receipt_rejected", json.dumps(result.model_dump()))
                self.assertIsNone(result.structuredContent)
        asyncio.run(exercise())


    def test_unrecognized_or_pending_entitlement_never_retrieves(self):
        self.ready()
        for grant in ("pending", "unrecognized", "legacy", None):
            with self.subTest(grant=grant):
                self.service.status_overrides = {"entitlement": {"decision": grant}}
                with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_entitlement_unverified"):
                    self.adapter.receipt("check", "next-action")
                self.clock += 3
        self.assertFalse(any(x[1].endswith("/evidence") for x in self.service.calls))

    def test_malformed_or_missing_reobservation_field_never_retrieves(self):
        self.ready()
        for value in ("true", "false", None, "_MISSING_", 0):
            with self.subTest(value=value):
                self.service.status_overrides = {"reobserve_required": value}
                with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_entitlement_unverified"):
                    self.adapter.receipt("check", "next-action")
                self.clock += 3
        self.assertFalse(any(x[1].endswith("/evidence") for x in self.service.calls))

    def test_contradictory_paid_entitlement_and_available_flag_never_retrieves(self):
        self.ready(); self.service.amount = 100; self.service.available = True
        with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_entitlement_unverified"):
            self.adapter.receipt("check", "next-action")
        self.assertFalse(any(x[1].endswith("/evidence") for x in self.service.calls))

    def test_paid_order_retrieval_is_outside_this_free_only_adapter(self):
        self.ready()
        self.service.status_overrides = {"payment_state": "paid", "entitlement": {"decision": "payment_required"}}
        with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_entitlement_unverified"):
            self.adapter.receipt("check", "next-action")
        self.assertFalse(any(x[1].endswith("/evidence") for x in self.service.calls))

    def test_free_grant_without_evidence_does_not_retrieve(self):
        self.ready(); self.service.available = False
        with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_entitlement_unverified"):
            self.adapter.receipt("check", "next-action")

    def test_pending_observation_does_not_retrieve(self):
        result = self.prepare()
        self.adapter.run("check", result["obligation_hash"], True, True)
        with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_not_ready"):
            self.adapter.receipt("check", "next-action")

    def test_wrong_order_binding_never_retrieves(self):
        self.ready(); self.service.status_overrides = {"id": "ord_" + "9" * 32}
        with self.assertRaisesRegex(m.buyer.BuyerError, "order_binding_changed"):
            self.adapter.receipt("check", "next-action")

    def test_invalid_zero_amount_types_never_retrieve(self):
        self.ready()
        for amount in (False, "0", None, -1):
            self.service.status_overrides = {"amount_due": {"amount": amount, "currency": "usd"}}
            with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_entitlement_unverified"):
                self.adapter.receipt("check", "next-action")
            self.clock += 3


    def test_status_inconclusive_grant_cannot_cover_signed_proved(self):
        self.ready("PROVED")
        self.service.status_overrides = {"verdict": "INCONCLUSIVE", "entitlement": {"decision": "inconclusive_free"}}
        with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_entitlement_unverified"):
            self.adapter.receipt("check", "next-action")

    def test_status_trial_grant_cannot_cover_signed_inconclusive(self):
        self.ready("INCONCLUSIVE")
        self.service.status_overrides = {"verdict": "PROVED", "entitlement": {"decision": "trial_free"}}
        with self.assertRaisesRegex(m.buyer.BuyerError, "receipt_entitlement_unverified"):
            self.adapter.receipt("check", "next-action")

    def test_mcp_wire_complete_no_spend_journey(self):
        from mcp.shared.memory import create_connected_server_and_client_session
        async def exercise():
            async with create_connected_server_and_client_session(m.make_server(self.adapter)) as client:
                prepared = await client.call_tool("noticer_prepare_receipt", {"check_label": "check", "scope": scope()})
                self.assertFalse(prepared.isError)
                data = prepared.structuredContent
                self.assertIsNone(data["remaining_free_checks"])
                self.assertIn("separate USD 1 approval", data["confirmation_notice"])
                run = await client.call_tool("noticer_run_receipt", {"check_label": "check", "obligation_hash": data["obligation_hash"], "confirmed": True, "no_spend_terms_confirmed": True})
                self.assertFalse(run.isError)
                self.service.sign("PROVED"); self.clock += 3
                receipt = await client.call_tool("noticer_get_verified_receipt", {"check_label": "check", "decision_ref": "next-action"})
                self.assertFalse(receipt.isError)
                self.assertEqual(receipt.structuredContent["decision"], "continue")
                self.assertFalse(receipt.structuredContent["action_performed"])
                for secret in (TENANT, CAPABILITY, PRIVATE_MARKER):
                    self.assertNotIn(secret, json.dumps(receipt.model_dump()))
        asyncio.run(exercise())

if __name__ == "__main__":
    unittest.main(verbosity=2)
