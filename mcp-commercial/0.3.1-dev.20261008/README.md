# Noticer: check the expected result before the next action

MCPB 0.4 UV commercial preview, version 0.3.1-dev.20261008. Linux and macOS/POSIX only. Windows is explicitly unsupported; macOS execution remains untested. This commercial connector is separate from the legacy operator-provisioned integration. The existing 0.1.0 owner API connector does not provide this commercial flow.

## Setup

Use an MCPB 0.4 host with UV support. The host resolves pinned mcp1.29.0 and cryptography50.0.0 dependencies; none are bundled. Fresh UV dependency resolution and runtime checks use this exact pinned dependency set; GUI host installation is a separate check.

No pre-existing config or credentials are required to connect and list tools. Leave the optional advanced configuration field empty. Initialization makes no remote call and creates no buyer state.

Ask the agent to show the setup notice, then explicitly approve `noticer_initialize_local`. On POSIX this creates an owner-only state directory with a0600 random local custody key and config. The canonical service origin and independently verified public signing key are pinned; no trust-on-first-use or key substitution from receipts/discovery occurs. Default location is XDG_STATE_HOME/noticer or ~/.local/state/noticer on Linux, and ~/Library/Application Support/Noticer on macOS. Native Windows setup is refused. A repeated setup reuses state; partial files and symlinks are never overwritten or re-keyed.

Encryption and its local key are protected by the same OS-user boundary. They do not protect against compromise of that OS user. Keep private backups separately; never paste credentials into chat.

Optionally consent to finding an already installed trusted Link CLI during local setup. This only discovers and validates its resolved executable; it never runs it, installs it, signs in, changes wallets or requests a payment. An existing authorized wallet is required before the separate payment tool can work.

Next review the service /start terms and explicitly approve commerce enrollment. Local setup is not enrollment or payment consent. Existing advanced users can still select their own private config using origin, private_directory, custody_key_file and trusted_public_key_file, with optional tenant_key_file, expected_build_sha and link_cli_path. Advanced configuration preserves its explicitly chosen trust; the default flow enforces the bundled public pin.

## Ten tools

Discovery, consent-gated local setup, enrollment, account, prepare, run, status, challenge, Link payment, and verified receipt. Scope is an explicitly authorized public HTTPS JSON predicate and a different known-good control on the same host. Confirm exact frozen scope before run. Five eligible initial checks; exact entitlement is server-controlled. Later eligible receipt access is one USD1 payment with separate owner/Link approval. Poll at most every three seconds.

Payment tools can cause a real charge when enabled and approved. SPT/capability stay private process memory and encrypted custody; returned approval URL goes to app.link.com. Denied/expired requests stop. Unknown create without an ID holds. Unknown submitted payment permits only existing-attempt read recovery, never reauthorization or resubmission. Receipt access is not evidence of success until two byte-identical packages pass pinned Ed25519/scope/package verification. No downstream action is performed.

## Verification and source scope

No real buyer enrollment, wallet grant, payment, or provider request was used for the offline acceptance tests. This is no live customer acceptance claim. Apache2.0 covers this distributed buyer connector and standalone verifier, consistent with the existing public connector and owner-approved client-only scope. LICENSE/NOTICE are retained from the public repository. Nothing here licenses or contains the private Noticer platform, engine, seller billing backend, database, customer evidence, or production keys.

## Source checkout

For source installation use INSTALL.md and install_local.py. Run the local suite with `python -m unittest discover -s tests -v`. No private server fixtures are included. Package entry is sales_mcp.py; manifest.json declares the UV stdio launch. The repository’s existing Node verifier remains separate and unchanged.

See [AGENT_GUIDE.md](AGENT_GUIDE.md) for call triggers, exact supported scope, examples, outputs and consent limits. This revision changes discovery descriptions, not verification/payment behavior or pricing.
