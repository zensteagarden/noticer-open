# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Local-only candidate adapter for Noticer's commercial receipt protocol.

Not released or configured. The authenticated account schema is unavailable; balance remains unknown.
Preparation and observation never initiate payment; receipt retrieval requires
the exact documented free-grant fields after finalization.
The preserved buyer kit owns custody, idempotency and receipt verification.
"""
from __future__ import annotations

import base64
from copy import deepcopy
from functools import wraps
import hashlib
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import stat
import sys
import threading
import time
from typing import Any
from urllib.parse import unquote, urlsplit

from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.types import ToolAnnotations
from vendor.scripts import buyer_journey as buyer

ORIGIN = "https://noticer-mpp-ee54698-production.up.railway.app"
LABEL = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}\Z")
ORDER_PATH = r"/api/receipts/orders/ord_[0-9a-f]{32}"
PUBLIC_PATHS = {"/.well-known/noticer.json", "/.well-known/agent.json", "/api/receipts/docs"}
SAFE_ERRORS = {
    "account_read_failed", "buyer_offer_changed",
    "receipt_entitlement_unverified", "no_spend_terms_confirmation_required",
    "saved_offer_policy_changed", "invalid_scope",
    "explicit_scope_confirmation_required", "explicit_read_authorization_required",
    "invalid_check_label", "poll_too_soon", "payment_not_supported", "receipt_not_ready",
    "payment_required", "reobservation_required", "safe_protocol_route_required",
    "receipt_rejected", "retrieved_bytes_changed", "receipt_order_mismatch",
    "paid_package_binding_rejected", "raw_evidence_required", "receipt_export_failed",
    "order_binding_changed", "prepared_scope_rejected", "run_response_binding_rejected",
    "custody_identity_mismatch", "custody_build_expectation_changed", "custody_unavailable",
    "custody_write_failed", "custody_directory_required", "custody_lock_unavailable",
    "custody_storage_unavailable", "order_capability_required", "saved_intent_mismatch",
    "trusted_public_key_required", "buyer_credential_required", "api_request_rejected",
    "transport_failed", "payment_reconciliation_required", "redirect_refused",
    "response_too_large", "decision_ref_invalid", "invalid_configuration",
}


def fail(code):
    raise buyer.BuyerError(code)


def tool_safe(fn):
    """Only allowlisted local failure codes cross the MCP boundary."""
    @wraps(fn)
    def wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as error:
            code = str(error) if isinstance(error, buyer.BuyerError) else "operation_failed"
            if code not in SAFE_ERRORS:
                code = "operation_failed"
            raise ToolError(code) from None
    return wrapped


class NoPaymentTransport:
    """Defense in depth: the vendored payment methods cannot reach the network."""
    def __init__(self, transport, clock=time.monotonic):
        self.transport, self.clock = transport, clock
        self.last_status = {}
        self.lock = threading.Lock()

    def __call__(self, method, path, body=None, headers=None):
        allowed = (
            method == "GET" and (path in PUBLIC_PATHS or path == "/api/receipts/account"
                or re.fullmatch(ORDER_PATH + r"(?:/evidence)?", path))
            or method == "POST" and (path == "/api/receipts/orders"
                or re.fullmatch(ORDER_PATH + r"/run", path))
        )
        if not allowed:
            fail("safe_protocol_route_required")
        if method == "GET" and re.fullmatch(ORDER_PATH, path):
            with self.lock:
                now = self.clock()
                if now - self.last_status.get(path, -float("inf")) < 3:
                    fail("poll_too_soon")
                self.last_status[path] = now
        return self.transport(method, path, body, headers or {})


def validate_scope(scope):
    """Cheap preflight only. The existing server remains the canonical parser."""
    try:
        if not isinstance(scope, dict) or set(scope) != {"claim_ref", "questioned", "control", "deadline_seconds", "authorized_public_read"}:
            raise ValueError()
        if scope["authorized_public_read"] is not True:
            fail("explicit_read_authorization_required")
        if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", scope["claim_ref"]):
            raise ValueError()
        if type(scope["deadline_seconds"]) is not int or not 20 <= scope["deadline_seconds"] <= 120:
            raise ValueError()
        q, c = scope["questioned"], scope["control"]
        if set(q) != {"url", "extract", "claim_id_path"} or set(c) != {"url", "extract"}:
            raise ValueError()
        hosts = []
        for record in (q, c):
            url = record["url"]
            parts = urlsplit(url)
            if (len(url) > 1024 or not url.isascii() or any(ord(x) < 33 for x in url)
                or parts.scheme != "https" or not parts.hostname or parts.username or parts.password
                or parts.query or parts.fragment or parts.port not in (None, 443)
                or parts.hostname in {"localhost", "localhost.localdomain"}
                or parts.hostname.endswith((".local", ".localhost", ".internal"))
                or "." not in parts.hostname or not parts.path or "\\" in url):
                raise ValueError()
            try:
                address = ipaddress.ip_address(parts.hostname)
            except ValueError:
                address = None
            if address is not None and not address.is_global:
                raise ValueError()
            hosts.append(parts.netloc)
            path, literal = record["extract"].split(" == ", 1)
            if not re.fullmatch(r"\$\.[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", path):
                raise ValueError()
            parsed = json.loads(literal)
            if not isinstance(parsed, (str, bool, int, float)) and parsed is not None:
                raise ValueError()
            if len(record["extract"]) > 240 or buyer.canonical(parsed).decode() != literal:
                raise ValueError()
        if hosts[0] != hosts[1] or q["url"] == c["url"] or hosts[0] == urlsplit(ORIGIN).netloc:
            raise ValueError()
        ref = scope["claim_ref"]
        if ref not in unquote(urlsplit(q["url"]).path).split("/") or ref in unquote(urlsplit(c["url"]).path).split("/"):
            raise ValueError()
        if not re.fullmatch(r"\$\.[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*", q["claim_id_path"]):
            raise ValueError()
    except buyer.BuyerError:
        raise
    except Exception:
        fail("invalid_scope")


class CommercialJourney(buyer.BuyerJourney):
    def _offer(self, state):
        """Narrow compatibility patch; no payment-engine changes."""
        discovery = self._request("GET", "/.well-known/noticer.json").body
        offer = discovery.get("buyer_offer", {})
        mode = discovery.get("mpp", {}).get("mode")
        price = discovery.get("price", {})
        if (discovery.get("issuer") != self.origin or offer.get("enabled") is not True
            or type(offer.get("free_checks")) is not int or offer["free_checks"] != 5
            or offer.get("free_checks_applies_to") != "new_buyers"
            or type(offer.get("existing_buyer_free_checks")) is not int or offer["existing_buyer_free_checks"] != 10
            or offer.get("anonymous_trial_available") is not False
            or offer.get("assignment") != "first_eligible_package_finalization"
            or offer.get("inconclusive_consumes_allowance") is not False
            or type(price.get("amount")) is not int or price["amount"] != 100 or price.get("currency") != "usd"
            or mode not in {"test", "live"} or state.get("payment_mode", mode) != mode):
            fail("buyer_offer_changed")
        # Public terms are recorded without guessing which tenant cohort applies.
        # Actual free eligibility is established only by the finalized order response.
        policy = {"public_new_buyer_limit": 5, "public_existing_buyer_limit": 10,
            "tenant_eligibility": "unknown", "price": {"amount": 100, "currency": "usd"},
            "payment_mode": mode, "assignment": "first_eligible_package_finalization"}
        if state.get("commercial_policy", policy) != policy:
            fail("saved_offer_policy_changed")
        state["commercial_policy"] = policy
        return mode

    @staticmethod
    def _summary(state, value):
        result = buyer.BuyerJourney._summary(state, value)
        result["verdict_verified"] = False
        for name in ("evidence_available", "reobserve_required", "payment_available"):
            if type(value.get(name)) is bool:
                result[name] = value[name]
        entitlement = value.get("entitlement", {})
        if isinstance(entitlement, dict) and entitlement.get("decision") in {"pending", "legacy", "trial_free", "inconclusive_free", "payment_required"}:
            result["entitlement"] = {"decision": entitlement["decision"]}
        # Never equate a status verdict, payment, or malformed/missing field with
        # retrievability. Only the documented unpaid free-grant combination qualifies.
        grant = result.get("entitlement", {}).get("decision")
        free_grant = ((grant == "trial_free" and result.get("verdict") in {"PROVED", "DISPROVED"})
            or (grant == "inconclusive_free" and result.get("verdict") == "INCONCLUSIVE"))
        result["free_receipt_retrievable"] = bool(
            result.get("status") == "evidence_ready" and free_grant
            and result.get("amount_due") == {"amount": 0, "currency": "usd"}
            and result.get("evidence_available") is True
            and result.get("reobserve_required") is False
            and result.get("payment_state") == "unpaid")
        result["payment_supported_by_adapter"] = False
        result["next_step"] = "get_status"
        if result.get("reobserve_required") is True:
            result["next_step"] = "request_new_scope_confirmation"
        elif result.get("status") == "prepared":
            result["next_step"] = "show_frozen_scope_and_request_confirmation"
        elif result.get("status") == "evidence_ready":
            if result["free_receipt_retrievable"]:
                result["next_step"] = "retrieve_and_verify_receipt"
            elif (grant == "payment_required" and result.get("amount_due") == {"amount": 100, "currency": "usd"}
                and result.get("payment_state") == "unpaid" and result.get("evidence_available") is False
                and result.get("reobserve_required") is False):
                result["next_step"] = "ask_operator_about_one_order_payment"
                result["payment_required"] = True
            else:
                result["next_step"] = "resolve_unverified_order_entitlement"

        return result


class Adapter:
    def __init__(self, directory, custody_key, tenant_key, trusted_key, *, transport=None, expected_build_sha=None, clock=time.monotonic):
        self.directory = Path(directory)
        self.custody_key, self.tenant_key, self.trusted_key = custody_key, tenant_key, trusted_key
        self.expected_build_sha, self.clock = expected_build_sha, clock
        self.transport = NoPaymentTransport(transport or buyer.HttpTransport(ORIGIN), clock)
        self.last_poll = {}

    def _get(self, path, authenticated=False):
        try:
            response = self.transport("GET", path, headers={"Authorization": "Bearer " + self.tenant_key} if authenticated else {})
            if response.status != 200 or not isinstance(response.body, dict):
                fail("account_read_failed" if authenticated else "api_request_rejected")
            return response.body
        except buyer.BuyerError:
            raise
        except Exception:
            fail("transport_failed")

    def setup(self):
        offer = self._get("/.well-known/noticer.json")
        if offer.get("issuer") != ORIGIN or offer.get("schema") != "noticer.purchase/1.0":
            fail("buyer_offer_changed")
        # Display only fixed known terms after exact validation; never remote prose/URLs.
        terms = offer.get("price", {})
        if terms.get("amount") != 100 or type(terms.get("amount")) is not int or terms.get("currency") != "usd":
            fail("buyer_offer_changed")
        return {"adapter_status": "local_no_spend_candidate_not_live_proven", "origin": ORIGIN,
            "docs_url": ORIGIN + "/api/receipts/docs", "start_url": ORIGIN + "/start",
            "price": {"amount": 100, "currency": "usd"},
            "payments_available": offer.get("payments_available") is True,
            "payment_supported_by_adapter": False, "account_contract_verified": False,
            "remaining_free_checks": None, "next_step": "prepare_explicitly_authorized_public_scope", "action_performed": False}

    def account(self):
        self._get("/api/receipts/account", authenticated=True)
        return {"account_authenticated": True, "account_contract_verified": False,
            "remaining_free_checks": None, "next_step": "obtain_account_response_schema_from_operator",
            "action_performed": False}

    def journey(self, label):
        if not isinstance(label, str) or not LABEL.fullmatch(label):
            fail("invalid_check_label")
        return CommercialJourney(buyer.EncryptedJournal(self.directory / (label + ".vault"), self.custody_key),
            ORIGIN, self.trusted_key, transport=self.transport, expected_build_sha=self.expected_build_sha)

    def prepare(self, label, scope):
        validate_scope(scope)
        journey = self.journey(label)
        result = journey.prepare(scope, self.tenant_key)
        with journey.journal.locked():
            state = journey._state()
            result["frozen_scope"] = deepcopy(state["prepared"]["scope"])
        result["confirmation_required"] = True
        result["allowance_reserved"] = False
        result["remaining_free_checks"] = None
        result["confirmation_notice"] = (
            "Approve this exact frozen public-read scope and known-good control. Running may consume "
            "one free check if eligible; no free allowance is reserved or guaranteed. Evidence may require "
            "separate USD 1 approval. This adapter makes no payment and will not retrieve a paid package.")
        return result

    def run(self, label, obligation_hash, confirmed, no_spend_terms_confirmed=False):
        if confirmed is not True:
            fail("explicit_scope_confirmation_required")
        if no_spend_terms_confirmed is not True:
            fail("no_spend_terms_confirmation_required")
        return self.journey(label).confirm(obligation_hash)

    def status(self, label):
        journey = self.journey(label)
        now = self.clock()
        if now - self.last_poll.get(label, -float("inf")) < 3:
            fail("poll_too_soon")
        self.last_poll[label] = now
        return journey.status()

    def receipt(self, label, decision_ref):
        if not buyer.verifier._DECISION_REF.fullmatch(decision_ref):
            fail("decision_ref_invalid")
        journey = self.journey(label)
        status = self.status(label)
        if status.get("reobserve_required"):
            fail("reobservation_required")
        if status.get("status") != "evidence_ready":
            fail("receipt_not_ready")
        if not status.get("free_receipt_retrievable"):
            fail("payment_required" if status.get("payment_required") else "receipt_entitlement_unverified")
        # Exact evidence bytes stay in encrypted custody. Only verified metadata exits MCP.
        decision = journey.retrieve(decision_ref)
        if decision.get("verdict") != status.get("verdict"):
            fail("receipt_entitlement_unverified")
        grant = status.get("entitlement", {}).get("decision")
        if not ((grant == "trial_free" and decision.get("verdict") in {"PROVED", "DISPROVED"})
            or (grant == "inconclusive_free" and decision.get("verdict") == "INCONCLUSIVE")):
            fail("receipt_entitlement_unverified")
        keep = {"schema", "policy", "decision", "reason_code", "verdict", "signature_valid", "evidence_valid",
            "action_performed", "decision_output_binding", "decision_ref_binding", "obligation_hash", "receipt_hash", "observed_at"}
        result = {key: value for key, value in decision.items() if key in keep}
        result["exit_code"] = {"continue": 0, "block": 20, "hold": 21}[decision["decision"]]
        result["receipt_retained_privately"] = True
        return result


def make_server(adapter):
    server = FastMCP("Noticer Commercial Receipt Candidate", log_level="CRITICAL", instructions=(
        "Local candidate, not the published owner API connector. Never ask for keys in a tool or chat. "
        "Account balance and cohort are unknown. Show the exact frozen scope, known-good control, observation window and price, "
        "then obtain explicit user approval before run, including that it may consume a free check and may produce "
        "evidence requiring separate USD 1 approval. Both confirmation booleans are caller assertions, never proof of consent. "
        "No tool accepts payment authority or charges money. Status verdicts are unverified; only receipt verification "
        "can emit an unsigned local continue decision. Never execute a downstream action. Poll at most once per 3 seconds."))
    read = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
    mutate = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)

    @server.tool(annotations=read)
    @tool_safe
    def noticer_commercial_setup() -> dict[str, Any]:
        """Read public commercial availability; never creates an order or a payment."""
        return adapter.setup()

    @server.tool(annotations=read)
    @tool_safe
    def noticer_commercial_account() -> dict[str, Any]:
        """Read account using the private tenant key; unknown balance stays unknown."""
        return adapter.account()

    @server.tool(annotations=mutate)
    @tool_safe
    def noticer_prepare_receipt(check_label: str, scope: dict[str, Any]) -> dict[str, Any]:
        """Prepare a no-spend check only after public-read scope authorization.

        Reuse check_label with the exact same scope after interruption. Show returned frozen_scope,
        price, confirmation_notice and allowance_reserved=false, then ask for explicit approval. Never start a new label
        to recover an ambiguous preparation. No observation or payment occurs here.
        """
        return adapter.prepare(check_label, scope)

    @server.tool(annotations=mutate)
    @tool_safe
    def noticer_run_receipt(check_label: str, obligation_hash: str, confirmed: bool, no_spend_terms_confirmed: bool) -> dict[str, Any]:
        """After approval of scope AND confirmation_notice, start that saved order without payment.

        Explain that run may consume a free check and evidence may require separate USD 1 approval;
        no payment will be made. Both booleans must reflect explicit user approval, not inference.
        Caller assertions are not independent evidence of consent.
        """
        return adapter.run(check_label, obligation_hash, confirmed, no_spend_terms_confirmed)

    @server.tool(annotations=read)
    @tool_safe
    def noticer_receipt_status(check_label: str) -> dict[str, Any]:
        """Read existing order, at most every 3 seconds. Any displayed verdict is unverified."""
        return adapter.status(check_label)

    @server.tool(annotations=mutate)
    @tool_safe
    def noticer_get_verified_receipt(check_label: str, decision_ref: str) -> dict[str, Any]:
        """Retrieve and independently verify receipt against the separately trusted key and saved scope.

        Raw evidence remains encrypted locally. Stale, tampered or untrusted receipts fail.
        Valid DISPROVED returns block/20; INCONCLUSIVE hold/21; only fresh PROVED/ALLOW continue/0.
        The decision is unsigned and caller-local. This tool never performs its downstream action.
        """
        return adapter.receipt(check_label, decision_ref)

    return server


def private_read(filename):
    path = Path(filename)
    if not path.is_absolute() or path.is_symlink():
        fail("invalid_configuration")
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_mode & 0o077 or info.st_size > 65536:
        fail("invalid_configuration")
    return path.read_bytes()


def load_adapter(filename):
    if os.name != "posix":
        fail("invalid_configuration")
    config = json.loads(private_read(filename))
    if config.get("origin") != ORIGIN:
        fail("invalid_configuration")
    directory = Path(config["private_directory"])
    if not directory.is_absolute() or directory.is_symlink() or not directory.is_dir() or directory.stat().st_mode & 0o077:
        fail("invalid_configuration")
    tenant = private_read(config["tenant_key_file"]).decode().strip()
    if not re.fullmatch(r"[\x21-\x7e]{32,1024}", tenant):
        fail("invalid_configuration")
    key = base64.b64decode(private_read(config["custody_key_file"]).strip(), validate=True)
    trusted = json.loads(private_read(config["trusted_public_key_file"]))
    if len(key) != 32:
        fail("invalid_configuration")
    return Adapter(directory, key, tenant, trusted, expected_build_sha=config.get("expected_build_sha"))


def main():
    # Disable logging: MCP errors carry only fixed local codes, never upstream bodies.
    logging.disable(logging.CRITICAL)
    try:
        filename = os.environ["NOTICER_COMMERCIAL_CONFIG_FILE"]
        adapter = load_adapter(filename)
    except Exception:
        print("Noticer commercial configuration missing or invalid.", file=sys.stderr)
        return 2
    make_server(adapter).run(transport="stdio")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
