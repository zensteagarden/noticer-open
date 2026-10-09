# Walkthrough: artifact to a readable result

This uses only the free standalone tools in this repository. No account, API key, MCP host, or network access is required.

You will:

1. write a small text artifact;
2. wrap it in a disclosed evidence packet;
3. verify it against a Success Contract;
4. read the verdict in plain language.

Use Node.js 24 if you have it. Node.js 22 also runs these commands.

## 1. Write an artifact

```sh
mkdir -p /tmp/noticer-walkthrough
printf 'report_accessible' > /tmp/noticer-walkthrough/report.txt
```

That file is the evidence. In a real check it would be bytes you already control, such as an exported status body.

## 2. Build an evidence packet

```sh
node examples/packet-from-text.mjs \
  /tmp/noticer-walkthrough/report.txt \
  /tmp/noticer-walkthrough/packet
```

Expected output:

```text
wrote packet /tmp/noticer-walkthrough/packet from report.txt
digest sha256:50a598f2be0a9455ab3e4a627e81167f9dbbb07605db0e9da545f00995bc6461
claim.expected "report_accessible"
```

The packet is a directory with `manifest.json` and one blob. The claim says the bytes equal `report_accessible`.

## 3. State the caller’s expectation, then verify

The packet’s own claim is not enough. Pass the text you actually required:

```sh
node src/cli.mjs verify /tmp/noticer-walkthrough/packet \
  --policy artifact.text.exact.v1 \
  --expected-text report_accessible
```

Expected output:

```text
policy: artifact.text.exact.v1
ALLOW (integrity)
scope: artifact.text
establishes: schema.valid.v1, references.resolve.v1, blob.sha256.v1, text.exact.v1, caller.expected.v1
does not establish: external_write_succeeded, claim_is_true, outcome_observed
unknown: none
next: read_establishes
```

Exit code is 0. `ALLOW` means the disclosed bytes matched the caller’s expected text. It does not mean a customer opened a report, and it does not authorize the next action.

## 4. Reject a packet that does not match your contract

The same packet is internally valid. If your contract required different text, verification must fail:

```sh
node src/cli.mjs verify /tmp/noticer-walkthrough/packet \
  --policy artifact.text.exact.v1 \
  --expected-text other_text
```

Expected output:

```text
policy: artifact.text.exact.v1
DENY (integrity)
scope: artifact.text
establishes: none
does not establish: external_write_succeeded, claim_is_true, outcome_observed
unknown: none
next: compare_policy_scope
```

Exit code is 1. The packet still hashes correctly. It does not match the caller’s declared expectation.

## Optional: JavaScript helper

```js
import { loadPacket, verifyAgainstContract } from "./src/index.mjs";
import { createSuccessContract } from "./src/intention.mjs";

const contract = createSuccessContract({
  intention: "The recipient can access the report.",
  requiredOutcome: "The disclosed evidence says report_accessible.",
  observableCheck: {
    policyId: "artifact.text.exact.v1",
    statement: "Evidence bytes equal report_accessible.",
    expectedText: "report_accessible",
  },
  doesNotEstablish: ["that a real recipient opened the report"],
});

const result = verifyAgainstContract(
  loadPacket("/tmp/noticer-walkthrough/packet"),
  contract,
);
console.log(result.verdict);
```

That prints `ALLOW`. Change `expectedText` to `other_text` and it prints `DENY`.

## Optional: guided contract wording

```sh
node examples/guided-first-run.mjs
```

It asks four short questions, prints the full proposed Success Contract, then asks you to confirm. Confirmation only accepts the wording. It does not authorize any external action.

For a no-input demonstration:

```sh
node examples/guided-first-run.mjs --demo
```

## What each result means

- `ALLOW` and exit 0: the named check passed on the disclosed packet.
- `DENY` and exit 1: a required check failed. If you passed `--expected-text`, the packet may be intact and still not match your contract.
- `INCONCLUSIVE` and exit 2: required evidence is missing or the check is unsupported.

No result authorizes a write, a payment, or the next workflow step.
