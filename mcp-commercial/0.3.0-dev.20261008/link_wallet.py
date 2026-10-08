# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Optional local Link CLI bridge; never install, authenticate, or log credentials.

Only used when the owner has already configured an absolute CLI path and wallet.
Commands are based on stripe/link-cli spend-request schemas (reviewed 2026-10-08).
"""
import json
import os
from pathlib import Path
import re
import subprocess
from urllib.parse import urlsplit
from commercial_mcp import fail

class LinkWallet:
    def __init__(self, executable, *, runner=None):
        path = Path(executable)
        if os.name != 'posix' or not path.is_absolute() or path.is_symlink():
            fail('wallet_configuration_required')
        path = path.resolve(strict=True)
        if not path.is_file() or not os.access(path, os.X_OK):
            fail('wallet_configuration_required')
        for entry in (path, *path.parents):
            info = entry.stat()
            if info.st_uid not in (0, os.getuid()) or info.st_mode & 0o022:
                fail('wallet_configuration_required')
        self.executable = str(path)
        self.runner = runner or subprocess.run

    def _run(self, args):
        # No shell and no credential in argv. Both streams are captured privately.
        try:
            result = self.runner([self.executable, *args, '--format', 'json'],
                stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                timeout=45, check=False, shell=False)
            if result.returncode != 0 or len(result.stdout) > 262144:
                fail('wallet_operation_failed')
            value = json.loads(result.stdout)
            if not isinstance(value, dict):
                fail('wallet_operation_failed')
            return value
        except Exception:
            fail('wallet_operation_failed')

    @staticmethod
    def checked(value, network):
        if (not re.fullmatch(r'lsrq_[A-Za-z0-9_*-]{1,200}', str(value.get('id','')))
            or value.get('credential_type') != 'shared_payment_token'
            or type(value.get('amount')) is not int or value['amount'] != 100
            or value.get('currency') != 'usd' or value.get('network_id') != network
            or value.get('status') not in {'created','pending_approval','approved','requires_action','canceled','expired','declined'}):
            fail('wallet_binding_rejected')
        return value

    def create(self, network, idempotency_key):
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,256}', network) or not re.fullmatch(r'[0-9a-f]{64}', idempotency_key):
            fail('wallet_binding_rejected')
        return self.checked(self._run(['spend-request','create','--credential-type','shared_payment_token',
            '--network-id',network,'--amount','100','--currency','usd','--idempotency-key',idempotency_key,
            '--request-approval','--context',
            'Purchase one Noticer verified evidence receipt for exactly USD 1.00 using my existing Link wallet. '
            'This is a one-time purchase for the saved order, not a subscription or permission for future charges.']), network)

    def retrieve(self, request_id, network):
        if not re.fullmatch(r'lsrq_[A-Za-z0-9_*-]{1,200}', request_id):
            fail('wallet_binding_rejected')
        value = self.checked(self._run(['spend-request','retrieve',request_id,'--include','shared_payment_token']),network)
        if value['id'] != request_id:
            fail('wallet_binding_rejected')
        return value

    @staticmethod
    def public_status(value):
        result = {'wallet_status':value['status'], 'payment_submitted':False}
        url = value.get('approval_url')
        if value['status'] == 'requires_action':
            action = value.get('status_details', {}).get('requires_action', {}).get('next_action', {})
            url = action.get('action_url') or url
            result['owner_action_required'] = True
        if url:
            if not isinstance(url, str) or len(url) > 4096:
                fail('wallet_binding_rejected')
            parsed=urlsplit(url)
            if parsed.scheme != 'https' or parsed.hostname != 'app.link.com' or parsed.username or parsed.password or parsed.port not in (None,443):
                fail('wallet_binding_rejected')
            result['approval_url']=url
        return result
