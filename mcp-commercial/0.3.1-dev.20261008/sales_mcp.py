# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Commercial sales adapter with optional owner-approved, private local Link payments."""
from copy import deepcopy
import hashlib
import re
import secrets
from pathlib import Path
from typing import Any

import commercial_mcp as base
from commercial_mcp import buyer, fail, ORIGIN, ORDER_PATH
from mcp.types import ToolAnnotations

TERMS_VERSION = 'self-service-five-v1'
base.SAFE_ERRORS.update({'enrollment_confirmation_required', 'enrollment_response_rejected',
    'account_contract_rejected', 'payment_challenge_binding_rejected', 'payment_not_required_or_not_ready',
    'payment_challenge_required', 'explicit_price_confirmation_required', 'wallet_configuration_required',
    'wallet_operation_failed', 'wallet_binding_rejected', 'wallet_closed', 'wallet_retry_requires_reconciliation',
    'local_setup_unsafe_path','local_setup_required','local_setup_confirmation_required','local_setup_posix_required','local_setup_incomplete'})

class SalesTransport(base.NoPaymentTransport):
    def __call__(self, method, path, body=None, headers=None):
        headers = headers or {}
        # Challenge only: arbitrary Payment/SPT authorization is never forwarded.
        if method == 'POST' and re.fullmatch(ORDER_PATH + r'/mpp', path):
            if body != {} or set(headers) != {'Authorization'} or not re.fullmatch(r'Bearer [A-Za-z0-9_-]{32,128}', headers.get('Authorization', '')):
                fail('safe_protocol_route_required')
            return self.transport(method, path, body, headers)
        if method == 'GET' and re.fullmatch(ORDER_PATH + r'/mpp', path):
            if body is not None or set(headers) != {'Authorization'} or not re.fullmatch(r'Bearer [A-Za-z0-9_-]{32,128}', headers.get('Authorization', '')):
                fail('safe_protocol_route_required')
            return self.transport(method, path, body, headers)
        if method == 'POST' and path == '/api/receipts/enroll':
            return self.transport(method, path, body, headers)
        return super().__call__(method, path, body, headers)

