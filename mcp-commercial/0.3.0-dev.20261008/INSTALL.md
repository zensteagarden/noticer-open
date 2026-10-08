# Local candidate installation (POSIX only)

This is a development package, not a published registry installation. Installing dependencies is a separate user-authorized operation. Native Windows is unsupported. No fresh install or dependency download was performed for this candidate.

1. Review README.md and source. Obtain Python 3.10+ on a POSIX host.
2. Run `python3 install_local.py`. This creates an isolated `.venv`, obtains pinned wheels from official PyPI, then runs checks. `python3 install_local.py --check` verifies an existing isolated environment without installing.
3. Launch the source adapter through launch_local.py, or import the MCPB into a UV-capable host. Leave NOTICER_COMMERCIAL_CONFIG_FILE / optional advanced file setting empty for guided setup. No existing credential/config file is required for initialization or tool listing.
4. Review and explicitly approve noticer_initialize_local. This creates owner-only local state and a random custody key using the canonical service and bundled public key pin; it performs no enrollment/network/payment. Existing advanced configuration remains optional.
5. Optionally allow discovery of an already installed trusted Link CLI. No software installation, login or wallet creation occurs. A caller-owned authorized wallet remains required for paid receipts.
6. Review /start terms and explicitly approve noticer_enroll_commerce, then read account allowance. Credentials stay encrypted in the local state directory. Keeping key and ciphertext under the same OS user does not protect against same-user compromise.
7. Prepare an authorized public JSON scope, approve its exact frozen predicate/control/window, run, and poll no more than every three seconds. Verify free receipts twice.
8. For a paid receipt, review the exact USD1 one-time challenge and separately approve the existing-Link payment tool. Present its Link approval URL; resume only the same order. Unknown create/submission is never automatically retried as a new authorization. Verify the paid receipt twice afterward.

No registration, remote MCP hosting, production configuration, deployment or publishing is included. Do not reuse the owner API token for commerce signup, invent a payer wallet, or claim owner-independent paid onboarding is live from fixture tests.
