# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Offline no-spend sales contract tests; fake wallet settlement is not live proof."""
import asyncio
import hashlib
import json
import time
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from test_candidate import FakeService, TENANT, CAPABILITY, ORDER, BUILD, scope, b64
import sales_mcp as s

TOKEN = 'ns_' + 'S' * 43
class SalesService(FakeService):
    def __init__(self):
        super().__init__()
        self.enroll_calls = []
        self.paid = False
    def __call__(self, method, path, body=None, headers=None):
        if path == '/api/receipts/enroll':
            self.enroll_calls.append((body, headers))
            value = dict(access_token=TOKEN, buyer_id='self_'+'1'*32, scope='commerce_only', identity_verified=False,
                free_checks=5, terms_version=s.TERMS_VERSION, price_after_trial={'amount':100,'currency':'usd'})
            return s.buyer.Response(201, value, {}, s.buyer.canonical(value))
        if path == '/api/receipts/account':
            value = dict(scope='commerce_only',identity_verified=False,free_checks=5,used=2,remaining=3,
                terms_version=s.TERMS_VERSION,price_after_trial={'amount':100,'currency':'usd'})
            return s.buyer.Response(200,value,{},s.buyer.canonical(value))
        if path.endswith('/mpp'):
            assert headers == {'Authorization':'Bearer '+CAPABILITY}
            assert method == 'POST' and body == {}
            terms = dict(order=ORDER,amount=100,currency='usd',livemode=True,merchant_account='acct_fixture',
                networkId='network_fixture', obligation_hash=self.scope['obligation_hash'],expires_at=int(time.time())+60,
                package_sha256=hashlib.sha256(s.buyer.canonical(self.package)).hexdigest())
            request = {k: terms[k] for k in ('order','amount','currency','livemode','networkId')}
            fields = dict(id='a'*64,realm='noticer-receipts',method='stripe',intent='charge',request=b64(s.buyer.canonical(request)),
                expires=str(terms['expires_at']),opaque=b64(s.buyer.canonical(terms)))
            header = 'Payment '+', '.join(k+'="'+v+'"' for k,v in fields.items())
            return s.buyer.Response(402, {}, {'WWW-Authenticate':header},b'{}')
        response = super().__call__(method,path,body,headers)
        if path == '/api/receipts/orders/'+ORDER and self.paid:
            response.body.update(payment_state='paid',amount_due={'amount':0,'currency':'usd'},evidence_available=True)
        return response

class SalesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.service = SalesService(); self.now = 100
        self.adapter = s.SalesAdapter(self.temp.name,b'c'*32,TENANT,self.service.key,
            transport=self.service,clock=lambda:self.now,expected_build_sha=BUILD)
        self.block = patch('socket.socket.connect',side_effect=AssertionError('Network forbidden'))
        self.block.start();self.addCleanup(self.block.stop)
    def ready(self):
        result=self.adapter.prepare('check',scope());self.now+=3
        self.adapter.run('check',result['obligation_hash'],True,True)
        self.service.sign();self.service.amount=100;self.service.available=False
    def test_enroll_custody_and_replay_no_secret_output(self):
        result=self.adapter.enroll(True,True,True)
        self.assertNotIn(TOKEN,json.dumps(result))
        self.assertNotIn(TOKEN.encode(),(Path(self.temp.name)/'enrollment.vault').read_bytes())
        self.adapter.enroll(True,True,True)
        self.assertEqual(len(self.service.enroll_calls),1)
        self.assertEqual(self.adapter.account()['remaining_free_checks'],3)
    def test_enroll_requires_explicit_consent(self):
        with self.assertRaisesRegex(s.buyer.BuyerError,'enrollment_confirmation_required'):
            self.adapter.enroll(True,False,True)
        self.assertEqual(self.service.enroll_calls,[])
    def test_external_paid_verified_twice_private_capability(self):
        self.ready()
        result=self.adapter.challenge('check','acct_fixture','network_fixture',100,'usd',True)
        self.assertNotIn(CAPABILITY,json.dumps(result));self.assertEqual(result['payment_submission_supported'],self.adapter.wallet is not None)
        self.service.paid=True;self.now+=3
        verified=self.adapter.receipt('check','next-action')
        self.assertTrue(verified['retrieved_twice_identical']);self.assertEqual(verified['decision'],'continue')
        self.assertEqual(sum(x[1].endswith('/evidence') for x in self.service.calls),2)
    def test_unexpected_paid_never_creates_challenge_or_charge(self):
        self.ready();self.service.paid=True
        with self.assertRaisesRegex(s.buyer.BuyerError,'payment_challenge_required'):
            self.adapter.receipt('check','next-action')
        self.assertFalse(any(x[1].endswith('/mpp') for x in self.service.calls))
    def test_raw_payment_credential_transport_rejected(self):
        with self.assertRaisesRegex(s.buyer.BuyerError,'safe_protocol_route_required'):
            self.adapter.transport('POST','/api/receipts/orders/'+ORDER+'/mpp',{}, {'Authorization':'Payment credential="secret"'})
    def test_paid_package_hash_changed_rejected(self):
        self.ready();self.adapter.challenge('check','acct_fixture','network_fixture',100,'usd',True)
        self.service.package['extra']='changed';self.service.paid=True;self.now+=3
        with self.assertRaisesRegex(s.buyer.BuyerError,'paid_package_binding_rejected'):
            self.adapter.receipt('check','next-action')
    def test_mcp_tools_no_payment_credentials(self):
        tools=asyncio.run(s.make_server(self.adapter).list_tools())
        self.assertEqual(len(tools),9)
        schemas=json.dumps([x.inputSchema for x in tools])
        for value in ('access_token','authorization','spt','tenant_key'):
            self.assertNotIn(value,schemas)
        for tool in tools:
            self.assertIsNotNone(tool.annotations)