class SalesJourney(base.CommercialJourney):
    def _offer(self, state):
        discovery = self._request('GET','/.well-known/noticer.json').body
        offer = discovery.get('buyer_offer', {})
        if offer.get('identity') != 'self_service_commerce_identity':
            return super()._offer(state)
        mode = discovery.get('mpp', {}).get('mode')
        price = discovery.get('price', {})
        expected = {'enabled':True,'identity':'self_service_commerce_identity','free_checks':5,
            'free_checks_applies_to':'new_self_service_identities','existing_buyer_free_checks':'preserved_by_recorded_cohort',
            'eligible_verdicts':['PROVED','DISPROVED'],'assignment':'first_eligible_package_finalization',
            'inconclusive_consumes_allowance':False,'card_required_for_free':False,'anonymous_trial_available':False,
            'enrollment':'self_service','enrollment_url':ORIGIN+'/api/receipts/enroll','account_url':ORIGIN+'/api/receipts/account'}
        if (discovery.get('issuer') != ORIGIN or any(type(offer.get(k)) is not type(v) or offer.get(k)!=v for k,v in expected.items())
            or type(price.get('amount')) is not int or price.get('amount') != 100 or price.get('currency') != 'usd'
            or mode not in ('test','live') or state.get('payment_mode',mode)!=mode):
            fail('buyer_offer_changed')
        policy = {'public_new_buyer_limit':5,'public_existing_buyer_limit':'preserved_by_recorded_cohort',
            'tenant_eligibility':'unknown','price':{'amount':100,'currency':'usd'},'payment_mode':mode,'assignment':expected['assignment'],
            'identity':'self_service_commerce_identity'}
        if state.get('commercial_policy',policy) != policy:
            fail('saved_offer_policy_changed')
        state['commercial_policy']=policy
        return mode

    def _challenge_terms(self, state, header, merchant, network):
        from datetime import datetime, timezone
        import json
        import time
        fields = buyer.payment_fields(header)
        try:
            terms = json.loads(buyer.verifier.decode(fields['opaque']))
            if 'wire_schema' not in terms:
                return super()._challenge_terms(state, header, merchant, network)
            expected = {'order': state['prepared']['id'], 'amount': 100, 'currency': 'usd',
                'livemode': state['payment_mode'] == 'live', 'merchant_account': merchant,
                'networkId': network, 'obligation_hash': state['prepared']['scope']['obligation_hash'],
                'wire_schema': 'noticer.mpp-stripe-charge.v1'}
            request = {'amount': '100', 'currency': 'usd', 'externalId': expected['order'],
                'methodDetails': {'networkId': network, 'paymentMethodTypes': ['card']}}
            if (set(fields) != {'id','realm','method','intent','request','expires','opaque'}
                or fields['realm'] != 'noticer-receipts' or fields['method'] != 'stripe' or fields['intent'] != 'charge'
                or not merchant or not network
                or set(terms) != set(expected) | {'expires_at','package_sha256'}
                or any(type(terms.get(k)) is not type(v) or terms.get(k) != v for k,v in expected.items())
                or json.loads(buyer.verifier.decode(fields['request'])) != request
                or type(terms['expires_at']) is not int or terms['expires_at'] <= time.time()
                or fields['expires'] != datetime.fromtimestamp(terms['expires_at'], timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z')
                or not re.fullmatch(r'[A-Za-z0-9_-]{43}', fields['id'])
                or not re.fullmatch(r'[0-9a-f]{64}', str(terms['package_sha256']))):
                fail('payment_challenge_binding_rejected')
            return terms
        except buyer.BuyerError:
            raise
        except Exception:
            fail('payment_challenge_binding_rejected')

    def payment_authorization(self, state, token):
        import base64
        if state['challenge_terms'].get('wire_schema'):
            envelope = {'challenge': buyer.payment_fields(state['challenge_header']), 'payload': {'spt': token}}
            return 'Payment ' + base64.urlsafe_b64encode(buyer.canonical(envelope)).decode().rstrip('=')
        return state['challenge_header'] + ', credential="' + token + '"'

    def pay_mpp(self, authorization, *, amount, currency):
        import json
        with self.journal.locked():
            state = self._state()
            if not state.get('challenge_terms', {}).get('wire_schema'):
                standard = False
            else:
                standard = True
                self._unsubmitted(state)
                if type(amount) is not int or (amount,currency) != (100,'usd'):
                    fail('explicit_price_confirmation_required')
                terms = state['challenge_terms']
                if self._challenge_terms(state,state['challenge_header'],terms['merchant_account'],terms['networkId']) != terms:
                    fail('payment_challenge_binding_rejected')
                try:
                    envelope = json.loads(buyer.verifier.decode(authorization[8:]))
                    if (not authorization.startswith('Payment ') or set(envelope) != {'challenge','payload'}
                        or envelope['challenge'] != buyer.payment_fields(state['challenge_header'])
                        or set(envelope['payload']) != {'spt'} or not envelope['payload']['spt']):
                        fail('payment_challenge_binding_rejected')
                except Exception:
                    fail('payment_challenge_binding_rejected')
                self._offer(state)
                value = self._status(state)
                if value.get('amount_due') != {'amount':100,'currency':'usd'} or value.get('payment_state') != 'unpaid':
                    fail('payment_not_required_or_not_ready')
                state['payment_attempt'] = {'method':'mpp','state':'submitted_or_unknown'}
                self.journal.save(state)
                self._request('POST', self._path(state,'/mpp'), {},
                    {'Authorization':authorization,'X-Noticer-Order-Token':state['prepared']['access_token']})
                return self._summary(state,self._status(state))
        if not standard:
            return super().pay_mpp(authorization,amount=amount,currency=currency)

    @staticmethod
    def _summary(state, value):
        result = base.CommercialJourney._summary(state, value)
        result['paid_receipt_retrievable'] = bool(result.get('status') == 'evidence_ready'
            and result.get('payment_state') == 'paid'
            and result.get('amount_due') == {'amount': 0, 'currency': 'usd'}
            and result.get('evidence_available') is True and result.get('reobserve_required') is False)
        if result['paid_receipt_retrievable']:
            result['next_step'] = 'retrieve_and_verify_receipt'
        elif result.get('payment_required'):
            result['next_step'] = 'request_exact_one_dollar_wallet_approval'
        return result

    def status(self):
        with self.journal.locked():
            state = self._state()
            value = self._status(state)
            result = self._summary(state, value)
            if state.get('payment_attempt') and state.get('payment_mode') == 'live' and value.get('payment_state') == 'unpaid':
                # Read-only recovery for the saved attempt. Never make a new
                # authorization or POST, and do not defeat status rate limiting
                # with an immediate second status read. Caller polls after 3s.
                self._request('GET', self._path(state, '/mpp'), headers=self._headers(state), accepted=(200,409,503))
                result['next_step'] = 'get_status_after_three_seconds'
                result['existing_payment_recovery_checked'] = True
            return result

    def retrieve(self, decision_ref, *, output=None):
        decision = super().retrieve(decision_ref, output=output)
        with self.journal.locked():
            state = self._state()
            terms = state.get('challenge_terms')
            if terms and hashlib.sha256(buyer.canonical(state['package'])).hexdigest() != terms['package_sha256']:
                fail('paid_package_binding_rejected')
        return decision

class SalesAdapter(base.Adapter):
    def __init__(self, *args, wallet=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.wallet = wallet
        self.transport = SalesTransport(self.transport.transport, self.clock)
        vault = buyer.EncryptedJournal(self.directory / 'enrollment.vault', self.custody_key)
        if vault.path.exists():
            with vault.locked():
                saved = vault.load()
                if saved.get('origin') != ORIGIN:
                    fail('custody_identity_mismatch')
                self.tenant_key = saved.get('access_token', self.tenant_key)

    def journey(self, label):
        original = super().journey(label)
        return SalesJourney(original.journal, ORIGIN, self.trusted_key, transport=self.transport,
            expected_build_sha=self.expected_build_sha)

    def setup(self):
        result = super().setup()
        result.update(adapter_status='unreleased_sales_candidate_not_live_proven',
            enrollment_url=ORIGIN + '/start', supported_scope='Authorized public HTTPS JSON predicate with same-host known-good control',
            wallet_required=True, wallet_bridge_available=self.wallet is not None,
            payment_submission_supported=self.wallet is not None, native_windows_supported=False)
        return result

    def prepare(self, label, scope):
        result = super().prepare(label, scope)
        result['confirmation_notice'] = (
            'Approve this exact frozen public-read scope and known-good control. Running may consume '
            'one eligible free check; no allowance is reserved. Later evidence may require separate '
            'USD 1 wallet approval. Only a separately configured existing Link wallet can submit payment. Paid receipts '
            'require the saved challenge and pinned-key verification before use.')
        return result

    def enroll(self, owner_authorized, commerce_scope_accepted, terms_accepted):
        if not all(x is True for x in (owner_authorized, commerce_scope_accepted, terms_accepted)):
            fail('enrollment_confirmation_required')
        vault = buyer.EncryptedJournal(self.directory / 'enrollment.vault', self.custody_key)
        with vault.locked():
            state = vault.load() if vault.path.exists() else {'schema': buyer.AAD.decode(), 'origin': ORIGIN, 'idempotency_key': secrets.token_urlsafe(32)}
            if state.get('origin') != ORIGIN:
                fail('custody_identity_mismatch')
            vault.save(state)  # Recover ambiguous enrollment using exactly the same private key.
            if not state.get('access_token'):
                response = self.transport('POST', '/api/receipts/enroll', {
                    'owner_authorized': True, 'commerce_scope_accepted': True, 'terms_accepted': True,
                    'terms_version': TERMS_VERSION}, {'Origin': ORIGIN, 'Idempotency-Key': state['idempotency_key']})
                value = response.body
                if (response.status not in (200, 201) or not isinstance(value, dict)
                    or not re.fullmatch(r'ns_[A-Za-z0-9_-]{43}', str(value.get('access_token', '')))
                    or not re.fullmatch(r'self_[0-9a-f]{32}', str(value.get('buyer_id', '')))
                    or value.get('scope') != 'commerce_only' or value.get('identity_verified') is not False
                    or type(value.get('free_checks')) is not int or value['free_checks'] != 5
                    or value.get('terms_version') != TERMS_VERSION
                    or value.get('price_after_trial') != {'amount': 100, 'currency': 'usd'}):
                    fail('enrollment_response_rejected')
                state.update(access_token=value['access_token'], buyer_id=value['buyer_id'])
                vault.save(state)
            self.tenant_key = state['access_token']
        return {'enrolled': True, 'credentials_retained_privately': True, 'scope': 'commerce_only',
            'identity_verified': False, 'free_checks': 5, 'terms_version': TERMS_VERSION,
            'payment_authorized': False, 'action_performed': False}

    def account(self):
        value = self._get('/api/receipts/account', authenticated=True)
        if (value.get('scope') != 'commerce_only' or value.get('identity_verified') is not False
            or value.get('terms_version') != TERMS_VERSION or type(value.get('free_checks')) is not int
            or value['free_checks'] != 5 or type(value.get('used')) is not int or value['used'] < 0
            or type(value.get('remaining')) is not int or value['remaining'] != max(0, 5-value['used'])
            or value.get('price_after_trial') != {'amount': 100, 'currency': 'usd'}):
            fail('account_contract_rejected')
        return {'account_authenticated': True, 'account_contract_verified': True,
            'remaining_free_checks': value['remaining'], 'used': value['used'], 'free_checks': 5,
            'allowance_reserved': False, 'action_performed': False}

    def challenge(self, label, merchant_account, network_id, amount, currency, confirmed):
        if confirmed is not True or type(amount) is not int or amount != 100 or currency != 'usd':
            fail('explicit_price_confirmation_required')
        journey = self.journey(label)
        summary = journey.challenge(merchant_account, network_id)
        with journey.journal.locked():
            state = journey._state()
            # _challenge_terms already checked exact realm, amount, order, network,
            # merchant, expiry, obligation and package hash. HMAC is server-verified.
            summary.update(challenge=state['challenge_header'], payment_endpoint=ORIGIN + journey._path(state, '/mpp'),
                merchant_account=merchant_account, network_id=network_id, wallet_required=True,
                wallet_bridge_available=self.wallet is not None, payment_submission_supported=self.wallet is not None,
                order_capability_retained_privately=True, payment_authorized=False)
        return summary

    def status(self, label):
        result = super().status(label)
        result['payment_supported_by_adapter'] = self.wallet is not None
        return result

    def wallet_payment(self, label, amount, currency, confirmed):
        if confirmed is not True or type(amount) is not int or amount != 100 or currency != 'usd':
            fail('explicit_price_confirmation_required')
        if self.wallet is None:
            fail('wallet_configuration_required')
        journey = self.journey(label)
        authorization = None
        with journey.journal.locked():
            state = journey._state()
            if state.get('payment_attempt'):
                fail('payment_reconciliation_required')
            terms = state.get('challenge_terms', {})
            header = state.get('challenge_header', '')
            if journey._challenge_terms(state, header, terms.get('merchant_account'), terms.get('networkId')) != terms:
                fail('payment_challenge_binding_rejected')
            if state.get('payment_mode') != 'live':
                fail('payment_not_supported')
            wallet_state = state.setdefault('wallet', {'idempotency_key': secrets.token_hex(32)})
            if wallet_state.get('closed'):
                fail('wallet_closed')
            journey.journal.save(state)  # Persist exact create intent before CLI side effect.
            if not wallet_state.get('request_id'):
                if wallet_state.get('create_attempt'):
                    fail('wallet_retry_requires_reconciliation')
                wallet_state['create_attempt'] = 'submitted_or_unknown'
                journey.journal.save(state)
                value = self.wallet.create(terms['networkId'], wallet_state['idempotency_key'])
                wallet_state['request_id'] = value['id']
            else:
                value = self.wallet.retrieve(wallet_state['request_id'], terms['networkId'])
            wallet_state['status'] = value['status']
            if value['status'] in {'canceled', 'expired', 'declined'}:
                wallet_state['closed'] = True
            journey.journal.save(state)
            public = self.wallet.public_status(value)
            if value['status'] != 'approved':
                return public
            # Credential stays in this private process buffer and is never persisted.
            token = value.get('shared_payment_token', {}).get('id', '')
            if not re.fullmatch(r'[A-Za-z0-9_*.-]{1,512}', token):
                fail('wallet_binding_rejected')
            authorization = journey.payment_authorization(state, token)
        # Only this saved, verified one-order submission bypasses the no-payment
        # tool transport. The vendored engine persists its attempt marker BEFORE
        # POST; on ambiguity it refuses any second authorization/submission.
        journey.transport = self.transport.transport
        result = journey.pay_mpp(authorization, amount=100, currency='usd')
        return {'wallet_status': 'approved', 'payment_submitted': True,
            'payment_state': result.get('payment_state'), 'action_performed': False,
            'next_step': 'retrieve_and_verify_receipt' if result.get('paid_receipt_retrievable') else 'reconcile_existing_payment'}

    def receipt(self, label, decision_ref):
        if not buyer.verifier._DECISION_REF.fullmatch(decision_ref):
            fail('decision_ref_invalid')
        journey = self.journey(label)
        status = self.status(label)
        if status.get('reobserve_required'):
            fail('reobservation_required')
        if status.get('status') != 'evidence_ready':
            fail('receipt_not_ready')
        if not (status.get('free_receipt_retrievable') or status.get('paid_receipt_retrievable')):
            fail('payment_required' if status.get('payment_required') else 'receipt_entitlement_unverified')
        if status.get('paid_receipt_retrievable'):
            with journey.journal.locked():
                if not journey._state().get('challenge_terms'):
                    fail('payment_challenge_required')
        decision = journey.retrieve(decision_ref)
        again = journey.retrieve(decision_ref)
        if decision != again or decision.get('verdict') != status.get('verdict'):
            fail('receipt_entitlement_unverified')
        keep = {'schema', 'policy', 'decision', 'reason_code', 'verdict', 'signature_valid', 'evidence_valid',
            'action_performed', 'decision_output_binding', 'decision_ref_binding', 'obligation_hash', 'receipt_hash', 'observed_at'}
        result = {k: v for k, v in decision.items() if k in keep}
        result.update(exit_code={'continue': 0, 'block': 20, 'hold': 21}[decision['decision']],
            receipt_retained_privately=True, retrieved_twice_identical=True)
        return result


def make_server(adapter):
    server = base.make_server(adapter)
    server._mcp_server.instructions = (
        'Use Noticer before the next workflow action when the owner needs to check an expected result at a public HTTPS JSON URL. It observes an explicit dotted-path equality condition with a separate same-host known-good control, then verifies the signed evidence package. The result is a verified receipt verdict plus a locally derived continue/block/hold decision, not signed permission to act. It never performs the next action. Do not use it for private/authenticated APIs, arbitrary web pages, arbitrary JSONPath/code, or proof of who caused a change. Missing, stale, rejected or inconclusive evidence never supports continuation. Start with noticer_commercial_setup; local setup and commerce enrollment require separate explicit owner consent. Prepare only an owner-authorized public-read scope, then show its frozen condition/control/window before run approval. New self-service buyers receive five eligible free checks; order entitlement is authoritative. Inconclusive packages are free. Later eligible paid receipts cost USD 1 with separate approval and an existing authorized Link wallet. Never ask for keys, tokens or payment credentials in chat/tools. Never create a replacement authorization after an uncertain payment. Status verdicts are unverified; use noticer_get_verified_receipt before relying on evidence. Poll at most once per 3 seconds.')
    mutate = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True)

    @server.tool(annotations=mutate)
    @base.tool_safe
    def noticer_enroll_commerce(owner_authorized: bool, commerce_scope_accepted: bool, terms_accepted: bool) -> dict[str, Any]:
        """Enroll once when the owner chooses commercial public-JSON checks and needs commerce-only access.
        
        First show https://noticer-mpp-ee54698-production.up.railway.app/start. Obtain host action-time approval
        for persistent commerce access and acceptance of terms before setting the consent booleans true.
        New self-service buyers receive five eligible free checks; later eligible receipts cost USD 1 with
        separate wallet approval. Enrollment itself never charges. Returns account-setup metadata while the
        credential and recovery secret remain in encrypted local custody. Booleans assert consent, not proof."""
        return adapter.enroll(owner_authorized, commerce_scope_accepted, terms_accepted)

    @server.tool(annotations=mutate)
    @base.tool_safe
    def noticer_payment_challenge(check_label: str, merchant_account: str, network_id: str,
                                  amount: int, currency: str, confirmed: bool) -> dict[str, Any]:
        """Get exact one-order payment terms only after the owner approves USD 1 for an eligible saved receipt.
        
        This prepares a public challenge, never a charge. Merchant and network must come from independently
        verified provider configuration. Returns bound challenge/endpoint metadata; order capability stays private.
        The separate optional existing-Link payment tool requires wallet approval. Never put SPTs, payment
        credentials or keys into tool arguments, chat, model output or logs."""
        return adapter.challenge(check_label, merchant_account, network_id, amount, currency, confirmed)
    @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
    @base.tool_safe
    def noticer_pay_with_existing_link(check_label: str, amount: int, currency: str, confirmed: bool) -> dict[str, Any]:
        """Pay for one eligible saved receipt only after separate exact USD 1 consent using an existing authorized Link wallet.
        
        Show the merchant, network, one-time amount and saved challenge first. Present any returned Link approval_url;
        resume only the SAME check_label/request. Both local consent and the wallet's approval are required.
        This tool can submit a real payment; approval alone is not settlement and settlement is not verified evidence.
        
        Never install software, log in, switch payment methods, or create a replacement request after denial,
        expiry or an uncertain payment. Credentials remain private subprocess memory; only sanitized status and
        approval URL are returned. After settlement, use noticer_get_verified_receipt. No downstream action runs."""
        return adapter.wallet_payment(check_label, amount, currency, confirmed)
    if getattr(type(adapter), 'initialize_local', None) is not None:
        @server.tool(annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False))
        @base.tool_safe
        def noticer_initialize_local(owner_authorized: bool, enable_existing_link: bool = False) -> dict[str, Any]:
            """Set up local private custody after the owner chooses Noticer and explicitly consents to local setup.
            
            Creates owner-only POSIX state/config and a random custody key with the canonical origin and independently
            pinned public signing key; no trust-on-first-use. Returns setup status, never secrets. Does not enroll,
            contact a server, pay, install software or sign in. Optionally discover an already installed trusted Link
            CLI only after consent. The key and encrypted records share one OS-user boundary; this does not protect
            against compromise of that same user."""
            return adapter.initialize_local(owner_authorized,enable_existing_link)
    return server


