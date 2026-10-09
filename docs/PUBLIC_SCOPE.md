# Public scope and known limits

This source is the Noticer Public Verifier, not the private hosted service or investigation system. It is independently useful without either.

## Separate questions

Packet structure, artifact integrity, issuer authenticity, evidence for a particular claim, authorization to act, and observation of an action's actual result are different questions. This starter checks the first four only within the limited, disclosed rules below. It provides no action authorization or live destination observer.

`packet.integrity.v1` checks the implemented packet structure, references and supplied blob hashes. `artifact.text.exact.v1` additionally requires a declared exact-text claim to match the supplied evidence bytes. When the caller also supplies `expectedText`, those bytes must match that caller value. A self-consistent packet that does not match the caller’s contract is DENY. Required failure is DENY; missing required bytes are INCONCLUSIVE; ALLOW requires the required checks to complete and pass. Optional failures remain visible without silently changing the chosen policy.

`adjudication.control.v1` is unsupported. Public PROVED and DISPROVED are disabled. A private conclusion dependent on undisclosed reasoning can only be treated as an issuer assertion, not an independently reproduced public conclusion.

The retained experimental `destination.capture.v1` evaluates supplied capture bytes and supplied time/subject context. It performs no collection, authenticates no collector, and does not prove who wrote those bytes or that they are still present. It is not the starter's default check.

## Trust and safety

A receipt's valid signature is separate from whether its issuer is trusted, whether the trust snapshot is current, and whether its enclosed verdict passed. Packet attestations are committed as inputs; their presence alone authenticates nothing. No result or exit code authorizes an external action.

There is no model or network call on the public verifier path. Directory packets are supported; ZIP import and extraction are not. Use a directory whose contents and parent directories are exclusively controlled by you during verification. Portable Node file checks are not confinement against another process changing directory ancestors.

The loader has file/byte limits and rejects selected link, encoding and parsing attacks, but full nested closed-schema coverage and comprehensive resource-exhaustion hardening are incomplete. Receipt/trust command input hardening also needs further review. Do not expose this development CLI as an unbounded public upload service.

Canonical JSON is a safe-integer subset, not full RFC 8785 conformance. Original blob bytes are not normalized. `verifier_source_digest` covers the six filenames named in the result, not the whole distribution, CLI wrapper, runtime, dependencies or operating system. Archive checksums establish artifact identity, not the truth of a signed claim or correctness of a release.

## Distribution boundary

Only the public source, disclosed formats/rules, synthetic fixtures, examples, tests and contributor documentation belong in this starter. It excludes service source, database evidence, billing, credentials, customer data, private discovery/learning mechanics, internal handoffs, vault history and repository history. The full internal boundary document is intentionally not shipped; this file is the public-facing scope statement.

The public source is this GitHub repository. The commercial MCP connector is published as GitHub pre-release `noticer-commercial-mcp-v0.3.1-dev.20261008`. GitHub’s Latest release is still the legacy 0.1.0 owner-API connector; do not treat Latest as 0.3.1. This tree still has no npm publication. A green local suite is not a security certification. The private hosted engine is not included.

## Intention guidance

The public repository includes a small Success Contract helper and agent guidance. These help a person state the outcome they care about, the disclosed proxy the public verifier can check, and the limits of that proxy. Confirmation means only that the wording was confirmed by the user; it grants no external permission and is not evidence that the outcome occurred.

Private candidate selection, comparison strategy, learning, scoring and promotion mechanics remain outside this distribution. The public project does not silently learn a reusable truth from a user's conversation or from one successful run.