class FakeWallet:
    def __init__(self): self.creates=[]; self.status='pending_approval'
    def value(self):
        return {'id':'lsrq_fixture','status':self.status,'approval_url':'https://app.link.com/approve/fixture',
            'shared_payment_token':{'id':'spt_FIXTURE_SECRET'}}
    def create(self, network, idem): self.creates.append((network,idem));return self.value()
    def retrieve(self, request_id, network): return self.value()
    def public_status(self, value):
        from link_wallet import LinkWallet
        return LinkWallet.public_status(value)

class WalletService(SalesService):
    def __init__(self): super().__init__();self.submissions=0;self.ambiguous=False
    def __call__(self, method,path,body=None,headers=None):
        if path.endswith('/mpp') and headers.get('Authorization','').startswith('Payment '):
            assert headers['X-Noticer-Order-Token']==CAPABILITY
            assert headers['Authorization'].endswith(', credential="spt_FIXTURE_SECRET"')
            self.submissions+=1
            if self.ambiguous: raise TimeoutError('spt_FIXTURE_SECRET')
            self.paid=True
            return s.buyer.Response(200,{'paid':True},{},b'{"paid":true}')
        return super().__call__(method,path,body,headers)

class WalletTests(SalesTests):
    def setUp(self):
        super().setUp();self.service=WalletService();self.wallet=FakeWallet()
        self.adapter=s.SalesAdapter(self.temp.name,b'c'*32,TENANT,self.service.key,
            transport=self.service,clock=lambda:self.now,expected_build_sha=BUILD,wallet=self.wallet)
    def test_wallet_pending_then_approved_once(self):
        self.ready();self.adapter.challenge('check','acct_fixture','network_fixture',100,'usd',True)
        pending=self.adapter.wallet_payment('check',100,'usd',True)
        self.assertEqual(pending['wallet_status'],'pending_approval');self.assertEqual(self.service.submissions,0)
        self.wallet.status='approved'
        paid=self.adapter.wallet_payment('check',100,'usd',True)
        self.assertEqual(paid['payment_state'],'paid');self.assertEqual(self.service.submissions,1)
        self.assertNotIn('spt_FIXTURE_SECRET',json.dumps(paid))
        with self.assertRaisesRegex(s.buyer.BuyerError,'payment_reconciliation_required'):
            self.adapter.wallet_payment('check',100,'usd',True)
        self.assertEqual(len(self.wallet.creates),1)
    def test_wallet_uncertain_no_resubmit_or_reauthorize(self):
        self.ready();self.adapter.challenge('check','acct_fixture','network_fixture',100,'usd',True)
        self.adapter.wallet_payment('check',100,'usd',True);self.wallet.status='approved';self.service.ambiguous=True
        with self.assertRaisesRegex(s.buyer.BuyerError,'transport_failed'):
            self.adapter.wallet_payment('check',100,'usd',True)
        with self.assertRaisesRegex(s.buyer.BuyerError,'payment_reconciliation_required'):
            self.adapter.wallet_payment('check',100,'usd',True)
        self.assertEqual(self.service.submissions,1);self.assertEqual(len(self.wallet.creates),1)
    def test_wallet_decline_stops(self):
        self.ready();self.adapter.challenge('check','acct_fixture','network_fixture',100,'usd',True)
        self.wallet.status='declined';self.adapter.wallet_payment('check',100,'usd',True)
        with self.assertRaisesRegex(s.buyer.BuyerError,'wallet_closed'):
            self.adapter.wallet_payment('check',100,'usd',True)
        self.assertEqual(self.service.submissions,0)
    def test_cli_argv_contains_no_credential_and_streams_private(self):
        import subprocess
        import sys
        from link_wallet import LinkWallet
        calls=[]
        def runner(args,**kwargs):
            calls.append((args,kwargs))
            return subprocess.CompletedProcess(args,0,json.dumps(dict(id='lsrq_fixture',credential_type='shared_payment_token',
                network_id='network_fixture',amount=100,currency='usd',status='approved',shared_payment_token={'id':'spt_PRIVATE'})).encode(),b'PRIVATE_STDERR')
        cli=object.__new__(LinkWallet)  # Command-buffer unit test; path policy tested separately.
        cli.executable='/fixture/trusted-link-cli';cli.runner=runner
        value=cli.retrieve('lsrq_fixture','network_fixture')
        self.assertEqual(value['shared_payment_token']['id'],'spt_PRIVATE')
        self.assertNotIn('spt_PRIVATE',json.dumps(calls[0][0]))
        self.assertFalse(calls[0][1]['shell']);self.assertEqual(calls[0][1]['stdout'],subprocess.PIPE)

