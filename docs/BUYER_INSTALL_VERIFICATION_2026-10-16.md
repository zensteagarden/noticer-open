# Buyer connector installation review — 2026-10-16

Scope: current commercial buyer installation references only. No runtime, payment, release, DNS or deployment changes. Historical version directories and the separate owner connector v0.1.0 are untouched.

## Baselines inspected

- noticer-open main: `4b22cf3e82743c9a8743dee7bc8fe3747bf5dd7e`.
- noticer-public-surface branch `seo/noticer-dev-canonical-20261010`: `ac782a77e2c06889830af925bc97dd141d68a6b1`.
- Published tag: `noticer-commercial-mcp-v0.3.2-dev.20261016`, published 2026-10-16 08:14:04 UTC, prerelease=true.
- Exact asset: https://github.com/zensteagarden/noticer-open/releases/download/noticer-commercial-mcp-v0.3.2-dev.20261016/noticer-commercial-mcp-0.3.2-dev.20261016.mcpb
- Independently downloaded asset SHA256: `cc34e591327b60362923f895b710ccc43264317a01b9dfc0c1dbd3393390d7fb` (106259 bytes). Matches GitHub's asset digest and the supplied expected checksum.
- Registry GET https://registry.modelcontextprotocol.io/v0.1/servers/io.github.zensteagarden%2Fnoticer/versions/0.3.2-dev.20261016 returned HTTP 200: active, isLatest=true, version 0.3.2-dev.20261016, expected package URL/checksum, stdio transport, source subfolder and identity `io.github.zensteagarden/noticer`. Local server.json agrees. Registry metadata records liveBuyerPaymentVerified=false.
- GitHub GET /repos/zensteagarden/noticer-open/releases/latest still returns 0.3.1-dev.20261008. No release designation was changed. Explicit version links avoid that channel mismatch.

## Corrections and prevention

The current unversioned commercial AGENT_GUIDE still contained the 0.3.1 download, old digest, VER assignment, host configuration directory and release wording. These now consistently identify 0.3.2-dev.20261016. README Registry links now pin that exact record. Both shell blocks use set -eu so a failed download/checksum stops before extraction.

Host configuration uses an absolute extracted-package directory and an empty NOTICER_COMMERCIAL_CONFIG_FILE for guided setup. The guide distinguishes that directory from private state: Linux ${XDG_STATE_HOME:-$HOME/.local/state}/noticer/config.json; macOS ~/Library/Application Support/Noticer/config.json (runtime untested). bootstrap.py confirms these paths. No local initialization or private state migration was performed.

The inspected website homepage had already been corrected to 0.3.2; do not overwrite that work. tools.html still advertised 0.3.1-dev. Companion source changes update that reference and add a homepage link to installation/configuration instructions, the pinned Registry record and the checksum. Existing .well-known/mcp already matches 0.3.2. A new offline site guard is invoked by the existing PR workflow. It checks the homepage, tools page and discovery metadata together and preserves the separate owner connector link.

Repository test/buyer-install.test.mjs is automatically included in the existing node --test release check. It pins Registry metadata, checksum, README/guide download commands, fail-fast behavior, host path and server identity, and rejects old primary buyer versions or moving latest URLs. Future releases require a deliberate update of this reviewed baseline. Historical directories are outside these documentation guards.

## Verification performed

- Extracted the downloaded MCPB into a fresh writable directory; uv run --frozen used its lockfile to create an isolated environment.
- Actual JSON-RPC initialize and tools/list through the package's sales_mcp.py stdio entry point: serverInfo.name=noticer, version=0.3.2-dev.20261016, 10 tools, clean process exit. No setup, enrollment, receipt, observation or payment tool invoked.
- All 15 shipped package files byte-match the corresponding versioned source files. The MCPB does not contain MANIFEST.sha256; the downloaded archive hash and source-file comparison were used instead.
- npm run check:release: 33 passing tests on Node 24.19.0 (CI pins 24.21.0; exact CI runtime not locally reproduced).
- Existing release server identity tests: 5 passing with the extracted package's dependencies.
- New site static guard: PASS. Four temporary mutation checks fail as expected for stale tools version, stale homepage version, wrong discovery checksum and removal of the legacy v0.1.0 link.
- Existing full Caddy HTTP suite was not run locally; no routing/Caddy changes are proposed. Its workflow remains intact and the new static guard runs before it.

## Read-only live observations, separate from proposed source

On 2026-10-16, GET https://noticer.dev/ returned HTTP 200 and already named 0.3.2-dev.20261016. GET https://noticer.dev/tools returned HTTP 200 and still named 0.3.1-dev. GET https://noticer.dev/.well-known/mcp returned HTTP 200 and named 0.3.2. These observations describe the existing live surface, not deployment verification of the proposed changes. No merge, release republishing or deployment was performed.

This is an agent-run technical installation/protocol check, not an independent customer installation or a customer payment. Real customer onboarding, real buyer settlement, macOS runtime and native Windows support are not established. Existing website copy describing an owner payment test is not independently revalidated by this review. Payment behavior, pricing and approval boundaries are unchanged.
