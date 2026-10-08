# Noticer

**Your automation says it succeeded. Noticer checks.**

## Start here

- **Check the expected result before the next action:** see the [commercial agent guide](mcp-commercial/AGENT_GUIDE.md) for when to call Noticer, its exact supported scope, outputs and consent steps. This POSIX-only client checks an explicitly authorized public HTTPS JSON predicate with a separate known-good control. It connects without an existing config file, then asks for consent before local setup and commerce enrollment. Five eligible checks are free; later eligible receipt access costs USD 1 with separate approval through the caller’s existing Link wallet.
- **Existing operator-provisioned integrations:** [MCP 0.1.0](https://github.com/zensteagarden/noticer-open/releases/tag/noticer-mcp-v0.1.0) remains the legacy owner-API connector. Its [installation guide](https://github.com/zensteagarden/noticer-open/releases/download/noticer-mcp-v0.1.0/README.md) requires assigned API access; it does not provide the new self-service commerce flow.
- **Try the offline verifier:** follow the Node.js quick start below. It checks supplied evidence packets locally without an account, API key or network access.

The [0.3.1 commercial release](https://github.com/zensteagarden/noticer-open/releases/tag/noticer-commercial-mcp-v0.3.1-dev.20261008) includes clearer agent-facing instructions and tool descriptions. Follow the agent guide for installation.

The commercial client has passed fresh Linux/UV installation, offline protocol checks, and mocked end-to-end payment tests. No real buyer payment is claimed. macOS runtime testing remains outstanding; native Windows is unsupported. Keep credentials out of chat and review the frozen scope before running a check. A verified receipt never executes a downstream action.

[Current commercial MCP Registry listing](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.zensteagarden%2Fnoticer/versions/latest) · [Setup help](mailto:hello@noticer.io)

## Offline public verifier

Noticer starts one step earlier than most automation tools: **what are you actually trying to have happen?**

The public project helps turn a human intention into an explicit Success Contract, then independently verifies disclosed evidence under small deterministic rules. The model or agent may help clarify the goal; it does not author the verifier's verdict.

> **Understand before acting. Observe before believing.**
>
> The user defines success. Automation attempts it. Noticer reports what the evidence can establish.

This repository is the public, Apache-2.0 verifier and protocol. It does **not** include Noticer's private service, private discovery/learning mechanics, billing, customer data or deployment secrets.

## See the whole idea in about a minute

Use Node.js 24 and run:

```sh
node examples/guided-first-run.mjs --demo
```

The demo does four things:

1. states a human intention;
2. freezes a small Success Contract and its limits;
3. rejects a synthetic false-green packet where the automation said success but the evidence does not match;
4. accepts a disclosed exact-text packet while still explaining what that ALLOW does **not** prove.

No account, API key, model, payment, database or network access is required. There are no npm dependencies.

## Let Noticer guide your own check

```sh
node examples/guided-first-run.mjs
```

It asks four short questions and reflects the Success Contract back before you confirm it. Confirmation clarifies the check; it **does not authorize any external action**.

Read [the intention guide](docs/INTENTION_GUIDE.md), [Success Contract v1](docs/SUCCESS_CONTRACT.md), and [the agent guide](mcp-commercial/AGENT_GUIDE.md) if you want to connect Noticer to ChatGPT, Claude, Cursor or another agent. Keep the agent outside the deterministic verdict path.

## Run the verifier directly

The original synthetic packet contains `accepted`, while its declared expectation is `ok`:

```sh
node src/cli.mjs verify fixtures/automation-said-success --policy packet.integrity.v1
node src/cli.mjs verify fixtures/automation-said-success --policy artifact.text.exact.v1
```

The integrity check exits 0. The exact-text check deliberately exits 1. That difference is the point: intact evidence is not automatically evidence for the claimed outcome.

Run the full local suite:

```sh
node --test
```

Or run the release check under Node 24:

```sh
npm run check:release
```

## Build on it

The JavaScript entry point is `src/index.mjs`. Intention helpers are available from `src/intention.mjs`.

```js
import { loadPacket, verifyPacket } from "./src/index.mjs";
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

const result = verifyPacket(loadPacket("./my-evidence-packet"), {
  policyId: contract.observable_proxy.policy_id,
});
console.log(result.verdict);
```

Good first projects are evidence-packet exporters, readable receipt viewers, adapters that produce disclosed packets, clearer explanations and hostile-input fixtures. Keep the success condition explicit and keep authorization separate.

## What this public release checks

`packet.integrity.v1` checks implemented packet structure, references and supplied blob hashes.

`artifact.text.exact.v1` additionally requires a declared exact-text claim to match supplied evidence bytes.

Both use `ALLOW`, `DENY` and `INCONCLUSIVE`. Public `PROVED` and `DISPROVED` remain disabled. This repository does not contact a live destination and does not prove that an automation performed an external write.

Receipts are a separate authenticity check. A valid signature is not the same as issuer trust, a passing evaluation or authorization to act.

Read [the implemented packet format](docs/PROTOCOL.md), [public scope and limits](docs/PUBLIC_SCOPE.md), [security guidance](SECURITY.md), and [contributing](CONTRIBUTING.md) before using untrusted packets.

## Verification status

The launch candidate is exercised locally before publication. `npm run check:release` requires Node 24; on other Node majors it returns `NOT_RUN` with exit 2 rather than pretending release acceptance passed.

A green local suite is not a security certification. Windows/macOS execution, complete hostile-input coverage, hosted outcome observation and manual assistive-technology testing are separate gates.

## License

Apache-2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).

The private Noticer service and private investigation/learning system are not part of this distribution.

## The story and working with me

Noticer began with a question: **what would we need to observe before believing “done”?** I’m sharing the build story and opening the public verifier for other builders to inspect and extend.

If you need help checking one automation’s intended result, I offer a scoped workflow review: an explicit success condition, an evidence report, and repair/recheck priorities. Scope and price are agreed first; unavailable evidence stays unresolved.

[Read the story and hiring offer](THE_STORY.md), visit [noticer.io](https://noticer.io), or contact [hello@noticer.io](mailto:hello@noticer.io).
