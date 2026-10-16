# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Synthetic no-network setup fixtures. No buyer credential or provider is created."""
import asyncio
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import sales_mcp as s
from bootstrap import LazyAdapter,PINNED_KEY
from test_sales import SalesTests

class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.directory=Path(self.tmp.name)/'state'
        self.lazy=LazyAdapter(directory=self.directory)
        block=patch('socket.socket.connect',side_effect=AssertionError('No network permitted'))
        block.start();self.addCleanup(block.stop)
    def test_initialize_and_list_are_write_free(self):
        server=s.make_server(self.lazy)
        tools=asyncio.run(server.list_tools())
        self.assertEqual(len(tools),10)
        self.assertIn('noticer_initialize_local',{x.name for x in tools})
        self.assertFalse(self.directory.exists())
        result=self.lazy.setup()
        self.assertTrue(result['local_setup_required']);self.assertFalse(result['remote_request_performed'])
        self.assertFalse(self.directory.exists())
    def test_consent_required_before_any_state_creation(self):
        with self.assertRaisesRegex(s.buyer.BuyerError,'local_setup_confirmation_required'):
            self.lazy.initialize_local(False)
        self.assertFalse(self.directory.exists())
    def test_owner_consent_local_setup_pin_permissions_and_no_enrollment(self):
        result=self.lazy.initialize_local(True)
        self.assertTrue(result['local_state_initialized']);self.assertFalse(result['enrollment_performed'])
        self.assertFalse(result['payment_authorized']);self.assertFalse(result['remote_request_performed'])
        self.assertEqual(self.directory.stat().st_mode&0o777,0o700)
        for name in ('config.json','custody.key','trusted-public-key.json'):
            self.assertEqual((self.directory/name).stat().st_mode&0o777,0o600)
        self.assertEqual(json.loads((self.directory/'trusted-public-key.json').read_text()),PINNED_KEY)
        self.assertFalse((self.directory/'enrollment.vault').exists())
        self.assertNotIn((self.directory/'custody.key').read_text().strip(),json.dumps(result))
    def test_default_public_pin_cannot_be_replaced_from_local_config(self):
        self.lazy.initialize_local(True)
        pin=self.directory/'trusted-public-key.json';changed=dict(PINNED_KEY,kid='untrusted')
        pin.write_text(json.dumps(changed))
        with self.assertRaisesRegex(s.buyer.BuyerError,'custody_identity_mismatch'):
            LazyAdapter(directory=self.directory).initialize_local(True)
    def test_repeated_setup_does_not_rekey(self):
        self.lazy.initialize_local(True);before={x.name:x.read_bytes() for x in self.directory.iterdir()}
        restarted=LazyAdapter(directory=self.directory);result=restarted.initialize_local(True)
        self.assertTrue(result['existing_configuration_used'])
        self.assertEqual(before,{x.name:x.read_bytes() for x in self.directory.iterdir()})
    def test_partial_setup_never_overwrites(self):
        self.directory.mkdir(mode=0o700);key=self.directory/'custody.key';key.write_bytes(b'keep');key.chmod(0o600)
        with self.assertRaisesRegex(s.buyer.BuyerError,'local_setup_incomplete'):
            self.lazy.initialize_local(True)
        self.assertEqual(key.read_bytes(),b'keep');self.assertFalse((self.directory/'config.json').exists())
    def test_symlink_directory_refused(self):
        target=Path(self.tmp.name)/'other';target.mkdir();self.directory.symlink_to(target,target_is_directory=True)
        with self.assertRaisesRegex(s.buyer.BuyerError,'local_setup_unsafe_path'):
            self.lazy.initialize_local(True)
        self.assertEqual(list(target.iterdir()),[])
    def test_existing_permissive_directory_refused(self):
        self.directory.mkdir(mode=0o755)
        with self.assertRaisesRegex(s.buyer.BuyerError,'local_setup_unsafe_path'):
            self.lazy.initialize_local(True)
    def test_no_link_discovery_without_explicit_option(self):
        with patch('bootstrap.shutil.which') as find:
            self.lazy.initialize_local(True)
        find.assert_not_called()
    def test_missing_optional_link_does_not_install_or_login(self):
        with patch('bootstrap.shutil.which',return_value=None) as find:
            result=self.lazy.initialize_local(True,True)
        find.assert_called_once_with('link-cli');self.assertFalse(result['wallet_available'])
    def test_windows_setup_refused(self):
        with patch('bootstrap.os.name','nt'):
            with self.assertRaisesRegex(s.buyer.BuyerError,'local_setup_posix_required'):
                self.lazy.initialize_local(True)
        self.assertFalse(self.directory.exists())
    def test_work_before_setup_fails_without_creating_state(self):
        with self.assertRaisesRegex(s.buyer.BuyerError,'local_setup_required'):
            self.lazy.account()
        self.assertFalse(self.directory.exists())
    def test_explicit_advanced_config_load_is_lazy(self):
        calls=[]
        with patch('bootstrap.default_directory',return_value=self.directory):
            adapter=LazyAdapter('/fixture/private/config.json',adapter_loader=lambda p:calls.append(p))
            s.make_server(adapter);self.assertEqual(calls,[])

class SelfServiceDiscoveryTests(SalesTests):
    def setUp(self):
        super().setUp()
        self.service.offer['buyer_offer']={
            'enabled':True,'identity':'self_service_commerce_identity','free_checks':5,
            'free_checks_applies_to':'new_self_service_identities','existing_buyer_free_checks':'preserved_by_recorded_cohort',
            'eligible_verdicts':['PROVED','DISPROVED'],'assignment':'first_eligible_package_finalization',
            'inconclusive_consumes_allowance':False,'card_required_for_free':False,'anonymous_trial_available':False,
            'enrollment':'self_service','enrollment_url':s.ORIGIN+'/api/receipts/enroll','account_url':s.ORIGIN+'/api/receipts/account'}
    def test_selfservice_shape_supported_without_balance_guess(self):
        self.service.offer['price']['unit']='one completed evidence package'
        self.assertTrue(self.adapter.prepare('new',__import__('test_candidate').scope())['confirmation_required'])
        self.assertIsNone(self.adapter.journey('new').journal.load()['commercial_policy'].get('remaining'))
    def test_selfservice_offer_drift_rejected(self):
        for field,value in [('free_checks',6),('anonymous_trial_available',True),('card_required_for_free',True),('existing_buyer_free_checks',10)]:
            old=self.service.offer['buyer_offer'][field];self.service.offer['buyer_offer'][field]=value
            with self.assertRaisesRegex(s.buyer.BuyerError,'buyer_offer_changed'):
                self.adapter.prepare('bad',__import__('test_candidate').scope())
            self.service.offer['buyer_offer'][field]=old
