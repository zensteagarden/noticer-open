# Install Noticer Expected Result Checks 0.3.1: Linux with uv (tested)

Version 0.3.1-dev.20261008 is a published public preview: [GitHub release](https://github.com/zensteagarden/noticer-open/releases/tag/noticer-commercial-mcp-v0.3.1-dev.20261008) and [MCP Registry record](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.zensteagarden%2Fnoticer/versions/0.3.1-dev.20261008). Linux with uv is tested. macOS runtime is untested. Native Windows is unsupported. Installing dependencies downloads pinned `mcp==1.29.0` and `cryptography==50.0.0` from PyPI; only do that with the machine owner's OK.

1. Get `uv`, `curl`, `unzip`, `sha256sum` and Python 3.10+.
2. Download the MCPB, verify SHA256 `d5fb5bf62cc9682fb6f3aa3dc837cabd79a85ffe1d1a0ed8aeed70537b409183`, and unzip it into a writable directory. The exact commands are in [AGENT_GUIDE.md › Linux with uv](../AGENT_GUIDE.md).
3. Launch with `NOTICER_COMMERCIAL_CONFIG_FILE= uv run --frozen --quiet --directory <install-dir> sales_mcp.py`, or add the `mcpServers` entry from the agent guide to your MCP host. Leave the advanced config empty for guided setup. Initializing and listing the ten tools need no existing credential or config file.

Working from a source checkout instead of the MCPB? `python3 install_local.py` still creates an isolated `.venv` from the pinned wheels (`--check` verifies without installing), and `launch_local.py` starts the adapter.

4. Review and explicitly approve noticer_initialize_local. This creates owner-only local state and a random custody key using the canonical service and bundled public key pin; it performs no enrollment/network/payment. Existing advanced configuration remains optional.
5. Optionally allow discovery of an already installed trusted Link CLI. No software installation, login or wallet creation occurs. A caller-owned authorized wallet remains required for paid receipts.
6. Review /start terms and explicitly approve noticer_enroll_commerce, then read account allowance. Credentials stay encrypted in the local state directory. Keeping key and ciphertext under the same OS user does not protect against same-user compromise.
7. Prepare an authorized public JSON scope, approve its exact frozen predicate/control/window, run, and poll no more than every three seconds. Verify free receipts twice.
8. For a paid receipt, review the exact USD1 one-time challenge and separately approve the existing-Link payment tool. Present its Link approval URL; resume only the same order. Unknown create/submission is never automatically retried as a new authorization. Verify the paid receipt twice afterward.

This client doesn't host a remote MCP endpoint and doesn't change any production configuration; the release and Registry record above are already published. Do not reuse the owner API token for commerce signup, invent a payer wallet, or claim owner-independent paid onboarding is live from fixture tests.