class StandardWalletService(WalletService):
    def __call__(self,method,path,body=None,headers=None):
        from datetime import datetime,timezone
        headers=headers or {}
        if path.endswith('/mpp') and headers.get('Authorization','').startswith('Payment '):
            envelope=json.loads(s.buyer.verifier.decode(headers['Authorization'][8:]))
            assert envelope['payload']=={'spt':'spt_FIXTURE_SECRET'}
            assert headers['X-Noticer-Order-Token']==CAPABILITY
            assert envelope['challenge']==self.expected_fields
            self.submissions+=1;self.paid=True
            return s.buyer.Response(200,{'paid':True},{},b'{"paid":true}')
        response=super().__call__(method,path,body,headers)
        if path.endswith('/mpp'):
            fields=s.buyer.payment_fields(response.headers['WWW-Authenticate'])
            terms=json.loads(s.buyer.verifier.decode(fields['opaque']));terms['wire_schema']='noticer.mpp-stripe-charge.v1'
            request={'amount':'100','currency':'usd','externalId':ORDER,'methodDetails':{'networkId':'network_fixture','paymentMethodTypes':['card']}}
            fields.update(id='a'*43,request=b64(s.buyer.canonical(request)),opaque=b64(s.buyer.canonical(terms)),
                expires=datetime.fromtimestamp(terms['expires_at'],timezone.utc).isoformat(timespec='milliseconds').replace('+00:00','Z'))
            self.expected_fields=fields
            response.headers['WWW-Authenticate']='Payment '+', '.join(k+'="'+v+'"' for k,v in fields.items())
        return response