def load_adapter(filename):
    import base64
    import json
    import os
    if os.name != 'posix':
        fail('invalid_configuration')
    config = json.loads(base.private_read(filename))
    if config.get('origin') != ORIGIN:
        fail('invalid_configuration')
    directory = Path(config['private_directory'])
    if not directory.is_absolute() or directory.is_symlink() or not directory.is_dir() or directory.stat().st_mode & 0o077:
        fail('invalid_configuration')
    tenant = base.private_read(config['tenant_key_file']).decode().strip() if config.get('tenant_key_file') else ''
    if tenant and not re.fullmatch(r'[\x21-\x7e]{32,1024}', tenant):
        fail('invalid_configuration')
    key = base64.b64decode(base.private_read(config['custody_key_file']).strip(), validate=True)
    trusted = json.loads(base.private_read(config['trusted_public_key_file']))
    if len(key) != 32:
        fail('invalid_configuration')
    from link_wallet import LinkWallet
    wallet = LinkWallet(config['link_cli_path']) if config.get('link_cli_path') else None
    return SalesAdapter(directory, key, tenant, trusted, expected_build_sha=config.get('expected_build_sha'), wallet=wallet)


def main():
    import logging
    import os
    import sys
    logging.disable(logging.CRITICAL)
    try:
        from bootstrap import LazyAdapter
        adapter = LazyAdapter(os.environ.get('NOTICER_COMMERCIAL_CONFIG_FILE') or None)
    except Exception:
        print('Noticer commercial configuration missing or invalid.', file=sys.stderr)
        return 2
    make_server(adapter).run(transport='stdio')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
