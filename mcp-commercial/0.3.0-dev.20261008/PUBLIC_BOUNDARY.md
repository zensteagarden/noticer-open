# Proposed public distribution boundary

Public source boundary: only the client and relying-party verification gate are included under the approved Apache-2.0 scope.

This allowlisted source package contains the local buyer/MCP connector, private local custody implementation, optional caller-owned Link CLI integration, standalone signed-receipt verifier, packaging instructions, and synthetic tests. It contains no production credentials, customer records, seller database, server HMAC secret, server receipt signing private key, seller billing implementation, source observer, worker, learning/investigation system, or deployment configuration. A previously known issuer public signing key, independently rechecked at the canonical HTTPS endpoint, is bundled as the default trust pin. It is public data, not a signing secret. Advanced users may explicitly configure a different trust file.

The folder name vendor/server is historical: its sole file public_verifier.py is a standalone relying-party verifier and imports no Noticer backend code.

Excluded from the private engineering candidate: all evidence/ logs, captured discovery snapshots, PROVENANCE.json with internal paths, bytecode/cache directories, every vault or config/key file, and all private platform code. The exact publishable source candidate file list is PUBLIC_FILE_ALLOWLIST.json. Synthetic tests intentionally contain clearly labeled fake credentials and deterministic fixture signing keys; these are not production credentials.

## Licensing gate

LICENSE is retained from the public zensteagarden/noticer-open repository; NOTICE preserves its attribution and adds the commercial client scope. Apache-2.0 covers the distributed connector, packaging, buyer_journey.py and standalone public_verifier.py under the owner's explicit release authorization. It does not license or include the private Noticer platform. No production key or customer data is included.

## Installation and registry gate

This directory contains reproducible client source and tests. The separately packaged release .mcpb is the installable artifact. POSIX Python 3.10+ only; native Windows explicitly unsupported. Linux offline tests passed; macOS and WSL are not runtime-tested. Existing 0.1.0 is the operator-provisioned owner connector and must remain described that way.

The release uses semantic pre-release0.3.0-dev.20261008 for Registry/MCPB (Python source0.3.0.dev20261008), local stdio, MCPB0.4 UV with frozen dependencies, optional advanced configuration and consent-gated bootstrap, and POSIX-only metadata. Do not label this source ZIP as mcpb or point new metadata at the old owner asset. A real hosted HTTP MCP endpoint is not implemented by this adapter.
