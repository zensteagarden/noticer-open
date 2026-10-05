# Noticer plugin contract

Status: experimental, tied to packet schema 0.1.

Noticer the trunk is `noticer-public-verifier` in this repository. A plugin is a packet producer for one use case. It is not a second verifier.

## What a plugin may do

- Ask the person what they are trying to have happen.
- Capture disclosed bytes the person chooses to export.
- Write a schema 0.1 directory packet, or a bundle that `unpack` turns into one.
- Name itself in `manifest.extensions`.
- Tell the person to run this repository's `src/cli.mjs verify` on that directory.

## What a plugin must not do

- Invent `ALLOW`, `DENY`, `INCONCLUSIVE`, `PROVED`, or `DISPROVED`.
- Import or reimplement `src/verify.mjs` as its own verdict.
- Put a verdict in the packet. `adjudication` and `verdict` stay unset.
- Put anything in `obligations`. Nonempty obligations cannot pass.
- Treat confirmation, a click, or a capture as authorization to act.
- Claim the capture proves who wrote the page, that the page still says it, or that an external write happened.
- Add a top-level packet entry other than `manifest.json`, `blobs/`, `attestations/`, and an inert `README.md`.
- Zip the packet and call that verification. This trunk verifies directories only.

## Required producer statement

Every plugin README states:

1. plugin id
2. the observable proxy (`artifact.text.exact.v1` until a new public policy exists)
3. what that proxy does not establish
4. the unpack command
5. the trunk command that actually verdicts

## Adding a use case

Copy `plugins/chrome-page-capture/` or write a new directory with the same shape: a producer, an unpack step if the host cannot write a directory, a fixture that should ALLOW, a fixture that should DENY on exact-text while still ALLOW on integrity, and a test that calls this repo's `verifyPacket`. MCP and HTTP adapters are the same contract. They are not separate trunks.

Apache-2.0. Same NOTICE as the trunk.
