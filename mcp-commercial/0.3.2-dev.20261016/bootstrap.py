# Copyright 2026 John Daly
# SPDX-License-Identifier: Apache-2.0
# Commercial client release additions prepared 2026-10-08.
"""Consent-gated POSIX local setup; startup is read/write/network side-effect free."""
import base64
import json
import os
from pathlib import Path
import secrets
import shutil
import stat

from commercial_mcp import fail, ORIGIN

# Root independently matched this public signing key to the canonical HTTPS
# endpoint and prior buyer kit on 2026-10-08. Never replace from receipt/discovery.
PINNED_KEY = {
    'alg':'EdDSA','crv':'Ed25519','kid':'noticer-82e8c8f8b588173a79cd',
    'kty':'OKP','use':'sig','x':'Ns2oe26xZrRYKXs-TqOUv1W6ZUeao1GCoG2SypcN2CU',
}

def default_directory():
    # Computing a location does not create it or read its contents.
    if os.sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Noticer'
    return Path(os.environ.get('XDG_STATE_HOME') or (Path.home()/'.local'/'state')) / 'noticer'


def check_directory_chain(path, *, create):
    if not path.is_absolute() or '..' in path.parts:
        fail('local_setup_unsafe_path')
    for current in (*reversed(path.parents), path):
        if not current.exists() and not current.is_symlink():
            if not create:
                fail('local_setup_required')
            current.mkdir(mode=0o700)
        info=current.lstat()
        if stat.S_ISLNK(info.st_mode) or not stat.S_ISDIR(info.st_mode):
            fail('local_setup_unsafe_path')
        if info.st_uid not in (0,os.getuid()):
            fail('local_setup_unsafe_path')
        # Sticky system temp may be an ancestor in tests; the final state directory
        # is always current-user-only. Same-user compromise is outside this boundary.
        if info.st_mode & 0o022 and not (info.st_mode & stat.S_ISVTX and current != path):
            fail('local_setup_unsafe_path')
    info=path.stat()
    if info.st_uid != os.getuid() or info.st_mode & 0o077:
        fail('local_setup_unsafe_path')


def write_new(path, raw):
    descriptor=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY|os.O_NOFOLLOW,0o600)
    try:
        os.fchmod(descriptor,0o600)
        with os.fdopen(descriptor,'wb',closefd=False) as file:
            file.write(raw);file.flush();os.fsync(file.fileno())
    finally:
        os.close(descriptor)


class LazyAdapter:
    def __init__(self, config_file=None, *, directory=None, adapter_loader=None):
        self.config_file=Path(config_file) if config_file else None
        self.directory=Path(directory) if directory is not None else default_directory()
        self.adapter_loader=adapter_loader
        self.adapter=None

    def _load(self):
        if self.adapter is None:
            target=self.config_file or self.directory/'config.json'
            if not self.config_file:
                check_directory_chain(self.directory,create=False)
            from sales_mcp import load_adapter
            loaded=(self.adapter_loader or load_adapter)(str(target))
            if not self.config_file and loaded.trusted_key != PINNED_KEY:
                fail('custody_identity_mismatch')
            self.adapter=loaded
        return self.adapter

    def __getattr__(self, name):
        # Tool handlers remain available before configuration; invoking work before
        # setup fails closed. No file or network action is performed by lookup.
        if name.startswith('_'):
            raise AttributeError(name)
        def invoke(*args,**kwargs):
            return getattr(self._load(),name)(*args,**kwargs)
        return invoke

    def setup(self):
        return {'origin':ORIGIN,'local_setup_required':self.adapter is None,
            'next_step':'noticer_initialize_local' if self.adapter is None else 'noticer_enroll_commerce',
            'terms_url':ORIGIN+'/start','trusted_key_id':PINNED_KEY['kid'],
            'price':{'amount':100,'currency':'usd'},'native_windows_supported':False,
            'remote_request_performed':False,'local_files_created':False,'action_performed':False}

    def initialize_local(self, owner_authorized, enable_existing_link=False):
        if owner_authorized is not True:
            fail('local_setup_confirmation_required')
        if os.name != 'posix':
            fail('local_setup_posix_required')
        if self.config_file:
            adapter=self._load()
            return {'local_state_initialized':True,'existing_configuration_used':True,
                'wallet_available':adapter.wallet is not None,'remote_request_performed':False,'action_performed':False}
        check_directory_chain(self.directory,create=True)
        config_path=self.directory/'config.json'
        if config_path.exists() or config_path.is_symlink():
            adapter=self._load()
            return {'local_state_initialized':True,'existing_configuration_used':True,
                'wallet_available':adapter.wallet is not None,'remote_request_performed':False,'action_performed':False}
        # Partial/unknown setup is never overwritten or silently re-keyed.
        key_path=self.directory/'custody.key';trust_path=self.directory/'trusted-public-key.json'
        if any(path.exists() or path.is_symlink() for path in (key_path,trust_path)):
            fail('local_setup_incomplete')
        wallet=None;wallet_path=None
        if enable_existing_link:
            candidate=shutil.which('link-cli')
            if candidate:
                from link_wallet import LinkWallet
                try:
                    wallet_path=str(Path(candidate).resolve(strict=True))
                    wallet=LinkWallet(wallet_path)
                except Exception:
                    wallet_path=None
        config={'origin':ORIGIN,'private_directory':str(self.directory),
            'custody_key_file':str(key_path),'trusted_public_key_file':str(trust_path)}
        if wallet_path:config['link_cli_path']=wallet_path
        try:
            write_new(key_path,base64.b64encode(secrets.token_bytes(32))+b'\n')
            write_new(trust_path,json.dumps(PINNED_KEY,sort_keys=True).encode()+b'\n')
            write_new(config_path,json.dumps(config,sort_keys=True).encode()+b'\n')
            fd=os.open(self.directory,os.O_RDONLY|os.O_DIRECTORY)
            try:os.fsync(fd)
            finally:os.close(fd)
        except Exception:
            fail('local_setup_incomplete')
        self._load()
        return {'local_state_initialized':True,'existing_configuration_used':False,
            'wallet_available':wallet is not None,'remote_request_performed':False,
            'enrollment_performed':False,'payment_authorized':False,'action_performed':False,
            'protection':'Local files are owner-only. Keeping ciphertext and its key under the same OS user does not protect against that user being compromised.'}