class StandardTests(WalletTests):
    def setUp(self):
        super().setUp();self.service=StandardWalletService()
        self.adapter=s.SalesAdapter(self.temp.name,b'c'*32,TENANT,self.service.key,
            transport=self.service,clock=lambda:self.now,expected_build_sha=BUILD,wallet=self.wallet)
    def test_standard_wallet_roundtrip_receipt_twice(self):
        self.ready();self.adapter.challenge('check','acct_fixture','network_fixture',100,'usd',True)
        self.adapter.wallet_payment('check',100,'usd',True);self.wallet.status='approved'
        result=self.adapter.wallet_payment('check',100,'usd',True)
        self.assertEqual(result['payment_state'],'paid');self.now+=3
        verified=self.adapter.receipt('check','release')
        self.assertTrue(verified['retrieved_twice_identical']);self.assertEqual(verified['decision'],'continue')
    def test_wallet_uncertain_no_resubmit_or_reauthorize(self):
        # Covered against original wire; standard engine likewise writes marker first.
        self.ready();self.adapter.challenge('check','acct_fixture','network_fixture',100,'usd',True)
        self.adapter.wallet_payment('check',100,'usd',True);self.wallet.status='approved'
        underlying=self.adapter.transport.transport
        def ambiguous(method,path,body=None,headers=None):
            if path.endswith('/mpp') and headers.get('Authorization','').startswith('Payment '):
                self.service.submissions+=1;raise TimeoutError('spt_FIXTURE_SECRET')
            return underlying(method,path,body,headers)
        self.adapter.transport.transport=ambiguous
        with self.assertRaisesRegex(s.buyer.BuyerError,'transport_failed'):
            self.adapter.wallet_payment('check',100,'usd',True)
        with self.assertRaisesRegex(s.buyer.BuyerError,'payment_reconciliation_required'):
            self.adapter.wallet_payment('check',100,'usd',True)
        self.assertEqual(self.service.submissions,1)

class WalletHardeningTests(WalletTests):
    def test_ambiguous_create_is_not_repeated(self):
        self.ready();self.adapter.challenge('check','acct_fixture','network_fixture',100,'usd',True)
        attempts=[]
        def ambiguous(network,idem):
            attempts.append(idem)
            raise s.buyer.BuyerError('wallet_operation_failed')
        self.wallet.create=ambiguous
        with self.assertRaisesRegex(s.buyer.BuyerError,'wallet_operation_failed'):
            self.adapter.wallet_payment('check',100,'usd',True)
        with self.assertRaisesRegex(s.buyer.BuyerError,'wallet_retry_requires_reconciliation'):
            self.adapter.wallet_payment('check',100,'usd',True)
        self.assertEqual(len(attempts),1);self.assertEqual(self.service.submissions,0)
    def test_symlink_cli_refused(self):
        import sys
        from link_wallet import LinkWallet
        target=Path(self.temp.name)/'link-cli';target.symlink_to(Path(sys.executable).resolve())
        with self.assertRaisesRegex(s.buyer.BuyerError,'wallet_configuration_required'):
            LinkWallet(str(target))
    def test_world_writable_cli_refused(self):
        from link_wallet import LinkWallet
        target=Path(self.temp.name)/'link-cli';target.write_text('#!/bin/false\n');target.chmod(0o777)
        with self.assertRaisesRegex(s.buyer.BuyerError,'wallet_configuration_required'):
            LinkWallet(str(target))

class RecoveryTests(WalletTests):
    def test_ambiguous_post_recovers_saved_attempt_read_only(self):
        self.ready();self.adapter.challenge('check','acct_fixture','network_fixture',100,'usd',True)
        self.adapter.wallet_payment('check',100,'usd',True);self.wallet.status='approved';self.service.ambiguous=True
        with self.assertRaisesRegex(s.buyer.BuyerError,'transport_failed'):
            self.adapter.wallet_payment('check',100,'usd',True)
        underlying=self.adapter.transport.transport;recoveries=[]
        def recovery(method,path,body=None,headers=None):
            if method=='GET' and path.endswith('/mpp'):
                assert headers=={'Authorization':'Bearer '+CAPABILITY}
                recoveries.append(path);self.service.paid=True
                return s.buyer.Response(200,{'paid':True,'provider_ref':'PRIVATE_PROVIDER_REF'},{},b'{}')
            return underlying(method,path,body,headers)
        self.adapter.transport.transport=recovery;self.now+=3
        result=self.adapter.status('check')
        self.assertTrue(result['existing_payment_recovery_checked'])
        self.assertNotIn('PRIVATE_PROVIDER_REF',json.dumps(result))
        self.now+=3;settled=self.adapter.status('check')
        self.assertEqual(settled['payment_state'],'paid')
        self.assertEqual(len(recoveries),1);self.assertEqual(self.service.submissions,1);self.assertEqual(len(self.wallet.creates),1)
